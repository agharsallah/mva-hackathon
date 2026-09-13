"""Iteration 2, step 3 — what the k-mer genotypes say, as SQL over the loaded tables.

Three questions, one derivation each, and each is a claim's test rather than a summary:

``it2_kmer_confirmation``  of the alleles step 2's callers reported, how many does an
                           instrument sharing neither the aligner nor the caller confirm —
                           split by whether the delivered callset had ever seen them? (H027)
``it2_kmer_reach``         does a gene the reachability gate excluded yield a confident
                           genotype anyway? (H029)
``it2_kmer_pairs``         which genes still carry two confirmed rare alleles once every
                           call has been through the second instrument, and does the decoy
                           set carry as many?

**The decoy set passes through identical rules.** H020 is refuted: with every allele scored,
targets and decoys carry a biallelic candidate at exactly the same rate. Step 3 must not
quietly re-import the assumption that a target-gene finding outweighs a decoy-gene one — it
does not, before the filter — so every rate here is reported for both and the SQL that
computes them is the same SQL.

**Every per-gene result carries reachability.** Entry 093 measured which genes the bait
reaches and the aligner could place reads in. An absence in a gene the gate excluded is not
a finding, and joining the flag here is what stops it being quoted as one.

**"Confirmed" is a narrow word and is used narrowly.** It means the k-mer model put at least
the posterior floor on the same class the caller spelled, with a full probe set. It does not
mean the allele is real, pathogenic, or in the gene the annotation says — only that two
instruments with no shared code agree about how many copies carry it.
"""

from .derivation import RESULT, Derivation

__all__ = ["IT2_KMER_CONFIRMATION", "IT2_KMER_DERIVATIONS", "IT2_KMER_PAIRS", "IT2_KMER_REACH"]


IT2_KMER_CONFIRMATION = Derivation(
    name="it2_kmer_confirmation",
    question=(
        "Of the alleles step 2's callers reported, how many does an alignment-free genotype "
        "confirm — and does the answer differ for the ones the delivered callset never "
        "reported? (H027)"
    ),
    reads_loaded=("it2_kmer_genotypes",),
    sql=f"""
    WITH called AS (
        SELECT *
        FROM {RESULT}.it2_kmer_genotypes
        WHERE caller_genotype <> ''
    )
    SELECT tier,
           novel,
           count(*) AS alleles,
           count(*) FILTER (probes >= 3) AS fully_probed,
           count(*) FILTER (call = 'no-call') AS no_call,
           count(*) FILTER (confirms_caller AND probes >= 3) AS confirmed,
           -- Numerator and denominator are both restricted to fully-probed alleles. A call
           -- made on one probe cannot show disagreement, so it is not evidence either way;
           -- letting it into the numerator alone would let the rate exceed 1.
           round(
               count(*) FILTER (confirms_caller AND probes >= 3) * 1.0
               / nullif(count(*) FILTER (probes >= 3), 0), 6
           ) AS confirmed_fraction,
           count(*) FILTER (NOT reachable) AS in_unreachable_gene,
           round(avg(posterior), 6) AS mean_posterior
    FROM called
    GROUP BY tier, novel
    ORDER BY novel, tier
    """,
)


IT2_KMER_REACH = Derivation(
    name="it2_kmer_reach",
    question=(
        "Do genes the stage-0 reachability gate excluded yield confident k-mer genotypes "
        "anyway — is the limit real or conservative? (H029)"
    ),
    reads_loaded=("it2_kmer_genotypes", "it2_mapq_profile"),
    sql=f"""
    SELECT m.reachable,
           m.sparse_bait,
           m.mapq_refused,
           count(DISTINCT m.symbol) AS genes,
           count(g.symbol) AS alleles,
           count(g.symbol) FILTER (g.call <> 'no-call') AS confident_calls,
           count(g.symbol) FILTER (g.call <> 'no-call' AND g.probes_agreeing = g.probes)
               AS confident_and_unanimous,
           round(
               count(g.symbol) FILTER (g.call <> 'no-call') * 1.0
               / nullif(count(g.symbol), 0), 6
           ) AS confident_fraction
    FROM {RESULT}.it2_mapq_profile m
    LEFT JOIN {RESULT}.it2_kmer_genotypes g ON g.symbol = m.symbol
    GROUP BY m.reachable, m.sparse_bait, m.mapq_refused
    ORDER BY m.reachable DESC, m.sparse_bait, m.mapq_refused
    """,
)


IT2_KMER_PAIRS = Derivation(
    name="it2_kmer_pairs",
    question=(
        "Once every call has been through the second instrument, which genes still carry "
        "two confirmed heterozygous alleles — and does the decoy set carry as many?"
    ),
    reads_loaded=("it2_kmer_genotypes", "it2_mapq_profile"),
    sql=f"""
    WITH confirmed AS (
        SELECT symbol, tier, novel
        FROM {RESULT}.it2_kmer_genotypes
        WHERE call = 'het'
          AND probes >= 3
          AND probes_agreeing = probes
          AND caller_genotype <> ''
          AND confirms_caller
    ),
    per_gene AS (
        SELECT symbol,
               any_value(tier) AS tier,
               count(*) AS confirmed_het,
               count(*) FILTER (novel) AS confirmed_novel
        FROM confirmed
        GROUP BY symbol
    )
    SELECT m.symbol,
           m.tier,
           m.reachable,
           m.bait_density,
           coalesce(p.confirmed_het, 0) AS confirmed_het,
           coalesce(p.confirmed_novel, 0) AS confirmed_novel,
           (coalesce(p.confirmed_het, 0) >= 2) AS biallelic_confirmed
    FROM {RESULT}.it2_mapq_profile m
    LEFT JOIN per_gene p ON p.symbol = m.symbol
    ORDER BY biallelic_confirmed DESC, confirmed_het DESC, m.symbol
    """,
)


#: Registered in :data:`mva.warehouse.analysis.DERIVATIONS` so the runner, the CLI's
#: ``--only`` choices and the provenance page all pick them up without a second list.
IT2_KMER_DERIVATIONS = (IT2_KMER_CONFIRMATION, IT2_KMER_REACH, IT2_KMER_PAIRS)
