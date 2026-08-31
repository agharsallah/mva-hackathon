import type { EvidenceRegister, EvidenceRow, HypothesisRegister, HypothesisRow } from '../api/types';

/**
 * FIXTURE — the research register, in the shape it will have once step 1 starts making
 * claims.
 *
 * NOTHING HERE IS MEASURED. Every statement, verdict and confidence below is invented to
 * exercise the layout: two claims with two revisions each (one that firmed up, one that
 * was refuted), four observations covering all three directions, and the nulls the real
 * register carries — an opening revision has no confidence, no reasoning and no path.
 *
 * The live API today returns `table_exists: false` with no rows, because the register has
 * never been written. That empty state is a designed state in the page, not a fallback:
 * the fixture exists so the *populated* layout can be reviewed before there is anything to
 * put in it.
 *
 * No genomic position appears here, and none ever will — `mva-science check` refuses a
 * coordinate in a statement or a claim, and this fixture holds itself to the same rule.
 */

const H001 = {
  hypothesis_id: 'H001',
  step: 'step-2',
  statement: 'A compound-heterozygous pair of rare damaging alleles in BUB1B causes this child’s MVA.',
  prediction:
    'Two different protein-altering alleles in BUB1B, each under 0.1% in gnomAD, both present in the callset.',
  refuted_by: 'Fewer than two rare protein-altering alleles in BUB1B, or either allele common in gnomAD.',
  gene: 'BUB1B',
  author: 'FIXTURE',
} as const;

const H002 = {
  hypothesis_id: 'H002',
  step: 'step-4',
  statement: 'The second allele is present but was discarded by a quality filter.',
  prediction: 'A non-PASS call in the same gene with balanced read support on both strands.',
  refuted_by: 'Every non-PASS call in the gene is strand-skewed or below the noise floor.',
  gene: 'BUB1B',
  author: 'FIXTURE',
} as const;

/** Every revision, oldest first, exactly as the endpoint orders them. */
export const hypothesisRowsFixture: HypothesisRow[] = [
  {
    ...H001,
    revision: 1,
    recorded_at: '2026-09-01T10:00:00',
    path: null,
    status: 'proposed',
    confidence: null,
    reasoning: null,
  },
  {
    ...H001,
    revision: 2,
    recorded_at: '2026-09-02T16:20:00',
    path: 'panel-first',
    status: 'supported',
    confidence: 0.69,
    reasoning:
      'One strong constraint observation for, one absence observation against; the suggestion was 0.69 and was committed unchanged.',
  },
  {
    ...H002,
    revision: 1,
    recorded_at: '2026-09-01T10:05:00',
    path: null,
    status: 'proposed',
    confidence: null,
    reasoning: null,
  },
  {
    ...H002,
    revision: 2,
    recorded_at: '2026-09-03T09:40:00',
    path: 'filter-rescue',
    status: 'refuted',
    confidence: 0.12,
    reasoning:
      'The refutation condition written before the run was met exactly: every non-PASS call in the gene is strand-skewed.',
  },
];

export const evidenceRowsFixture: EvidenceRow[] = [
  {
    evidence_id: 1,
    recorded_at: '2026-09-01T12:00:00',
    hypothesis_id: 'H001',
    kind: 'annotation',
    direction: 'supports',
    strength: 0.7,
    claim: 'BUB1B is strongly depleted of loss-of-function variants in gnomAD.',
    source_ref: 'methodology/032',
    lineage_ref: 'results.panel_gene_constraint',
    author: 'FIXTURE',
  },
  {
    evidence_id: 2,
    recorded_at: '2026-09-01T12:10:00',
    hypothesis_id: 'H001',
    kind: 'absence',
    direction: 'refutes',
    strength: 0.3,
    claim: 'Only one protein-altering BUB1B allele survives the quality filters.',
    source_ref: 'methodology/033',
    lineage_ref: null,
    author: 'FIXTURE',
  },
  {
    evidence_id: 3,
    recorded_at: '2026-09-02T08:00:00',
    hypothesis_id: 'H002',
    kind: 'measurement',
    direction: 'neutral',
    strength: 0.1,
    claim: 'Three non-PASS calls exist inside the gene interval.',
    source_ref: 'methodology/033',
    lineage_ref: null,
    author: 'FIXTURE',
  },
  {
    evidence_id: 4,
    recorded_at: '2026-09-03T08:30:00',
    hypothesis_id: 'H002',
    kind: 'measurement',
    direction: 'refutes',
    strength: 0.6,
    claim: 'All three non-PASS calls are strand-skewed in the raw reads.',
    source_ref: 'methodology/033',
    lineage_ref: 'reads.kmer_probe',
    author: 'FIXTURE',
  },
];

export const hypothesisRegisterFixture: HypothesisRegister = {
  table_exists: true,
  rows: hypothesisRowsFixture,
};

export const evidenceRegisterFixture: EvidenceRegister = {
  table_exists: true,
  rows: evidenceRowsFixture,
};
