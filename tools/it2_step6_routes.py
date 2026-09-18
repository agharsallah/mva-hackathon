"""Who is allowed to vote, with what weight, and which route read whose output.

Three decisions live here, and all three are made from measurements the earlier steps already
published rather than from a judgement taken at fusion time:

* **admission** — a route may rank only if it separates its targets from matched decoys and
  reorders a trivial baseline. That conjunction is ``RouteWeight.ranking_route`` in
  :mod:`mva.knowledge.baselines`, written by step 5; this module calls it instead of
  restating it, because a second copy of a rule is a second copy able to disagree.
* **the read route** — measured recall 0.905 and measured discrimination **0** (entries 087,
  090). ``plan.md`` §11.6 pre-registered it as a **confirmation route at weight 0** before any
  of this ran. It is still loaded, still exported and still drawn, at weight 0, because the
  measurement that disqualified it is a result.
* **the dependency graph** — declared, not derived. A graph read out of the code would only
  ever say what the code does; the claim being audited is what each route *read*.
"""

from __future__ import annotations

from typing import Any

from mva.knowledge.baselines import RouteWeight
from mva.pipeline.fusion import Route
from mva.pipeline.nulls import Separation

__all__ = ["EDGES", "routes", "sensitivity_weights"]


#: The route-dependency graph, declared rather than inferred: a graph derived from the code
#: would only ever say what the code does, and the claim being audited is what each route
#: *read*. ``shared_input`` marks an edge where two routes consumed the same raw source —
#: those are the edges the independent-evidence count collapses.
EDGES: tuple[dict[str, Any], ...] = (
    {
        "source": "hpo",
        "target": "phenotype",
        "consumed": "the eight clinical terms, ranked against the HPO corpus",
        "shared_input": True,
    },
    {
        "source": "hpo",
        "target": "likelihood",
        "consumed": "the same eight terms, as the phenotype lane of the likelihood ratio",
        "shared_input": True,
    },
    {
        "source": "vcf",
        "target": "likelihood",
        "consumed": "5.0 M delivered records, every protein-coding gene, no hard filter",
        "shared_input": True,
    },
    {
        "source": "vcf",
        "target": "knowledge",
        "consumed": "which alleles and dbSNP identifiers to ask the literature about",
        "shared_input": True,
    },
    {
        "source": "literature",
        "target": "knowledge",
        "consumed": "LitVar 2.0, PubTator 3.0, ClinVar, InterPro, AlphaFold",
        "shared_input": False,
    },
    {
        "source": "reads",
        "target": "confirmation",
        "consumed": "14.7 M baited reads: alleles, k-mer multiplicity, per-exon copy number",
        "shared_input": False,
    },
    {
        "source": "likelihood",
        "target": "knowledge",
        "consumed": "the top-20 gene list the catalogue and the anchors were built around",
        "shared_input": False,
    },
    {
        "source": "confirmation",
        "target": "likelihood",
        "consumed": "biallelic_confirmed, as one lane among many — not a filter",
        "shared_input": False,
    },
)


def routes(
    *,
    recall: dict[str, Any],
    lr: Separation,
    null: dict[str, Any],
    knowledge: list[str] | None,
    knowledge_weight: RouteWeight | None,
) -> list[Route]:
    """The four routes with their admission decisions, each carrying the reason in words."""
    admitted_lr = lr.separates
    return [
        Route(
            name="phenotype",
            unit="gene",
            admitted=True,
            weight=1.0,
            inputs=("hpo",),
            reason=(
                f"orders every curated gene from the symptoms alone; held-out recall@300 "
                f"{recall['recall']:.3f} [{recall['low']:.3f}, {recall['high']:.3f}] "
                f"(entry 091) — an enrichment, never coverage"
            ),
        ),
        Route(
            name="likelihood",
            unit="pair",
            admitted=admitted_lr,
            weight=1.0 if admitted_lr else 0.0,
            inputs=("hpo", "vcf"),
            reason=(
                f"target-vs-decoy {lr.verdict}; permutation p = {null['p_value']:.3f} "
                f"({null['reached']} of {null['draws']} random term sets reach the leader)"
            ),
        ),
        Route(
            name="knowledge",
            unit="gene",
            admitted=bool(knowledge_weight and knowledge_weight.ranking_route),
            weight=1.0 if knowledge_weight and knowledge_weight.ranking_route else 0.0,
            inputs=("literature", "vcf"),
            reason=(
                knowledge_weight.verdict
                if knowledge_weight is not None
                else "step 5 has not loaded results.it2_knowledge_ranks: not asked, not zero"
            ),
        ),
        Route(
            name="confirmation",
            unit="allele",
            admitted=False,
            weight=0.0,
            inputs=("reads",),
            reason=(
                "measured recall 0.905 [0.815, 0.974] and measured discrimination 0 "
                "(10 of 396 targets against 10 of 396 decoys, Fisher p = 0.589, entry 090): "
                "finds almost everything, orders nothing — pre-registered as confirmation "
                "in plan.md §11.6 before this ran"
            ),
        ),
    ]


def sensitivity_weights(
    *, recall: dict[str, Any], null: dict[str, Any], knowledge_auc: float | None
) -> dict[str, float]:
    """The second weighting: each route's own measured error rate, never a band guessed now."""
    return {
        "phenotype": round(float(recall["recall"]), 4),
        "likelihood": round(1.0 - float(null["p_value"]), 4),
        "knowledge": round(knowledge_auc, 4) if knowledge_auc is not None else 0.0,
        "confirmation": 0.0,
    }
