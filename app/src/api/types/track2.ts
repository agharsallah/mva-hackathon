/**
 * Track 2 — drug repurposing: `GET /api/track2`.
 *
 * One payload for the whole Track 2 report in progress. The **mechanism card**
 * (`ressources/track2/mechanism.json`) is the hand-off from Track 1: it names the gene, the
 * protein, the variant *classes* and the pathway, and it never carries a genomic position —
 * which is what makes every table below committable. Everything else is derived from it by
 * `mva-drugs snapshot` against seven public APIs, each table with a provenance manifest.
 *
 * The rows are deliberately raw: the TSV columns as the snapshot wrote them, so the page
 * renders what the tool produced rather than a shape this app fixed in advance.
 */

import type {
  AntiDirection,
  CardEvidenceLadder,
  DecoyCard,
  DecoyComparisonRow,
  DrugMechanismLiteratureRow,
  LadderRow,
  MeasuredFact,
  PediatricTrialRow,
  ShortlistRow,
  StandardOfCare,
  Track2EvidenceRow,
  TransferCard,
  TransferComparisonRow,
} from './track2-step7';

/** One of the two alleles, named by consequence class — never by position. */
export interface CardAllele {
  label: string;
  consequence: string;
  /** `17 of 23` — which exon, out of how many. A count, not a coordinate. */
  exon: string;
  clinvar: string | null;
  classification: string;
  /** What the class implies for the protein: a dead copy, or a partly working one. */
  reading: string;
}

/** A citation the card rests on. */
export interface CardLiterature {
  pmid: string;
  role: string;
}

export interface CardMechanism {
  /** Loss- versus gain-of-function, the methods form's question 15. */
  class: string;
  status: string;
  pathway: string;
  immediate_effect: string;
  /** The consequence chain, most immediate first. */
  downstream: string[];
  /** Why fully switching the protein off is not a therapeutic direction. */
  complete_loss: string;
  literature: CardLiterature[];
}

/** One therapeutic angle, with the genes it would act on. */
export interface RepurposingDirection {
  id: string;
  name: string;
  rationale: string;
  seed_targets: string[];
  /**
   * True when the direction is about the tumour the child already has. Only a context
   * direction may reach automated rungs 4 and 5, because those rest on a registered trial
   * in the tumour context — card v3 added the flag so the rule can be checked, not assumed.
   */
  context?: boolean;
}

export interface CardCase {
  proband_id: string;
  disease: string;
  omim_phenotype: string;
  orphanet: string;
  mondo: string;
  clinical_terms_source: string;
  hpo_terms: string[];
  /** The child's presenting malignancy — the clinical anchor for direction D4. */
  tumour_context: string;
  /** Card v3: the chemotherapy already given for that malignancy, and why it is set aside. */
  context_standard_of_care?: StandardOfCare;
}

export interface CardGene {
  symbol: string;
  ensembl_gene_id: string;
  canonical_transcript: string;
  uniprot: string;
  protein: string;
  hgnc_id: string;
}

export interface CardConstraints {
  eligibility: string;
  public_sources_only: boolean;
  sources: string[];
  /** Source → why it was not queried. DrugBank needs a licence. */
  not_used: Record<string, string>;
}

/** One revision of the card. Revised, never edited: the version is bumped and appended here. */
export interface CardHistory {
  version: number;
  date: string;
  change: string;
}

/** `ressources/track2/mechanism.json`, verbatim. */
export interface MechanismCard {
  version: number;
  case: CardCase;
  gene: CardGene;
  alleles: CardAllele[];
  mechanism: CardMechanism;
  repurposing_directions: RepurposingDirection[];
  constraints: CardConstraints;
  history: CardHistory[];
  /** Card v3, F1-F9: what iteration 2 measured, and what each measurement implies. */
  measured_facts?: MeasuredFact[];
  /** Card v3: the classes that would make things worse — the do-not table's source. */
  anti_directions?: AntiDirection[];
  /** Card v3: the five rungs, stated before any drug was looked up. */
  evidence_ladder?: CardEvidenceLadder;
}

/** One column of one snapshot table, with its plain-English meaning. */
export interface Track2Column {
  name: string;
  type: string;
  description: string;
}

/** One public API the snapshot read, as its manifest records it. */
export interface Track2Input {
  name: string;
  url: string;
  retrieved_at: string;
  /** Null where the API states no release — recorded as a gap rather than faked. */
  version: string | null;
  /** Roll-up digest over every cached reply body read from this API. */
  sha256: string;
}

/** One `ressources/track2/*.tsv`, joined to its provenance manifest. */
export interface Track2CatalogTable {
  /** The bare table name (`targets`), not schema-qualified. */
  table: string;
  path: string;
  rows: number;
  columns: Track2Column[];
  sha256: string;
  built_at: string;
  code_version: string;
  method: string;
  inputs: Track2Input[];
}

/** One gene in the expanded target set. */
export interface TargetRow {
  symbol: string;
  /** `seed` = named by the card; `pathway` = added by the Reactome expansion. */
  role: string;
  /** Which of the card's directions (D1-D4) this gene serves. Empty for a pathway-only gene. */
  direction_ids: string[];
  /** Reactome stable ids this gene participates in. */
  pathways: string[];
  uniprot: string;
}

/** One Reactome pathway the expansion walked. */
export interface PathwayRow {
  st_id: string;
  display_name: string;
  /** True when the name matched the expansion pattern, so its participants entered the set. */
  matched: boolean;
  n_participants: number;
}

/** One drug/target interaction. Not one drug: a molecule appears once per target. */
export interface CandidateRow {
  drug_name: string;
  drug_id: string;
  target_symbol: string;
  target_role: string;
  direction_ids: string[];
  /** Every public API that reported this pair: `opentargets`, `chembl`, `dgidb`. */
  source: string[];
  interaction_or_moa: string;
  action_type: string;
  /** Highest clinical phase in ChEMBL; 4 is market-approved. Null where unstated. */
  max_phase: number | null;
  approved: boolean;
  /** The openFDA generic name when an approved drug has a label; empty otherwise. */
  fda_label: string;
  pmids: string[];
  first_approval: string | number | null;
  /** ATC classification codes — the WHO drug class. */
  atc: string[];
}

/** One registered clinical study. */
export interface TrialRow {
  nct_id: string;
  title: string;
  phase: string;
  overall_status: string;
  conditions: string[];
  interventions: string[];
  start_date: string;
  study_type: string;
  /** The registry query that returned it — the provenance of the join. */
  query: string;
}

export interface LiteratureRow {
  pmid: string;
  title: string;
  journal: string;
  year: number | string;
  doi: string;
  query: string;
}

/** How many replies one API gave this build, and how many of them were live. */
export interface RequestCount {
  replies: number;
  live: number;
}

/** One query the snapshot ran against a registry or PubMed, and what it returned. */
export interface SourceQuery {
  /** What the query was derived from: `disease`, `candidate`, `gene`, `pathway`, `direction`. */
  family: string;
  label: string;
  query: string;
  hits: number;
  /** PubMed only: how many of the hits were kept (the retmax cap). */
  kept?: number;
}

/** `ressources/track2/snapshot.json` — the counts behind every number on the page. */
export interface Track2Summary {
  built_at: string;
  built_by: string;
  code_version: string;
  card: {
    path: string;
    version: number;
    gene: string;
    uniprot: string;
    disease: string;
    tumour_context: string;
    pathway: string;
    directions: { id: string; name: string; seed_targets: number }[];
  };
  retrieved_at: { from: string; to: string };
  rows: Record<string, number>;
  targets: { seed: number; pathway: number; total: number };
  pathways: { walked: number; matched: number; pattern: string };
  candidates: {
    total: number;
    approved: number;
    with_fda_label: number;
    by_source: Record<string, number>;
    distinct_drugs: number;
    distinct_approved_drugs: number;
  };
  requests: Record<string, RequestCount>;
  trial_queries: SourceQuery[];
  literature_queries: SourceQuery[];
}

/** A root this snapshot rests on. `card` is the hand-off, `api` a queried public service. */
export interface Track2Source {
  kind: 'card' | 'api' | 'submission' | 'table' | string;
  ref: string;
  version: string;
  sha256: string;
  note: string;
}

/** One recorded derivation edge — the same row shape as `/api/provenance/lineage`. */
export interface Track2LineageEdge {
  produced_at: string;
  target_schema: string;
  target_table: string;
  target_rows: number;
  source_kind: string;
  source_ref: string;
  source_version: string;
  source_sha256: string;
  transform: string;
  tool: string;
  notes: string;
  is_current: boolean;
}

/**
 * `available: false` means the warehouse was unreachable, so `edges` is empty for a reason
 * the page must state rather than render as "no lineage". `sources` survives it: the roots
 * are read off the provenance manifests on disk.
 */
export interface Track2Lineage {
  available: boolean;
  note: string;
  sources: Track2Source[];
  edges: Track2LineageEdge[];
}

/** One step-8 claim, as the research register holds it. */
export interface Track2RegisterEntry {
  hypothesis_id: string;
  step: string;
  status: string;
  /** A stated triage heuristic with its arithmetic printed — never a probability. */
  confidence: number | null;
  statement: string;
  prediction: string;
  refuted_by: string;
  revision: number;
}

/** A Track 1 iteration whose hypotheses the mechanism card cites. */
export interface LinkedIteration {
  track: string;
  number: number;
  folder: string;
  state: string;
  standing: string;
  /** The ids shared with the card — the actual link, not a folder reference. */
  hypotheses: string[];
}

/** `waiting` is the yellow state: blocked on an oracle reply, not merely unstarted. */
export type PhaseStatus = 'done' | 'open' | 'waiting';

export interface StrategyPhase {
  id: string;
  title: string;
  status: PhaseStatus;
  detail: string;
  depends_on: string[];
}

/** The strategy is a plain ordered list: phase *n* depends on the ids in `depends_on`. */
export type Track2Strategy = StrategyPhase[];

/** GET /api/track2 */
export interface Track2 {
  card: MechanismCard;
  catalog: Track2CatalogTable[];
  targets: TargetRow[];
  pathways: PathwayRow[];
  candidates: CandidateRow[];
  trials: TrialRow[];
  literature: LiteratureRow[];
  /**
   * The step-7 enrichment. Optional because a checkout that has never run
   * `tools/track2_enrich.py` has none of these TSVs and the route answers `[]`; every
   * consumer defaults them rather than assuming the enrichment ran.
   */
  evidence?: Track2EvidenceRow[];
  drug_mechanism_literature?: DrugMechanismLiteratureRow[];
  /** ~11k rows: aggregate per drug, never render the table. */
  pediatric_trials?: PediatricTrialRow[];
  evidence_ladder?: LadderRow[];
  shortlist?: ShortlistRow[];
  do_not?: ShortlistRow[];
  decoy_comparison?: DecoyComparisonRow[];
  decoys?: DecoyCard[];
  /**
   * The scalability evidence: the same pipeline on a different **case**, not a different
   * gene. Empty until `tools/track2_transfer.py` has run.
   */
  transfer_comparison?: TransferComparisonRow[];
  transfers?: TransferCard[];
  summary: Track2Summary;
  lineage: Track2Lineage;
  register: Track2RegisterEntry[];
  linked_iterations: LinkedIteration[];
  strategy: Track2Strategy;
}
