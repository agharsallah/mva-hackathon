"""Iteration 2, step 5 — what public knowledge says, as SQL over the loaded rows.

Six questions, one derivation each, and three of them exist to argue against the other
three:

``it2_catalogue_overlap``     of the alleles this child carries, how many has anyone ever
                              published about - with the unqueryable ones counted, not
                              hidden? (H036)
``it2_anchor_match``          does any single paper discuss a leading gene alongside five
                              or more of the child's seven proband terms? (H037)
``it2_knowledge_separation``  scored by the identical queries, do the symptom-nominated
                              genes separate from their matched decoys? (H038)
``it2_knowledge_vs_citations``does the knowledge ordering differ from ranking the same
                              genes by publication count alone? (H039)
``it2_protein_agreement``     does the leading missense land in an annotated domain, in a
                              region the structure model is confident about, with
                              AlphaMissense agreeing? (H040)
``it2_knowledge_leaders``     the knowledge ordering itself, beside the step-4 rank, so the
                              two routes can be read against each other in step 6

**The decoy set goes through every one of these queries.** Step 2 measured targets and
decoys as indistinguishable before any filter, and step 4 measured a real separation once
the scoring was applied. A literature route that cannot repeat that has no ranking power,
and this is where that is decided rather than asserted.

**Citation volume is a baseline here, never an input.** ``it2_knowledge_ranks`` carries the
raw PubMed count as its own column precisely so the knowledge score can be compared with
it; nothing in the score is derived from it.

**A publication is not evidence about this child.** ``it2_pub_alleles`` keeps
``pmid_count`` (somebody wrote about this variant) and ``child_call`` (this child carries
it, by k-mer multiplicity with no aligner) in separate columns, and only the second is a
statement about the patient.
"""

from .derivation import RESULT, Derivation

__all__ = [
    "IT2_ANCHOR_MATCH",
    "IT2_CATALOGUE_OVERLAP",
    "IT2_KNOWLEDGE_DERIVATIONS",
    "IT2_KNOWLEDGE_LEADERS",
    "IT2_KNOWLEDGE_SEPARATION",
    "IT2_KNOWLEDGE_VS_CITATIONS",
    "IT2_PROTEIN_AGREEMENT",
]

#: Matched terms a paper needs before it counts as a case-report anchor. Pre-registered in
#: H037 as "five or more of the child's seven proband terms" and written once here.
ANCHOR_TERMS = 5


IT2_CATALOGUE_OVERLAP = Derivation(
    name="it2_catalogue_overlap",
    question=(
        "Per gene, how many of the alleles this child carries has anyone published about, "
        "how many could not be looked up at all, and how many are ClinVar pathogenic "
        "alleles the child actually carries? (H036)"
    ),
    reads_loaded=("it2_pub_alleles",),
    sql=f"""
    SELECT gene,
           any_value(is_target)        AS is_target,
           any_value(is_decoy)         AS is_decoy,
           any_value(in_top_leaders)   AS in_top_leaders,
           count(*)                    AS alleles,
           -- An allele with no dbSNP identifier was never asked about. Counting it as
           -- "nobody published" would turn a gap in a public index into a finding.
           count(*) FILTER (WHERE pmid_count >= 0)  AS queryable,
           count(*) FILTER (WHERE pmid_count < 0)   AS unqueryable,
           count(*) FILTER (WHERE pmid_count > 0)   AS described,
           coalesce(max(pmid_count), 0)             AS most_cited_allele,
           count(*) FILTER (
               WHERE child_call IN ('het', 'hom-alt') AND lower(clin_sig) LIKE '%pathogenic%'
           )                                        AS carried_pathogenic
    FROM {RESULT}.it2_pub_alleles
    GROUP BY gene
    ORDER BY carried_pathogenic DESC, described DESC, gene
    """,
)


IT2_ANCHOR_MATCH = Derivation(
    name="it2_anchor_match",
    question=(
        "Does any single published paper discuss a candidate gene alongside five or more "
        "of the child's seven proband terms, and which gene produced it? (H037)"
    ),
    reads_loaded=("it2_anchors",),
    sql=f"""
    SELECT gene,
           pmid,
           title,
           journal,
           year,
           terms_matched,
           terms_total,
           matched_terms,
           is_target,
           is_decoy,
           in_top_leaders,
           (terms_matched >= {ANCHOR_TERMS}) AS reaches_threshold
    FROM {RESULT}.it2_anchors
    WHERE terms_matched >= 2
    ORDER BY terms_matched DESC, in_top_leaders DESC, gene, pmid
    """,
)


IT2_KNOWLEDGE_SEPARATION = Derivation(
    name="it2_knowledge_separation",
    question=(
        "Scored by the identical literature queries, where do the symptom-nominated "
        "target genes sit against their size-matched decoys? (H038)"
    ),
    reads_loaded=("it2_knowledge_ranks",),
    sql=f"""
    WITH labelled AS (
        SELECT CASE WHEN is_target THEN 'target'
                    WHEN is_decoy  THEN 'decoy'
                    WHEN curated   THEN 'curated-other'
                    ELSE 'uncurated-other' END AS grouping,
               knowledge_score,
               best_terms_matched,
               described_alleles,
               pubmed_count
        FROM {RESULT}.it2_knowledge_ranks
    )
    SELECT grouping,
           count(*)                                  AS genes,
           round(avg(knowledge_score), 4)            AS mean_score,
           median(knowledge_score)                   AS median_score,
           max(knowledge_score)                      AS max_score,
           count(*) FILTER (WHERE best_terms_matched >= {ANCHOR_TERMS}) AS genes_with_anchor,
           count(*) FILTER (WHERE described_alleles > 0) AS genes_with_published_allele,
           median(pubmed_count)                      AS median_pubmed_count
    FROM labelled
    GROUP BY grouping
    ORDER BY median_score DESC, grouping
    """,
)


IT2_KNOWLEDGE_VS_CITATIONS = Derivation(
    name="it2_knowledge_vs_citations",
    question=(
        "Gene by gene, how far does the knowledge ordering move a gene away from where a "
        "raw publication count alone would have put it? (H039)"
    ),
    reads_loaded=("it2_knowledge_ranks",),
    sql=f"""
    SELECT gene,
           knowledge_rank,
           citation_rank,
           lr_rank,
           knowledge_score,
           pubmed_count,
           best_terms_matched,
           described_alleles,
           is_target,
           is_decoy,
           citation_rank - knowledge_rank AS moved,
           abs(citation_rank - knowledge_rank) AS distance
    FROM {RESULT}.it2_knowledge_ranks
    ORDER BY knowledge_rank
    """,
)


IT2_PROTEIN_AGREEMENT = Derivation(
    name="it2_protein_agreement",
    question=(
        "For each missense allele of a leading pair: is it inside an annotated InterPro "
        "domain, is the structure model confident there, and does AlphaMissense agree? "
        "(H040)"
    ),
    reads_loaded=("it2_protein_residues",),
    sql=f"""
    SELECT gene,
           gene_rank,
           uniprot,
           rsid,
           consequence_class,
           in_domain,
           domain_accession,
           domain_name,
           plddt,
           confident,
           round(fraction, 4) AS fraction,
           am_class,
           am_agrees,
           -- All three conditions, kept separate so a refutation names the half that failed.
           (in_domain AND confident AND am_agrees) AS all_three,
           note
    FROM {RESULT}.it2_protein_residues
    ORDER BY gene_rank, gene, rsid
    """,
)


IT2_KNOWLEDGE_LEADERS = Derivation(
    name="it2_knowledge_leaders",
    question=(
        "Which genes does public knowledge put at the top, and where did the genome-wide "
        "likelihood ratio and the raw publication count put the same genes?"
    ),
    reads_loaded=("it2_knowledge_ranks", "it2_pub_alleles"),
    sql=f"""
    WITH carried AS (
        SELECT gene,
               count(*) FILTER (
                   WHERE child_call IN ('het', 'hom-alt')
                     AND lower(clin_sig) LIKE '%pathogenic%'
               ) AS carried_pathogenic
        FROM {RESULT}.it2_pub_alleles
        GROUP BY gene
    )
    SELECT r.knowledge_rank,
           r.gene,
           r.knowledge_score,
           r.best_terms_matched,
           r.terms_with_any_paper,
           r.described_alleles,
           coalesce(c.carried_pathogenic, 0) AS carried_pathogenic,
           r.pubmed_count,
           r.citation_rank,
           r.lr_rank,
           r.is_target,
           r.is_decoy,
           r.curated
    FROM {RESULT}.it2_knowledge_ranks r
    LEFT JOIN carried c ON c.gene = r.gene
    ORDER BY r.knowledge_rank
    """,
)


IT2_KNOWLEDGE_DERIVATIONS: tuple[Derivation, ...] = (
    IT2_CATALOGUE_OVERLAP,
    IT2_ANCHOR_MATCH,
    IT2_KNOWLEDGE_SEPARATION,
    IT2_KNOWLEDGE_VS_CITATIONS,
    IT2_PROTEIN_AGREEMENT,
    IT2_KNOWLEDGE_LEADERS,
)
