"""Fetch only the rows of a huge remote score table that this case's alleles need.

*Plain words.* Some publishers score **every** possible single-letter change in the genome
and ship the answers as one enormous file — GPN-MSA's is 37 GB. Downloading it to look up
40,000 rows would be like cloning a monorepo to read one file. A **bgzipped TSV** (a text
table compressed in independently-decompressable 64 KB blocks) with a **tabix index** (a
side file mapping *genomic position → byte range*) is exactly the shape that lets a client
ask for byte ranges instead: `tabix URL 17:43044295-43044300` opens an HTTP range request
per block and prints those rows. This module is that idea, batched.

The recipe, and why each step is there:

1. **Plan regions.** The record set names ~36k single-base positions. Asking for each one
   separately costs one index seek each (measured ~0.3 s over HTTPS), so neighbours closer
   than ``merge_gap`` bases are merged into one region: fewer seeks, a little more data.
2. **Pin the bytes.** The index (a few MB) is downloaded once and hashed; a ``HEAD`` on the
   score file records its size and ``ETag`` without downloading it. That pair is the
   provenance of a subset whose source is never held locally in full.
3. **Fan out.** The regions are split into shards and one ``tabix`` process runs per shard
   against ``<url>##idx##<local index>`` — htslib's spelling for "this remote file, that
   local index". Measured ~1.8x on four workers; the bottleneck is per-seek latency. A
   dropped conversation costs a *round*, not the run: see :func:`subset`'s resume.
4. **Digest the subset**, then convert it to one Parquet keyed on ``chrom/pos/ref/alt``.

**The coordinates never leave ``build/``.** The BED files, the TSV shards and the Parquet
are all written under the caller's output directory, which is gitignored; what leaves is the
row count and the digests. The join against the record set happens later, inside DuckDB
(:mod:`mva.zoo.adapters.coordinate_table`), and only ``allele_id`` comes out of it.

Nothing here is case-specific: the records file, the URL, the output directory and the
shapes are all arguments.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .tabix_plan import (
    DEFAULT_GAP,
    Region,
    merge_positions,
    shard,
    snv_positions,
    snv_regions,
    write_bed,
)

__all__ = [
    "DEFAULT_GAP",
    "DEFAULT_JOBS",
    "Region",
    "SubsetResult",
    "TabixMissingError",
    "digest",
    "download",
    "merge_positions",
    "resolve_url",
    "shard",
    "snv_positions",
    "snv_regions",
    "subset",
    "tabix_command",
    "to_parquet",
    "upstream_head",
    "write_bed",
]

#: Parallel ``tabix`` processes. Four measured 1.8x faster than one against Hugging Face's
#: CDN; the work is latency-bound, not bandwidth-bound, so more workers help sub-linearly.
DEFAULT_JOBS = 8


class TabixMissingError(RuntimeError):
    """No ``tabix`` on the PATH. htslib ships it; ``brew install htslib`` on macOS."""


@dataclass(frozen=True)
class SubsetResult:
    """What one subset fetch produced, and everything its provenance row needs."""

    url: str
    resolved_url: str
    index_path: Path
    index_sha256: str
    upstream_bytes: int | None
    upstream_etag: str
    regions: int
    positions: int
    span: int
    rows: int
    subset_path: Path
    subset_sha256: str
    parquet_path: Path
    parquet_rows: int
    seconds: float = 0.0
    shards: int = 0
    failures: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        """Plain JSON for a provenance manifest. No coordinate appears in it."""
        return {
            "url": self.url,
            "resolved_host": self.resolved_url.split("/")[2] if "//" in self.resolved_url else "",
            "index_sha256": self.index_sha256,
            "upstream_bytes": self.upstream_bytes,
            "upstream_etag": self.upstream_etag,
            "regions": self.regions,
            "positions": self.positions,
            "span_bases": self.span,
            "subset_rows": self.rows,
            "subset_sha256": self.subset_sha256,
            "parquet_rows": self.parquet_rows,
            "seconds": round(self.seconds, 1),
            "shards": self.shards,
            "failures": list(self.failures),
        }


# ── step 2: pin the remote bytes without downloading them ─────────────────────────────


def resolve_url(url: str) -> str:
    """Follow the redirects once and return the final URL.

    Hugging Face answers ``/resolve/main/<file>`` with a redirect to a signed CDN URL.
    Resolving it once is a measured 25 % faster per seek, and the workers are **not** given
    the result: the signature expires in hours and the first real fan-out ran 3 h 13 m before
    every worker died on it at once. What this is for is the provenance line — the host the
    bytes actually came from — which is worth one ``HEAD`` and no risk.
    """
    import httpx

    with httpx.Client(follow_redirects=True, timeout=60.0) as client:
        reply = client.head(url)
        reply.raise_for_status()
        return str(reply.url)


def upstream_head(url: str) -> tuple[int | None, str]:
    """``(size in bytes, ETag)`` of the remote file, from a ``HEAD`` — no body is fetched."""
    import httpx

    with httpx.Client(follow_redirects=True, timeout=60.0) as client:
        reply = client.head(url)
        reply.raise_for_status()
        raw = reply.headers.get("content-length") or reply.headers.get("x-linked-size")
        size = int(raw) if raw and raw.isdigit() else None
        etag = reply.headers.get("etag", "") or reply.headers.get("x-linked-etag", "")
        return size, etag.strip('"')


def download(url: str, dest: Path) -> str:
    """Stream a small file (the index) to disk and return its sha256."""
    import httpx

    dest.parent.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256()
    with httpx.stream("GET", url, follow_redirects=True, timeout=120.0) as reply:
        reply.raise_for_status()
        with dest.open("wb") as handle:
            for chunk in reply.iter_bytes(1 << 20):
                handle.write(chunk)
                sha.update(chunk)
    return sha.hexdigest()


def digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            sha.update(block)
    return sha.hexdigest()


# ── step 3: fan out ───────────────────────────────────────────────────────────────────


def tabix_command(url: str, index: Path, bed: Path, *, tabix: str = "tabix") -> list[str]:
    """The exact argv one worker runs.

    ``<url>##idx##<path>`` is htslib's own syntax for "this data file, that index": without
    it tabix would look for the index beside the URL and re-download it for every process.
    """
    return [tabix, "-R", str(bed), f"{url}##idx##{index}"]


def _keep_parts(target: Path) -> list[Path]:
    """Promote any previous run's shard output to a numbered *part*, and list every part.

    A shard file is this run's scratch; a part is a finished piece of the answer. Renaming
    rather than deleting is what makes a re-run cheap instead of a re-run from zero, and it
    keeps the old bytes around to be re-read rather than re-fetched.
    """
    parts = sorted(target.glob("scores.part-*.tsv"))
    for shard_file in sorted(target.glob("scores.[0-9][0-9].tsv")):
        if shard_file.stat().st_size == 0:
            shard_file.unlink()
            continue
        moved = target / f"scores.part-{len(parts):03d}.tsv"
        shard_file.rename(moved)
        _drop_partial_line(moved)
        parts.append(moved)
    return parts


def _drop_partial_line(path: Path) -> None:
    """Truncate a file to its last complete line.

    A worker killed mid-write leaves half a row, and half a row is a parse error three
    steps later — where it looks like a bad table rather than a killed process.
    """
    with path.open("rb+") as handle:
        handle.seek(0, 2)
        size = handle.tell()
        if not size:
            return
        handle.seek(size - 1)
        if handle.read(1) == b"\n":
            return
        window = min(size, 1 << 16)
        handle.seek(size - window)
        tail = handle.read(window)
        cut = tail.rfind(b"\n")
        handle.truncate(size - window + cut + 1 if cut >= 0 else 0)


def _covered(parts: Sequence[Path], *, connection: Any = None) -> set[tuple[str, int]]:
    """Which ``(contig, position)`` pairs the parts already hold."""
    import duckdb

    live = [path for path in parts if path.exists() and path.stat().st_size]
    if not live:
        return set()
    con = connection or duckdb.connect()
    files = ", ".join("?" for _ in live)
    rows = con.execute(
        f"SELECT DISTINCT column0, column1 FROM read_csv([{files}], delim='\t', header=false, "
        "types=['VARCHAR', 'BIGINT', 'VARCHAR', 'VARCHAR', 'DOUBLE'])",
        [str(path) for path in live],
    ).fetchall()
    return {(str(row[0]), int(row[1])) for row in rows}


# ── step 4: the whole thing ───────────────────────────────────────────────────────────


def subset(
    url: str,
    records_parquet: Path | str,
    out_dir: Path | str,
    *,
    index_url: str | None = None,
    merge_gap: int = DEFAULT_GAP,
    jobs: int = DEFAULT_JOBS,
    tabix: str = "tabix",
    columns: Sequence[str] = ("chrom", "pos", "ref", "alt", "score"),
    progress: Any = print,
    connection: Any = None,
) -> SubsetResult:
    """Fetch every row of the remote table this record set needs, and Parquet it.

    Everything it writes lands under ``out_dir`` (``build/<prefix>/tables/<lane>/``): the BED
    plan, the TSV shards, the concatenated subset and the Parquet. Nothing is committed.

    **It resumes.** Whatever earlier runs already fetched is kept as ``scores.part-NN.tsv``,
    the positions in those parts are subtracted from the plan, and only the remainder is
    asked for. That is not a nicety: the first real run of this lane took 3 h 13 m and every
    worker died at the end of it, because the signed CDN URL the redirect had handed out
    expired mid-flight (measured 2026-09-20 — "Operation timed out" with an ``Expires``
    policy in the argv). The fix is both halves — this resume, and handing the workers the
    *un*-redirected URL below so htslib re-signs on each open.
    """
    import time

    if shutil.which(tabix) is None:
        raise TabixMissingError(
            f"{tabix!r} is not on the PATH. htslib ships it (macOS: `brew install htslib`); "
            "without it a remote bgzipped table cannot be range-read."
        )
    started = time.time()
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)

    parts = _keep_parts(target)
    wanted = snv_positions(records_parquet, connection=connection)
    positions = len(wanted)
    already = _covered(parts, connection=connection)
    remaining = [row for row in wanted if row not in already]
    regions = merge_positions(remaining, merge_gap=merge_gap)
    span = sum(region.span for region in regions)
    if already:
        # Count the *wanted* ones. `already` also holds every position a merged region swept
        # up on the way, which is a much bigger number and means nothing here.
        done = positions - len(remaining)
        progress(f"    resuming: {done:,} of {positions:,} wanted positions already fetched")
    progress(f"    {len(regions):,} regions, {span:,} bases, merge_gap={merge_gap}")

    index = target / (url.rsplit("/", 1)[-1] + ".tbi")
    index_sha = digest(index) if index.exists() else download(index_url or f"{url}.tbi", index)
    progress(f"    index {index.name}  sha256 {index_sha[:16]}…")
    size, etag = upstream_head(url)
    resolved = resolve_url(url)
    progress(f"    upstream {size:,} bytes, etag {etag}" if size else "    upstream size unknown")

    shards = shard(regions, jobs) if regions else []
    procs: list[tuple[Any, Any, Path]] = []
    outputs: list[Path] = list(parts)
    for number, block in enumerate(shards):
        bed = target / f"regions.{number:02d}.bed"
        write_bed(block, bed)
        out = target / f"scores.{number:02d}.tsv"
        # The *un*-resolved URL on purpose: htslib re-opens the file for every seek, and a
        # signed CDN link resolved once expires under a multi-hour fan-out. Resolving is
        # ~25 % faster per seek and loses the whole run at hour three.
        argv = tabix_command(url, index, bed, tabix=tabix)
        handle = out.open("wb")
        procs.append((subprocess.Popen(argv, stdout=handle, stderr=subprocess.PIPE), handle, out))
        outputs.append(out)
    progress(f"    {len(procs)} worker(s) running …")

    failures: list[str] = []
    for number, (proc, handle, out) in enumerate(procs):
        _, err = proc.communicate()
        handle.close()
        if proc.returncode != 0:
            failures.append(f"shard {number}: exit {proc.returncode}: {err.decode()[-300:]}")
        progress(f"    shard {number:02d} done ({out.stat().st_size:,} bytes)")

    joined = target / "scores.subset.tsv"
    rows = 0
    with joined.open("wb") as sink:
        for out in outputs:
            with out.open("rb") as source_handle:
                for line in source_handle:
                    sink.write(line)
                    rows += 1
    subset_sha = digest(joined)
    parquet = Path(str(target) + ".parquet")
    parquet_rows = to_parquet(joined, parquet, columns=columns, connection=connection)
    return SubsetResult(
        url=url,
        resolved_url=resolved,
        index_path=index,
        index_sha256=index_sha,
        upstream_bytes=size,
        upstream_etag=etag,
        regions=len(regions),
        positions=positions,
        span=span,
        rows=rows,
        subset_path=joined,
        subset_sha256=subset_sha,
        parquet_path=parquet,
        parquet_rows=parquet_rows,
        seconds=time.time() - started,
        shards=len(shards),
        failures=failures,
    )


def to_parquet(
    tsv: Path,
    parquet: Path,
    *,
    columns: Sequence[str] = ("chrom", "pos", "ref", "alt", "score"),
    connection: Any = None,
) -> int:
    """Headerless TSV → Parquet with the column names the lane joins on. Returns the rows.

    An empty input is a real outcome, not a crash: every worker may have failed, or a case
    may genuinely need no row of this table. DuckDB's CSV sniffer refuses an empty file, so
    the empty table is written from its declared schema instead.
    """
    import duckdb

    con = connection or duckdb.connect()
    names = ", ".join(f"'{name}'" for name in columns)
    types = ", ".join(
        "'BIGINT'" if name == "pos" else ("'DOUBLE'" if name == "score" else "'VARCHAR'")
        for name in columns
    )
    parquet.parent.mkdir(parents=True, exist_ok=True)
    if tsv.stat().st_size == 0:
        empty = ", ".join(
            f"CAST(NULL AS {'BIGINT' if n == 'pos' else ('DOUBLE' if n == 'score' else 'VARCHAR')})"
            f" AS {n}"
            for n in columns
        )
        con.execute(f"COPY (SELECT {empty} WHERE false) TO '{parquet}' (FORMAT parquet)")
        return 0
    con.execute(
        f"COPY (SELECT * FROM read_csv('{tsv}', delim='\t', header=false, "
        f"names=[{names}], types=[{types}])) TO '{parquet}' (FORMAT parquet)"
    )
    counted = con.execute("SELECT count(*) FROM read_parquet(?)", [str(parquet)]).fetchone()
    return int(counted[0]) if counted else 0
