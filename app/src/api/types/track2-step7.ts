/**
 * Track 2, step 7 — the enrichment tables and the mechanism card's version-3 blocks.
 *
 * The snapshot (`track2.ts`) answers *which drugs exist for these targets*. Step 7 answers
 * the next question: **how good is the evidence for each one, and how much of it would a
 * decoy gene have got for free**. Seven more TSVs, written by `tools/track2_enrich.py`,
 * typed by `mva.viz.track2_catalog_step7` and served on the same `/api/track2` payload.
 *
 * Two conventions run through every row here and are worth stating once.
 *
 * **A rung is a kind of evidence, not a score.** `rung` is the *highest test the drug
 * passed* — 5 approved with paediatric use, 4 a trial in a related indication, 3 an animal
 * model, 2 a cell model, 1 mechanism only. Two drugs on rung 2 are not equally good; the
 * `curated_pmids` and `proxy` fields beside the rung are what tells them apart.
 *
 * **Automated and curated are never merged silently.** `automated_rung` is what a program
 * can look up for any card (approval, label, trials) — which is exactly what a *decoy* card
 * also gets. `curated_rung` comes from a PMID a person read. Both are carried.
 *
 * Every field is optional-safe at the payload level rather than here: a checkout that has
 * never run the enrichment has no TSVs, so `Track2` declares these lists with `?` and the
 * page defaults them to `[]`.
 */

/** Integer columns arrive `null` when the TSV field was empty — unknown, not zero. */
type Count = number | null;

/** Boolean columns arrive `null` for an empty field, for the same reason. */
type Flag = boolean | null;

/**
 * One curated result: a paper a person read, attached to a drug and a direction.
 *
 * Named `Track2EvidenceRow` rather than `EvidenceRow` because the research register already
 * owns that name (`types/science.ts`) for a different thing — an observation filed against a
 * hypothesis — and the barrel re-exports both.
 */
export interface Track2EvidenceRow {
  drug_name: string;
  direction_id: string;
  rung: Count;
  /** `cell` or `in vivo` — what kind of experiment the paper reports. */
  model: string;
  pmid: string;
  target: string;
  /** What the paper showed, in one sentence written by a person. */
  claim: string;
  /** True when the result is for a same-axis compound, not this molecule. */
  proxy: Flag;
  /** The compound actually tested, when `proxy` is true. */
  proxy_of: string;
}

/** One PubMed count for one drug: how much has been written, never a rung. */
export interface DrugMechanismLiteratureRow {
  drug_name: string;
  /** `mechanism` (drug AND gene/pathway/disease) or `context` (drug AND tumour). */
  family: string;
  /** The PubMed query exactly as sent. */
  term: string;
  hits: Count;
  /** At most 10 ids, so the count can be opened. */
  pmids: string[];
}

/** One registered study of a drug that admits children — any indication, not only this one. */
export interface PediatricTrialRow {
  drug_name: string;
  nct_id: string;
  title: string;
  phase: string[];
  overall_status: string;
  conditions: string[];
  /** The registry's own words: `1 Year`, `6 Months`. Never parsed into a number. */
  min_age: string;
  max_age: string;
  /** The registry's age groups; `CHILD` is what the filter asked for. */
  std_ages: string[];
  query: string;
}

/** One drug on one direction, graded. The unit of the ladder matrix. */
export interface LadderRow {
  drug_name: string;
  /** `D1`-`D4`, or `pathway` for a drug attached only through expansion targets. */
  direction_id: string;
  rung: Count;
  rung_label: string;
  /** What approval, labels and trials alone gave it — what a decoy card would also get. */
  automated_rung: Count;
  /** What a PMID read by a person gave it, or null. */
  curated_rung: Count;
  approved: Flag;
  fda_label: Flag;
  /** The label carries a section 8.4 Pediatric Use. */
  pediatric_label: Flag;
  trial_in_context: Flag;
  pediatric_trial: Flag;
  mechanism_hits: Count;
  context_hits: Count;
  curated_pmids: string[];
  proxy: Flag;
  targets: string[];
  action_types: string[];
  /** `A1`/`A2` an anti-direction, `standard_of_care`, `curated_only`, `approval_unverified`. */
  flags: string[];
}

/** One row of the shortlist or of the do-not table — the same shape, different verdicts. */
export interface ShortlistRow {
  /** Position in the shortlist; null in the do-not table. */
  rank: Count;
  drug_name: string;
  direction_id: string;
  rung: Count;
  /**
   * Shortlist: `argue`, or `context trial only - not a mechanism finding`.
   * Do-not table: `do not`, `caution` or `standard of care`.
   */
  verdict: string;
  /** The ordering reasons, or the exclusion reason, in words. */
  why: string;
  /** Label section 8.4, a study admitting children, or `none found`. */
  pediatric_evidence: string;
  curated_pmids: string[];
  targets: string[];
  flags: string[];
}

/** One decoy card against one direction of the real card. The control, quantified. */
export interface DecoyComparisonRow {
  decoy: string;
  /** One of the real card's directions, `pathway`, or `all`. */
  direction_id: string;
  direction_approved: Count;
  decoy_approved: Count;
  shared: Count;
  /** `shared / union`, as a string: the TSV's own text, never re-rounded. */
  jaccard: string;
  shared_drugs: string[];
  decoy_with_context_trial: Count;
  decoy_with_fda_label: Count;
}

/** Why this gene was chosen as a control, and what of it is comparable. */
export interface DecoyMeta {
  control_for: string;
  template_card_version: number;
  /** The draw that picked it — a seeded query, not a hand-pick. */
  picked_by: string;
  pathway_pattern: string;
  /** Which stages may be compared at all: the automated ones. */
  comparable: string;
}

/** The counts a decoy's own snapshot reported. The page shows these, never its rows. */
export interface DecoySnapshot {
  built_at: string | null;
  rows: Record<string, number> | null;
  targets: { seed: number; pathway: number; total: number } | null;
  pathways: { walked: number; matched: number; pattern: string } | null;
  candidates: { total: number; approved: number; distinct_approved_drugs: number } | null;
}

/** One decoy: its card, its counts, nothing else. */
export interface DecoyCard {
  symbol: string;
  /** The decoy's `mechanism.json` — the real card's shape, minus the v3 blocks. */
  card: { decoy?: DecoyMeta; gene?: { symbol: string } } & Record<string, unknown>;
  snapshot: DecoySnapshot;
}

/* --- mechanism card, version 3 ------------------------------------------------------- */

/** One thing iteration 2 measured about the genotype, with what it implies for a drug. */
export interface MeasuredFact {
  /** `F1`-`F9`. */
  id: string;
  fact: string;
  /** The measurement in words — or, for F8, that it was never made. */
  value: string;
  /** The methodology entry that measured it. */
  source: string;
  step: string;
  implication: string;
}

/** A drug class the mechanism says would make things worse. */
export interface AntiDirection {
  /** `A1`, `A2`. */
  id: string;
  name: string;
  agents: string;
  why: string;
  /** `do not` or `caution`. */
  status: string;
  /** The mechanism-of-action regex the ladder flags rows with. */
  moa_pattern: string;
}

/** One rung of the ladder, as the card states it before any drug is looked up. */
export interface LadderRungDef {
  rung: number;
  label: string;
  test: string;
}

/** The ladder itself, pre-registered on the card. */
export interface CardEvidenceLadder {
  purpose: string;
  rungs: LadderRungDef[];
  rule: string;
}

/** The chemotherapy the child is already on — high rungs for free, and not a repurposing. */
export interface StandardOfCare {
  note: string;
  drugs: string[];
  source: string;
}
