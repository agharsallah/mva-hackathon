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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# The path shim above must run before these imports; that is why they are not at the top.
from mva.drugs import provenance
from mva.zoo import registry, tabix_subset, table_convert

#: Everything a fetch writes lives here; `.gitignore` keeps it out of the repository.
DEFAULT_OUT = Path("build/it4/tables")

#: Bytes per chunk while streaming and hashing. One MiB, same as the provenance helper.
CHUNK = 1 << 20

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


def _fragment(card: registry.ModelCard, sha: str) -> str:
    return (
        f"# src/mva/zoo/models.d/{card.key}.toml — written from a measured fetch.\n"
        f"[models.{card.key}]\n"
        f'params = {{ sha256 = "{sha}" }}\n'
    )


def do_fetch(
    card: registry.ModelCard,
    out_dir: Path,
    *,
    execute: bool,
    only: frozenset[str] = frozenset(),
) -> int:
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
    rows = table_convert.to_parquet(card, raw, target, only)
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


def do_subset(
    card: registry.ModelCard,
    records: Path,
    out_dir: Path,
    *,
    execute: bool,
    jobs: int,
    merge_gap: int,
    rounds: int = 1,
) -> int:
    """Fetch **only the rows this case needs** of a remote bgzipped, tabix-indexed table.

    The whole-file path above is wrong for a table like GPN-MSA's 37 GB of every possible
    SNV in the genome: the record set asks about ~36k positions, so the fetch is a set of
    HTTP range reads driven by the published index rather than a download. Plan §10 R7
    ("tier 1 = parquet subset for the ~40k records only"), executed.
    """
    url = str(card.params.get("url", ""))
    target = out_dir / card.key
    if not execute:
        regions = tabix_subset.snv_regions(records, merge_gap=merge_gap)
        span = sum(region.span for region in regions)
        print("DRY RUN — nothing fetched. Re-run with --execute to do this:\n")
        print(f"  model      {card.name} ({card.key}), {card.version}")
        print(f"  licence    {card.licence} <{card.licence_url}>")
        print(f"  index      {url}.tbi -> {target}/  (a few MB, hashed)")
        print(f"  regions    {len(regions):,} merged at gap {merge_gap} ({span:,} bases)")
        print(f"  workers    {jobs} tabix processes against the resolved CDN url")
        print(
            f"  then       parquet -> {out_dir / (card.key + '.parquet')}, keyed chrom/pos/ref/alt"
        )
        print(f"             provenance -> {out_dir / (card.key + '.subset.provenance.json')}")
        return 0

    print(f"  subsetting {card.name} from {url}")
    # Rounds, not one pass. Range-reading 21,722 regions out of a 37 GB file over HTTPS is
    # a multi-hour conversation with a CDN, and the CDN drops it: both real runs ended with
    # every worker dead on "Operation timed out" or a failed BGZF header, after hours of
    # good rows. Each round resumes from what the last one wrote, so a flaky link costs a
    # round rather than the run. The loop stops when nothing is left to ask for, or when a
    # round adds no rows at all — which is the honest signal that retrying will not help.
    previous = -1
    result = None
    for number in range(1, rounds + 1):
        print(f"  round {number} of at most {rounds}")
        result = tabix_subset.subset(url, records, target, jobs=jobs, merge_gap=merge_gap)
        print(f"    {result.rows:,} rows -> {result.parquet_path} in {result.seconds:.0f}s")
        for failure in result.failures:
            print(f"    FAILED {failure}")
        if result.regions == 0:
            print("    nothing left to ask for")
            break
        if result.rows == previous:
            print("    a whole round added no rows — stopping rather than looping")
            break
        previous = result.rows
    if result is None:
        raise SystemExit(f"{card.key}: --rounds must be at least 1")

    manifest = provenance.envelope(f"zoo-table-{card.key}", built_by=Path(__file__).name)
    manifest["model"] = card.as_dict()
    manifest["inputs"] = [
        {
            "name": card.key,
            "url": url,
            "version": card.version,
            "role": "precomputed variant-effect score table, range-read by tabix",
            "retrieved_at": provenance.now(),
            "sha256": result.subset_sha256,
            "sha256_scope": "the concatenated subset TSV this run wrote, not the upstream file",
            "licence": card.licence,
            "licence_url": card.licence_url,
            "non_commercial": card.non_commercial,
            **result.as_dict(),
        },
        {
            "name": "record set",
            "path": str(records),
            "role": "which positions were asked for (SNV alleles only)",
        },
    ]
    manifest["outputs"] = [provenance.output(result.parquet_path, result.parquet_rows)]
    manifest["licence"] = f"{card.licence} — see {card.licence_url}. {registry.SHIPS['table']}."
    manifest["patient_data"] = PATIENT_DATA + (
        " The *choice of rows* is patient-derived, so the subset file itself stays under "
        "build/ like every other coordinate-bearing artefact."
    )
    written = provenance.write(manifest, out_dir / f"{card.key}.subset.provenance.json")
    print(f"  provenance -> {written}")
    print(f"\nPaste this into src/mva/zoo/models.d/{card.key}.toml:\n")
    print(_fragment(card, result.subset_sha256))
    return 1 if result.failures else 0


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
    parser.add_argument(
        "--accessions",
        type=Path,
        help="a file of accessions, one per line: convert only those members of an "
        "archive. The plan's tier-1 rule — a parquet subset for this case's records "
        "only — and for a matrix archive it is the difference between minutes and "
        "never finishing.",
    )
    parser.add_argument(
        "--subset-from",
        type=Path,
        metavar="RECORDS",
        help="fetch only the rows this record set needs, by tabix range reads over the "
        "published index, instead of downloading the whole table. For a table of every "
        "possible SNV in the genome this is the difference between 37 GB and a few "
        "hundred MB (plan §10 R7).",
    )
    parser.add_argument(
        "--jobs", type=int, default=tabix_subset.DEFAULT_JOBS, help="parallel tabix workers"
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=1,
        help="with --subset-from: retry the remainder this many times. A long range-read "
        "over HTTPS is dropped by the CDN often enough that one pass rarely finishes; "
        "each round resumes from what the last one wrote.",
    )
    parser.add_argument(
        "--merge-gap",
        type=int,
        default=tabix_subset.DEFAULT_GAP,
        help="merge wanted positions this close into one region (fewer seeks, more rows)",
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
    if args.subset_from:
        return do_subset(
            card,
            args.subset_from,
            args.out,
            execute=args.execute,
            jobs=args.jobs,
            merge_gap=args.merge_gap,
            rounds=args.rounds,
        )
    expected = card.params.get("bytes")
    if args.execute and isinstance(expected, int) and _free_disk(args.out) < expected * 3:
        raise SystemExit(
            f"not enough free disk for {card.key}: it needs about "
            f"{expected * 3 / 1e9:.1f} GB free (raw + extracted + parquet)"
        )
    only: frozenset[str] = frozenset()
    if args.accessions:
        only = frozenset(args.accessions.read_text().split())
        print(f"  restricted to {len(only):,} accessions from {args.accessions}")
    return do_fetch(card, args.out, execute=args.execute, only=only)


if __name__ == "__main__":
    raise SystemExit(main())
