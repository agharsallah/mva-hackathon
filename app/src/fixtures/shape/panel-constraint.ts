import type { PanelConstraintRow } from '../../api/types';
import { rows } from '../loader';

/**
 * FIXTURE — gnomAD constraint + ClinVar counts per panel gene. Rows in
 * `data/panel-constraint.json`.
 *
 * ***SHAPE ONLY — none of these numbers is a measurement from this project.*** The live
 * endpoint reads them from the gnomAD constraint table and a ClinVar summary; until it
 * answers, these fill the chart so the exhibit is readable offline, and the app badges
 * every one of them `fixture`.
 *
 * The shape it deliberately exercises is the counter-intuitive one the exhibit exists to
 * show: MVA is **recessive**, so healthy carriers of a single broken copy are common and
 * the established MVA genes score as *unconstrained* (pLI ≈ 0, LOEUF ≫ 0.35). TRIP13
 * carries `null` constraint to exercise the unknown rendering — null is "no row in the
 * source table", never "unconstrained".
 */
type Row = [
  gene: string,
  chrom: string,
  nAll: number,
  nPass: number,
  loeuf: number | null,
  pli: number | null,
  misZ: number | null,
  lofObs: number | null,
  lofExp: number | null,
  clinvar: [number, number, number],
  note: string,
];

function build([
  gene,
  chrom,
  nAll,
  nPass,
  loeuf,
  pli,
  misZ,
  lofObs,
  lofExp,
  clinvar,
  note,
]: Row): PanelConstraintRow {
  return {
    gene,
    chrom,
    n_all: nAll,
    n_pass: nPass,
    loeuf,
    pli,
    mis_z: misZ,
    oe_lof: lofObs !== null && lofExp ? Math.round((lofObs / lofExp) * 1000) / 1000 : null,
    lof_obs: lofObs,
    lof_exp: lofExp,
    clinvar_plp: clinvar[0],
    clinvar_vus: clinvar[1],
    clinvar_benign: clinvar[2],
    ensembl_id: '', // supplied by the live API from the panel BED
    note,
  };
}

export async function panelConstraintFixture(): Promise<PanelConstraintRow[]> {
  const table = await rows<Row[]>('panel-constraint');
  return table.map(build);
}
