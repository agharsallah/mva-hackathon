#!/usr/bin/env python3
"""What step 6 reads out of the warehouse: four routes, their orderings, and their receipts.

Step 6 fuses orderings it did not produce. Everything it needs therefore arrives through
this module as *ordered keys plus the measurement that admitted the route*, never as a score
to be re-interpreted. A route's rank is its own statement; step 6's job is to combine
statements and to say how much they overlap.

**Who ranks, and who only confirms** is decided in :mod:`it2_step6_routes`, from the
measurements this module loads. The split is the seam: here is what the warehouse says, there
is what step 6 is entitled to do about it.

**The pair identity is coordinate-free, and that costs something.** A pair is
``gene | left class:rsid | right class:rsid``. Two different variants of the same consequence
class in the same gene, at least one of them without a dbSNP identifier, share a spelling
once the position is removed; the collapse keeps the **best-scoring** representative and
records in ``collapsed_rows`` how many scored rows it stood for, so the loss is a column
rather than a silence. The run reports both counts. Positions stay in the database and
nothing here can write one.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mva.io.writers import write_json, write_tsv
from mva.knowledge.baselines import RouteWeight, weigh
from mva.pipeline import fusion
from mva.pipeline.fusion import Confirmation, Pair
from mva.pipeline.nulls import Separation, separation
from mva.viz.queries.access import fetch
from mva.warehouse.postgres import ALIAS
from mva.warehouse.settings import Postgres

__all__ = [
    "DEFAULT_OUT",
    "SEED",
    "allele_id",
    "confirmations",
    "knowledge_route",
    "likelihood_separation",
    "load",
    "permutation_null",
    "phenotype_order",
    "phenotype_recall",
    "rows",
    "scored_pairs",
    "settings",
    "write_json",
    "write_tsv",
]

DEFAULT_OUT = Path("build/it2/step-6")

#: Fixed so the bootstrap interval of a re-run reproduces. The date step 6 opened.
SEED = 20260918


def settings() -> Postgres:
    return Postgres.from_env()


def rows(sql: str) -> list[dict[str, Any]]:
    return fetch(settings(), sql)


def allele_id(consequence_class: str | None, rsid: str | None) -> str:
    """One side of a pair, named without a position.

    An allele with no dbSNP identifier keeps its class and an empty identifier rather than
    being dropped: the leading pair's missense side is exactly such an allele, and a scheme
    that could not name it would have deleted the case.
    """
    if not consequence_class:
        return ""
    return f"{consequence_class}:{rsid or ''}"


def scored_pairs() -> tuple[list[Pair], dict[str, dict[str, Any]]]:
    """Every biallelic hypothesis the ranking scored, collapsed to coordinate-free keys.

    Returns the pairs in ranked order (best first) and a lookup of what the warehouse says
    about each: its likelihood ratio, its shape, its phase, its tier, whether it is a target
    or a matched decoy, and how many scored rows the key stood for.
    """
    sql = f"""
        SELECT gene, shape, phase, tier, is_target, is_decoy, curated, reachable,
               unphaseable, biallelic_confirmed, phenotype_rank,
               left_class, left_rsid, right_class, right_rsid,
               combined_lr, lr_without_phenotype, posterior
        FROM {ALIAS}.results.it2_lr_pairs
        ORDER BY combined_lr DESC, gene
    """
    best: dict[str, dict[str, Any]] = {}
    order: list[Pair] = []
    for row in rows(sql):
        pair = Pair(
            gene=row["gene"],
            allele_a=allele_id(row["left_class"], row["left_rsid"]),
            allele_b=allele_id(row["right_class"], row["right_rsid"]),
        )
        held = best.get(pair.id)
        if held is None:
            row["collapsed_rows"] = 1
            best[pair.id] = row
            order.append(pair)
        else:
            held["collapsed_rows"] += 1
    return order, best


#: Where step 1 wrote its held-out recall curve. Read rather than retyped: the number that
#: weights the phenotype route is the same number entry 091 reports, or the run fails.
BENCHMARK = Path("build/it2/step-1/benchmark-full.json")

#: The cutoff the target set was drawn at, and therefore the cutoff its recall is quoted at.
RECALL_AT = 300


def phenotype_recall(path: Path = BENCHMARK, *, at: int = RECALL_AT) -> dict[str, Any]:
    """Step 1's measured held-out recall at ``at``, with its bootstrap interval.

    Refuses rather than defaults when the file is missing: a fusion that weighted the
    symptom route by a guessed recall would be exactly the "step-level band guessed now"
    the plan rules out.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"{path} is missing — run tools/render_it2_step1_figures.py's benchmark stage "
            "first; step 6 will not invent the recall it weights the phenotype route by"
        )
    curve = json.loads(path.read_text(encoding="utf-8"))["curve"]
    point = next((row for row in curve if int(row["n"]) == at), None)
    if point is None:
        raise ValueError(f"{path} has no recall at N = {at}; it has {[r['n'] for r in curve]}")
    low, high = point["interval"]
    return {"n": at, "recall": float(point["recall"]), "low": float(low), "high": float(high)}


def phenotype_order() -> list[str]:
    """The pure symptom-score ranking: gene symbols, best first.

    ``score_rank`` is the rank the symptom ranker produced with the DNA unread. It is the
    ordering the rediscovery claim is made on (§10 B1), which is why it is read here from the
    target table rather than recomputed from the tiers.
    """
    sql = f"""
        SELECT symbol FROM {ALIAS}.results.it2_targets
        WHERE score_rank IS NOT NULL
        ORDER BY score_rank, symbol
    """
    return [row["symbol"] for row in rows(sql)]


def knowledge_route() -> tuple[list[str] | None, RouteWeight | None]:
    """The knowledge ranking and step 5's own admission measurement, or ``(None, None)``.

    ``None`` is not an empty list: an empty ordering would say "the literature was asked and
    said nothing", a missing table says "it was not asked". Step 6 records the second as an
    unavailable route at weight 0, never as a silent zero.

    The admission test is step 5's, not step 6's: :func:`mva.knowledge.baselines.weigh`
    asks whether the score separates the symptom-nominated genes from their matched decoys
    **and** reorders a raw publication count. Both, or the route confirms rather than ranks.
    Step 6 calls that rule; restating it here would be a second copy able to disagree.
    """
    exists = rows(
        f"""
        SELECT 1 AS present FROM {ALIAS}.information_schema.tables
        WHERE table_schema = 'results' AND table_name = 'it2_knowledge_ranks'
        """
    )
    if not exists:
        return None, None
    scored = rows(
        f"""
        SELECT gene, knowledge_rank, knowledge_score, pubmed_count, is_target, is_decoy
        FROM {ALIAS}.results.it2_knowledge_ranks
        WHERE knowledge_rank IS NOT NULL
        ORDER BY knowledge_rank, gene
        """
    )
    weight = weigh(
        [float(r["knowledge_score"]) for r in scored if r["is_target"]],
        [float(r["knowledge_score"]) for r in scored if r["is_decoy"]],
        [(r["gene"], float(r["knowledge_score"])) for r in scored],
        [(r["gene"], float(r["pubmed_count"] or 0)) for r in scored],
        seed=SEED,
    )
    return [r["gene"] for r in scored], weight


def confirmations(pairs: list[Pair]) -> dict[str, Confirmation]:
    """The read route's three booleans, per pair, inherited from its gene.

    **Gene-level, and that is a limitation, not a shortcut.** The k-mer genotype table keys
    on ``(symbol, origin, allele_ordinal)`` and carries no dbSNP identifier, so it cannot be
    joined to one side of a pair. What it can answer is answered: does this gene carry a
    read-confirmed heterozygous allele, is it at single copy, and is no exon of it below the
    copy-number null band.
    """
    confirmed = {
        row["symbol"]: row
        for row in rows(
            f"""
            SELECT symbol, confirmed_het, confirmed_novel, biallelic_confirmed, reachable
            FROM {ALIAS}.results.it2_kmer_pairs
            """
        )
    }
    single_copy = {
        row["symbol"]: row["calls"]
        for row in rows(
            f"""
            SELECT symbol, count(*) AS calls
            FROM {ALIAS}.results.it2_kmer_genotypes
            WHERE call = 'het' AND posterior >= 0.95
            GROUP BY symbol
            """
        )
    }
    lost = {
        row["symbol"]
        for row in rows(
            f"""
            SELECT DISTINCT symbol FROM {ALIAS}.results.it2_exon_cn WHERE below_null_band
            """
        )
    }
    measured = set(confirmed)
    out: dict[str, Confirmation] = {}
    for pair in pairs:
        gene = pair.gene
        if gene not in measured:
            continue
        out[pair.id] = Confirmation(
            read_confirmed=bool(confirmed[gene]["confirmed_het"]),
            single_copy=single_copy.get(gene, 0) > 0,
            no_cn_loss=gene not in lost,
        )
    return out


def likelihood_separation(best: dict[str, dict[str, Any]]) -> Separation:
    """Does the likelihood route separate the symptom-nominated genes from matched decoys?

    Recomputed here from the same rows the fusion will rank, rather than quoted from step 4,
    so the number that admits the route and the number in the fused table cannot drift apart.
    One score per gene — its best pair — because a gene with many pairs would otherwise vote
    many times in its own admission test.
    """
    by_gene: dict[tuple[str, bool], float] = {}
    for row in best.values():
        if not (row["is_target"] or row["is_decoy"]):
            continue
        key = (row["gene"], bool(row["is_target"]))
        by_gene[key] = max(by_gene.get(key, 0.0), float(row["combined_lr"] or 0.0))
    positives = [value for (_, target), value in by_gene.items() if target]
    negatives = [value for (_, target), value in by_gene.items() if not target]
    return separation(positives, negatives, seed=SEED)


def permutation_null() -> dict[str, Any]:
    """Step 4's permutation null, read back: how many random symptom sets reach the leader.

    The fraction is the route's measured error rate and becomes its weight in the second
    sensitivity analysis — the plan's "measured error rates, not step-level bands".
    """
    (row,) = rows(
        f"""
        SELECT count(*) AS draws,
               count(*) FILTER (genes_above_observed > 0) AS reached
        FROM {ALIAS}.results.it2_lr_nulls
        """
    )
    draws = int(row["draws"] or 0)
    reached = int(row["reached"] or 0)
    p_value = (reached + 1) / (draws + 1) if draws else 1.0
    return {"draws": draws, "reached": reached, "p_value": p_value}


def load(top: int = fusion.TOP_N) -> dict[str, Any]:
    """Everything step 6 reads, in one call, so a stage cannot read half of it."""
    order, best = scored_pairs()
    knowledge, knowledge_weight = knowledge_route()
    return {
        "pairs": order,
        "best": best,
        "phenotype": phenotype_order(),
        "knowledge": knowledge,
        "knowledge_weight": knowledge_weight,
        "confirmations": confirmations(order),
        "separation": likelihood_separation(best),
        "null": permutation_null(),
        "recall": phenotype_recall(),
        "top": top,
    }
