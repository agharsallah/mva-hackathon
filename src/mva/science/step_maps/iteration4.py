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
        status="open",
        track="track1",
        # Drawn into figures/it4/, not the per-step convention directory: one renderer
        # writes them all at once (tools/render_it4_figures.py). Entry 129 drew the first
        # twelve; commit 2dc82d0 added the coverage matrix, and run it4-5e25dd45eee2 the
        # ESM2 and GPN-MSA histograms.
        figures=(
            "figures/it4/score-histogram-alphamissense.svg",
            "figures/it4/score-histogram-alphamissense.html",
            "figures/it4/score-histogram-esm1b.svg",
            "figures/it4/score-histogram-esm1b.html",
            "figures/it4/score-histogram-revel.svg",
            "figures/it4/score-histogram-revel.html",
            "figures/it4/score-histogram-spliceai.svg",
            "figures/it4/score-histogram-spliceai.html",
            "figures/it4/score-histogram-esm2.svg",
            "figures/it4/score-histogram-esm2.html",
            "figures/it4/score-histogram-gpnmsa.svg",
            "figures/it4/score-histogram-gpnmsa.html",
            "figures/it4/coverage-matrix.svg",
            "figures/it4/coverage-matrix.html",
            "figures/it4/agreement-matrix.svg",
            "figures/it4/agreement-matrix.html",
            "figures/it4/confirmed-rank.svg",
            "figures/it4/confirmed-rank.html",
        ),
    ),
    Step(
        slug="step-6",
        title="The merged report",
        goal=(
            "Do the models agree, and what does the merged report conclude under each of "
            "the three merge methods?"
        ),
        iteration="iteration4",
        status="done",
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
        # Entry 142 settled both walk claims (P4-11, P4-12). The GNN half was skipped by
        # the user's decision of 2026-09-23, so nothing is pending: the step is closed.
        status="done",
        track="track2",
        # Drawn into figures/it4/ by tools/render_track2_walk_figures.py (T2 of the close-out).
        figures=("figures/it4/track2-walk-overlap.svg",),
    ),
    Step(
        slug="step-8",
        title="The GPU tier on Modal",
        goal=(
            "Do the roster's GPU models (NT-v2, Evo 2, ESM-C, Boltz-2), run on Modal behind "
            "one HTTP contract and a $50 cap, score the confirmed pair's alleles the laptop "
            "lanes abstain on — and does adding them move the consensus rank?"
        ),
        iteration="iteration4",
        # Opened 2026-09-23 on the user's request for wave 5 (plan §7b, B1–B2): one Modal
        # app per model, sequence windows and allele ids only, every GPU second in a ledger.
        # Entries 143-148 ran it; H078, H079, H081 and H082 are undecided by their own terms.
        status="open",
        track="track1",
        figures=(
            "figures/it4/step8-consensus-ablation.svg",
            "figures/it4/esmc-vs-esm2.svg",
            "figures/it4/boltz2-plddt-profile.svg",
            "figures/it4/boltz2-local-delta.svg",
            "figures/it4/boltz2-ca-trace.svg",
        ),
    ),
    Step(
        slug="step-9",
        title="Track 2 — one mechanism, many independent sources",
        goal=(
            "Does the mechanism class of the child's BUB1B alleles, checked against sources "
            "that share nothing (a structure atlas, mouse phenotypes, expression signatures, "
            "cell-line screens, the child's own pharmacogenome, phenotype-specific safety), "
            "support each drug direction — and which approved candidates survive all of them?"
        ),
        iteration="iteration4",
        # Opened 2026-09-24 on the user's request for creative Track 2 experiments (E1-E10,
        # plan in docs/iteration4/step-9/README.md), graded on the panel's four criteria.
        # Every experiment writes a submission note under step-9/submission-notes/ so the
        # final Track 2 submission is assembled from them, not rewritten.
        status="open",
        track="track2",
        figures=(
            "figures/it4/step9-e1-atlas.svg",
            "figures/it4/step9-e1-distribution.svg",
            "figures/it4/step9-e1-roc.svg",
            "figures/it4/step9-e2-rank.svg",
            "figures/it4/step9-e2-terms.svg",
            "figures/it4/step9-e2-controls.svg",
            "figures/it4/step9-e4-effects.svg",
            "figures/it4/step9-e4-background.svg",
            "figures/it4/step9-e4-coverage.svg",
            "figures/it4/step9-e3-engines.svg",
            "figures/it4/step9-e3-control.svg",
            "figures/it4/step9-e56-evidence.svg",
            "figures/it4/step9-e56-baserate.svg",
            "figures/it4/step9-e56-coverage.svg",
        ),
    ),
    Step(
        slug="step-10",
        title="Track 2 — iteration 4's own answer",
        goal=(
            "From iteration 4's evidence alone, which approved drugs do its independent "
            "generators (the PrimeKG walk, the phenotype twin, a screen-wide PRISM sweep, "
            "LINCS signature reversal) converge on beyond chance, and which of those survive "
            "every iteration-4 check (mechanism direction, the child's own safety, a decoy)?"
        ),
        iteration="iteration4",
        # Opened 2026-09-25 on the user's request for a Track 2 submission built from
        # iteration 4 only (submissions/track2/iteration-4/). Steps 7 and 9 tested drugs
        # drawn from iteration 2's shortlist; this step generates its own candidate set and
        # re-runs the checks on it. E7 (grading D5) is answered here, not in step 9.
        status="open",
        track="track2",
        figures=(
            "figures/it4/step10-s1-volcano.svg",
            "figures/it4/step10-s1-percentiles.svg",
            "figures/it4/step10-s1-funnel.svg",
        ),
    ),
)
