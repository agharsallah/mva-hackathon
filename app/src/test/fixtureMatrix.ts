/**
 * The request matrix the fixture dump walks: every path the registry answers, with the
 * params that actually change its payload. Shared by the baseline dump and the
 * equivalence test so both sides ask exactly the same questions.
 */
export const MATRIX: Array<[string, Record<string, string | number> | undefined]> = [
  ['/api/overview', undefined],
  ['/api/genome/allele-balance', undefined],
  ['/api/genome/contig-density', undefined],
  ['/api/genome/density-bins', undefined],
  ['/api/genome/density-bins', { chrom: '15' }],
  ['/api/genome/density-bins', { chrom: 'X' }],
  ['/api/genome/baf-bins', undefined],
  ['/api/genome/baf-bins', { chrom: '15' }],
  ['/api/callset/filters', undefined],
  ['/api/callset/genotypes', undefined],
  ['/api/callset/depth-distribution', undefined],
  ['/api/callset/substitutions', undefined],
  ['/api/callset/tstv', undefined],
  ['/api/callset/indel-lengths', undefined],
  ['/api/callset/observed-expected', undefined],
  ['/api/callset/funnel', undefined],
  ['/api/callset/zygosity-split', undefined],
  ['/api/callset/fields', undefined],
  ['/api/panel/genes', undefined],
  ['/api/panel/constraint', undefined],
  ['/api/panel/background', undefined],
  ['/api/panel/annotations', undefined],
  ['/api/panel/annotations', { gene: 'BUB1B' }],
  ['/api/panel/annotations', { gene: 'CEP57' }],
  ['/api/panel/locus', undefined],
  ['/api/panel/locus', { gene: 'TRIP13' }],
  ['/api/panel/het-pairs', undefined],
  ['/api/panel/het-pairs', { gene: 'CENPE' }],
  ['/api/panel/clinvar-presence', undefined],
  ['/api/panel/clinvar-presence', { gene: 'BUB1B' }],
  ['/api/panel/suppressed', undefined],
  ['/api/panel/suppressed', { gene: 'BUB1B' }],
  // The curated gene set the structure exhibits read their vocabulary from: three groups,
  // and the `in_panel` / `coding` flags that decide whether an allele can be painted and
  // whether a protein exists at all.
  ['/api/panel/structure-genes', undefined],
  ['/api/panel/gene-structure', undefined],
  ['/api/panel/gene-structure', { gene: 'TP53' }],
  // One row per gene that has its own committed AlphaFold trace, because the point of the
  // per-gene fixtures is that they are *different* models: one hash for all of them would
  // pass while every gene silently served BUB1B's backbone, which is what they replaced.
  ['/api/panel/protein-structure', undefined],
  ['/api/panel/protein-structure', { gene: 'TP53' }],
  ['/api/panel/protein-structure', { gene: 'CEP57' }],
  ['/api/panel/protein-structure', { gene: 'DICER1' }],
  ['/api/panel/gene-structure', { gene: 'CEP57' }],
  ['/api/panel/gene-structure', { gene: 'DICER1' }],
  ['/api/reads/runs', undefined],
  ['/api/reads/partitions', undefined],
  ['/api/reads/flowcell', undefined],
  ['/api/reads/flowcell', { lane: 2, read: 2, shard: 1 }],
  ['/api/reads/cycle-quality', undefined],
  ['/api/reads/quality-levels', undefined],
  ['/api/reads/yield', undefined],
  ['/api/catalog/objects', undefined],
  ['/api/catalog/tables', undefined],
  ['/api/catalog/columns', undefined],
  ['/api/provenance/lineage', undefined],
  ['/api/provenance/derivations', undefined],
  ['/api/provenance/sources', undefined],
  ['/api/provenance/reference', undefined],
  ['/api/probe/ledger', undefined],
  ['/api/science/hypotheses', undefined],
  ['/api/science/evidence', undefined],
  ['/api/search', { q: '15:1000000-1002000' }],
  ['/api/search', { q: 'BUB1B' }],
  ['/api/search', { q: 'rs1042522' }],
  ['/api/search', { q: 'nonsense query' }],
  ['/api/callset/region', { chrom: '15', start: 1000000, end: 1002000 }],
  ['/api/health/dependencies', undefined],
  // Phenotype: both term sets, because the delta between them is a result rather than a
  // display option, and a gene inside the panel plus one outside the captured set, which
  // exercises the fallback in the registry.
  ['/api/phenotype/terms', undefined],
  ['/api/phenotype/genes', undefined],
  ['/api/phenotype/genes', { term_set: 'with-parental' }],
  ['/api/phenotype/genes', { term_set: 'proband-only' }],
  ['/api/phenotype/delta', undefined],
  ['/api/phenotype/gene', { symbol: 'BUB1B' }],
  ['/api/phenotype/gene', { symbol: 'TRIP13' }],
  ['/api/phenotype/gene', { symbol: 'NOT_CAPTURED' }],
  // One iteration dossier, unparameterised: the endpoint answers with every
  // `submissions/<track>/iteration-<n>/` folder at once so a page can never render a
  // half-joined submission.
  ['/api/submissions', undefined],
  // The Track 2 report: one payload holding the mechanism card and all five snapshot tables.
  ['/api/track2', undefined],
];

export const key = (path: string, params?: Record<string, string | number>): string =>
  params
    ? `${path}?${new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)])).toString()}`
    : path;
