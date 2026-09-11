#!/usr/bin/env python3
"""Prepare a reference genome this project's tools and this project's callset agree on.

**Why a build step at all.** A reference genome is a coordinate system, and two copies of
"GRCh38" can disagree in ways that silently move every result: whether contigs are named
``chr1`` or ``1``, whether the decoy and HLA sequences are present, whether pseudo-autosomal
regions on Y are hard-masked. Getting that wrong does not raise an error — it produces
plausible calls in the wrong place.

**What this project needs, and why.**

*Bare contig names* (``1``, not ``chr1``). The delivered callset was produced against a
*no-chr* reference (``ideation/data-findings.md`` §2) and the gene model in
``ressources/reference/coding_regions.tsv`` is Ensembl, also bare. Renaming here means no
later stage needs a translation table, which is the class of bug that shifts an analysis
by a whole contig.

*The no-alt analysis set, decoys included.* The delivery names
``GRCh38_no_alt_analysis_set_plus_hs38d1``. Its closest public equivalent is NCBI's
analysis set, which carries the same hs38d1 decoys. Decoys matter: without them, reads
from decoy-homologous sequence have nowhere correct to go and pile onto primary contigs,
inventing variants. The remaining difference from the vendor's build (its extra masking)
is an assumption, stated in the provenance manifest rather than assumed away.

The description after the first word of each header is dropped, so contig names in a BAM
header stay short and comparable.

Usage::

    uv run python tools/build_reference_genome.py            # uses the downloaded .fna.gz
    uv run python tools/build_reference_genome.py --source path.fna.gz --out build/reference
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_SOURCE = Path("build/reference/GCA_000001405.15_GRCh38_no_alt_analysis_set.fna.gz")
DEFAULT_OUT = Path("build/reference")
DEFAULT_NAME = "GRCh38.fa"

#: Where the source came from, recorded so the manifest names a URL and not just a file.
SOURCE_URL = (
    "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/000/001/405/GCA_000001405.15_GRCh38/"
    "seqs_for_alignment_pipelines.ucsc_ids/"
    "GCA_000001405.15_GRCh38_no_alt_analysis_set.fna.gz"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 22), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bare(name: str) -> str:
    """``chr1`` -> ``1``, ``chrM`` -> ``MT``; everything else kept as it is.

    Mirrors :func:`mva.kmer.fasta.rename`, which applies the same rule when the bait is
    cut, so the FASTA on disk and the k-mers in memory cannot disagree.
    """
    stripped = name[3:] if name.startswith("chr") else name
    return "MT" if stripped in {"M", "MT"} else stripped


def rewrite(source: Path, target: Path) -> dict[str, int]:
    """Decompress and rename headers in one streaming pass; return contig lengths."""
    lengths: dict[str, int] = {}
    current = ""
    opener = gzip.open if source.suffix == ".gz" else open
    with opener(source, "rb") as handle, target.open("wb") as out:
        for line in handle:
            if line.startswith(b">"):
                current = bare(line[1:].split()[0].decode("ascii"))
                lengths[current] = 0
                out.write(f">{current}\n".encode("ascii"))
                continue
            out.write(line)
            lengths[current] += len(line.strip())
    return lengths


def faidx(target: Path) -> Path:
    """Index with samtools so every downstream tool can seek by coordinate."""
    if shutil.which("samtools") is None:
        raise RuntimeError("samtools not on PATH — `brew install samtools`")
    subprocess.run(["samtools", "faidx", str(target)], check=True)
    return target.with_suffix(target.suffix + ".fai")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--name", default=DEFAULT_NAME)
    parser.add_argument("--source-url", default=SOURCE_URL)
    parser.add_argument("--skip-index", action="store_true", help="write the FASTA only")
    args = parser.parse_args(argv)

    if not args.source.exists():
        print(f"missing source: {args.source}\n  download it from {args.source_url}")
        return 1
    args.out.mkdir(parents=True, exist_ok=True)
    target = args.out / args.name

    print(f"source {args.source} ({args.source.stat().st_size:,} B)")
    source_digest = sha256(args.source)
    print(f"  sha256 {source_digest}")
    print(f"rewriting headers to bare contigs -> {target}")
    lengths = rewrite(args.source, target)
    primary = [name for name in lengths if name.isdigit() or name in {"X", "Y", "MT"}]
    print(f"  {len(lengths):,} contigs, {sum(lengths.values()):,} bases")
    print(f"  {len(primary)} primary: {', '.join(primary[:5])} … {', '.join(primary[-3:])}")

    index = None if args.skip_index else faidx(target)
    if index:
        print(f"indexed -> {index}")

    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "tool": "tools/build_reference_genome.py",
        "source": {
            "url": args.source_url,
            "file": args.source.name,
            "bytes": args.source.stat().st_size,
            "sha256": source_digest,
        },
        "output": {
            "file": target.name,
            "bytes": target.stat().st_size,
            "sha256": sha256(target),
            "contigs": len(lengths),
            "bases": sum(lengths.values()),
            "primary_contigs": primary,
        },
        "transformation": (
            "gzip -> plain FASTA; header rewritten to its first word with a leading 'chr' "
            "stripped and M renamed MT (mva.kmer.fasta.rename); sequence bytes unchanged"
        ),
        "assumptions": [
            (
                "The delivered callset names the vendor's no-alt analysis set plus hs38d1, "
                "additionally GRC-exclusion masked (ideation/data-findings.md §2). This is "
                "NCBI's analysis set: the same no-alt primary assembly and the same hs38d1 "
                "decoys, without that extra masking. Concordance checks against the "
                "delivered callset are therefore restricted to primary contigs."
            ),
            (
                "Contig naming matches ressources/reference/coding_regions.tsv "
                "(Ensembl 116, bare), so bait intervals need no translation."
            ),
        ],
        "contig_lengths": lengths,
    }
    path = args.out / f"{target.stem}.provenance.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"provenance -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
