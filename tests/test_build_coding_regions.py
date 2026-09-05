"""The coding-regions builder: what it keeps from a GTF and how it merges.

A six-line synthetic GTF exercises every rule: a non-coding transcript is dropped, a
non-canonical contig is dropped, two overlapping CDS of one gene merge, two CDS of one
gene with a gap stay apart, the stop codon joins the CDS it touches, and the flank never
goes below position 1.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def tool():
    spec = importlib.util.spec_from_file_location(
        "build_coding_regions", ROOT / "tools" / "build_coding_regions.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["build_coding_regions"] = module
    spec.loader.exec_module(module)
    return module


def attrs(gene: str, transcript: str, biotype: str = "protein_coding", tag: str = "") -> str:
    extra = f' tag "{tag}";' if tag else ""
    return (
        f'gene_id "ENSG_{gene}"; transcript_id "{transcript}"; gene_name "{gene}"; '
        f'transcript_biotype "{biotype}";{extra}'
    )


def line(chrom: str, feature: str, start: int, end: int, attribute: str) -> str:
    return "\t".join([chrom, "test", feature, str(start), str(end), ".", "+", "0", attribute])


GTF = "\n".join(
    [
        "#!genome-build GRCh38",
        line("1", "CDS", 100, 200, attrs("A", "T1", tag="Ensembl_canonical")),
        line("1", "CDS", 190, 260, attrs("A", "T2")),  # overlaps T1's CDS → merges
        line("1", "stop_codon", 261, 263, attrs("A", "T2")),  # adjacent → merges
        line("1", "CDS", 1000, 1100, attrs("A", "T1", tag="Ensembl_canonical")),  # gap → apart
        line("1", "exon", 50, 300, attrs("A", "T1")),  # not CDS → ignored
        line("1", "CDS", 5, 30, attrs("B", "T3")),  # flank would go below 1
        line("1", "CDS", 400, 500, attrs("NC", "T4", biotype="lncRNA")),  # dropped
        line("KI270728.1", "CDS", 100, 200, attrs("Z", "T5")),  # non-canonical → dropped
    ]
)


@pytest.fixture(scope="module")
def regions(tool, tmp_path_factory) -> list[tuple]:
    folder = tmp_path_factory.mktemp("gtf")
    gtf = folder / "mini.gtf"
    gtf.write_text(GTF + "\n", encoding="utf-8")
    con = duckdb.connect()
    n = tool.load_cds(con, gtf, canonical_only=False)
    assert n == 5
    out = folder / "coding_regions.tsv"
    counts = tool.merge(con, 8, out)
    assert counts["rows"] == 3
    rows = out.read_text(encoding="utf-8").splitlines()
    assert rows[0] == "chrom\tstart\tend\tgene\tgene_id\tn_cds\tn_transcripts"
    return [tuple(r.split("\t")) for r in rows[1:]]


def test_overlapping_and_adjacent_intervals_merge_with_the_flank(regions):
    merged = next(r for r in regions if r[3] == "A" and int(r[1]) < 500)
    assert (merged[1], merged[2], merged[5], merged[6]) == ("92", "271", "3", "2")


def test_a_gap_keeps_two_intervals_of_one_gene_apart(regions):
    assert sum(1 for r in regions if r[3] == "A") == 2


def test_the_flank_never_goes_below_position_one(regions):
    b = next(r for r in regions if r[3] == "B")
    assert (b[1], b[2]) == ("1", "38")


def test_canonical_only_drops_the_untagged_transcripts(tool, tmp_path: Path):
    gtf = tmp_path / "mini.gtf"
    gtf.write_text(GTF + "\n", encoding="utf-8")
    con = duckdb.connect()
    assert tool.load_cds(con, gtf, canonical_only=True) == 2
