#!/usr/bin/env python3
"""Fetch the zoo's precomputed score tables — and prove which bytes were fetched.

*Plain words.* Some models in the roster are not programs at all: somebody already ran the
model over every possible variant and published the answers as a big file. This script is
the only way that file enters the repository's working set. It downloads it, hashes it,
writes a provenance manifest, converts it to a lookup-friendly parquet, and prints the
one-line TOML fragment that records the digest in the registry.

Three rules it exists to enforce:

1. **A digest is measured, never typed.** The registry ships ``sha256 = ""`` until a fetch
   has run; the fragment this script prints is the only legitimate source of that value.
2. **The score file is never committed.** Everything lands under ``build/it4/tables/``,
   which is gitignored. The public repository ships this script and the digest.
3. **Dry run by default.** Nothing is downloaded without ``--execute``. A 1.2 GiB download
   is not something a stray command should start.

Usage::

    uv run python tools/fetch_zoo_tables.py --list
    uv run python tools/fetch_zoo_tables.py --fetch esm1b              # plan only
    uv run python tools/fetch_zoo_tables.py --fetch esm1b --execute    # actually download

Only ``source = "table"`` lanes appear here. A warehouse-column lane has nothing to fetch, a
REST lane fetches per allele at score time, and a local/remote model pulls its own weights.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# The path shim above must run before these imports; that is why they are not at the top.
from mva.drugs import provenance
from mva.zoo import registry

#: Everything a fetch writes lives here; `.gitignore` keeps it out of the repository.
DEFAULT_OUT = Path("build/it4/tables")

#: Bytes per chunk while streaming and hashing. One MiB, same as the provenance helper.
CHUNK = 1 << 20

#: How the downloaded file is shaped, from `params.layout` in the roster.
LAYOUTS = ("tsv", "csv", "matrix-zip", "csv-zip")

PATIENT_DATA = (
    "none. A public precomputed score table for every possible variant in the human "
    "genome. Nothing in it was derived from this callset; the join against the callset "
    "happens later, inside build/it4/, and only allele_id leaves."
)


def _table_lanes(cards: dict[str, registry.ModelCard]) -> dict[str, registry.ModelCard]:
    return {key: card for key, card in cards.items() if card.source == "table"}


def _size_hint(card: registry.ModelCard) -> str:
    raw = card.params.get("bytes")
    if not isinstance(raw, int):
        return "unknown (verify on fetch)"
    return f"{raw / 1e9:.2f} GB ({raw:,} bytes)"


def do_list(cards: dict[str, registry.ModelCard]) -> int:
    """Print every downloadable lane: where it comes from, how big, under what terms."""
    lanes = _table_lanes(cards)
    if not lanes:
        print('no `source = "table"` lanes in the roster')
        return 0
    print(f"{len(lanes)} downloadable lane(s) — nothing is fetched without --execute\n")
    for key, card in lanes.items():
        state = "enabled" if card.enabled else "declared, not enabled"
        digest = card.params.get("sha256") or "(not fetched yet)"
        print(f"  {key}  [{card.scope}, {state}, tier {card.tier}, {card.input_class}]")
        print(f"      name     {card.name} — {card.version}")
        print(f"      url      {card.params.get('url', '(none recorded)')}")
        print(f"      size     {_size_hint(card)}")
        print(f"      layout   {card.params.get('layout', '(unrecorded)')}")
        print(f"      key      {', '.join(str(k) for k in card.params.get('key', []))}")
        print(
            f"      licence  {card.licence}"
            f"{' — NON-COMMERCIAL' if card.non_commercial else ''}  <{card.licence_url}>"
        )
        print(f"      ships    {registry.SHIPS[card.source]}")
        print(f"      sha256   {digest}")
        print()
    return 0


def _plan(card: registry.ModelCard, out_dir: Path) -> int:
    """What ``--execute`` would do, printed instead of done."""
    raw = out_dir / card.key
    print("DRY RUN — nothing downloaded. Re-run with --execute to do this:\n")
    print(f"  model      {card.name} ({card.key}), {card.version}")
    print(f"  licence    {card.licence} <{card.licence_url}>")
    if card.non_commercial:
        print("             NON-COMMERCIAL: hackathon use is fine; the file is never committed.")
    print(f"  download   {card.params.get('url')}")
    print(f"  into       {raw}/")
    print(f"  size       {_size_hint(card)}")
    print("  disk       about three times the download (raw + extracted + parquet)")
    print(f"  then       sha256 -> {out_dir / (card.key + '.provenance.json')}")
    print(
        f"             parquet -> {out_dir / (card.key + '.parquet')}, keyed on "
        f"{', '.join(str(k) for k in card.params.get('key', []))}"
    )
    print(f"             prints the models.d/{card.key}.toml fragment carrying the digest")
    return 0


def _download(url: str, dest: Path) -> tuple[str, int]:
    """Stream a URL to a file, hashing as it goes. Returns ``(sha256, bytes)``.

    Streaming matters: these tables are gigabytes, and holding one in memory to hash it
    afterwards would be the slowest possible way to do the same arithmetic.
    """
    import httpx

    dest.parent.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256()
    size = 0
    with httpx.stream("GET", url, follow_redirects=True, timeout=60.0) as reply:
        reply.raise_for_status()
        with dest.open("wb") as handle:
            for chunk in reply.iter_bytes(CHUNK):
                handle.write(chunk)
                sha.update(chunk)
                size += len(chunk)
                print(f"\r    {size / 1e9:6.2f} GB", end="", flush=True)
    print()
    return sha.hexdigest(), size


def _extract(archive: Path, into: Path) -> list[Path]:
    """Unpack a zip into ``into`` and return the member files, largest first."""
    into.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(into)
    return sorted((p for p in into.rglob("*") if p.is_file()), key=lambda p: -p.stat().st_size)


def _convert(card: registry.ModelCard, raw: Path, target: Path) -> int:
    """Turn whatever was downloaded into one parquet keyed for lookup. Returns row count."""
    import duckdb

    layout = str(card.params.get("layout", "tsv"))
    if layout not in LAYOUTS:
        raise SystemExit(f"{card.key}: layout={layout!r} is not one of {LAYOUTS}")
    con = duckdb.connect()
    try:
        if layout in ("tsv", "csv"):
            rows = _convert_flat(con, raw, target, layout)
        else:
            rows = _convert_archive(con, card, raw, target, layout)
    finally:
        con.close()
    return rows


def _convert_flat(con: Any, raw: Path, target: Path, layout: str) -> int:
    """A single delimited table (possibly bgzipped) → parquet, columns unchanged."""
    delimiter = "\t" if layout == "tsv" else ","
    source = str(raw)
    con.execute(
        "COPY (SELECT * FROM read_csv(?, delim=?, header=true, union_by_name=true, "
        "filename=false, auto_detect=true)) TO ? (FORMAT parquet)",
        [source, delimiter, str(target)],
    )
    return int(con.execute("SELECT count(*) FROM read_parquet(?)", [str(target)]).fetchone()[0])


def _convert_archive(
    con: Any, card: registry.ModelCard, raw: Path, target: Path, layout: str
) -> int:
    """A zip of per-protein files → one long parquet.

    ``csv-zip``: every member is already long (one row per variant) and they are simply
    unioned. ``matrix-zip`` (ESM1b): every member is a matrix — one column per protein
    position, one row per substituted amino acid — so it is unpivoted into
    ``(uniprot, hgvs_p, score)``. The member layout is printed before the conversion runs
    so the assumption is checked against the real file rather than trusted.
    """
    members = _extract(raw, raw.parent / f"{card.key}-extracted")
    if not members:
        raise SystemExit(f"{card.key}: the archive held no files")
    glob = str(members[0].parent / str(card.params.get("member_glob", "*.csv")))
    print(f"    {len(members):,} members; first: {members[0].name}")
    head = con.execute("SELECT * FROM read_csv(?, header=true) LIMIT 3", [str(members[0])])
    print(f"    columns: {[d[0] for d in head.description][:8]} …")
    if layout == "csv-zip":
        con.execute(
            "COPY (SELECT * FROM read_csv(?, header=true, union_by_name=true, "
            "filename=true)) TO ? (FORMAT parquet)",
            [glob, str(target)],
        )
    else:
        sign = int(card.params.get("score_sign", 1))
        con.execute(
            "COPY (SELECT regexp_extract(filename, '([^/]+?)_LLR', 1) AS uniprot, "
            "       name AS hgvs_p, ? * value AS score "
            "      FROM (SELECT * FROM read_csv(?, header=true, union_by_name=true, "
            "            filename=true)) UNPIVOT (value FOR name IN (COLUMNS(* EXCLUDE "
            "            (filename, column0)))) WHERE value IS NOT NULL) "
            "TO ? (FORMAT parquet)",
            [sign, glob, str(target)],
        )
    return int(con.execute("SELECT count(*) FROM read_parquet(?)", [str(target)]).fetchone()[0])


def _fragment(card: registry.ModelCard, sha: str) -> str:
    return (
        f"# src/mva/zoo/models.d/{card.key}.toml — written from a measured fetch.\n"
        f"[models.{card.key}]\n"
        f'params = {{ sha256 = "{sha}" }}\n'
    )


def do_fetch(card: registry.ModelCard, out_dir: Path, *, execute: bool) -> int:
    """Download one lane's table, digest it, convert it, and print its fragment."""
    url = str(card.params.get("url", ""))
    if not url:
        raise SystemExit(f"{card.key}: no url in params — nothing to fetch")
    if not execute:
        return _plan(card, out_dir)

    raw_dir = out_dir / card.key
    raw_dir.mkdir(parents=True, exist_ok=True)
    name = url.rsplit("/", 1)[-1].split("?", maxsplit=1)[0] or f"{card.key}.data"
    raw = raw_dir / name
    print(f"  downloading {card.name} ({_size_hint(card)}) …")
    sha, size = _download(url, raw)
    print(f"    sha256 {sha}  ({size:,} bytes)")

    target = out_dir / f"{card.key}.parquet"
    print("  converting to parquet …")
    rows = _convert(card, raw, target)
    print(f"    {rows:,} rows -> {target}")

    manifest = provenance.envelope(f"zoo-table-{card.key}", built_by=Path(__file__).name)
    manifest["model"] = card.as_dict()
    manifest["inputs"] = [
        {
            "name": card.key,
            "url": url,
            "version": card.version,
            "role": "precomputed variant-effect score table",
            "retrieved_at": provenance.now(),
            "sha256": sha,
            "sha256_scope": "the downloaded bytes, hashed while streaming",
            "bytes": size,
            "licence": card.licence,
            "licence_url": card.licence_url,
            "non_commercial": card.non_commercial,
        }
    ]
    manifest["outputs"] = [provenance.output(target, rows)]
    manifest["licence"] = f"{card.licence} — see {card.licence_url}. {registry.SHIPS['table']}."
    manifest["patient_data"] = PATIENT_DATA
    written = provenance.write(manifest, out_dir / f"{card.key}.provenance.json")
    print(f"  provenance -> {written}")

    print(f"\nPaste this into src/mva/zoo/models.d/{card.key}.toml:\n")
    print(_fragment(card, sha))
    return 0


def _free_disk(path: Path) -> int:
    probe = path
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    return int(shutil.disk_usage(probe).free)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--list", action="store_true", help="print every downloadable lane")
    parser.add_argument("--fetch", metavar="KEY", help="download one lane's table")
    parser.add_argument(
        "--execute", action="store_true", help="actually download (default: dry run)"
    )
    parser.add_argument(
        "--out", type=Path, default=DEFAULT_OUT, help=f"target folder (default {DEFAULT_OUT})"
    )
    parser.add_argument("--models", type=Path, default=registry.DEFAULT_MODELS_TOML)
    parser.add_argument("--fragments", type=Path, default=registry.DEFAULT_FRAGMENTS_DIR)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cards = registry.load(args.models, args.fragments)
    if args.list or not args.fetch:
        return do_list(cards)
    lanes = _table_lanes(cards)
    card = lanes.get(args.fetch)
    if card is None:
        known = ", ".join(lanes) or "(none)"
        raise SystemExit(f"{args.fetch!r} is not a downloadable lane. Known: {known}")
    expected = card.params.get("bytes")
    if args.execute and isinstance(expected, int) and _free_disk(args.out) < expected * 3:
        raise SystemExit(
            f"not enough free disk for {card.key}: it needs about "
            f"{expected * 3 / 1e9:.1f} GB free (raw + extracted + parquet)"
        )
    return do_fetch(card, args.out, execute=args.execute)


if __name__ == "__main__":
    raise SystemExit(main())
