import type { PanelFilterCensusRow, PanelSuppressed, PanelSuppressedRecord, VariantImpact } from '../api/types';

/**
 * FIXTURE — the suppressed-call mining view.
 *
 * MEASURED: the whole census below. Per-gene, per-FILTER record counts are aggregates,
 * not locations, and `ideation/data-findings.md` §3 and §6 already own them — TRIP13's
 * 6 suppressed of 12 in particular. They are transcribed here so the exhibit reads
 * truthfully offline.
 *
 * ***SYNTHETIC POSITIONS, DELIBERATELY.*** The record list uses the same 1000, 2000,
 * 3000 … counter the locus and annotation fixtures use: this repo commits no genomic
 * coordinate. QUAL, depths and VAF are shaped after the real rows (a suppressed call is
 * low-QUAL, thin, or off-balance) but no individual value here is a measurement.
 */

/** `[gene, bare contig, FILTER value, records]`, PASS included — the measured census. */
const CENSUS: [string, string, string, number][] = [
  ['BUB1B', '15', 'PASS', 76],
  ['BUB1B', '15', 'MQ40', 3],
  ['BUB1B', '15', 'LowQual;QD2', 1],
  ['CENPE', '4', 'PASS', 166],
  ['CENPE', '4', 'LowQual;QD2', 1],
  ['CENPE', '4', 'MQ40', 1],
  ['CENPE', '4', 'QD2', 1],
  ['CEP192', '18', 'PASS', 251],
  ['CEP192', '18', 'MQ40', 3],
  ['CEP192', '18', 'LowQual', 1],
  ['CEP57', '11', 'PASS', 13],
  ['DICER1', '14', 'PASS', 87],
  ['SMC5', '9', 'PASS', 124],
  ['SMC5', '9', 'LowQual', 1],
  ['TP53', '17', 'PASS', 118],
  ['TP53', '17', 'LowQual', 1],
  ['TP53', '17', 'LowQual;QD2', 1],
  ['TRIP13', '5', 'PASS', 6],
  ['TRIP13', '5', 'MQ40', 5],
  ['TRIP13', '5', 'QD2', 1],
];

const totals = new Map<string, number>();
for (const [gene, , , n] of CENSUS) totals.set(gene, (totals.get(gene) ?? 0) + n);

export const panelFilterCensusFixture: PanelFilterCensusRow[] = CENSUS.map(
  ([gene, chrom, filter, n]) => {
    const all = totals.get(gene) as number;
    return {
      gene,
      chrom,
      filter,
      is_pass: filter === 'PASS',
      n,
      n_gene_all: all,
      pct_of_gene: Math.round((100 * n) / all * 100) / 100,
    };
  },
);

/**
 * `[gene, FILTER, GT, DP, alt reads, consequence, impact, gnomAD AF]`.
 *
 * One row per suppressed record in the census, in the same order, so the two halves of
 * the payload agree. The last CENPE row is deliberately **unannotated** — VEP did in fact
 * cover every panel allele in the live run, but the contract allows a null and the
 * exhibit has to render it as "not annotated" rather than as a blank.
 */
const RECORDS: [string, string, string, number, number, string | null, VariantImpact | null, number | null][] = [
  ['BUB1B', 'MQ40', '1/1', 25, 25, 'intron_variant', 'MODIFIER', 0.9897],
  ['BUB1B', 'MQ40', '0/1', 31, 12, 'intron_variant', 'MODIFIER', 0.08522],
  ['BUB1B', 'MQ40', '1/1', 38, 38, 'intron_variant', 'MODIFIER', 0.6341],
  ['BUB1B', 'LowQual;QD2', '0/1', 13, 5, 'non_coding_transcript_exon_variant', 'MODIFIER', 0.2204],
  ['CENPE', 'MQ40', '0/1', 12, 5, 'intron_variant', 'MODIFIER', 0.2104],
  ['CENPE', 'QD2', '0/1', 27, 7, 'intron_variant', 'MODIFIER', 0.1621],
  ['CENPE', 'LowQual;QD2', '0/1', 34, 7, null, null, null],
  ['CEP192', 'MQ40', '1/1', 52, 52, 'intron_variant', 'MODIFIER', 0.6888],
  ['CEP192', 'MQ40', '1/1', 32, 31, 'intron_variant', 'MODIFIER', 0.6958],
  ['CEP192', 'MQ40', '1/1', 32, 31, 'intron_variant', 'MODIFIER', 0.6952],
  ['CEP192', 'LowQual', '0/1', 5, 2, 'intron_variant', 'MODIFIER', 0.08709],
  ['SMC5', 'LowQual', '0/1', 8, 5, 'intron_variant', 'MODIFIER', 0.2401],
  ['TP53', 'LowQual', '1/1', 4, 3, 'intron_variant', 'MODIFIER', 0.002591],
  ['TP53', 'LowQual;QD2', '0/1', 13, 5, 'intron_variant', 'MODIFIER', 0.005743],
  ['TRIP13', 'MQ40', '0/1', 24, 6, 'non_coding_transcript_exon_variant', 'MODIFIER', 0.4367],
  ['TRIP13', 'MQ40', '0/1', 25, 6, 'non_coding_transcript_exon_variant', 'MODIFIER', 0.3933],
  ['TRIP13', 'MQ40', '0/1', 20, 4, 'non_coding_transcript_exon_variant', 'MODIFIER', 0.4542],
  ['TRIP13', 'MQ40', '0/1', 17, 2, 'non_coding_transcript_exon_variant', 'MODIFIER', 0.06156],
  ['TRIP13', 'MQ40', '0/1', 39, 11, 'intron_variant', 'MODIFIER', 0.3306],
  ['TRIP13', 'QD2', '0/1', 48, 6, 'missense_variant', 'MODERATE', 0.3241],
];

const CHROM = new Map(CENSUS.map(([gene, chrom]) => [gene, chrom]));
const BASES = ['A', 'C', 'G', 'T'];

/** A suppressed record's QUAL, shaped by why it was flagged. Deterministic, not measured. */
function qualFor(filter: string, i: number): number {
  const base = filter.includes('LowQual') ? 12 : filter.includes('QD2') ? 45 : 120;
  return Math.round((base + (i % 7) * 13.4) * 100) / 100;
}

export const panelSuppressedRecordsFixture: PanelSuppressedRecord[] = RECORDS.map(
  ([gene, filter, gt, dp, adAlt, consequence, impact, af], i) => ({
    gene,
    chrom: CHROM.get(gene) as string,
    pos: (i + 1) * 1000, // SYNTHETIC — a counter, not a coordinate
    ref: BASES[i % 4],
    alt: BASES[(i + 1) % 4],
    qual: qualFor(filter, i),
    filter,
    gt,
    dp,
    gq: 40 + ((i * 17) % 60),
    ad_ref: dp - adAlt,
    ad_alt: adAlt,
    vaf: Math.round((adAlt / dp) * 10000) / 10000,
    is_het: gt === '0/1',
    annotated_alt: consequence === null ? null : BASES[(i + 1) % 4],
    rsid: consequence === null ? null : `rs${500_000 + i * 137}`,
    consequence,
    impact,
    gnomad_af: af,
    gnomad_af_grpmax: af === null ? null : Math.round(af * 1.14 * 1e6) / 1e6,
    clin_sig: null,
    annotated: consequence !== null,
  }),
);

/** `gene` omitted returns every suppressed record; the census is always the whole panel. */
export function panelSuppressedFixture(gene?: string): PanelSuppressed {
  const want = gene?.toUpperCase();
  return {
    gene: gene ?? null,
    census: panelFilterCensusFixture,
    records: want
      ? panelSuppressedRecordsFixture.filter((r) => r.gene.toUpperCase() === want)
      : panelSuppressedRecordsFixture,
  };
}
