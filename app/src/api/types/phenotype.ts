/**
 * The phenotype ranking: `/api/phenotype/*`.
 *
 * Every gene HPO curates, scored against the child's clinical features by a ranker that
 * reads two public ontology files and **never** the callset, the candidate panel, or a
 * variant. That independence is the whole value of these rows: the panel-first candidate
 * list cannot corroborate itself.
 *
 * Nothing here carries a genomic position. The ranking is over genes and ontology terms,
 * so unlike the panel locus routes there is no coordinate to withhold.
 */

/** One of the child's delivered HPO terms. */
export interface PhenotypeTerm {
  hpo_id: string;
  label: string;
  /** The clinical detail from the phenotype document. */
  note: string;
  /**
   * False for `HP:0200067` only — the parents' reproductive history, not a feature of the
   * child. Every ranker assumes each term describes the patient, so including it is a
   * modelling choice rather than a data entry.
   */
  proband: boolean;
  /** How rare the term is, in nats. Null when this HPO release curates no gene to it. */
  information_content: number | null;
}

/** One of the two readings of the delivered terms. */
export interface PhenotypeTermSet {
  name: string;
  size: number;
  rationale: string;
  ids: string[];
}

/** A feature a textbook would expect and the document does not list. Never scored. */
export interface AbsentFeature {
  hpo_id: string;
  label: string;
}

export interface PhenotypeTerms {
  terms: PhenotypeTerm[];
  sets: PhenotypeTermSet[];
  notably_absent: AbsentFeature[];
}

/** One gene's standing against a term set. */
export interface PhenotypeGene {
  gene: string;
  entrez_id: string | null;
  /** 1 = best match. */
  rank: number;
  /** Symmetric similarity over the best score this term set could achieve, in 0..1. */
  score: number;
  /** "Is each of the child's features explained by this gene?" — ignores the gene's others. */
  forward: number;
  /** "Is each of the gene's features present in the child?" — penalises heavy curation. */
  reverse: number;
  curated_terms: number;
  /** Which of the child's features matched most strongly. */
  best_term: string | null;
  /** The most informative term both descend from — where the match actually happened. */
  best_common_ancestor: string | null;
  best_ic: number | null;
  /** Marks a candidate-panel gene. Played no part in the ordering. */
  in_panel: boolean;
}

export interface PhenotypeRanking {
  term_set: string;
  /**
   * The denominator a rank is quoted against. Larger than `rows.length` and than `scored`,
   * because genes that scored zero carry no signal and are not written.
   */
  considered: number;
  scored: number;
  rows: PhenotypeGene[];
  panel: string[];
}

/** How one gene moved between the two term sets. */
export interface PhenotypeDeltaRow {
  gene: string;
  with_parental: number | null;
  proband_only: number | null;
  /** Places gained when the parental term was removed. Positive means it rose. */
  moved: number | null;
  /** False when this HPO release curates no features for the gene at all. */
  curated: boolean;
}

export interface PhenotypeDelta {
  parental_term: string;
  parental_label: string;
  considered: number;
  rows: PhenotypeDeltaRow[];
}

export interface PhenotypeGeneDetail {
  gene: string;
  in_panel: boolean;
  term_set: string;
  by_term_set: Record<string, PhenotypeGene>;
  delta: { with_parental: number | null; proband_only: number | null; moved: number | null };
}
