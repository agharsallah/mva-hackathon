"""Iteration 1's step map — the top-down route that produced submission 1. Frozen.

Part of :mod:`mva.science.steps`, which owns the API; this module only holds the map.
"""

from ..step import PLATFORM, Step

__all__ = ["ITERATION1"]

#: Iteration 1 — the top-down route that produced submission 1: trust the caller's VCF,
#: filter hard, check convergence. Frozen; kept importable so its record still resolves.
ITERATION1: tuple[Step, ...] = (
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
        title="Normalize the callset",
        goal=(
            "Does every variant in the callset have exactly one spelling, so that an "
            "exact-string-matching scorer can be trusted with an indel?"
        ),
        status="open",
        unblocks=("step-2", "step-4"),
        iteration="iteration1",
    ),
    Step(
        slug="step-2",
        title="Annotate the callset",
        goal=(
            "Which variants are rare enough and damaging enough to cause an ultra-rare "
            "recessive disease, and in which gene?"
        ),
        # Open, not planned: the eight-gene panel is annotated (VEP REST, step-0 entry 031)
        # and reduces to one BUB1B pair. The genome-wide pass has not run.
        status="open",
        unblocks=("step-3", "step-6"),
        iteration="iteration1",
    ),
    Step(
        slug="step-3",
        title="Rank by phenotype",
        goal=(
            "Does an unbiased genome-wide ranking driven by the child's HPO terms agree "
            "with the panel-first candidate list?"
        ),
        # Open, not planned: the ranking is built and has run. It needed neither step 1 nor
        # step 2 - ranking genes by symptoms reads no callset - so the dependency the
        # roadmap assumed turned out not to exist. See docs/iteration1/step-3/methodology/067.
        status="open",
        unblocks=("step-6",),
        iteration="iteration1",
    ),
    Step(
        slug="step-4",
        title="Mine the suppressed calls",
        goal=(
            "Is one of the two alleles hiding in a call the quality filters discarded, "
            "rather than absent from the sample?"
        ),
        # Open, not planned: the panel's non-PASS calls were mined in step-0 entry 049 and
        # held nothing rare and protein-altering. Genome-wide, the question is untested.
        status="open",
        unblocks=("step-6",),
        iteration="iteration1",
    ),
    Step(
        slug="step-5",
        title="Recover the second allele from the reads",
        goal=(
            "Is the missing allele a variant the caller could not emit at all — a "
            "structural variant, a deep intronic call, or a low-fraction mosaic?"
        ),
        unblocks=("step-6",),
        iteration="iteration1",
    ),
    Step(
        slug="step-6",
        title="Spend the oracle budget",
        goal=(
            "Which candidate pair does the scorer confirm, and what does each reply "
            "tell us that the next submission should exploit?"
        ),
        iteration="iteration1",
    ),
    Step(
        slug="step-7",
        title="Knowledge and literature",
        goal=(
            "Does public knowledge - published MVA cases, ClinVar, protein-model scores - "
            "name an allele or a pair the data-driven steps missed, or independently "
            "corroborate the one they found?"
        ),
        unblocks=("step-6",),
        iteration="iteration1",
    ),
    Step(
        slug="step-8",
        title="Track 2 - drug repurposing",
        # Opens for desk research in parallel with steps 1-7; its verdicts wait for the
        # pair step-6 confirms, because a mechanism argued from an unconfirmed allele is a
        # guess dressed as rigour.
        goal=(
            "Which market-approved drugs act on the mechanism the confirmed alleles imply, "
            "and how strong is the evidence for each?"
        ),
        iteration="iteration1",
    ),
)
