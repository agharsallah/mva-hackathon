import type { FunnelStageRow } from '../api/types';

/**
 * FIXTURE — MEASURED, every row. This is the verbatim output of the `candidate_funnel`
 * derivation executed against the warehouse (docs/step-0/methodology/039), transcribed so
 * the exhibit reads correctly with the API down. Nothing here is shaped or interpolated.
 *
 * Both scopes are present, `of_previous_pct` is null exactly where the live table nulls it
 * (stage 1 has no predecessor; stage 4 is a scope change; stage 9 changes unit), and every
 * stage carries its note.
 */
export const candidateFunnelFixture: FunnelStageRow[] = [
  {
    stage_no: 1,
    stage: 'records called',
    scope: 'genome',
    n: 5_012_204,
    of_previous_pct: null,
    note: 'COUNT(*) over the delivered callset. Every record the variant caller emitted, before any judgement is applied.',
  },
  {
    stage_no: 2,
    stage: 'FILTER = PASS',
    scope: 'genome',
    n: 4_740_790,
    of_previous_pct: 94.5849,
    note: "The caller's own veto. A suppressed record carries a filter label (MQ40, QD2, LowQual) saying which quality test it failed.",
  },
  {
    stage_no: 3,
    stage: 'heterozygous call',
    scope: 'genome',
    n: 2_913_813,
    of_previous_pct: 61.4626,
    note: "GT names two different non-missing alleles (0/1, 1/2, ...), read from each record's own FORMAT keys. A homozygous call cannot be half of a compound heterozygote, which needs two different broken copies.",
  },
  {
    stage_no: 4,
    stage: 'inside a panel interval',
    scope: 'panel',
    n: 841,
    of_previous_pct: null,
    note: 'SCOPE CHANGE — annotation exists only inside the 8-gene panel, so every stage below counts panel records only. PASS records inside the 8 candidate-gene intervals (BED, 20 kb padding), of 861 records there in total. Not a subset of the row above: it counts PASS records of every genotype, so no percentage of that row would mean anything.',
  },
  {
    stage_no: 5,
    stage: 'VEP-annotated allele',
    scope: 'panel',
    n: 854,
    of_previous_pct: 101.5458,
    note: 'Unit changes from record to allele: a multi-allelic record carries one annotation per ALT, so this can exceed the record count above it. 874 alleles are annotated in total; 0 match no callset record and 20 matched only a filtered one.',
  },
  {
    stage_no: 6,
    stage: 'rare in gnomAD',
    scope: 'panel',
    n: 32,
    of_previous_pct: 3.7471,
    note: 'gnomAD AF below 0.01 or absent entirely (absent is not frequency zero — the database simply has no row). 0.01 is the recessive cutoff: the dominant 1e-3 would drop real carrier alleles from a compound-heterozygous search.',
  },
  {
    stage_no: 7,
    stage: 'protein-altering',
    scope: 'panel',
    n: 2,
    of_previous_pct: 6.25,
    note: 'VEP IMPACT HIGH (truncates the protein) or MODERATE (swaps an amino acid). LOW and MODIFIER cannot change the protein sequence.',
  },
  {
    stage_no: 8,
    stage: 'in a gene carrying two or more',
    scope: 'panel',
    n: 2,
    of_previous_pct: 100,
    note: 'Of the row above, 2 are heterozygous, and these fall in 1 gene(s) carrying at least two — the compound-heterozygous shape. Shape only: phase is unproven, and with one sample and no parents this callset cannot prove it.',
  },
  {
    stage_no: 9,
    stage: 'candidate pairs',
    scope: 'panel',
    n: 1,
    of_previous_pct: null,
    note: 'Every within-gene pairing of the alleles above: k*(k-1)/2 per gene. Unit changes from allele to pair, so a gene with more than three alleles yields more pairs than alleles.',
  },
];
