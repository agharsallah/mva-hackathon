"""Iteration 2's step map — the blind mirror of iteration 1.

Part of :mod:`mva.science.steps`, which owns the API; this module only holds the map.
"""

from ..step import PLATFORM, Step

__all__ = ["ITERATION2"]

#: Iteration 2 — the mirror of iteration 1, run blind: start from the raw reads, the VCF
#: and the eight HPO terms as if no candidate were known, and rediscover the pair by
#: routes that share no code with iteration 1. The plan is ``docs/iteration2/plan.md``;
#: the goals below are its §2 table.
ITERATION2: tuple[Step, ...] = (
    Step(
        slug="step-0",
        title="The platform",
        goal="Can the delivered bytes be trusted, stored without loss, and queried in SQL?",
        kind=PLATFORM,
        status="done",
        unblocks=("step-1",),
    ),
    Step(
        slug="step-1",
        title="The blind target set",
        goal=(
            "Which genes do the child's symptoms alone nominate — a target set chosen "
            "with the DNA never read?"
        ),
        # Done: all four claims (H012-H015) carry committed verdicts in entry 084, and
        # the full-population re-test of H012 is entry 091.
        status="done",
        unblocks=("step-2", "step-3", "step-4"),
        iteration="iteration2",
    ),
    Step(
        slug="step-2",
        title="Discover the alleles from the reads",
        goal=(
            "Which alleles do the raw reads carry in the target set, discovered without "
            "the vendor caller — small variants, structural variants, per-exon coverage, "
            "and read-backed phase?"
        ),
        # Done: the five claims filed for this step carry committed verdicts and the
        # step README records the completion audit.
        status="done",
        unblocks=("step-3", "step-6", "step-7"),
        iteration="iteration2",
    ),
    Step(
        slug="step-3",
        title="Alignment-free genotype and copy number",
        goal=(
            "Read without an aligner or a caller, are the discovered alleles at "
            "heterozygous multiplicity, is every target-gene exon at two copies, and "
            "which public ClinVar P/LP alleles are present at all?"
        ),
        # Done: six claims filed before the run, six settled - four refuted, two
        # supported. H027, the step's own headline, is one of the refutations and is
        # the most useful thing it produced.
        status="done",
        unblocks=("step-4", "step-6", "step-7"),
        iteration="iteration2",
    ),
    Step(
        slug="step-4",
        title="Likelihood-ratio ranking over the VCF",
        goal=(
            "Over every protein-coding gene in the VCF, with no hard filter, which "
            "biallelic pair has the highest posterior, and what is its P(trans)?"
        ),
        # Done: six claims filed before the run, six settled. The leader is the gene
        # step 1 nominated blind with the DNA unread; the margin claim is what failed,
        # and the runner-up is a gene nobody has ever curated a phenotype for.
        status="done",
        unblocks=("step-5", "step-6"),
        iteration="iteration2",
    ),
    Step(
        slug="step-5",
        title="Knowledge engine",
        goal=(
            "Does public knowledge — published alleles, case reports, protein-language "
            "models — nominate or corroborate a pair for this phenotype?"
        ),
        # Done: five claims filed before the first request, five settled. The route passed
        # both pre-registered conditions — it separates from matched decoys and it is not
        # citation volume — and its own top two genes are decoys, with the confirmed lead
        # at knowledge rank 293 of 815. Both facts go to step 6.
        status="done",
        unblocks=("step-6", "step-7"),
        iteration="iteration2",
    ),
    Step(
        slug="step-6",
        title="Fusion and unblinding",
        goal=(
            "Fused across steps 2-5 and then unblinded, does iteration 2 rediscover "
            "iteration 1's pair, and is a second upload informative?"
        ),
        # Done: four claims filed before the fusion ran, four settled. The blind route put
        # the same pair first -- and the leave-one-route-out table says one route carried
        # it, which is the half of the result the report has to lead with as well.
        status="done",
        unblocks=("step-7",),
        iteration="iteration2",
    ),
    Step(
        slug="step-7",
        title="Track 2 enrichment",
        goal=(
            "Which mechanism facts from steps 2-5 and 8 revise the Track 2 card, and "
            "what does the drug evidence say for each direction?"
        ),
        # Open, not done: the six claims filed for this step (H045-H050) carry committed
        # verdicts (methodology 110-113) and the card is at version 3, but the goal names
        # step 8's fact - the aneuploidy burden in the sample - and that is still unmeasured
        # (card fact F8). The step closes when step 8's row lands on the card.
        status="open",
        iteration="iteration2",
    ),
    Step(
        slug="step-8",
        title="The mosaic aneuploidy bound",
        goal=(
            "Is mosaic aneuploidy detectable in the sequenced sample with a statistic "
            "that has power, and what cell-fraction bound does the data set per "
            "chromosome?"
        ),
        unblocks=("step-7",),
        iteration="iteration2",
    ),
)
