import type { LocusVariant, PanelGeneRow } from '../api/types';
import { prng } from './prng';

/**
 * FIXTURE — MVA candidate panel scorecard.
 *
 * MEASURED: gene, chrom, n_all, n_pass, variants_per_mb, pct_pass for every row below.
 *
 * SYNTHETIC BY DESIGN: `start` / `end` are placeholders (1,000,000-based) — this repo
 * never commits a genomic coordinate, so the fixture carries none. `span_bp` is derived
 * from the measured n_all / variants_per_mb, which is a size, not a location. The live
 * API supplies the real interval and the Ensembl id from the panel BED.
 */
function gene(
  g: string,
  chrom: string,
  nAll: number,
  nPass: number,
  perMb: number,
  pctPass: number,
  note: string,
): PanelGeneRow {
  const spanBp = Math.round((nAll / perMb) * 1e6);
  return {
    gene: g,
    chrom,
    start: 1_000_000, // synthetic placeholder — see module note
    end: 1_000_000 + spanBp, // synthetic placeholder
    ensembl_id: '', // supplied by the live API from the panel BED
    note,
    n_all: nAll,
    n_pass: nPass,
    n_filtered: nAll - nPass,
    span_bp: spanBp,
    variants_per_mb: perMb,
    pct_pass: pctPass,
  };
}

/**
 * variants_per_mb is a measured anchor for BUB1B, CENPE, CEP192, SMC5 and TP53. For
 * CEP57, TRIP13 and DICER1 only the counts were recorded, so the density below is a
 * 1000.0 placeholder; the live API returns the measured value.
 */
export const panelGenesFixture: PanelGeneRow[] = [
  gene('BUB1B', 'chr15', 80, 76, 798.8, 95.0, 'spindle assembly checkpoint; the canonical MVA gene'),
  gene('CEP57', 'chr11', 13, 13, 1000.0, 100.0, 'centrosomal, microtubule nucleation; MVA type 2'),
  gene('TRIP13', 'chr5', 12, 6, 1000.0, 50.0, 'AAA-ATPase, checkpoint silencing; MVA type 3'),
  gene('CENPE', 'chr4', 169, 166, 1269.6, 98.2, 'centromere kinesin, chromosome congression'),
  gene('CEP192', 'chr18', 255, 251, 1467.4, 98.4, 'centrosome maturation and duplication'),
  gene('SMC5', 'chr9', 125, 124, 915.0, 99.2, 'SMC5/6 complex, genome stability'),
  gene('DICER1', 'chr14', 87, 87, 1000.0, 100.0, 'miRNA processing; tumour-predisposition overlap'),
  gene('TP53', 'chr17', 120, 118, 1824.6, 98.3, 'tumour suppressor; mitotic surveillance'),
];

/**
 * FIXTURE — locus explorer.
 *
 * ***SYNTHETIC POSITIONS, DELIBERATELY.*** The live endpoint returns real patient
 * coordinates; committing one would break the project's patient-data rule. So the
 * positions here are a plain arithmetic ladder (1000, 2000, 3000, …) and are obviously
 * not genomic. Only the *shape* of the response is faithful: a QUAL spread, a mix of
 * PASS and suppressed records, 0/1 · 1/1 · 1/2 genotypes, depths around the 44x mode
 * and VAFs around 0.5.
 */
export function locusFixture(geneName: string): LocusVariant[] {
  const row = panelGenesFixture.find((g) => g.gene.toUpperCase() === geneName.toUpperCase());
  const n = row ? Math.min(row.n_all, 120) : 40;
  const rand = prng(geneName.split('').reduce((a, c) => a + c.charCodeAt(0), 7));
  const bases = ['A', 'C', 'G', 'T'];
  const out: LocusVariant[] = [];
  for (let i = 0; i < n; i++) {
    const r = rand();
    const filter = r < 0.05 ? 'MQ40' : r < 0.08 ? 'QD2' : 'PASS';
    const gtRoll = rand();
    const gt = gtRoll < 0.6 ? '0/1' : gtRoll < 0.94 ? '1/1' : '1/2';
    const dp = Math.max(6, Math.round(44 + (rand() - 0.5) * 26));
    const vaf = gt === '1/1' ? 0.94 + rand() * 0.06 : 0.42 + rand() * 0.17;
    const adAlt = Math.round(dp * vaf);
    out.push({
      pos: (i + 1) * 1000, // SYNTHETIC — a counter, not a coordinate
      ref: bases[Math.floor(rand() * 4)],
      alt: bases[Math.floor(rand() * 4)],
      qual: Math.round((filter === 'PASS' ? 200 + rand() * 1600 : 20 + rand() * 90) * 10) / 10,
      filter,
      gt,
      dp,
      ad_ref: dp - adAlt,
      ad_alt: adAlt,
      vaf: Math.round(vaf * 1000) / 1000,
      gq: Math.min(99, Math.round(30 + rand() * 69)),
    });
  }
  return out;
}
