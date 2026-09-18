"""Iteration 2, step 6 — what the fused ranking says, as SQL over the loaded rows.

Four questions, one derivation each, and each one argues back at the fusion rather than
summarising it:

``it2_fusion_matrix``     routes × leading pairs: where did each instrument actually put
                          each candidate, and where is a cell just the "absent" default?
``it2_fusion_stability``  does the leader survive every single-route removal, and does it
                          survive re-weighting by measured error rates? (H042)
``it2_fusion_evidence``   how many *disjoint inputs* speak for each pair once routes sharing
                          a source are collapsed, and which input is missing? (H043)
``it2_fusion_reach``      how far down the fused ranking do the symptom-nominated genes and
                          their matched decoys sit — the fusion's own decoy null

**The decoy set goes through the identical SQL**, as in every step since 3. A fused ranking
that cannot be told apart from one built on matched controls has resolved nothing, and the
only way to know is to score the controls the same way.

**A rank is not a probability.** Reciprocal rank fusion produces an ordering from orderings;
it carries no calibration and none is implied. Everywhere one of these numbers is quoted, the
sentence says which routes were in it and what carried it.
"""

from .derivation import RESULT, Derivation

__all__ = [
    "IT2_FUSION_DERIVATIONS",
    "IT2_FUSION_EVIDENCE",
    "IT2_FUSION_MATRIX",
    "IT2_FUSION_REACH",
    "IT2_FUSION_STABILITY",
]

#: How many fused rows the matrix and the reach tables look at. The head of the ranking is
#: what the step's claims are about; the frozen file keeps every row regardless.
TOP = 20


IT2_FUSION_MATRIX = Derivation(
    name="it2_fusion_matrix",
    question=(
        "For each leading pair, where did each route put it, and is that cell a real "
        "opinion or the rank-51 default a route gives everything it never listed?"
    ),
    reads_loaded=("it2_fusion_scores", "it2_fusion_ranks", "it2_fusion_routes"),
    sql=f"""
    WITH leaders AS (
        SELECT pair_id, gene, fused_rank, rrf_score, independent_evidence,
               is_target, is_decoy, tier
        FROM {RESULT}.it2_fusion_scores
        WHERE fused_rank <= {TOP}
    ),
    cells AS (
        SELECT l.pair_id, l.gene, l.fused_rank, r.route, r.unit, r.admitted,
               k.rank AS route_rank, k.inherited
        FROM leaders l
        CROSS JOIN {RESULT}.it2_fusion_routes r
        LEFT JOIN {RESULT}.it2_fusion_ranks k
               ON k.pair_id = l.pair_id AND k.route = r.route
    )
    SELECT c.pair_id,
           c.gene,
           c.fused_rank,
           c.route,
           c.unit,
           c.admitted,
           -- A route that never listed the pair has no rank row at all. It is reported as
           -- the pre-registered default rather than as a null, because "absent from my top
           -- 50" is a statement the route made and a blank cell is not.
           coalesce(c.route_rank, 51)          AS route_rank,
           c.route_rank IS NULL                AS defaulted,
           coalesce(c.inherited, false)        AS inherited,
           l.independent_evidence,
           l.is_target,
           l.is_decoy,
           l.tier
    FROM cells c
    JOIN leaders l ON l.pair_id = c.pair_id
    ORDER BY c.fused_rank, c.pair_id, c.route
    """,
)


IT2_FUSION_STABILITY = Derivation(
    name="it2_fusion_stability",
    question=(
        "Does any single route carry the result? For each admitted route, where does the "
        "all-routes leader land once that route is silenced, and what takes its place? (H042)"
    ),
    reads_loaded=("it2_fusion_loo", "it2_fusion_scores", "it2_fusion_routes"),
    sql=f"""
    WITH leader AS (
        SELECT pair_id, gene FROM {RESULT}.it2_fusion_scores WHERE fused_rank = 1 LIMIT 1
    ),
    per_route AS (
        SELECT o.removed,
               min(o.fused_rank) FILTER (o.pair_id = (SELECT pair_id FROM leader))
                   AS leader_rank,
               count(*) FILTER (o.fused_rank = 1)               AS pairs_at_rank_one,
               count(DISTINCT o.gene) FILTER (o.fused_rank = 1) AS genes_at_rank_one,
               min(o.gene) FILTER (o.fused_rank = 1)            AS a_new_leader_gene
        FROM {RESULT}.it2_fusion_loo o
        GROUP BY o.removed
    )
    SELECT p.removed,
           r.unit,
           r.statistic,
           p.leader_rank,
           -- The claim is about rank 1, so the boolean is stated rather than left to a
           -- reader comparing two integers. NULL leader_rank means the leader fell outside
           -- the exported top 20 entirely, which is a harder failure than a rank change.
           coalesce(p.leader_rank = 1, false) AS leader_kept_rank_one,
           p.pairs_at_rank_one,
           p.genes_at_rank_one,
           p.a_new_leader_gene
    FROM per_route p
    LEFT JOIN {RESULT}.it2_fusion_routes r ON r.route = p.removed
    ORDER BY coalesce(p.leader_rank, 999) DESC, p.removed
    """,
)


IT2_FUSION_EVIDENCE = Derivation(
    name="it2_fusion_evidence",
    question=(
        "How many disjoint inputs speak for each leading pair once routes sharing a source "
        "are collapsed, and which of the four is missing? (H043)"
    ),
    reads_loaded=("it2_fusion_scores",),
    sql=f"""
    SELECT fused_rank,
           pair_id,
           gene,
           independent_evidence,
           inputs,
           -- Named one by one rather than left inside a comma-joined string: the exhibit
           -- needs to show *which* witness is absent, and "3 of 4" does not say that.
           inputs LIKE '%hpo%'        AS has_hpo,
           inputs LIKE '%vcf%'        AS has_vcf,
           inputs LIKE '%reads%'      AS has_reads,
           inputs LIKE '%literature%' AS has_literature,
           read_confirmed,
           single_copy,
           no_cn_loss,
           read_confirmed AND single_copy AND no_cn_loss AS confirmation_complete,
           is_target,
           is_decoy,
           tier,
           unphaseable
    FROM {RESULT}.it2_fusion_scores
    WHERE fused_rank <= {TOP}
    ORDER BY fused_rank, pair_id
    """,
)


IT2_FUSION_REACH = Derivation(
    name="it2_fusion_reach",
    question=(
        "Does the fused ranking separate the symptom-nominated genes from their matched "
        "decoys, or does it put a control gene in its own top 20?"
    ),
    reads_loaded=("it2_fusion_scores",),
    sql=f"""
    WITH classed AS (
        SELECT CASE
                   WHEN is_target THEN 'target'
                   WHEN is_decoy  THEN 'decoy'
                   ELSE 'neither'
               END AS class,
               fused_rank,
               gene,
               rank_sensitivity
        FROM {RESULT}.it2_fusion_scores
    )
    SELECT class,
           count(*)                                        AS pairs,
           count(DISTINCT gene)                            AS genes,
           min(fused_rank)                                 AS best_rank,
           median(fused_rank)                              AS median_rank,
           count(*) FILTER (fused_rank <= {TOP})           AS pairs_in_top,
           count(DISTINCT gene) FILTER (fused_rank <= {TOP}) AS genes_in_top,
           -- The same question under measured-error-rate weights. If a class only reaches
           -- the top under equal weights, the equal-weight result is the artefact.
           count(*) FILTER (rank_sensitivity <= {TOP})     AS pairs_in_top_sensitivity
    FROM classed
    GROUP BY class
    ORDER BY best_rank
    """,
)


IT2_FUSION_DERIVATIONS: tuple[Derivation, ...] = (
    IT2_FUSION_MATRIX,
    IT2_FUSION_STABILITY,
    IT2_FUSION_EVIDENCE,
    IT2_FUSION_REACH,
)
