"""Reference/alternate probe pairs: the windows, the two uniqueness rules, and what is kept.

Toy contigs and a small k, because the production shape — tens of thousands of alleles
against 3.1 billion reference windows — is where a one-base slip becomes a wrong genotype
rather than a crash.
"""

import pytest

from mva.kmer import encode, uniqueness
from mva.kmer.membership import Bait
from mva.kmer.probes import (
    Allele,
    Design,
    ProbePair,
    design,
    occurrence_map,
    stream_alleles,
    unique_only,
)

K = 7


def write_fasta(path, contigs: dict[str, str]):
    path.write_text("".join(f">{name}\n{seq}\n" for name, seq in contigs.items()), encoding="ascii")
    return path


def kmer_of(sequence: str) -> int:
    kmers, valid = encode.window_kmers(encode.codes_of(sequence), k=K)
    assert valid[0]
    return int(kmers[0])


#: 60 bases with no repeat, so every window of it is unique in the toy genome.
CONTIG = "ACGTTGCAAGGTCCATGACTTAGCGGATCCTTAGGACTTGCAAGTCGATCAGGTTACCGA"


def test_three_windows_span_the_variant_and_differ_only_by_it(tmp_path):
    reference = write_fasta(tmp_path / "ref.fa", {"1": CONTIG})
    allele = Allele(contig="1", position=30, ref=CONTIG[29], alt="A", label="GENE|1")
    built = design(reference, [allele], k=K, probes=3)

    assert len(built.pairs) == 3
    for pair in built.pairs:
        assert -(K - 1) <= pair.offset <= 0
        assert pair.ref_kmer != pair.alt_kmer


def test_the_reference_probe_is_the_reference_and_the_alternate_carries_the_allele(tmp_path):
    reference = write_fasta(tmp_path / "ref.fa", {"1": CONTIG})
    # Variant at 1-based position 11; a window starting there is CONTIG[10:17].
    original = CONTIG[10]
    alt = "A" if original != "A" else "C"
    built = design(reference, [Allele("1", 11, original, alt, "GENE|1")], k=K, probes=3)

    flush = next(pair for pair in built.pairs if pair.offset == 0)
    assert flush.ref_kmer == kmer_of(CONTIG[10 : 10 + K])
    assert flush.alt_kmer == kmer_of(alt + CONTIG[11 : 10 + K])


def test_windows_are_spread_across_the_variant_rather_than_bunched(tmp_path):
    """Adjacent windows share all but one base, so three of them fail together. The point
    of three probes is that they fail independently."""
    reference = write_fasta(tmp_path / "ref.fa", {"1": CONTIG})
    built = design(reference, [Allele("1", 30, CONTIG[29], "A", "GENE|1")], k=K, probes=3)
    offsets = sorted(pair.offset for pair in built.pairs)
    assert offsets == [-6, -3, 0]


def test_an_allele_at_the_contig_edge_keeps_the_windows_that_fit(tmp_path):
    """Fewer than three probes is a weaker measurement, not a missing one — it is kept and
    the loss is counted."""
    reference = write_fasta(tmp_path / "ref.fa", {"1": CONTIG})
    built = design(reference, [Allele("1", 2, CONTIG[1], "A", "GENE|1")], k=K, probes=3)
    assert 0 < len(built.pairs) < 3
    assert built.skipped["window_off_contig_or_n"] >= 1


def test_an_allele_on_a_contig_the_reference_does_not_have_is_counted_not_dropped(tmp_path):
    reference = write_fasta(tmp_path / "ref.fa", {"1": CONTIG})
    built = design(reference, [Allele("17", 30, "A", "C", "GENE|1")], k=K, probes=3)
    assert built.pairs == ()
    assert built.skipped["contig_not_in_reference"] == 1


def test_an_insertion_gets_pairs_that_each_span_the_inserted_bases(tmp_path):
    """VCF spells an insertion with the preceding base repeated on both sides as an anchor,
    so a window that stops at that anchor spells both haplotypes identically. The offset
    range accounts for it rather than producing probes that discriminate nothing."""
    reference = write_fasta(tmp_path / "ref.fa", {"1": CONTIG})
    assert CONTIG[29:32] == "CTT", "fixture assumption: the anchor base and what follows"
    built = design(
        reference, [Allele("1", 30, CONTIG[29], CONTIG[29] + "GG", "GENE|1")], k=K, probes=3
    )
    assert len(built.pairs) == 3
    for pair in built.pairs:
        assert pair.ref_kmer != pair.alt_kmer


def test_an_insertion_that_repeats_what_follows_it_loses_the_edge_window(tmp_path):
    """Inserting TT immediately before TT leaves the leftmost window reading the same on
    both haplotypes — a real ambiguity in the data, not a defect. It is refused and counted,
    so the allele is reported with two probes rather than three agreeing ones, and H024's
    "all probes agree" is evaluated on probes that could have disagreed."""
    reference = write_fasta(tmp_path / "ref.fa", {"1": CONTIG})
    built = design(
        reference, [Allele("1", 30, CONTIG[29], CONTIG[29] + "TT", "GENE|1")], k=K, probes=3
    )
    assert len(built.pairs) == 2
    assert built.skipped["ref_equals_alt"] == 1


def test_a_window_whose_two_spellings_coincide_is_not_a_probe(tmp_path):
    """An indel inside a homopolymer can spell the alternate exactly as the reference reads.
    Such a window discriminates nothing and is refused rather than counted as agreement."""
    contig = "ACGT" + "A" * 20 + "CGTACGTACGTACGTACGT"
    reference = write_fasta(tmp_path / "ref.fa", {"1": contig})
    built = design(reference, [Allele("1", 10, "AA", "A", "GENE|1")], k=K, probes=3)
    assert built.skipped.get("ref_equals_alt", 0) >= 1


def test_a_window_containing_n_is_refused(tmp_path):
    reference = write_fasta(tmp_path / "ref.fa", {"1": "ACGT" + "N" * 10 + CONTIG})
    built = design(reference, [Allele("1", 8, "N", "A", "GENE|1")], k=K, probes=3)
    assert built.pairs == ()
    assert built.skipped["window_off_contig_or_n"] == 3


def _counts(built: Design, reference) -> dict[int, int]:
    values = built.kmers()
    bait = Bait.of(values, k=K)
    occurrence = uniqueness.count_in_genome(reference, bait)
    return occurrence_map(built, occurrence.counts)


def test_a_true_alternate_kmer_is_absent_from_the_reference_and_its_partner_occurs_once(
    tmp_path,
):
    reference = write_fasta(tmp_path / "ref.fa", {"1": CONTIG})
    built = design(reference, [Allele("1", 30, CONTIG[29], "A", "GENE|1")], k=K, probes=3)
    counts = _counts(built, reference)
    for pair in built.pairs:
        assert counts[pair.alt_kmer] == 0
        assert counts[pair.ref_kmer] == 1
    kept, report = unique_only(built, counts)
    assert len(kept.pairs) == len(built.pairs)
    assert "alt_kmer_occurs_in_reference" not in report


def test_an_alternate_kmer_that_already_exists_elsewhere_is_dropped(tmp_path):
    """The alternate is the spelling being counted in the reads. If it already occurs in
    the genome, reads from that other place are counted as this allele being present —
    which is exactly the failure step 2's witness set had, filtering on the reference side.
    """
    built = Design(
        alleles=(Allele("1", 30, "C", "A", "GENE|1"),),
        pairs=(ProbePair(allele=0, offset=0, ref_kmer=11, alt_kmer=22),),
        skipped={},
    )
    kept, report = unique_only(built, {11: 1, 22: 3})
    assert kept.pairs == ()
    assert report["alt_kmer_occurs_in_reference"] == 1


def test_a_reference_kmer_that_is_not_unique_is_dropped(tmp_path):
    built = Design(
        alleles=(Allele("1", 30, "C", "A", "GENE|1"),),
        pairs=(ProbePair(allele=0, offset=0, ref_kmer=11, alt_kmer=22),),
        skipped={},
    )
    kept, report = unique_only(built, {11: 4, 22: 0})
    assert kept.pairs == ()
    assert report["ref_kmer_not_unique"] == 1


def test_counts_per_allele_reports_the_zeros_too(tmp_path):
    built = Design(
        alleles=(Allele("1", 1, "C", "A", "A|1"), Allele("1", 9, "C", "A", "B|1")),
        pairs=(ProbePair(allele=0, offset=0, ref_kmer=11, alt_kmer=22),),
        skipped={},
    )
    assert list(built.counts_per_allele()) == [1, 0]


def test_the_uniqueness_input_holds_both_sides_of_every_pair(tmp_path):
    built = Design(
        alleles=(Allele("1", 1, "C", "A", "A|1"),),
        pairs=(ProbePair(allele=0, offset=0, ref_kmer=11, alt_kmer=22),),
        skipped={},
    )
    assert sorted(built.kmers().tolist()) == [11, 22]


def test_stream_alleles_reads_sql_shaped_rows():
    rows = [("1", 30, "C", "A", "GENE|1")]
    assert list(stream_alleles(rows)) == [Allele("1", 30, "C", "A", "GENE|1")]


@pytest.mark.parametrize("probes", [1, 2, 3, 5])
def test_the_requested_number_of_windows_is_produced_where_the_contig_allows(tmp_path, probes):
    reference = write_fasta(tmp_path / "ref.fa", {"1": CONTIG})
    built = design(reference, [Allele("1", 30, CONTIG[29], "A", "GENE|1")], k=K, probes=probes)
    assert len(built.pairs) == probes
