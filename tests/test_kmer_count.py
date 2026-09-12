"""Multiplicity: how many reads carry each probe, which membership cannot answer.

Every case is small enough to count by hand, because the production shape — tens of
thousands of probes over 15.8 million reads — is exactly where an off-by-one turns into a
plausible genotype instead of an error.
"""

import numpy as np
import pytest

from mva.kmer import encode
from mva.kmer.count import Tally, by_fragment, hits_per_read, tally
from mva.kmer.membership import Bait

K = 6


def bait_of(*sequences: str) -> Bait:
    """A probe set built from whole short sequences, one probe each.

    ``Bait.of`` sorts, so a probe's index is its rank among the canonical integers and not
    the order it was written here. Every assertion below reads probe *index*, so the helper
    refuses a set whose two orders differ rather than let a test quietly check the wrong
    probe — pick different sequences if this fires.
    """
    kmers = [encode.window_kmers(encode.codes_of(seq), k=K)[0][0] for seq in sequences]
    packed = np.array(kmers, dtype=np.uint64)
    if list(packed) != sorted(packed):
        raise AssertionError(f"probe indices would not match argument order: {sequences}")
    return Bait.of(packed, k=K)


def reads(*sequences: str) -> np.ndarray:
    """A code matrix. Reads are padded with ``N`` to the longest, which yields no k-mer."""
    width = max(len(seq) for seq in sequences)
    return np.stack([encode.codes_of(seq.ljust(width, "N")) for seq in sequences])


def test_a_probe_in_two_reads_is_counted_twice():
    probes = bait_of("ACGTTG")
    result = tally(reads("AACGTTGA", "TTACGTTG"), probes)
    assert list(result.counts) == [2]
    assert result.reads_scanned == 2


def test_a_probe_no_read_carries_counts_zero_rather_than_going_missing():
    probes = bait_of("ACGTTG", "GGGGCC")
    result = tally(reads("AACGTTGA"), probes)
    assert list(result.counts) == [1, 0]
    assert result.observed == 1 and result.silent == 1


def test_a_probe_is_found_on_either_strand():
    """A fragment is sequenced from whichever strand it came off, so one stored canonical
    probe must answer for both spellings — the same promise `membership` makes."""
    probes = bait_of("ACGTTG")
    forward = tally(reads("AACGTTGA"), probes)
    reverse = tally(reads("TCAACGTT"), probes)
    assert list(forward.counts) == list(reverse.counts) == [1]


def test_a_probe_occurring_twice_in_one_read_is_two_occurrences_but_one_hit():
    """`tally` counts windows; `hits_per_read` counts reads. A tandem repeat inside one
    read is a property of that sequence, not two independent observations of the allele."""
    probes = bait_of("ACGTTG")
    matrix = reads("ACGTTGACGTTG")
    assert list(tally(matrix, probes).counts) == [2]
    rows, cols = hits_per_read(matrix, probes)
    assert list(rows) == [0] and list(cols) == [0]


def test_a_window_containing_n_contributes_nothing():
    probes = bait_of("ACGTTG")
    assert list(tally(reads("AACGTNGA"), probes).counts) == [0]


def test_chunking_does_not_change_the_answer():
    """The chunk size is a memory knob, never a correctness one — the same promise the
    membership bitmap makes."""
    probes = bait_of("ACGTTG", "TTGCAA")
    matrix = reads(*["AACGTTGA", "GGTTGCAA", "CCCCCCCC"] * 7)
    whole = tally(matrix, probes, chunk_rows=1000)
    split = tally(matrix, probes, chunk_rows=2)
    assert list(whole.counts) == list(split.counts)
    assert whole.windows_scanned == split.windows_scanned


def test_hits_name_the_read_and_the_probe():
    probes = bait_of("ACGTTG", "TTGCAA")
    rows, cols = hits_per_read(reads("AACGTTGA", "GGTTGCAA", "CCCCCCCC"), probes)
    assert list(zip(rows.tolist(), cols.tolist(), strict=True)) == [(0, 0), (1, 1)]


def test_one_read_carrying_two_different_probes_appears_twice():
    probes = bait_of("ACGTTG", "TTGCAA")
    rows, cols = hits_per_read(reads("AACGTTGCAA"), probes)
    assert sorted(zip(rows.tolist(), cols.tolist(), strict=True)) == [(0, 0), (0, 1)]


def test_a_fragment_seen_by_both_its_reads_is_one_observation():
    """R1 and R2 are two reads of one piece of DNA. At a ~266 bp fragment against 2 x 150 bp
    of read they overlap, so a probe in the overlap would otherwise be counted twice for a
    single molecule — and the genotype model's coverage parameter is per molecule."""
    probes = bait_of("ACGTTG")
    rows, cols = hits_per_read(reads("AACGTTGA", "TTACGTTG"), probes)
    same = by_fragment(rows, cols, np.array([0, 0]), probes=1)
    apart = by_fragment(rows, cols, np.array([0, 1]), probes=1)
    assert list(same) == [1]
    assert list(apart) == [2]


def test_by_fragment_with_no_hits_returns_zeros_not_an_empty_array():
    assert list(by_fragment(np.empty(0, np.int64), np.empty(0, np.int64), np.zeros(3), 2)) == [
        0,
        0,
    ]


def test_tallies_over_the_same_probe_set_fold_together():
    """Counting is a fold, so a caller may stream a store in pieces without holding it."""
    probes = bait_of("ACGTTG", "TTGCAA")
    first = tally(reads("AACGTTGA"), probes)
    second = tally(reads("GGTTGCAA"), probes)
    merged = first.merged(second)
    assert list(merged.counts) == [1, 1]
    assert merged.reads_scanned == 2


def test_merging_tallies_of_different_probe_sets_is_refused():
    one = Tally(counts=np.zeros(2, np.uint32), reads_scanned=0, windows_scanned=0)
    other = Tally(counts=np.zeros(3, np.uint32), reads_scanned=0, windows_scanned=0)
    with pytest.raises(ValueError, match="different probe sets"):
        one.merged(other)


def test_an_empty_probe_set_counts_nothing_rather_than_raising():
    probes = Bait.of(np.empty(0, dtype=np.uint64), k=K)
    result = tally(reads("AACGTTGA"), probes)
    assert result.counts.size == 0
    rows, cols = hits_per_read(reads("AACGTTGA"), probes)
    assert rows.size == cols.size == 0
