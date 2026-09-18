"""Chromosome arm geometry: the reduction, the acrocentric rule, and the committed table.

``tools/build_cytobands.py`` turns UCSC's ~1,200-row band table into 24 rows saying where
each chromosome's centromere sits. Step 8 tests allele balance per arm, and an arm
boundary that is off by a few megabases would move heterozygous sites between the two
halves of a test — so the reduction is asserted on bands written here, and the committed
table is asserted against facts published independently of it.

Nothing reaches the network: the UCSC download is gitignored scratch, so every test builds
its own gzip stream in ``tmp_path``.

The committed table carries reference coordinates — where a centromere sits in GRCh38 —
and no position of any sample. That is the same perimeter ``tools/check_coordinates.py``
draws by exempting ``ressources/``, and the last test states it as an assertion rather
than leaving it to the gate.
"""

import csv
import gzip
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import build_cytobands as cyto

REPO = Path(__file__).resolve().parent.parent
COMMITTED = REPO / "ressources" / "reference" / "cytoband_arms.tsv"


def write_bands(path: Path, rows: list[tuple[str, int, int, str, str]]) -> Path:
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        for row in rows:
            handle.write("\t".join(str(value) for value in row) + "\n")
    return path


def metacentric(chrom: str) -> list[tuple[str, int, int, str, str]]:
    """A chromosome with a real short arm: two bands, the centromere, two more."""
    return [
        (chrom, 0, 100, "p12", "gneg"),
        (chrom, 100, 400, "p11", "gpos50"),
        (chrom, 400, 500, "p11.1", "acen"),
        (chrom, 500, 600, "q11.1", "acen"),
        (chrom, 600, 1000, "q21", "gneg"),
    ]


class TestArms:
    def test_the_boundary_is_the_span_of_the_acen_bands(self):
        geometry = cyto.arms([row[1:] for row in metacentric("chr1")])
        assert geometry["p_end"] == 400
        assert geometry["cen_start"] == 400
        assert geometry["cen_end"] == 600
        assert geometry["q_start"] == 600

    def test_length_is_the_largest_band_end(self):
        geometry = cyto.arms([row[1:] for row in metacentric("chr1")])
        assert geometry["chrom_length"] == 1000
        assert geometry["bands"] == 5

    def test_a_contig_with_no_centromere_is_refused_not_guessed(self):
        with pytest.raises(ValueError, match="no acen band"):
            cyto.arms([(0, 100, "p12", "gneg")])

    def test_a_stalk_on_the_short_arm_marks_an_acrocentric(self):
        bands = [row[1:] for row in metacentric("chr13")]
        bands[1] = (100, 400, "p12", "stalk")
        assert cyto.arms(bands)["acrocentric"] is True

    def test_a_stalk_after_the_centromere_does_not(self):
        """The flag is about the *short* arm; a q-arm stain must not set it."""
        bands = [row[1:] for row in metacentric("chr1")]
        bands[4] = (600, 1000, "q21", "stalk")
        assert cyto.arms(bands)["acrocentric"] is False


class TestBuild:
    def test_alternate_contigs_are_dropped(self, tmp_path):
        source = write_bands(
            tmp_path / "bands.txt.gz",
            [row for name in cyto.CANONICAL for row in metacentric(name)]
            + [("chr1_KI270706v1_random", 0, 10, "p1", "acen")],
        )
        rows = cyto.build(source, tmp_path / "out.tsv")
        assert rows == len(cyto.CANONICAL) == 24
        written = list(csv.DictReader((tmp_path / "out.tsv").open(), delimiter="\t"))
        assert [row["chrom"] for row in written] == list(cyto.CANONICAL)

    def test_a_missing_canonical_contig_fails_the_build(self, tmp_path):
        source = write_bands(
            tmp_path / "bands.txt.gz",
            [row for name in cyto.CANONICAL[:-1] for row in metacentric(name)],
        )
        with pytest.raises(SystemExit, match="missing 1 canonical"):
            cyto.build(source, tmp_path / "out.tsv")


class TestTheCommittedTable:
    @pytest.fixture(scope="class")
    @staticmethod
    def rows() -> dict[str, dict[str, str]]:
        with COMMITTED.open(encoding="utf-8") as handle:
            return {row["chrom"]: row for row in csv.DictReader(handle, delimiter="\t")}

    def test_every_canonical_contig_is_present(self, rows):
        assert list(rows) == list(cyto.CANONICAL)

    def test_the_five_acrocentrics_are_the_ones_cytogenetics_names(self, rows):
        flagged = {chrom for chrom, row in rows.items() if row["acrocentric"] == "True"}
        assert flagged == {"chr13", "chr14", "chr15", "chr21", "chr22"}

    @pytest.mark.parametrize(
        ("chrom", "length"),
        # GRCh38 primary-assembly lengths, published in the assembly report and quoted in
        # every reference FASTA index -- independent of the band file this table came from.
        [("chr1", 248_956_422), ("chr21", 46_709_983), ("chrX", 156_040_895)],
    )
    def test_lengths_match_the_published_assembly(self, rows, chrom, length):
        assert int(rows[chrom]["chrom_length"]) == length

    def test_the_centromere_lies_inside_the_chromosome(self, rows):
        for row in rows.values():
            assert 0 < int(row["cen_start"]) < int(row["cen_end"]) < int(row["chrom_length"])

    def test_chr1_centromere_matches_the_published_position(self, rows):
        """~121.7-125.1 Mb in GRCh38, the most-quoted centromere in the assembly."""
        assert int(rows["chr1"]["cen_start"]) == 121_700_000
        assert int(rows["chr1"]["cen_end"]) == 125_100_000
