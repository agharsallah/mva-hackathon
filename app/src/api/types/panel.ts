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

/** One exon of the canonical transcript, numbered 1..n in *transcript* order. */
export interface Exon {
  /** Transcript-order number. On the minus strand exon 1 is the highest coordinate. */
  n: number;
  start: number;
  end: number;
  id: string | null;
}

/** One protein domain from Pfam / SMART / PROSITE / Gene3D / SUPERFAMILY / CDD / PRINTS. */
export interface ProteinDomain {
  source: string;
  accession: string | null;
  /** The database's description, falling back to the accession when it has none. */
  name: string;
  start_aa: number;
  end_aa: number;
  interpro: string | null;
}

/**
 * One protein-altering allele in the gene, placed in *amino-acid* space.
 *
 * Deliberately carries **no genomic coordinate**: the locus tracks already show those,
 * and keeping them out means this payload (unlike `/api/panel/locus`) holds nothing
 * patient-identifying. `protein_pos` is null whenever VEP put no amino-acid offset on
 * the canonical transcript, and `reason` then says why — never dropped silently.
 */
export interface GeneCandidate {
  consequence: string;
  impact: VariantImpact | null;
  rsid: string | null;
  /** gnomAD AF below the recessive threshold, or absent from gnomAD altogether. */
  rare: boolean;
  clin_sig: string | null;
  gt: string | null;
  filter: string | null;
  /** Short human handle: `"missense · rs1801516"`. */
  label: string;
  protein_pos: number | null;
  reason: string | null;
}

/**
 * GET /api/panel/gene-structure?gene=… — one gene's anatomy, from Ensembl REST.
 *
 * Static reference data, disk-cached server-side (`?refresh=true` rebuilds). The browser
 * never calls Ensembl itself. A 502 means Ensembl was unreachable — there is no fallback
 * shape, because an invented gene structure is worse than a missing one.
 */
export interface GeneStructure {
  gene: string;
  ensembl_id: string;
  /** Bare contig, the way the callset spells it (`"15"`, not `"chr15"`). */
  chrom: string;
  start: number;
  end: number;
  /** `1` = forward, `-1` = reverse. */
  strand: number;
  biotype: string | null;
  /** Canonical transcript id, unversioned. Domains and `protein_pos` are both on it. */
  transcript: string | null;
  protein: string | null;
  protein_length: number | null;
  exons: Exon[];
  domains: ProteinDomain[];
  candidates: GeneCandidate[];
}

/**
 * One heterozygous PASS ALT allele inside a panel gene — a *member* of the gene's
 * compound-heterozygous pair grid, not a pair.
 *
 * A `1/2` multi-allelic record contributes **two** rows, distinguished by `allele_ix`:
 * one copy of each ALT means one per haplotype, which is compound heterozygosity proven
 * by the genotype alone.
 *
 * `pgt` / `pid` are Sentieon's physical phasing, carried raw so a client can check the
 * server's verdict. `pid` names the read-backed island a variant belongs to and `pgt`
 * which haplotype inside it; both are **null** on the ~85 % of records phasing never
 * reached, and that is "unphased", not a missing measurement.
 *
 * `annotated` false means VEP never saw this allele, and then every annotation-derived
 * field is **null** — never `false`, which would read as "measured and not rare".
 *
 * Real patient coordinates at runtime; never persisted (the fixture is synthetic).
 */
export interface PanelHetVariant {
  gene: string;
  /** Bare contig, the way the callset spells it (`"15"`, not `"chr15"`). */
  chrom: string;
  pos: number;
  ref: string;
  alt: string;
  /** Which ALT of the record this row is: 1 always, 2 for the second allele of a `1/2`. */
  allele_ix: number;
  gt: string;
  qual: number | null;
  dp: number | null;
  /** This allele's depth over the record's total — defined per allele, so never null on `1/2`. */
  vaf: number | null;
  /** Phased genotype within the phase set, e.g. `"0|1"`. Null = unphased. */
  pgt: string | null;
  /** Phase-set id: two variants sharing it were seen on the same reads. Null = unphased. */
  pid: string | null;
  rsid: string | null;
  consequence: string | null;
  impact: VariantImpact | null;
  gnomad_af: number | null;
  gnomad_af_grpmax: number | null;
  clin_sig: string | null;
  annotated: boolean;
  is_rare_recessive: boolean | null;
  is_protein_altering: boolean | null;
}

/**
 * One cell of the pair matrix that phasing actually resolves. `i` and `j` index
 * `PanelHetPairs.variants` in the order it arrives (position order), which is both axes.
 * Every pair *not* listed is unknown — the common case by a wide margin.
 */
export interface PanelHetPair {
  i: number;
  j: number;
  /** `trans` = opposite copies (a real compound het); `cis` = same copy (excluded). */
  phase: 'trans' | 'cis';
  /** True when the two alleles are the two ALTs of one `1/2` record — trans by genotype. */
  auto: boolean;
}

/** How much of the grid the callset resolves. `pct_unknown` is null when there are no pairs. */
export interface PanelHetPairSummary {
  n_het: number;
  n_pairs: number;
  n_trans: number;
  n_auto_trans: number;
  n_cis: number;
  n_unknown: number;
  pct_unknown: number | null;
}

/** GET /api/panel/het-pairs?gene=… — one gene's compound-het pair matrix. */
export interface PanelHetPairs {
  gene: string;
  variants: PanelHetVariant[];
  pairs: PanelHetPair[];
  summary: PanelHetPairSummary;
}
