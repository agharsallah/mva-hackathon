/**
 * Offline stand-in for `/api/panel/clinvar-presence`.
 *
 * The **per-gene P/LP counts are measured** — they come from the committed ClinVar extract
 * and reproduce the per-gene table in `ressources/reference/README.md`. Everything about
 * the *callset side* is SHAPED, not measured: the positions are invented, and the hit
 * counts are chosen so the exhibit has one of each state to render — present + PASS + het,
 * present but suppressed, absent, and a row ClinVar gives no alternate allele for.
 *
 * No real patient coordinate appears here or in any other fixture.
 */

import type { ClinvarPresence, ClinvarPresenceSite, ClinvarPresenceSummary } from '../api/types';

/** Measured: ClinVar P/LP records per panel gene in the committed extract. */
const PLP_PER_GENE: Record<string, number> = {
  TP53: 1147,
  DICER1: 860,
  BUB1B: 84,
  CEP57: 19,
  TRIP13: 9,
  CENPE: 5,
  SMC5: 5,
  CEP192: 0,
};

/** SHAPED: how many of those the fixture pretends were called, and in what state. */
const SHAPED: Record<string, { present: number; pass: number; het: number; uncomparable: number }> =
  {
    BUB1B: { present: 2, pass: 1, het: 1, uncomparable: 1 },
    CEP57: { present: 1, pass: 0, het: 0, uncomparable: 0 },
  };

const summary: ClinvarPresenceSummary[] = Object.entries(PLP_PER_GENE)
  .map(([gene, n_plp]) => {
    const s = SHAPED[gene] ?? { present: 0, pass: 0, het: 0, uncomparable: 0 };
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

/** SYNTHETIC positions — never real. */
const sites: ClinvarPresenceSite[] = [
  {
    gene: 'BUB1B',
    chrom: '15',
    pos: 40200001,
    ref: 'T',
    alt: 'G',
    rsid: 'rs000000001',
    variation_id: 900001,
    clnsig: 'Pathogenic/Likely_pathogenic',
    clnrevstat: 'criteria_provided,_multiple_submitters,_no_conflicts',
    review_stars: 2,
    condition: 'not_provided|Mosaic_variegated_aneuploidy_syndrome_1',
    comparable: true,
    present: true,
    gt: '0/1',
    filter: 'PASS',
    qual: 708.8,
    dp: 46,
    allele_ix: 1,
    vaf: 0.5435,
    carries_alt: true,
    is_het: true,
  },
  {
    gene: 'BUB1B',
    chrom: '15',
    pos: 40210002,
    ref: 'C',
    alt: 'CT',
    rsid: null,
    variation_id: 900002,
    clnsig: 'Pathogenic',
    clnrevstat: 'criteria_provided,_single_submitter',
    review_stars: 1,
    condition: 'Mosaic_variegated_aneuploidy_syndrome_1',
    comparable: true,
    present: true,
    gt: '0/1',
    filter: 'LowQual',
    qual: 31.2,
    dp: 9,
    allele_ix: 1,
    vaf: 0.3333,
    carries_alt: true,
    is_het: true,
  },
  {
    gene: 'BUB1B',
    chrom: '15',
    pos: 40220003,
    ref: 'A',
    alt: '.',
    rsid: null,
    variation_id: 900003,
    clnsig: 'Pathogenic',
    clnrevstat: null,
    review_stars: null,
    condition: 'not_provided',
    comparable: false,
    present: null,
    gt: null,
    filter: null,
    qual: null,
    dp: null,
    allele_ix: null,
    vaf: null,
    carries_alt: null,
    is_het: null,
  },
  {
    gene: 'CEP57',
    chrom: '11',
    pos: 95800004,
    ref: 'G',
    alt: 'A',
    rsid: 'rs000000004',
    variation_id: 900004,
    clnsig: 'Likely_pathogenic',
    clnrevstat: 'reviewed_by_expert_panel',
    review_stars: 3,
    condition: 'Mosaic_variegated_aneuploidy_syndrome_2',
    comparable: true,
    present: true,
    gt: '1/1',
    filter: 'LowQual',
    qual: 44.0,
    dp: 12,
    allele_ix: 1,
    vaf: 0.9167,
    carries_alt: true,
    is_het: false,
  },
];

export function clinvarPresenceFixture(gene?: string): ClinvarPresence {
  if (!gene) return { summary, sites };
  return {
    summary: summary.filter((row) => row.gene === gene),
    sites: sites.filter((row) => row.gene === gene),
  };
}
