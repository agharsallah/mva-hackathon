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
  /**
   * Whether this gene is in the annotated panel. False means `candidates` is empty because
   * no annotation was ever run for it — not because the proband has no alleles there.
   */
  in_panel: boolean;
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

/**
 * GET /api/panel/background — one row per panel gene, its numbers next to the background.
 *
 * A raw density or PASS share means nothing on its own; the reading is the *distance* from
 * what the surrounding sequence does. The background population is every 1 Mb window of
 * the callset (one window is one megabase, so a window's record count is a density), and
 * the distance is a **z-score**: standard deviations from that window distribution.
 *
 * Every `z_*` is nullable: **null means the background had no usable spread**, never zero.
 * A low `z_pass_*` is a **callability** statement — mappability, repeats, telomeric
 * sequence — and never a pathogenicity one.
 */
export interface PanelBackgroundRow {
  gene: string;
  /** `chr`-prefixed, as the panel delivers it. */
  chrom: string;
  n_all: number;
  n_pass: number;
  span_bp: number;
  gene_variants_per_mb: number;
  gene_pct_pass: number;
  contig_variants_per_mb: number;
  contig_pct_pass: number;
  genome_variants_per_mb: number;
  genome_pct_pass: number;
  contig_n_bins: number;
  contig_bin_mean_density: number;
  contig_bin_sd_density: number | null;
  contig_bin_mean_pct_pass: number | null;
  contig_bin_sd_pct_pass: number | null;
  genome_n_bins: number;
  genome_bin_mean_density: number;
  genome_bin_sd_density: number | null;
  genome_bin_mean_pct_pass: number | null;
  genome_bin_sd_pct_pass: number | null;
  z_density_vs_contig: number | null;
  z_density_vs_genome: number | null;
  z_pass_vs_contig: number | null;
  z_pass_vs_genome: number | null;
}

/**
 * One row of GET /api/panel/suppressed → `census`: a panel gene's records counted per
 * FILTER value, **PASS included**, so one gene's rows stack to its whole record count.
 *
 * `filter` is the caller's string verbatim. GATK packs every threshold a record tripped
 * into one `;`-joined value, so `"LowQual;QD2"` is a single record that failed two tests
 * — never two records, and never split into two reason rows.
 */
export interface PanelFilterCensusRow {
  gene: string;
  /** Bare contig, the way the callset spells it (`"15"`, not `"chr15"`). */
  chrom: string;
  filter: string;
  is_pass: boolean;
  n: number;
  /** Records in the gene at every FILTER value — the denominator, repeated per row. */
  n_gene_all: number;
  pct_of_gene: number;
}

/**
 * One suppressed (non-PASS) record inside a panel gene, from GET /api/panel/suppressed
 * → `records`. Real patient coordinates at runtime; never persisted (the fixture is
 * synthetic).
 *
 * A suppressed record is a call the caller **kept and flagged**, not one it deleted — so
 * every field here is measured evidence a reader can weigh against the flag. `vaf` is
 * null on a multi-allelic (`1/2`) record, where no single alternate owns the reads.
 *
 * `annotated` false means VEP never saw any alternate allele of this record, and then
 * every annotation field is **null** — absent, never "looked up and harmless".
 * `annotated_alt` names which alternate allele the annotation columns describe, because
 * a comma-packed record joins once, to its most severe annotated allele.
 */
export interface PanelSuppressedRecord {
  gene: string;
  chrom: string;
  pos: number;
  ref: string;
  /** Comma-packed on a multi-allelic record, exactly as the callset delivers it. */
  alt: string;
  qual: number | null;
  /** The FILTER value verbatim, `;`-joined where the record tripped several thresholds. */
  filter: string;
  gt: string;
  dp: number | null;
  /** Genotype quality: confidence in the genotype, as distinct from QUAL's "it varies". */
  gq: number | null;
  ad_ref: number | null;
  ad_alt: number | null;
  vaf: number | null;
  /** One copy of an alternate allele — the shape a hidden second allele would take. */
  is_het: boolean;
  annotated_alt: string | null;
  rsid: string | null;
  consequence: string | null;
  impact: VariantImpact | null;
  gnomad_af: number | null;
  gnomad_af_grpmax: number | null;
  clin_sig: string | null;
  annotated: boolean;
}

/**
 * GET /api/panel/suppressed?gene=… — the mining view over the calls the caller flagged.
 *
 * `census` is **always the whole panel** (the chart compares genes against each other);
 * `records` is narrowed to `gene` when one is given. An empty `records` for a real panel
 * gene is not an error — nothing suppressed there is the good outcome.
 */
export interface PanelSuppressed {
  gene: string | null;
  census: PanelFilterCensusRow[];
  records: PanelSuppressedRecord[];
}
