import type { ClinvarPresence, ClinvarPresenceSite, ClinvarPresenceSummary } from '../../api/types';
import { rows } from '../loader';

/**
 * Offline stand-in for `/api/panel/clinvar-presence`.
 *
 * The **per-gene P/LP counts are measured** — `data/panel-clinvar.json`'s `plpPerGene`
 * comes from the committed ClinVar extract and reproduces the per-gene table in
 * `ressources/reference/README.md`. Everything about the *callset side* is SHAPED, not
 * measured: `shaped` and `data/panel-clinvar-sites.json`'s positions are invented, and the
 * hit counts are chosen so the exhibit has one of each state to render — present + PASS +
 * het, present but suppressed, absent, and a row ClinVar gives no alternate allele for.
 *
 * No real patient coordinate appears here or in any other fixture.
 */

interface Shaped {
  present: number;
  pass: number;
  het: number;
  uncomparable: number;
}

interface ClinvarInputs {
  plpPerGene: Record<string, number>;
  shaped: Record<string, Shaped>;
}

function buildSummary({ plpPerGene, shaped }: ClinvarInputs): ClinvarPresenceSummary[] {
  return Object.entries(plpPerGene)
    .map(([gene, n_plp]) => {
      const s = shaped[gene] ?? { present: 0, pass: 0, het: 0, uncomparable: 0 };
      const n_comparable = n_plp - s.uncomparable;
      return {
        gene,
        n_plp,
        n_comparable,
        n_uncomparable: s.uncomparable,
        n_present: s.present,
        n_present_pass: s.pass,
        n_present_het: s.het,
        n_absent: n_comparable - s.present,
      };
    })
    .sort((a, b) => b.n_present - a.n_present || b.n_plp - a.n_plp);
}

export async function clinvarPresenceFixture(gene?: string): Promise<ClinvarPresence> {
  const [inputs, sites] = await Promise.all([
    rows<ClinvarInputs>('panel-clinvar'),
    rows<ClinvarPresenceSite[]>('panel-clinvar-sites'),
  ]);
  const summary = buildSummary(inputs);
  if (!gene) return { summary, sites };
  return {
    summary: summary.filter((row) => row.gene === gene),
    sites: sites.filter((row) => row.gene === gene),
  };
}
