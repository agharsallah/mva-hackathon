"""Iteration 4's step map — the model zoo (``docs/iteration4/plan.md``).

Part of :mod:`mva.science.steps`, which owns the API; this module only holds the map.
"""

from ..step import PLATFORM, Step

__all__ = ["ITERATION4"]

#: Iteration 4 — the model zoo: every credible open variant-effect model run under one
#: contract (record → adapter → cache → rank → template → merge), with lineage, and a
#: merged report that no single model produces. Nothing is trained. The plan is
#: ``docs/iteration4/plan.md``; the goals below are its §4 table. Declared 2026-09-18,
#: every research step ``planned``: a step opens when its first run files an entry.
ITERATION4: tuple[Step, ...] = (
    Step(
        slug="step-0",
        title="The platform",
        goal="Can the delivered bytes be trusted, stored without loss, and queried in SQL?",
        kind=PLATFORM,
        status="done",
        unblocks=("step-1", "step-2", "step-7"),
    ),
    Step(
        slug="step-1",
        title="The allele record",
        goal=(
            "Can every allele in scope be expressed as one normalized record that every "
            "model class can read — genomic change, transcript, protein change, DNA window, "
            "protein window — with lineage?"
        ),
        unblocks=("step-3",),
        iteration="iteration4",
        status="done",
        track="track1",
    ),
    Step(
        slug="step-2",
        title="The zoo registry",
        goal=(
            "Which open models are credible, runnable and licensed for this case, and what "
            "is each one's coverage of the record set?"
        ),
        unblocks=("step-3",),
        iteration="iteration4",
        status="done",
        track="track1",
    ),
    Step(
        slug="step-3",
        title="The inference API",
        goal=(
            "Can one batch inference API serve every model through the same contract, cache "
            "every score with provenance, and dispatch GPU work without sending more than a "
            "sequence window?"
        ),
        unblocks=("step-4",),
        iteration="iteration4",
        status="open",
        track="track1",
    ),
    Step(
        slug="step-4",
        title="The workflow DAG",
        goal=(
            "Does a checkpointed DAG run the whole zoo end-to-end, resumably, from one "
            "command — and what does it cost in wall-clock and dollars?"
        ),
        unblocks=("step-5",),
        iteration="iteration4",
        status="done",
        track="track1",
    ),
    Step(
        slug="step-5",
        title="The report per model",
        goal=(
            "Can one report template describe every model identically — coverage, "
            "distribution, the confirmed pair's rank and percentile, limitations — with an "
            "LLM writing only the interpretation?"
        ),
        unblocks=("step-6",),
        iteration="iteration4",
        track="track1",
    ),
    Step(
        slug="step-6",
        title="The merged report",
        goal=(
            "Do the models agree, and what does the merged report conclude under each of "
            "the three merge methods?"
        ),
        iteration="iteration4",
        track="track1",
    ),
    Step(
        slug="step-7",
        title="Track 2 — two engines, one graph",
        goal=(
            "Do a graph walk and a GNN over the same knowledge graph converge on the same "
            "approved drugs for the mechanism, and how does each rank against a decoy?"
        ),
        iteration="iteration4",
        track="track2",
    ),
)
