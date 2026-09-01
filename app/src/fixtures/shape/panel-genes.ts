import type { PanelGeneRow } from '../../api/types';
import { rows } from '../loader';

/**
 * FIXTURE — MVA candidate panel scorecard. Rows in `data/panel-genes.json`.
 *
 * MEASURED: gene, chrom, n_all, n_pass, variants_per_mb, pct_pass for every row.
 * variants_per_mb is a measured anchor for BUB1B, CENPE, CEP192, SMC5 and TP53. For
 * CEP57, TRIP13 and DICER1 only the counts were recorded, so the density there is a
 * 1000.0 placeholder; the live API returns the measured value.
 *
 * SYNTHETIC BY DESIGN: `start` / `end` are placeholders (1,000,000-based) — this repo
 * never commits a genomic coordinate, so the fixture carries none. `span_bp` is derived
 * from the measured n_all / variants_per_mb, which is a size, not a location. The live
 * API supplies the real interval and the Ensembl id from the panel BED.
 */
type Row = [
  gene: string,
  chrom: string,
  nAll: number,
  nPass: number,
  perMb: number,
  pctPass: number,
  note: string,
];

function build([gene, chrom, nAll, nPass, perMb, pctPass, note]: Row): PanelGeneRow {
  const spanBp = Math.round((nAll / perMb) * 1e6);
  return {
    gene,
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

export async function panelGenesFixture(): Promise<PanelGeneRow[]> {
  const table = await rows<Row[]>('panel-genes');
  return table.map(build);
}
