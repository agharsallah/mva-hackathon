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
        track="track1",
    ),
    Step(
        slug="step-2",
        title="Annotate the callset",
        goal=(
            "Which variants are rare enough and damaging enough to cause an ultra-rare "
            "recessive disease, and in which gene?"
        ),
        # Done: exit criterion met 2026-09-05 - the genome-wide coding scan ran and H004
        # (*no coding gene outranks the BUB1B pair*) is supported (entries 069, 070).
        # Non-coding annotation stayed open and was never opened before the freeze.
        status="done",
        unblocks=("step-3", "step-6"),
        iteration="iteration1",
        track="track1",
        figures=(
            "figures/track1/funnel.json",
            "figures/track1/track1-funnel.png",
        ),
    ),
    Step(
        slug="step-3",
        title="Rank by phenotype",
        goal=(
            "Does an unbiased genome-wide ranking driven by the child's HPO terms agree "
            "with the panel-first candidate list?"
        ),
        # Done: exit criterion met 2026-09-05 - the ranking is joined to the genome-wide
        # callset and H005 is supported (entries 067, 071). It needed neither step 1 nor
        # step 2 - ranking genes by symptoms reads no callset - so the dependency the
        # roadmap assumed turned out not to exist.
        status="done",
        unblocks=("step-6",),
        iteration="iteration1",
        track="track1",
        figures=("figures/track1/track1-gene-scatter.png",),
    ),
    Step(
        slug="step-4",
        title="Mine the suppressed calls",
        goal=(
            "Is one of the two alleles hiding in a call the quality filters discarded, "
            "rather than absent from the sample?"
        ),
        # Done: exit criterion met for coding calls 2026-09-05 - H006 (panel,
        # retrospective) and H007 (genome-wide coding) supported (entry 072).
        status="done",
        unblocks=("step-6",),
        iteration="iteration1",
        track="track1",
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
        track="track1",
    ),
    Step(
        slug="step-6",
        title="Spend the oracle budget",
        goal=(
            "Which candidate pair does the scorer confirm, and what does each reply "
            "tell us that the next submission should exploit?"
        ),
        # Done: designed and rehearsed 2026-09-05 (074), rows re-derived 2026-09-09 (082),
        # uploaded 2026-09-09 and answered - full match at rank 1, 100 rank points,
        # F-max 1.0 (083). H009 supported. 1 of 6 oracle submissions spent.
        status="done",
        iteration="iteration1",
        track="track1",
        figures=("figures/track1/track1-decode-table.png",),
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
        track="track1",
    ),
    Step(
        slug="step-8",
        title="Track 2 - drug repurposing",
        # Open: opened 2026-09-06 (entry 078) - the mechanism hand-off is written and the
        # drug data layer is built, but the iteration froze before any verdict was
        # committed. Its verdicts waited for the pair step-6 confirms, because a mechanism
        # argued from an unconfirmed allele is a guess dressed as rigour.
        status="open",
        goal=(
            "Which market-approved drugs act on the mechanism the confirmed alleles imply, "
            "and how strong is the evidence for each?"
        ),
        iteration="iteration1",
        track="track2",
    ),
)
