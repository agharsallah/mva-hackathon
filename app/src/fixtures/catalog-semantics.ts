import type { CatalogColumnRow } from '../api/types';

/**
 * FIXTURE — the semantics half of the catalogue: how each table is created, why it
 * exists, and what every column of it means.
 *
 * The live API resolves both from registries in `mva.viz.catalog_semantics` and
 * `mva.viz.catalog_columns`, keyed the same way this file is: a shared map for the
 * columns that recur across tables (`chrom`, `pos`, `ref`, `alt`, `sha256`…) and a
 * table-specific map that beats it. The fixture reproduces that resolution order rather
 * than flattening it, so the "one entry covers every table carrying this column"
 * behaviour is visible with no API running.
 *
 * Three gaps are deliberate and match what the contract can emit:
 * - `results.kmer_counts` has **no** `created_by` / `why` — a table written outside the
 *   warehouse build, which the registry does not know.
 * - `warehouse.vep_staging.raw_json` and `results.kmer_counts.hits` have **no** meaning.
 * - every other column resolves, most of them through the shared map.
 *
 * Sentences are shortened from the live registry; no genomic position appears here,
 * because a column meaning describes semantics, never a value.
 */

/** `table → [created_by, why]`, applied by `fixtures/catalog-tables.ts`. */
export const CREATION: Record<string, [string, string]> = {
  variants_raw: ['mva-warehouse vcf-ingest (replaces the table wholesale)', 'The lossless landing layer: every VCF field as text, so the original file can be rebuilt and checked against its digest.'],
  variant_samples: ['mva-warehouse pg-derive (rebuilt from scratch)', 'Splits the sample column into queryable genotype fields, so a call can be filtered on without string surgery.'],
  variant_info: ['mva-warehouse pg-derive (rebuilt from scratch)', 'Unpivots INFO so a key can be queried by name instead of parsed out of a packed string.'],
  contigs: ['mva-warehouse stage + pg-ingest', 'Gives every contig a length, without which a record count says nothing about density.'],
  bcftools_sn: ['mva-warehouse stage + pg-ingest', 'The callset’s headline counters, kept as the tool printed them so every derived number is traceable.'],
  bcftools_filter: ['mva-warehouse stage + pg-ingest', 'Records how much the caller suppressed, which is the first thing a quality review asks.'],
  bcftools_st: ['mva-warehouse stage + pg-ingest', 'The substitution spectrum, from which the Ts/Tv sanity check is computed.'],
  bcftools_idd: ['mva-warehouse stage + pg-ingest', 'The indel length spectrum, whose shape says whether the caller behaved.'],
  bcftools_dp: ['mva-warehouse stage + pg-ingest', 'The depth histogram — how well covered the genome actually is.'],
  panel_regions: ['mva-warehouse stage + pg-ingest', 'Makes "inside a candidate gene" a join condition rather than a judgement call.'],
  read_manifest: ['mva-reads convert (replaces the table wholesale)', 'One row per shard, so a query can read part of the read store instead of all of it.'],
  read_runs: ['mva-reads convert (replaces the table wholesale)', 'Says which instrument, flowcell and lane each delivered FASTQ came from.'],
  vep_staging: ['mva-warehouse annotate-panel (replaces the table wholesale)', 'Holds the annotator’s raw answer before it is projected into columns, so a re-parse never needs a second API call.'],
  gnomad_af_panel: ['loaded by hand before lineage recording existed', 'Supplies the population frequency the callset does not carry — its INFO/AF is within-sample.'],
  contig_density: ['mva-warehouse pg-derive (rebuilt from scratch)', 'How does variant density vary across the chromosomes?'],
  variant_density_bins: ['mva-warehouse pg-derive (rebuilt from scratch)', 'Where along each chromosome does variation and quality concentrate, at 1 Mb resolution?'],
  allele_balance_flags: ['mva-warehouse pg-derive (rebuilt from scratch)', 'Does any chromosome deviate from the 0.50 heterozygous balance a diploid genome should show?'],
  panel_gene_density: ['mva-warehouse pg-derive (rebuilt from scratch)', 'Which candidate gene carries the most variation per base sequenced?'],
  panel_candidates: ['mva-warehouse pg-derive (rebuilt from scratch)', 'For every annotated panel allele: the consequence and population frequency next to the genotype evidence the callset carries.'],
  panel_constraint: ['mva-warehouse pg-derive (rebuilt from scratch)', 'How badly do healthy people tolerate breaking each candidate gene, and what has ClinVar already classified there?'],
  qc_observed_expected: ['mva-warehouse pg-derive (rebuilt from scratch)', 'For every QC norm this callset can be measured against: the observed value, the published range, and a verdict.'],
  genotype_counts: ['mva-warehouse pg-derive (rebuilt from scratch)', 'The heterozygous/homozygous split, a standard check that the caller was not systematically wrong.'],
  filter_funnel: ['mva-warehouse pg-derive (rebuilt from scratch)', 'Which quality filters remove the most records?'],
  depth_distribution: ['mva-warehouse pg-derive (rebuilt from scratch)', 'How is per-record read depth distributed across the callset?'],
  substitution_spectrum: ['mva-warehouse pg-derive (rebuilt from scratch)', 'Which base substitutions dominate, and are they transitions?'],
  indel_lengths: ['mva-warehouse pg-derive (rebuilt from scratch)', 'How long are the insertions and deletions, and is the spectrum the expected decay?'],
  read_partitions: ['mva-warehouse pg-derive (rebuilt from scratch)', 'The read store’s shape, so a reader knows what a partition costs before opening one.'],
  cycle_quality: ['mva-warehouse pg-derive (rebuilt from scratch)', 'Does base quality decay along the read, as sequencing chemistry predicts?'],
  quality_levels: ['mva-warehouse pg-derive (rebuilt from scratch)', 'How the instrument’s four-level quality binning distributes across partitions.'],
  flowcell_occupancy: ['mva-warehouse pg-derive (rebuilt from scratch)', 'Whether clusters are spread evenly over the flowcell, or a physical defect is visible.'],
  probe_ledger: ['append-only ledger — written by mva-warehouse probe-log', 'Oracle submissions are a hard budget, and a budget tracked in chat messages gets double-spent.'],
};

/** Columns that recur across tables with one meaning — written once, as on the server. */
const SHARED: Record<string, string> = {
  chrom: 'Contig (chromosome) the row is about, spelled as that table stores it — bare on the callset side, chr-prefixed on the panel side.',
  pos: 'Position of the variant on the contig, 1-based, the VCF’s POS.',
  ref: 'Reference allele — the base or bases GRCh38 has at this position.',
  alt: 'Alternate allele — what was seen instead of the reference.',
  qual: 'Phred-scaled confidence the caller has in the site: 30 means a 1-in-1,000 chance it is wrong.',
  filter: 'The caller’s verdict — PASS, or the names of the filters the site failed.',
  gene: 'HGNC gene symbol the row is about; null where no gene applies.',
  sha256: 'SHA-256 digest of the bytes — a 64-hex fingerprint. Equal digests mean not one bit differs.',
  count: 'How many records fall in this row’s bucket.',
  n_all: 'Variant records inside this gene’s interval, before any filter.',
  n_pass: 'Of those records, how many carry FILTER=PASS.',
  loeuf: 'Upper bound of the observed/expected loss-of-function ratio. Low means healthy people almost never carry a broken copy.',
  gnomad_af: 'Allele frequency in gnomAD. Null means never seen there — rarer than any number, not zero.',
};

/** Meanings that belong to one table. Beats {@link SHARED} on the same column name. */
const SPECIFIC: Record<string, string> = {
  'variants_raw.line_no': 'The record’s position among the VCF’s data lines. Ordering by it reproduces the original file byte for byte.',
  'variants_raw.info': 'The whole INFO field as delivered, semicolon-packed, unparsed.',
  'contigs.length': 'Length of the contig in bases, as the callset’s header declares it.',
  'bcftools_idd.length': 'Length of the indel in bases — negative is a deletion, positive an insertion.',
  'bcftools_sn.metric': 'Name of the headline counter, e.g. “number of SNPs”.',
  'bcftools_sn.value': 'That counter’s value for this callset.',
  'panel_regions.name': 'The candidate gene the interval belongs to — a BED file’s fourth column is the feature name.',
  'panel_regions.start': 'Interval start, 0-based and half-open, so the first base is start + 1 in VCF coordinates.',
  'panel_regions.end': 'Interval end, exclusive, and therefore the last base’s 1-based VCF coordinate.',
  'allele_balance_flags.mean_vaf': 'Mean share of reads carrying the alternate allele at heterozygous sites. A diploid genome sits at 0.50.',
  'allele_balance_flags.balance_call': 'flagged when the mean leaves 0.45–0.55, balanced otherwise. A screen, not a diagnosis.',
  'variant_density_bins.mb': 'Which 1-megabase window of the contig this row covers.',
  'variant_density_bins.n': 'Variant records in the window.',
  'panel_candidates.vaf': 'Fraction of reads carrying the alternate allele. Null at a 1/2 site, where no single alternate owns the reads.',
  'probe_ledger.probe_id': 'Sequential id of the submission, assigned on append.',
  'probe_ledger.payload': 'Exactly what was uploaded, kept in full so a reply can be decoded later.',
};

/** `schema.table → [column, sql type][]`, in the order the table declares them. */
const LAYOUT: [string, string, [string, string][]][] = [
  ['warehouse', 'variants_raw', [['line_no', 'bigint'], ['chrom', 'character varying'], ['pos', 'character varying'], ['ref', 'character varying'], ['alt', 'character varying'], ['qual', 'character varying'], ['filter', 'character varying'], ['info', 'character varying']]],
  ['warehouse', 'contigs', [['chrom', 'character varying'], ['length', 'bigint']]],
  ['warehouse', 'bcftools_sn', [['metric', 'character varying'], ['value', 'bigint']]],
  ['warehouse', 'bcftools_idd', [['length', 'integer'], ['count', 'bigint']]],
  ['warehouse', 'panel_regions', [['chrom', 'character varying'], ['start', 'bigint'], ['end', 'bigint'], ['name', 'character varying']]],
  ['warehouse', 'gnomad_af_panel', [['chrom', 'character varying'], ['pos', 'bigint'], ['ref', 'character varying'], ['alt', 'character varying'], ['gnomad_af', 'double precision']]],
  ['warehouse', 'vep_staging', [['chrom', 'character varying'], ['pos', 'bigint'], ['raw_json', 'character varying']]],
  ['warehouse', 'read_manifest', [['sha256', 'character varying'], ['count', 'bigint']]],
  ['results', 'allele_balance_flags', [['chrom', 'character varying'], ['mean_vaf', 'double precision'], ['balance_call', 'character varying']]],
  ['results', 'variant_density_bins', [['chrom', 'character varying'], ['mb', 'bigint'], ['n', 'bigint']]],
  ['results', 'panel_gene_density', [['gene', 'character varying'], ['chrom', 'character varying'], ['n_all', 'bigint'], ['n_pass', 'bigint']]],
  ['results', 'panel_candidates', [['chrom', 'character varying'], ['pos', 'bigint'], ['ref', 'character varying'], ['alt', 'character varying'], ['gene', 'character varying'], ['gnomad_af', 'double precision'], ['vaf', 'double precision']]],
  ['results', 'panel_constraint', [['gene', 'character varying'], ['loeuf', 'double precision']]],
  ['results', 'probe_ledger', [['probe_id', 'bigint'], ['payload', 'character varying']]],
  ['results', 'kmer_counts', [['hits', 'bigint']]],
];

export const catalogColumnsFixture: CatalogColumnRow[] = LAYOUT.flatMap(([schema, table, columns]) =>
  columns.map(([column, data_type], index) => ({
    schema,
    table,
    column,
    data_type,
    ordinal: index + 1,
    meaning: SPECIFIC[`${table}.${column}`] ?? SHARED[column] ?? null,
  })),
);
