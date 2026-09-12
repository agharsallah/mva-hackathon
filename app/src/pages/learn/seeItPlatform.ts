/**
 * See-it links for the second half of the dictionary — chapters 7 to 15: databases, tools,
 * the platform, scores, statistics, hackathon scoring and the research record. Merged into
 * `SEE_IT` by `seeIt.ts`.
 */

import { at, method, type SeeIt } from './seeItShared';

export const SEE_IT_PLATFORM: Record<string, SeeIt> = {
  // ── chapter 7: databases ─────────────────────────────────────────────────
  clinvar: {
    app: [
      {
        to: '/compare#every-clinvar-pathogenic-panel-site-checked-against-this-callset',
        label: 'every pathogenic panel site, checked',
      },
    ],
    docs: [method('051-clinvar-presence', 'ClinVar presence')],
  },
  gnomad: {
    app: [
      {
        to: '/compare#rarity-in-the-healthy-population-against-the-patient-s-own-allele-fraction',
        label: 'rarity against the patient’s VAF',
      },
    ],
    docs: [method('030-population-reference-data', 'population reference data')],
  },
  'constraint-pli-loeuf-missense-z-score': {
    app: [
      {
        to: '/panel#constraint-and-clinvar-burden-per-panel-gene-context-not-a-ranking',
        label: 'constraint per panel gene',
      },
    ],
  },
  'vep-variant-effect-predictor': {
    app: [
      {
        to: '/compare#candidate-list-rare-in-the-population-and-able-to-change-the-protein',
        label: 'the annotated candidate list',
      },
    ],
    docs: [method('031-vep-rest-panel-annotation', 'VEP REST panel annotation')],
  },
  rsid: { app: [{ to: '/search', label: 'look one up' }] },
  provenance: {
    app: [
      {
        to: '/provenance#lineage-every-derived-table-and-what-produced-it',
        label: 'the lineage graph',
      },
    ],
    docs: [method('014-source-of-truth-and-lineage', 'source of truth and lineage')],
  },
  'alphafold-db-pdb-uniprot': {
    app: [{ to: '/panel', label: 'the fold, from AlphaFold DB' }],
    docs: [method('056-protein-structure-endpoint', 'the protein structure endpoint')],
  },
  // ── chapter 8: tools and platform ────────────────────────────────────────
  parquet: {
    app: [
      { to: '/reads#read-store-shape-8-partitions-272-shards', label: 'the read store’s shards' },
    ],
    docs: [method('021-the-row-group-is-a-memory-budget', 'the row group is a memory budget')],
  },
  'data-warehouse': {
    app: [
      {
        to: '/catalog#every-table-explained-what-it-is-for-what-writes-it-what-each-column-means',
        label: 'every table, explained',
      },
    ],
    docs: [method('010-postgres-ingest-and-derivations', 'Postgres ingest and derivations')],
  },
  'data-lineage': {
    app: [
      {
        to: '/provenance#lineage-every-derived-table-and-what-produced-it',
        label: 'the lineage graph',
      },
    ],
  },
  'provenance-manifest': {
    app: [
      {
        to: '/provenance#reference-data-where-the-public-inputs-came-from',
        label: 'one card per manifest',
      },
    ],
    docs: [method('061-reference-data-provenance', 'reference data provenance')],
  },
  'checksum-sha-256': {
    app: [
      {
        to: '/catalog#raw-delivery-every-object-we-were-given',
        label: 'every delivered object, verified',
      },
    ],
  },
  'dependency-health-check': {
    app: [
      {
        to: '/status#dependency-board-every-backing-service-probed-live',
        label: 'the dependency board',
      },
    ],
    docs: [method('053-dependency-health', 'dependency health')],
  },
  'k-mer': {
    app: [
      {
        to: '/probes',
        label: 'ask the raw reads for a k-mer',
      },
    ],
    docs: [method('024-the-kmer-strike-works', 'the k-mer strike works')],
  },
  'design-token': {
    app: [{ to: '/style-guide#the-tokens', label: 'the tokens, live' }],
    docs: [method('055-design-tokens', 'design tokens')],
  },
  catalog: {
    app: [
      {
        to: '/catalog#derived-tables-what-each-one-holds-and-what-produced-it',
        label: 'the table catalog',
      },
    ],
  },
  // ── chapters 9–13: scores, structure, statistics, scoring ────────────────
  alphafold: {
    app: [{ to: '/panel', label: 'the fold in 3D' }],
    docs: [method('057-protein-explorer-exhibit', 'the protein explorer')],
  },
  plddt: { app: [{ to: '/panel', label: 'residues shaded by pLDDT' }] },
  'domain-tpr-pseudo-kinase-ken-box': {
    app: [{ to: '/panel', label: 'the domain lollipop' }],
    docs: [method('040-locus-gene-track', 'the locus gene track')],
  },
  'baf-b-allele-frequency': {
    app: [
      { to: at('/genome', 'baf-karyogram-allele-balance-per-megabase'), label: 'BAF per megabase' },
    ],
  },
  'probe-ledger': {
    app: [{ to: '/science#oracle-budget-the-research-view', label: 'the ledger, 0 of 6 spent' }],
    docs: [method('016-lineage-backfill-and-probe-ledger', 'the probe ledger')],
  },
  oracle: { app: [{ to: '/probes', label: 'the probe console' }] },
  // ── chapter 15: the research record ──────────────────────────────────────
  hypothesis: {
    app: [{ to: '/science#hypothesis-board', label: 'the hypothesis board' }],
    docs: [method('017-the-research-record', 'the research record')],
  },
  evidence: { app: [{ to: '/science#evidence-ledger', label: 'the evidence ledger' }] },
  verdict: {
    app: [{ to: '/science#the-loop-a-claim-goes-through', label: 'the loop a claim goes through' }],
  },
  'refutation-condition': {
    app: [{ to: '/science#hypothesis-board', label: 'each claim’s refuted_by' }],
  },
  // ── chapter 17: iteration 2's blind step 1 ───────────────────────────────
  'zemojtel-style-degradation': {
    app: [
      {
        to: '/steps/step-1#held-out-recall-against-the-cutoff-with-the-promise-it-missed',
        label: 'the recall curve the degraded queries produced',
      },
    ],
    docs: [
      {
        path: 'docs/iteration2/step-1/methodology/091-recall-at-the-full-population.md',
        label: 'the same degradation at the full population',
      },
    ],
  },
  'bootstrap-interval': {
    app: [
      {
        to: '/steps/step-1#held-out-recall-against-the-cutoff-with-the-promise-it-missed',
        label: 'the shaded band around each recall curve',
      },
      {
        to: '/steps/step-1#the-pre-registered-gates-including-the-three-that-failed',
        label: 'the gates those intervals were judged against',
      },
    ],
    docs: [
      {
        path: 'docs/iteration2/step-1/methodology/091-recall-at-the-full-population.md',
        label: 'the interval the full-population re-test was judged against',
      },
    ],
  },
};
