"""Iteration 2, step 4 — what the likelihood-ratio ranking says, as SQL over the loaded rows.

Four questions, one derivation each, and each is a claim's test rather than a summary:

``it2_lr_top_pairs``      which biallelic hypothesis leads, by how much, and what else is
                          within an order of magnitude of it? (H030, H031)
``it2_lr_target_decoy``   scored by the identical likelihood ratio, do the symptom-nominated
                          genes separate from their size-matched controls? (H034)
``it2_lr_uncurated``      does any gene with no curated phenotype — scored only through the
                          network-proximity lane — reach the top of the table? (H032)
``it2_lr_lane_coverage``  how many alleles could each lane score **at all**, which is the
                          number that says what the ranking was actually built from

**Every gene in the callset is in these tables.** There is no filter anywhere in the chain:
a gene is ordered low, never removed. That is what makes ``it2_lr_uncurated`` answerable and
what separates this step from iteration 1's funnel.

**The decoy set goes through the same SQL as the targets**, for the same reason it did in
step 3: H020 was refuted, targets and decoys carry a biallelic candidate at the same rate
before any filter, so the discriminating power has to be measured in the *filter* — and here
the filter is the likelihood ratio itself.

**A ratio is not a probability of causation.** These numbers order hypotheses; they are a
transparent product of pre-registered terms, not a calibrated posterior, and every place
that quotes one says so.
"""

from .derivation import RESULT, Derivation

__all__ = [
    "IT2_LR_DERIVATIONS",
    "IT2_LR_LANE_COVERAGE",
    "IT2_LR_TARGET_DECOY",
    "IT2_LR_TOP_PAIRS",
    "IT2_LR_UNCURATED",
]


IT2_LR_TOP_PAIRS = Derivation(
    name="it2_lr_top_pairs",
    question=(
        "Over every protein-coding gene in the VCF, with no hard filter, which biallelic "
        "hypothesis has the highest likelihood ratio, how far ahead of the runner-up gene "
        "is it, and what is its P(trans)? (H030, H031, H035)"
    ),
    reads_loaded=("it2_lr_pairs", "it2_ptrans"),
    sql=f"""
    WITH best AS (
        SELECT gene,
               arg_max(shape, combined_lr)          AS shape,
               arg_max(phase, combined_lr)          AS phase,
               arg_max(tier, combined_lr)           AS tier,
               arg_max(is_target, combined_lr)      AS is_target,
               arg_max(is_decoy, combined_lr)       AS is_decoy,
               arg_max(curated, combined_lr)        AS curated,
               arg_max(phenotype_rank, combined_lr) AS phenotype_rank,
               arg_max(baseline, combined_lr)       AS baseline,
               arg_max(unphaseable, combined_lr)    AS unphaseable,
               arg_max(biallelic_confirmed, combined_lr) AS biallelic_confirmed,
               arg_max(terms, combined_lr)          AS terms,
               max(combined_lr)                     AS combined_lr,
               count(*)                             AS hypotheses
        FROM {RESULT}.it2_lr_pairs
        GROUP BY gene
    ),
    ordered AS (
        SELECT *,
               row_number() OVER (ORDER BY combined_lr DESC, gene) AS gene_rank,
               max(combined_lr) OVER ()                            AS leader_lr
        FROM best
    )
    SELECT o.gene_rank,
           o.gene,
           o.shape,
           o.phase,
           o.tier,
           o.is_target,
           o.is_decoy,
           o.curated,
           o.phenotype_rank,
           o.hypotheses,
           o.combined_lr,
           o.baseline,
           o.unphaseable,
           o.biallelic_confirmed,
           round(o.leader_lr / nullif(o.combined_lr, 0), 3) AS behind_leader,
           (o.leader_lr / nullif(o.combined_lr, 0) < 10)    AS within_one_order,
           p.p_trans,
           p.state AS p_trans_state,
           o.terms
    FROM ordered o
    LEFT JOIN {RESULT}.it2_ptrans p ON p.gene = o.gene
    ORDER BY o.gene_rank
    """,
)


IT2_LR_TARGET_DECOY = Derivation(
    name="it2_lr_target_decoy",
    question=(
        "Scored by the identical likelihood ratio, do the symptom-nominated target genes "
        "separate from their size-matched decoys — and where does each group sit? (H034)"
    ),
    reads_loaded=("it2_lr_pairs",),
    sql=f"""
    WITH best AS (
        SELECT gene,
               any_value(tier)      AS tier,
               any_value(is_target) AS is_target,
               any_value(is_decoy)  AS is_decoy,
               any_value(curated)   AS curated,
               max(combined_lr)     AS combined_lr
        FROM {RESULT}.it2_lr_pairs
        GROUP BY gene
    ),
    labelled AS (
        SELECT CASE WHEN is_target THEN coalesce(nullif(tier, ''), 'target')
                    WHEN is_decoy  THEN 'decoy'
                    WHEN curated   THEN 'curated-other'
                    ELSE 'uncurated-other' END AS grouping,
               combined_lr
        FROM best
    )
    SELECT grouping,
           count(*)                                        AS genes,
           round(median(combined_lr), 4)                   AS median_lr,
           round(quantile_cont(combined_lr, 0.9), 4)       AS p90_lr,
           round(max(combined_lr), 4)                      AS max_lr,
           count(*) FILTER (combined_lr >= 100)            AS genes_over_100,
           count(*) FILTER (combined_lr >= 1000)           AS genes_over_1000
    FROM labelled
    GROUP BY grouping
    ORDER BY median_lr DESC
    """,
)


IT2_LR_UNCURATED = Derivation(
    name="it2_lr_uncurated",
    question=(
        "Does any gene the symptom ranker could not score at all — reachable only through "
        "the network-proximity lane — reach the top of the genome-wide table? (H032)"
    ),
    reads_loaded=("it2_lr_pairs",),
    sql=f"""
    WITH best AS (
        SELECT gene,
               any_value(curated)   AS curated,
               any_value(is_decoy)  AS is_decoy,
               arg_max(shape, combined_lr) AS shape,
               arg_max(terms, combined_lr) AS terms,
               max(combined_lr)     AS combined_lr
        FROM {RESULT}.it2_lr_pairs
        GROUP BY gene
    ),
    ordered AS (
        SELECT *, row_number() OVER (ORDER BY combined_lr DESC, gene) AS gene_rank
        FROM best
    )
    SELECT gene_rank,
           gene,
           shape,
           combined_lr,
           is_decoy,
           -- The network lane only ever fires for a gene with no curated phenotype, so its
           -- presence in the printed terms is the evidence that this row entered that way.
           terms LIKE '%network%' AS entered_by_network
    FROM ordered
    WHERE NOT curated
    ORDER BY gene_rank
    LIMIT 200
    """,
)


IT2_LR_LANE_COVERAGE = Derivation(
    name="it2_lr_lane_coverage",
    question=(
        "How many alleles could each calibrated lane score at all? A lane that answers for "
        "one allele in twenty is a lane the ranking barely used, whatever its calibration."
    ),
    reads_loaded=("it2_lr_pairs",),
    sql=f"""
    WITH sides AS (
        SELECT left_class AS lane_class, left_scored_by AS scored_by FROM {RESULT}.it2_lr_pairs
        UNION ALL
        SELECT right_class, right_scored_by FROM {RESULT}.it2_lr_pairs WHERE right_class <> ''
    )
    SELECT lane_class,
           coalesce(nullif(scored_by, ''), 'no lane spoke') AS scored_by,
           count(*)                                         AS allele_slots,
           round(100.0 * count(*) / sum(count(*)) OVER (), 2) AS percent
    FROM sides
    GROUP BY lane_class, scored_by
    ORDER BY allele_slots DESC
    """,
)


#: Registered in :data:`mva.warehouse.analysis.DERIVATIONS` so the runner, the CLI's
#: ``--only`` choices and the provenance page all pick them up without a second list.
IT2_LR_DERIVATIONS = (
    IT2_LR_TOP_PAIRS,
    IT2_LR_TARGET_DECOY,
    IT2_LR_UNCURATED,
    IT2_LR_LANE_COVERAGE,
)
