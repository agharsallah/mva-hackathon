/** GET /api/panel/genes — the MVA candidate gene panel. */
export interface PanelGeneRow {
  gene: string;
  chrom: string;
  start: number;
  end: number;
  ensembl_id: string;
  note: string;
  n_all: number;
  n_pass: number;
  n_filtered: number;
  span_bp: number;
  variants_per_mb: number;
  pct_pass: number;
}

/**
 * GET /api/panel/constraint — one row per panel gene.
 *
 * Constraint is gnomAD's measure of how much loss-of-function a gene tolerates in the
 * healthy population. The source table is autosome-only, so `loeuf`, `pli`, `mis_z` and
 * `oe_lof` are nullable: **null means unknown, never "unconstrained"**.
 */
export interface PanelConstraintRow {
  gene: string;
  chrom: string;
  n_all: number;
  n_pass: number;
  /** Loss-of-function Observed/Expected upper bound Fraction. Lower = more intolerant. */
  loeuf: number | null;
  /** Probability of being LoF-intolerant, 0–1. */
  pli: number | null;
  /** Missense depletion z-score. */
  mis_z: number | null;
  /** Point estimate of observed/expected LoF. */
  oe_lof: number | null;
  lof_obs: number | null;
  lof_exp: number | null;
  clinvar_plp: number;
  clinvar_vus: number;
  clinvar_benign: number;
  ensembl_id: string;
  note: string;
}

/** VEP's coarse severity bucket for a consequence. */
export type VariantImpact = 'HIGH' | 'MODERATE' | 'LOW' | 'MODIFIER';

/**
 * GET /api/panel/annotations?gene=… — one row per annotated variant in the panel
 * (gene omitted = every panel row). Real patient coordinates at runtime; never persisted.
 *
 * `gnomad_af` null = the variant is absent from gnomAD (novel), which is not the same as
 * frequency zero. `vaf` is null on `1/2` multiallelic records.
 */
export interface PanelAnnotationRow {
  chrom: string;
  pos: number;
  ref: string;
  alt: string;
  rsid: string | null;
  /** null = intergenic — VEP found no gene for this record (the panel BED pads ±20 kb). */
  gene: string | null;
  consequence: string;
  impact: VariantImpact;
  gnomad_af: number | null;
  /** Highest AF across gnomAD's population groups — the number that matters for rarity. */
  gnomad_af_grpmax: number | null;
  clin_sig: string | null;
  qual: number | null;
  filter: string;
  gt: string;
  dp: number | null;
  vaf: number | null;
  is_rare_recessive: boolean;
  is_protein_altering: boolean;
}

/**
 * GET /api/panel/locus?gene=… — one row per variant record inside a gene.
 * These are real patient coordinates at runtime. Never persist them to a file
 * in this repo (the fixture uses obviously synthetic positions).
 */
export interface LocusVariant {
  pos: number;
  ref: string;
  alt: string;
  qual: number;
  filter: string;
  gt: string;
  dp: number | null;
  ad_ref: number | null;
  ad_alt: number | null;
  vaf: number | null;
  gq: number | null;
}
