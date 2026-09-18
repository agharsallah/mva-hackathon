/**
 * Iteration 2 step 5 — what public knowledge says, and the two nulls that judge it.
 *
 * Its own file for the reason `step4.ts` has one: `/api/steps` carries the shared shape of
 * every step, and this payload is seven blocks plus four analysis summaries of its own.
 *
 * Two column families are deliberately never merged. `pmid_count` says *somebody published
 * about this variant*; `child_call` says *this child carries it*, measured by k-mer
 * multiplicity in step 3. Only the second is evidence about the patient.
 */

/** One gene in the knowledge ordering, beside the two baselines it has to beat. */
export interface Step5Leader {
  knowledge_rank: number;
  gene: string;
  knowledge_score: number;
  /** Matched terms of the best single paper found for this gene, 0–7. */
  best_terms_matched: number;
  /** How many of the child's seven terms the gene co-occurs with at all. */
  terms_with_any_paper: number;
  /** Alleles of this gene, carried by this child, that anyone has published about. */
  described_alleles: number;
  /** ClinVar pathogenic alleles step 3 typed as present in the reads. */
  carried_pathogenic: number;
  pubmed_count: number;
  citation_rank: number;
  lr_rank: number | null;
  is_target: boolean;
  is_decoy: boolean;
  curated: boolean;
}

/** Per gene, what the literature could and could not be asked about. */
export interface Step5Catalogue {
  gene: string;
  is_target: boolean;
  is_decoy: boolean;
  in_top_leaders: boolean;
  alleles: number;
  /** Alleles carrying a dbSNP identifier, so a literature index could answer at all. */
  queryable: number;
  /** Alleles with no identifier. Not "unpublished" — never asked. */
  unqueryable: number;
  described: number;
  most_cited_allele: number;
  carried_pathogenic: number;
}

/** One paper, and how much of the child's phenotype it covers alongside a gene. */
export interface Step5Anchor {
  gene: string;
  pmid: string;
  title: string;
  journal: string;
  year: string;
  terms_matched: number;
  terms_total: number;
  /** `Rhabdomyosarcoma; Short stature; …` — which searches returned this paper. */
  matched_terms: string;
  is_target: boolean;
  is_decoy: boolean;
  in_top_leaders: boolean;
  reaches_threshold: boolean;
}

/** One missense allele of a leading gene against the domain map and the structure. */
export interface Step5Residue {
  gene: string;
  gene_rank: number;
  uniprot: string;
  rsid: string;
  /** Inside an InterPro entry of type `domain` — the pre-registered test. */
  in_domain: boolean;
  /** Inside *any* InterPro entry, families and superfamilies included. */
  in_superfamily: boolean;
  domain_accession: string;
  domain_name: string;
  plddt: number | null;
  confident: boolean;
  /** Position along the protein, 0–1. A fraction, never a residue number. */
  fraction: number | null;
  am_class: string;
  am_agrees: boolean;
  all_three: boolean;
  note: string;
}

/** The InterPro map of one protein, as fractions of its length. */
export interface Step5Domain {
  gene: string;
  uniprot: string;
  protein_length: number;
  interpro: string;
  domain_name: string;
  entry_type: string;
  start_fraction: number;
  end_fraction: number;
}

/** Targets, decoys and the rest of the genome, scored by the identical queries. */
export interface Step5Group {
  grouping: string;
  genes: number;
  mean_score: number;
  median_score: number;
  max_score: number;
  genes_with_anchor: number;
  genes_with_published_allele: number;
  median_pubmed_count: number;
}

/** How far the knowledge ordering moves a gene from its citation-count position. */
export interface Step5Citation {
  gene: string;
  knowledge_rank: number;
  citation_rank: number;
  lr_rank: number | null;
  knowledge_score: number;
  pubmed_count: number;
  best_terms_matched: number;
  described_alleles: number;
  is_target: boolean;
  is_decoy: boolean;
  /** Positive = the literature promoted the gene above where its citations put it. */
  moved: number;
  distance: number;
}

export interface Step5Payload {
  leaders: Step5Leader[];
  catalogue: Step5Catalogue[];
  anchors: Step5Anchor[];
  protein: Step5Residue[];
  domains: Step5Domain[];
  groups: Step5Group[];
  citations: Step5Citation[];
  coverage: {
    genes?: number;
    alleles?: number;
    queryable?: number;
    unqueryable?: number;
    described?: number;
    clinvar_carried?: number;
    asked_litvar?: boolean;
    source?: string;
  };
  anchor_summary: {
    genes?: number;
    terms?: string[];
    searches?: number;
    anchor_rows?: number;
    min_terms_written?: number;
    genes_reaching_five_terms?: string[];
    source?: string;
  };
  protein_summary: {
    genes?: number;
    alleles?: number;
    resolved_residue?: number;
    in_domain?: number;
    in_superfamily?: number;
    confident?: number;
    all_three?: number;
    with_accession?: number;
    with_structure?: number;
    confident_plddt?: number;
    esm1b?: string;
    leader?: Step5Residue | null;
  };
  baselines: {
    genes?: number;
    term_weight?: number;
    pubmed_query?: string;
    separation?: {
      auc: number;
      low: number;
      high: number;
      targets: number;
      decoys: number;
      separates: boolean;
      verdict: string;
    };
    agreement?: {
      rho: number;
      overlap: number;
      k: number;
      knowledge_top: string[];
      citation_top: string[];
      /** How many genes share the score that decides entry to the top k. */
      tied_at_k?: number;
      reorders: boolean;
      verdict: string;
    };
    route?: { ranking_route: boolean; verdict: string };
  };
}
