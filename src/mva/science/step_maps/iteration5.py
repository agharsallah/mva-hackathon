"""Iteration 5's step map — allele-first Track 2 (``docs/iteration5/plan.md``).

Part of :mod:`mva.science.steps`, which owns the API; this module only holds the map.
"""

from ..step import PLATFORM, Step

__all__ = ["ITERATION5"]

#: Iteration 5 — start from the child's two alleles and the protein, not from the drug
#: databases. One exploratory step, no pre-registered claims (user decision 2026-09-25,
#: ``docs/iteration5/notes/exploratory-no-hypotheses.md``); every route carries its own
#: positive control instead. Declared 2026-09-25.
ITERATION5: tuple[Step, ...] = (
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
        title="Track 2 — allele-first therapy routes",
        goal=(
            "Starting from the child's two BUB1B alleles and the BubR1 protein, which "
            "therapeutic routes exist per allele (stop-codon readthrough, protein "
            "stabilisation, BubR1-raising interventions from protein-level data and the "
            "literature), each validated on a positive control, and which one should the "
            "treating team pursue given the one lab test that separates them?"
        ),
        iteration="iteration5",
        status="open",
        track="track2",
        # Drawn into figures/it5/, one renderer per route (tools/render_it5_r{1,2,3,4}.py)
        # plus tools/render_it5_s1.py for the transfer check (entries 161, 162).
        figures=(
            "figures/it5/r1-stop-anatomy.svg",
            "figures/it5/r1-control.svg",
            "figures/it5/r1-plus4.svg",
            "figures/it5/r1-dosage.svg",
            "figures/it5/r2-proliferation.svg",
            "figures/it5/r2-control.svg",
            "figures/it5/r2-hits.svg",
            "figures/it5/r3-extraction-funnel.svg",
            "figures/it5/r3-evidence-map.svg",
            "figures/it5/r3-mva-exposures.svg",
            "figures/it5/r4-decision-tree.svg",
            "figures/it5/r4-voi-curve.svg",
            "figures/it5/r4-heatmap.svg",
            "figures/it5/r4-tornado.svg",
            "figures/it5/s1-transfer.svg",
            "figures/it5/r5-cross-iteration.svg",
            "figures/it5/r6-pitch-overview.svg",
        ),
    ),
)
