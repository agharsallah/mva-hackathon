"""Dosage from k-mers: the probe set, the two denominators, and the pass that counts them.

This is the only route in the package that can see a chromosome with no heterozygous sites —
the male X, or a gain present in every cell — so the tests inject exactly those cases and
check the number that comes back.

The counting pass is tested against the kernel it wraps rather than against a fixture: a
shard-by-shard tally must equal the tally of the concatenation, which is the property that
makes a 272-shard pass equivalent to one impossible pass over everything at once.
"""

import numpy as np
import pytest

from mva.kmer import count
from mva.kmer import dosage as dosage_module
from mva.kmer.chromosome import CALIBRATION_NAME, design, sample_contig
from mva.kmer.encode import codes_of
from mva.kmer.fasta import Contig
from mva.kmer.membership import Bait
from mva.pipeline import nulls


def contig(name: str, size: int, seed: int) -> Contig:
    rng = np.random.default_rng(seed)
    return Contig(name, rng.choice(np.frombuffer(b"ACGT", dtype=np.uint8), size=size))


@pytest.fixture(scope="module")
def probes():
    return design(
        [contig(str(index), 120_000, seed=index) for index in range(1, 6)]
        + [contig("X", 100_000, seed=99)],
        per_chromosome=400,
        calibration=300,
        seed=3,
    )


def counts_for(probes, truth: dict[str, float], *, depth: float = 44.0, seed: int = 7):
    """Poisson counts at `depth × copies ÷ 2` — the forward model dosage inverts."""
    rng = np.random.default_rng(seed)
    values = np.zeros(len(probes), dtype=np.int64)
    for index, name in enumerate(probes.contigs):
        mask = probes.owner == index
        copies = 1.0 if name == CALIBRATION_NAME else truth.get(name, 1.0)
        values[mask] = rng.poisson(depth * copies / 2, size=int(mask.sum()))
    return values


class TestProbeDesign:
    def test_every_contig_gets_its_quota_and_a_calibration_set_exists(self, probes):
        per = probes.per_contig()
        assert per["1"] == 400
        assert per[CALIBRATION_NAME] == 300
        assert CALIBRATION_NAME in probes.contigs

    def test_probes_are_spread_rather_than_clustered(self):
        """An even stride, not a random sample: every part of a contig weighs the same in
        the dosage, which is what makes the number a property of the chromosome."""
        one = contig("1", 200_000, seed=11)
        picked = sample_contig(one, count=100, rng=np.random.default_rng(0))
        assert picked.size == 100
        # The same contig always yields the same probes: the design is deterministic.
        again = sample_contig(one, count=100, rng=np.random.default_rng(12345))
        assert np.array_equal(picked, again)

    def test_a_contig_with_no_usable_sequence_yields_nothing_rather_than_raising(self):
        empty = Contig("21", np.frombuffer(b"NNNNNNNNNN", dtype=np.uint8))
        assert sample_contig(empty, count=10, rng=np.random.default_rng(0)).size == 0

    def test_the_report_says_what_was_considered_and_what_survived(self, probes):
        described = probes.as_dict()
        assert set(described["per_contig"]) == set(probes.contigs)
        assert described["k"] == 31


class TestDosage:
    def test_a_balanced_genome_reads_one(self, probes):
        values = counts_for(probes, {})
        for row in dosage_module.dosage(values, probes, resamples=200, seed=5):
            assert row.relative == pytest.approx(1.0, abs=0.05)

    def test_a_chromosome_at_three_copies_reads_one_and_a_half(self, probes):
        values = counts_for(probes, {"3": 1.5})
        found = {
            row.chrom: row for row in dosage_module.dosage(values, probes, resamples=200, seed=5)
        }
        assert found["3"].relative == pytest.approx(1.5, abs=0.06)
        assert found["3"].low > 1.3

    def test_a_single_copy_chromosome_reads_one_half(self, probes):
        """The case allele balance cannot see at all: one X in a male has no heterozygous
        sites to be unbalanced, so only dosage can find it."""
        values = counts_for(probes, {"X": 0.5})
        found = {
            row.chrom: row for row in dosage_module.dosage(values, probes, resamples=200, seed=5)
        }
        assert found["X"].relative == pytest.approx(0.5, abs=0.05)

    def test_the_sex_chromosomes_stay_out_of_the_denominator(self, probes):
        """Including a hemizygous contig would drag the median every autosome is judged by."""
        values = counts_for(probes, {"X": 0.5})
        found = {
            row.chrom: row for row in dosage_module.dosage(values, probes, resamples=100, seed=5)
        }
        assert found["1"].relative == pytest.approx(1.0, abs=0.05)

    def test_the_absolute_denominator_agrees_with_the_relative_one_on_a_normal_genome(self, probes):
        values = counts_for(probes, {"3": 1.5})
        for row in dosage_module.dosage(values, probes, resamples=100, seed=5):
            assert abs(row.disagreement) < 0.1

    def test_silent_probes_are_counted_rather_than_averaged_away(self, probes):
        values = counts_for(probes, {})
        values[:50] = 0
        found = {
            row.chrom: row for row in dosage_module.dosage(values, probes, resamples=50, seed=5)
        }
        assert found["1"].silent >= 50 - 1
        assert found["1"].silent_share > 0.1

    def test_a_mismatched_tally_is_refused_rather_than_broadcast(self, probes):
        with pytest.raises(ValueError, match="not from the same design"):
            dosage_module.dosage(np.zeros(len(probes) - 1), probes)

    def test_the_interval_convention_matches_the_rest_of_the_project(self):
        """mva.kmer is a leaf and cannot import mva.pipeline, so the constants are copied —
        and this is the check that turns a copy from a drift risk into a checked one."""
        assert dosage_module.RESAMPLES == nulls.RESAMPLES
        assert dosage_module.LEVEL == nulls.LEVEL


class TestCountingPass:
    def test_a_shard_by_shard_tally_equals_the_tally_of_everything_at_once(self):
        """The property that makes 272 shards equivalent to one impossible pass."""
        rng = np.random.default_rng(21)
        reference = rng.choice(np.frombuffer(b"ACGT", dtype=np.uint8), size=5_000)
        picked = sample_contig(Contig("1", reference), count=40, rng=rng)
        bait = Bait(np.sort(np.unique(picked)), k=31)

        reads = [bytes(reference[start : start + 150]) for start in range(0, 3_000, 150)]
        matrix = np.vstack([codes_of(read) for read in reads])
        whole = count.tally(matrix, bait)
        first = count.tally(matrix[:10], bait)
        second = count.tally(matrix[10:], bait)
        merged = first.merged(second)
        assert np.array_equal(merged.counts, whole.counts)
        assert merged.reads_scanned == whole.reads_scanned


def packed(spelling: str) -> np.ndarray:
    """One 2-bit packed k-mer, the way a probe array holds it.

    ``window_kmers`` returns the **canonical** spelling -- whichever of the k-mer and its
    reverse complement sorts smaller. That is GC-safe: complementing swaps A with T and C
    with G, so the count of G and C is the same either way.
    """
    from mva.kmer.encode import window_kmers

    kmers, _ = window_kmers(codes_of(spelling), len(spelling))
    return kmers


class TestGcFraction:
    def test_it_reads_gc_straight_off_the_packing(self):
        for spelling, expected in (("G" * 31, 1.0), ("A" * 31, 0.0), ("C" * 31, 1.0)):
            assert dosage_module.gc_fraction(packed(spelling), 31)[0] == pytest.approx(expected)

    def test_a_mixed_kmer_counts_only_g_and_c(self):
        # 'GC' twelve times then 'ATATATA': 24 of the 31 bases are G or C.
        spelling = "GC" * 12 + "ATATATA"
        assert dosage_module.gc_fraction(packed(spelling), 31)[0] == pytest.approx(24 / 31)


class TestComposition:
    """The correction exists because a bootstrap over probes cannot see a chromosome-wide bias.

    So the tests inject exactly that: a per-chromosome multiplier that is a function of GC and
    nothing else. Every chromosome is truly diploid, the naive ratio says otherwise, and the
    residual has to put them back.
    """

    def test_it_removes_a_gc_trend_a_bootstrap_would_have_missed(self, probes):
        gc = {name: 0.35 + 0.02 * index for index, name in enumerate(probes.contigs)}
        counts = counts_for(probes, {})
        biased = counts.astype(np.float64)
        for index, name in enumerate(probes.contigs):
            biased[probes.owner == index] *= 1.0 + 2.0 * (gc[name] - 0.40)
        rows = dosage_module.dosage(np.rint(biased).astype(np.int64), probes)

        naive = np.std([row.relative for row in rows if row.chrom != "X"], ddof=1)
        fit = dosage_module.composition(rows, probes, exclude=frozenset({"X"}), gc=gc)

        assert fit.correlation > 0.9
        assert fit.residual_spread < naive / 2
        assert all(abs(value - 1.0) < 0.05 for value in fit.residual.values())

    def test_an_excluded_contig_does_not_enter_the_fit(self, probes):
        rows = dosage_module.dosage(counts_for(probes, {"X": 1.0}), probes)
        fit = dosage_module.composition(rows, probes, exclude=frozenset({"X"}))
        assert "X" not in fit.fitted
        assert "X" not in fit.residual

    def test_the_regressor_it_used_is_recorded(self, probes):
        rows = dosage_module.dosage(counts_for(probes, {}), probes)
        supplied = {name: 0.38 + 0.01 * index for index, name in enumerate(probes.contigs)}
        assert "chromosome" in dosage_module.composition(rows, probes, gc=supplied).source
        assert dosage_module.composition(rows, probes).source == "probe GC"

    def test_probe_gc_and_supplied_gc_are_not_interchangeable(self, probes):
        """The reason the reference regressor exists: the two disagree, so the fit differs.

        A probe set is what the uniqueness filter left, which is not composed like the
        sequence it was cut from. Feeding one where the other belongs silently changes every
        residual, so the API makes the choice explicit rather than defaulting quietly.
        """
        rows = dosage_module.dosage(counts_for(probes, {}), probes)
        shifted = {name: 0.30 + 0.05 * index for index, name in enumerate(probes.contigs)}
        by_probe = dosage_module.composition(rows, probes, exclude=frozenset({"X"}))
        by_reference = dosage_module.composition(rows, probes, exclude=frozenset({"X"}), gc=shifted)
        assert by_probe.gc != by_reference.gc
        assert by_probe.slope != pytest.approx(by_reference.slope)


class TestGcContent:
    def test_it_ignores_n_runs_rather_than_counting_them_as_at(self):
        from mva.kmer.chromosome import gc_content

        plain = Contig("t", np.frombuffer(b"GCGCATAT", dtype=np.uint8))
        gapped = Contig("t", np.frombuffer(b"GCGCATAT" + b"N" * 500, dtype=np.uint8))
        assert gc_content(plain) == pytest.approx(0.5)
        assert gc_content(gapped) == pytest.approx(0.5)

    def test_soft_masked_sequence_still_counts(self):
        from mva.kmer.chromosome import gc_content

        assert gc_content(Contig("t", np.frombuffer(b"gcgcatat", dtype=np.uint8))) == pytest.approx(
            0.5
        )
