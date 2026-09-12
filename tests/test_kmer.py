"""The k-mer engine: packing, canonical form, membership, bait cutting, uniqueness.

Every test here is checkable by hand — toy sequences, short k — because the production
path (40 M k-mers over 1.07 B reads) is exactly the shape where a silent off-by-one
disappears into a plausible-looking count.
"""

import gzip

import numpy as np
import pytest

from mva.kmer import encode, fasta, scaling, uniqueness
from mva.kmer.bait import Interval, cut, expected_reads, merge, plan
from mva.kmer.membership import Bait, hits


def test_codes_map_bases_and_reject_n():
    codes = encode.codes_of("ACGTN")
    assert list(codes[:4]) == [0, 1, 2, 3]
    assert codes[4] == encode.INVALID


def test_lower_case_reads_the_same_as_upper():
    assert list(encode.codes_of("acgt")) == list(encode.codes_of("ACGT"))


def test_window_kmers_round_trip_through_decode():
    sequence = "ACGTTGCAACGT"
    kmers, valid = encode.window_kmers(encode.codes_of(sequence), k=4)
    assert valid.all()
    assert kmers.size == len(sequence) - 3
    # Window 0 is ACGT; its reverse complement is also ACGT, so canonical == forward.
    assert encode.decode(int(kmers[0]), k=4) == "ACGT"


def test_canonical_form_is_strand_agnostic():
    forward = "AACCGGTTACGTACGTACGTACGTACGTACG"
    reverse = "CGTACGTACGTACGTACGTACGTAACCGGTT"[::-1].translate(str.maketrans("ACGT", "TGCA"))
    a, _ = encode.window_kmers(encode.codes_of(forward), k=31)
    b, _ = encode.window_kmers(encode.codes_of(reverse), k=31)
    assert a[0] == b[0]


def test_a_window_containing_n_is_invalid_not_silently_a():
    kmers, valid = encode.window_kmers(encode.codes_of("ACNGT"), k=3)
    assert list(valid) == [False, False, False]
    assert kmers.size == 3


def test_sequence_shorter_than_k_yields_nothing():
    kmers, valid = encode.window_kmers(encode.codes_of("ACG"), k=31)
    assert kmers.size == 0 and valid.size == 0


def test_strided_kmers_match_the_windows_they_sample():
    reads = np.array([list(b"ACGTTGCAACGTACGT"), list(b"TTTTTTTTTTTTTTTT")], dtype=np.uint8)
    codes = encode.CODES[reads]
    strided, valid = encode.strided_kmers(codes, k=4, stride=3)
    every, _ = encode.window_kmers(codes[0], k=4)
    assert valid.all()
    assert list(strided[0]) == list(every[encode.offsets_for(16, 4, 3)])


def test_offsets_cover_the_start_and_respect_the_stride():
    assert list(encode.offsets_for(150, 31, 16)) == list(range(0, 120, 16))
    assert encode.offsets_for(10, 31, 1).size == 0


def _bait_of(*sequences, k=8):
    kmers = [encode.window_kmers(encode.codes_of(s), k)[0] for s in sequences]
    return Bait.of(np.concatenate(kmers), k=k)


def test_membership_is_exact_and_shape_preserving():
    bait = _bait_of("ACGTTGCAACGTACGT")
    probe, _ = encode.window_kmers(encode.codes_of("ACGTTGCA"), k=8)
    absent, _ = encode.window_kmers(encode.codes_of("TTTTTTTT"), k=8)
    values = np.stack([probe, absent])
    answer = bait.contains(values)
    assert answer.shape == values.shape
    assert answer[0].all() and not answer[1].any()


def test_membership_without_a_bitmap_agrees_with_the_prefiltered_answer():
    kmers, _ = encode.window_kmers(encode.codes_of("ACGTTGCAACGTACGTGGCC"), k=8)
    indexed = Bait.of(kmers, k=8)
    plain = Bait.of(kmers, k=8, bits=None)
    query = np.concatenate([kmers, np.array([np.uint64(7), np.uint64(999)])])
    assert list(indexed.contains(query)) == list(plain.contains(query))


def test_an_empty_bait_matches_nothing():
    assert not Bait.of(np.empty(0, dtype=np.uint64)).contains(np.array([1, 2], np.uint64)).any()


def test_positions_index_back_into_the_kmer_array():
    bait = _bait_of("ACGTTGCAACGTACGT")
    slots = bait.positions(bait.kmers)
    assert list(slots) == list(range(len(bait)))
    assert bait.positions(np.array([np.uint64(3)]))[0] == -1


def test_hits_finds_a_read_on_either_strand():
    bait = _bait_of("ACGTTGCAACGTACGT")
    plus = b"ACGTTGCAACGTACGT"
    minus = bytes(reversed(plus.translate(bytes.maketrans(b"ACGT", b"TGCA"))))
    noise = b"TTTTTTTTTTTTTTTT"
    codes = encode.CODES[np.array([list(plus), list(minus), list(noise)], dtype=np.uint8)]
    assert list(hits(codes, bait, stride=1)) == [True, True, False]


def test_hits_survive_a_single_substitution_in_the_middle():
    reference = "ACGTTGCAACGTACGTGGCCAATTCCGGATCG"
    bait = _bait_of(reference, k=8)
    mutated = reference[:16] + ("A" if reference[16] != "A" else "C") + reference[17:]
    codes = encode.CODES[np.array([list(mutated.encode())], dtype=np.uint8)]
    assert hits(codes, bait, stride=1)[0]


def test_a_read_of_all_n_is_not_a_hit():
    bait = _bait_of("ACGTTGCAACGTACGT")
    codes = encode.CODES[np.array([list(b"NNNNNNNNNNNNNNNN")], dtype=np.uint8)]
    assert not hits(codes, bait, stride=1)[0]


def test_intervals_merge_only_within_a_contig():
    merged = merge([Interval("1", 0, 100), Interval("1", 50, 150), Interval("2", 0, 100)])
    assert [(i.contig, i.start, i.end) for i in merged] == [("1", 0, 150), ("2", 0, 100)]


def test_padding_clamps_at_zero_and_at_the_limit():
    padded = Interval("1", 10, 20).padded(50, limit=40)
    assert (padded.start, padded.end) == (0, 40)


def test_an_empty_interval_is_refused():
    with pytest.raises(ValueError, match="empty interval"):
        Interval("1", 10, 10)


def test_plan_counts_every_base_once():
    laid = plan([Interval("1", 0, 100), Interval("1", 50, 150)])
    assert laid.bases == 150 and laid.by_contig == {"1": 150}


def test_expected_reads_is_bases_times_depth_over_read_length():
    assert expected_reads(1_000_000, 44.0, 150) == pytest.approx(293_333.33, rel=1e-4)


def _write_fasta(path, contigs, compress=False):
    text = "".join(f">{name} extra\n{seq}\n" for name, seq in contigs)
    if compress:
        path.write_bytes(gzip.compress(text.encode()))
    else:
        path.write_text(text)
    return path


def test_fasta_renames_contigs_to_the_bare_spelling():
    assert fasta.rename("chr1") == "1"
    assert fasta.rename("chrM") == "MT"
    assert fasta.rename("17") == "17"


def test_fasta_streams_wrapped_sequences_and_gzip(tmp_path):
    reference = _write_fasta(tmp_path / "ref.fa.gz", [("chr1", "ACGT\nTGCA"), ("chr2", "GG")], True)
    found = {c.name: bytes(c.bases).decode() for c in fasta.contigs(reference)}
    assert found == {"1": "ACGTTGCA", "2": "GG"}
    assert fasta.names(reference) == ["1", "2"]


def test_fasta_skips_contigs_nobody_asked_for(tmp_path):
    reference = _write_fasta(tmp_path / "ref.fa", [("chr1", "ACGT"), ("chr2", "GGGG")])
    assert [c.name for c in fasta.contigs(reference, wanted={"2"})] == ["2"]


def test_cut_takes_only_the_requested_slice(tmp_path):
    reference = _write_fasta(tmp_path / "ref.fa", [("chr1", "ACGTTGCAACGTACGTGGCC")])
    bait, laid = cut(reference, [Interval("1", 0, 8)], k=8, bits=None)
    assert laid.bases == 8
    assert len(bait) == 1
    assert encode.decode(int(bait.kmers[0]), 8) in {"ACGTTGCA", "TGCAACGT"}


def test_cut_drops_windows_that_span_an_assembly_gap(tmp_path):
    reference = _write_fasta(tmp_path / "ref.fa", [("chr1", "ACGTNNNNACGTACGT")])
    bait, _ = cut(reference, [Interval("1", 0, 16)], k=8, bits=None)
    assert len(bait) == len(set(encode.window_kmers(encode.codes_of("ACGTACGT"), 8)[0].tolist()))


def test_uniqueness_counts_a_repeated_kmer_twice(tmp_path):
    repeat = "ACGTTGCA"
    reference = _write_fasta(tmp_path / "ref.fa", [("chr1", repeat + "GGGGGGGG" + repeat)])
    bait, _ = cut(reference, [Interval("1", 0, 8)], k=8, bits=None)
    occurrence = uniqueness.count_in_genome(reference, bait, chunk_bases=16)
    assert occurrence.unseen == 0
    assert int(occurrence.counts[0]) == 2
    kept, report = uniqueness.drop_repeats(bait, occurrence)
    assert len(kept) == 0 and report["repeated"] == 1


def test_uniqueness_keeps_a_kmer_that_occurs_once(tmp_path):
    reference = _write_fasta(tmp_path / "ref.fa", [("chr1", "ACGTTGCAGGCCAATTCCGGATCGTTAA")])
    bait, _ = cut(reference, [Interval("1", 0, 12)], k=8, bits=None)
    occurrence = uniqueness.count_in_genome(reference, bait, chunk_bases=9)
    kept, report = uniqueness.drop_repeats(bait, occurrence)
    assert report["unseen"] == 0
    assert len(kept) == len(bait)


def test_chunking_does_not_lose_a_window_on_the_boundary(tmp_path):
    sequence = "ACGTTGCAGGCCAATTCCGGATCGTTAACCGGTTAA"
    reference = _write_fasta(tmp_path / "ref.fa", [("chr1", sequence)])
    bait, _ = cut(reference, [Interval("1", 0, len(sequence))], k=8, bits=None)
    whole = uniqueness.count_in_genome(reference, bait, chunk_bases=10_000)
    split = uniqueness.count_in_genome(reference, bait, chunk_bases=9)
    assert list(whole.counts) == list(split.counts)


# --- the scaling gate (plan stage 4) ---------------------------------------------------


def _pool(size: int) -> np.ndarray:
    return np.unique(np.random.default_rng(7).integers(0, 2**62, size=size, dtype=np.uint64))


def test_sample_bait_draws_the_asked_for_size():
    bait = scaling.sample_bait(_pool(10_000), 500)
    assert len(bait) == 500


def test_sample_bait_caps_at_the_pool_when_asked_for_more():
    pool = _pool(200)
    assert len(scaling.sample_bait(pool, 10_000)) == pool.size


def test_sample_bait_does_not_take_the_sorted_prefix():
    # taking bait[:n] would make every drawn k-mer share a leading prefix and flatter both
    # the binary search and the bitmap; a draw must not be ordered like its pool
    pool = _pool(10_000)
    drawn = np.asarray(scaling.sample_bait(pool, 100).kmers)
    assert drawn.max() > pool[500]


def test_measure_returns_one_point_per_size_over_the_same_reads():
    codes = encode.codes_of(np.frombuffer(("ACGT" * 40).encode(), dtype=np.uint8))
    matrix = np.tile(codes, (32, 1))
    points = scaling.measure(matrix, _pool(5_000), (100, 1_000), stride=4, k=31)
    assert [p.bait_kmers for p in points] == [100, 1_000]
    assert {p.reads for p in points} == {32}
    assert all(p.seconds > 0 and p.bait_bytes > 0 for p in points)


def test_project_scales_the_measured_rate_to_the_whole_store():
    point = scaling.Point(
        bait_kmers=1, reads=1_000, seconds=2.0, hit_rate=0.0, bait_bytes=8, peak_rss_bytes=1
    )
    assert scaling.project(point, 10_000) == pytest.approx(20.0)


def test_project_is_infinite_when_nothing_was_measured():
    point = scaling.Point(
        bait_kmers=1, reads=0, seconds=0.0, hit_rate=0.0, bait_bytes=8, peak_rss_bytes=1
    )
    assert scaling.project(point, 10_000) == float("inf")
