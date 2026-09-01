import type { PanelFilterCensusRow, PanelSuppressed, PanelSuppressedRecord, VariantImpact } from '../../api/types';
import { rows } from '../loader';

/**
 * FIXTURE — the suppressed-call mining view. `gene` omitted returns every suppressed
 * record; the census is always the whole panel.
 *
 * MEASURED: the whole census (`data/panel-suppressed-census.json`). Per-gene, per-FILTER
 * record counts are aggregates, not locations, and `ideation/data-findings.md` §3 and §6
 * already own them — TRIP13's 6 suppressed of 12 in particular. They are transcribed
 * there so the exhibit reads truthfully offline.
 *
 * ***SYNTHETIC POSITIONS, DELIBERATELY.*** The record list (`data/panel-suppressed-records.json`)
 * uses the same 1000, 2000, 3000 … counter the locus and annotation fixtures use: this repo
 * commits no genomic coordinate. QUAL, depths and VAF are shaped after the real rows (a
 * suppressed call is low-QUAL, thin, or off-balance) but no individual value here is a
 * measurement.
 */

type CensusRow = [gene: string, chrom: string, filter: string, n: number];
type RecordRow = [
  gene: string,
  filter: string,
  gt: string,
  dp: number,
  adAlt: number,
  consequence: string | null,
  impact: VariantImpact | null,
  af: number | null,
];

function buildCensus(census: CensusRow[]): PanelFilterCensusRow[] {
  const totals = new Map<string, number>();
  for (const [gene, , , n] of census) totals.set(gene, (totals.get(gene) ?? 0) + n);

  return census.map(([gene, chrom, filter, n]) => {
    const all = totals.get(gene) as number;
    return {
      gene,
      chrom,
      filter,
      is_pass: filter === 'PASS',
      n,
      n_gene_all: all,
      pct_of_gene: Math.round(((100 * n) / all) * 100) / 100,
    };
  });
}

/** A suppressed record's QUAL, shaped by why it was flagged. Deterministic, not measured. */
function qualFor(filter: string, i: number): number {
  const base = filter.includes('LowQual') ? 12 : filter.includes('QD2') ? 45 : 120;
  return Math.round((base + (i % 7) * 13.4) * 100) / 100;
}

const BASES = ['A', 'C', 'G', 'T'];

/**
 * One row per suppressed record in the census, in the same order, so the two halves of
 * the payload agree. The last CENPE row is deliberately **unannotated** — VEP did in fact
 * cover every panel allele in the live run, but the contract allows a null and the
 * exhibit has to render it as "not annotated" rather than as a blank.
 */
function buildRecords(records: RecordRow[], chromOf: Map<string, string>): PanelSuppressedRecord[] {
  return records.map(([gene, filter, gt, dp, adAlt, consequence, impact, af], i) => ({
    gene,
    chrom: chromOf.get(gene) as string,
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
  }));
}

export async function panelSuppressedFixture(gene?: string): Promise<PanelSuppressed> {
  const [census, records] = await Promise.all([
    rows<CensusRow[]>('panel-suppressed-census'),
    rows<RecordRow[]>('panel-suppressed-records'),
  ]);
  const chromOf = new Map(census.map(([g, chrom]) => [g, chrom]));
  const allRecords = buildRecords(records, chromOf);
  const want = gene?.toUpperCase();
  return {
    gene: gene ?? null,
    census: buildCensus(census),
    records: want ? allRecords.filter((r) => r.gene.toUpperCase() === want) : allRecords,
  };
}
