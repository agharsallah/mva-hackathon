#!/usr/bin/env python3
"""Fetch PrimeKG's ``kg.csv`` — and prove which bytes were fetched.

*Plain words.* PrimeKG (Chandak, Huang & Zitnik 2023, PMID 36732524) is a public **knowledge
graph** (a table of typed edges: ``disease — gene``, ``gene — pathway``, ``drug — gene``, …)
built from 20 curated resources. It is the one graph step 7's walk reads. This script is the
only way it enters the working set:

1. ask Harvard Dataverse for the dataset's current version, licence and the file's MD5;
2. stream ``kg.csv`` into ``build/primekg/`` (gitignored), hashing sha256 while it streams;
3. refuse the file if its MD5 differs from the one Dataverse publishes;
4. convert it once to parquet with DuckDB (the walk reads the parquet);
5. write a provenance manifest beside it, and a data-free copy under ``ressources/track2/``.

The graph is public reference data (licence CC0 1.0 on the Dataverse record) and holds
nothing about the proband. It is still never committed: it is ~1 GB and rebuildable.

Usage::

    uv run python tools/fetch_primekg.py             # plan only: prints what would happen
    uv run python tools/fetch_primekg.py --execute   # download, verify, convert, manifest
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# The path shim above must run before this import.
from mva.drugs import provenance

DATAVERSE = "https://dataverse.harvard.edu"
DOI = "doi:10.7910/DVN/IXA7BM"
FILENAME = "kg.csv"
DEFAULT_OUT = Path("build/primekg")
COMMITTED_MANIFEST = Path("ressources/track2/primekg.provenance.json")
CHUNK = 1 << 20

PATIENT_DATA = (
    "none. A public biomedical knowledge graph (diseases, genes, drugs, pathways, "
    "phenotypes). Nothing in it was derived from this case's callset or clinical record."
)


def dataset_record() -> dict[str, Any]:
    """The dataset's latest version as Dataverse describes it (version, licence, files)."""
    import httpx

    url = f"{DATAVERSE}/api/datasets/:persistentId/"
    reply = httpx.get(url, params={"persistentId": DOI}, timeout=60.0, follow_redirects=True)
    reply.raise_for_status()
    latest: dict[str, Any] = reply.json()["data"]["latestVersion"]
    return latest


def file_entry(latest: dict[str, Any], filename: str) -> dict[str, Any]:
    """The Dataverse ``dataFile`` block for one file name; raises when it is absent."""
    for item in latest.get("files", []):
        data = item.get("dataFile", {})
        if data.get("filename") == filename:
            return dict(data)
    raise SystemExit(f"{filename} is not in {DOI}'s latest version")


def download(url: str, dest: Path) -> tuple[str, str, int]:
    """Stream ``url`` to ``dest``; returns ``(sha256, md5, bytes)`` measured while streaming."""
    import httpx

    dest.parent.mkdir(parents=True, exist_ok=True)
    sha, md5, size = hashlib.sha256(), hashlib.md5(usedforsecurity=False), 0
    with httpx.stream("GET", url, follow_redirects=True, timeout=120.0) as reply:
        reply.raise_for_status()
        with dest.open("wb") as handle:
            for chunk in reply.iter_bytes(CHUNK):
                handle.write(chunk)
                sha.update(chunk)
                md5.update(chunk)
                size += len(chunk)
                print(f"\r    {size / 1e9:6.2f} GB", end="", flush=True)
    print()
    return sha.hexdigest(), md5.hexdigest(), size


def hash_file(path: Path) -> tuple[str, str, int]:
    """``(sha256, md5, bytes)`` of a file already on disk (``--reuse``)."""
    sha, md5, size = hashlib.sha256(), hashlib.md5(usedforsecurity=False), 0
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK):
            sha.update(chunk)
            md5.update(chunk)
            size += len(chunk)
    return sha.hexdigest(), md5.hexdigest(), size


def to_parquet(csv: Path, target: Path) -> int:
    """``kg.csv`` → parquet, every column kept as text. Returns the row count."""
    import duckdb

    con = duckdb.connect()
    con.execute(
        f"COPY (SELECT * FROM read_csv('{csv}', header=true, all_varchar=true, "
        "delim=',', quote='\"', escape='\"')) "
        f"TO '{target}' (FORMAT parquet, COMPRESSION zstd)"
    )
    rows = con.execute(f"SELECT count(*) FROM read_parquet('{target}')").fetchone()
    return int(rows[0]) if rows else 0


def manifest(latest: dict[str, Any], entry: dict[str, Any], measured: dict[str, Any]) -> dict:
    """The provenance manifest: where the graph came from, under what terms, which bytes."""
    licence = latest.get("license") or {}
    version = f"{latest.get('versionNumber')}.{latest.get('versionMinorNumber')}"
    out = provenance.envelope("primekg", built_by=Path(__file__).name)
    out["method"] = (
        f"Harvard Dataverse {DOI}, latest version {version}: {FILENAME} streamed to disk, "
        "sha256 and md5 measured while streaming, md5 checked against the Dataverse record, "
        "then converted once to parquet by DuckDB read_csv(all_varchar=true, RFC-4180 quoting)."
    )
    out["citation"] = (
        "Chandak P, Huang K, Zitnik M. Building a knowledge graph to enable precision "
        "medicine. Sci Data 10, 67 (2023). PMID 36732524. doi:10.1038/s41597-023-01960-3"
    )
    out["inputs"] = [
        {
            "name": "primekg-kg.csv",
            "url": f"{DATAVERSE}/api/access/datafile/{entry['id']}",
            "doi": DOI,
            "version": version,
            "release_time": latest.get("releaseTime"),
            "role": "the knowledge graph the step-7 walk reads",
            "retrieved_at": provenance.now(),
            "sha256": measured["sha256"],
            "sha256_scope": (
                "the kg.csv bytes: hashed while streaming, or re-read from disk (--reuse)"
            ),
            "md5": measured["md5"],
            "md5_published": entry.get("md5"),
            "bytes": measured["bytes"],
            "licence": licence.get("rightsIdentifier") or licence.get("name"),
            "licence_url": licence.get("uri"),
        }
    ]
    out["outputs"] = measured["outputs"]
    out["licence"] = (
        f"{licence.get('name')} ({licence.get('uri')}) as stated on the Dataverse record; "
        "the graph stays under build/ and is never committed (size, not terms)."
    )
    out["patient_data"] = PATIENT_DATA
    return out


def run(out_dir: Path, *, execute: bool, reuse: bool = False) -> int:
    latest = dataset_record()
    entry = file_entry(latest, FILENAME)
    url = f"{DATAVERSE}/api/access/datafile/{entry['id']}"
    size = int(entry.get("filesize") or 0)
    print(f"  PrimeKG {DOI} v{latest.get('versionNumber')}.{latest.get('versionMinorNumber')}")
    print(f"  licence  {(latest.get('license') or {}).get('name')}")
    print(f"  file     {FILENAME}  {size / 1e9:.2f} GB  md5 {entry.get('md5')}")
    print(f"  from     {url}")
    print(f"  into     {out_dir}/")
    if not execute:
        print("DRY RUN — nothing downloaded. Re-run with --execute.")
        return 0
    if shutil.disk_usage(out_dir.parent if out_dir.parent.exists() else Path()).free < size * 2:
        raise SystemExit("not enough free disk: need about twice the file size")
    raw = out_dir / FILENAME
    if reuse and raw.exists():
        print(f"  reusing {raw} (hashed again, never trusted by name)")
        sha, md5, got = hash_file(raw)
    else:
        sha, md5, got = download(url, raw)
    if entry.get("md5") and md5 != entry["md5"]:
        raise SystemExit(f"md5 mismatch: got {md5}, Dataverse publishes {entry['md5']}")
    print(f"    sha256 {sha}  md5 ok  ({got:,} bytes)")
    target = out_dir / "kg.parquet"
    rows = to_parquet(raw, target)
    print(f"    {rows:,} edges -> {target}")
    measured = {
        "sha256": sha,
        "md5": md5,
        "bytes": got,
        "outputs": [provenance.output(target, rows)],
    }
    record = manifest(latest, entry, measured)
    provenance.write(record, out_dir / "primekg.provenance.json")
    provenance.write(record, COMMITTED_MANIFEST)
    print(f"  provenance -> {out_dir / 'primekg.provenance.json'} and {COMMITTED_MANIFEST}")
    print(json.dumps(record["inputs"][0], indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--execute", action="store_true", help="download (default: dry run)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="target folder")
    parser.add_argument(
        "--reuse", action="store_true", help="hash an already-downloaded kg.csv, skip the fetch"
    )
    args = parser.parse_args(argv)
    return run(args.out, execute=args.execute, reuse=args.reuse)


if __name__ == "__main__":
    raise SystemExit(main())
