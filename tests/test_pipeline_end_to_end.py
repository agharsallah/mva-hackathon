"""End-to-end: a VCF in, a scored submission out.

This is the tracer that proves the seams connect. It runs entirely on the synthetic
fixture and a fabricated answer key, so it asserts the machinery works — never that we
have found the real variant.
"""

import io
from pathlib import Path

from mva.pipeline import (
    Annotation,
    DictAnnotator,
    Phase,
    Row,
    Variant,
    candidate_pairs,
    rank_pairs,
    read_calls,
    score,
    write_submission,
)

FIXTURE = Path(__file__).parent / "fixtures" / "mini.vcf"

TRANS_A = Variant("chr15", 40143000, "T", "C")
TRANS_B = Variant("chr15", 40143500, "G", "T")

# A pretend answer key. The trans pair the fixture encodes is the "causal" one.
PRETEND_TRUTH = frozenset({TRANS_A, TRANS_B})

ANNOTATOR = DictAnnotator(
    {
        TRANS_A: Annotation("BUB1B", "stop_gained", 0.0),
        TRANS_B: Annotation("BUB1B", "frameshift_variant", 0.0),
        Variant("chr15", 40142000, "C", "T"): Annotation("BUB1B", "missense_variant", 0.3),
        Variant("chr15", 40142100, "A", "G"): Annotation("BUB1B", "intron_variant", 0.3),
        Variant("chr15", 40144000, "A", "C"): Annotation("BUB1B", "missense_variant", 2e-4),
        Variant("chr15", 40144800, "C", "G"): Annotation("BUB1B", "missense_variant", 2e-4),
    }
)


def build_submission():
    calls = read_calls(FIXTURE)
    pairs = [p for p in candidate_pairs(calls) if p.is_compound_het_candidate]
    ranked = rank_pairs(
        [(p.left.variant, p.right.variant) for p in pairs],
        ANNOTATOR,
        gene_prior={"BUB1B": 2.0},
    )
    epcrs = [round(0.99 - i / 100, 2) for i in range(len(ranked[:10]))]
    return [
        Row(p.left, p.right, epcr=e, notes=f"{p.gene} biallelic candidate")
        for p, e in zip(ranked[:10], epcrs)
    ]


def test_the_cis_pair_never_reaches_the_submission():
    # 40142000/40142100 share a haplotype. Phase, not annotation, is what excludes them.
    submitted = {(r.variant.pos, r.partner.pos) for r in build_submission()}
    assert (40142000, 40142100) not in submitted


def test_the_pipeline_ranks_the_trans_damaging_pair_first():
    top = build_submission()[0]
    assert {top.variant, top.partner} == PRETEND_TRUTH


def test_the_emitted_submission_scores_a_perfect_result():
    rows = build_submission()
    result = score(rows, PRETEND_TRUTH)
    assert result.full_match_rank == 1
    assert result.rank_points == 100.0
    assert result.f_max == 1.0


def test_the_submission_survives_a_csv_round_trip():
    # The scorer reads a CSV, not our objects. Anything lost in serialisation is lost
    # for real, so the file itself is what gets validated.
    out = io.StringIO()
    write_submission(build_submission(), out)
    lines = out.getvalue().strip().split("\n")
    assert lines[0].startswith("proband_id,")
    assert all(line.startswith("PROBAND01,chr") for line in lines[1:])
    assert len(lines) - 1 <= 10


def test_every_pair_the_fixture_offers_is_accounted_for():
    phases = {p.phase for p in candidate_pairs(read_calls(FIXTURE))}
    assert phases == {Phase.CIS, Phase.TRANS, Phase.UNKNOWN}
