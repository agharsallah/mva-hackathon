/**
 * Short paths through the dictionary. The fifteen chapters are the complete course; a track
 * is the fifteen-minute version for one job — the terms to know before opening one part of
 * the app, in the order the dictionary itself defines them. Slugs are dictionary anchors and
 * `src/test/learn-links.test.tsx` proves each one exists.
 */

export interface Track {
  id: string;
  title: string;
  /** Which pages this prepares the reader for. */
  forPages: string;
  slugs: string[];
}

export const TRACKS: Track[] = [
  {
    id: 'read-a-callset',
    title: 'Read a callset',
    forPages: 'Reads, Callset, Genome',
    slugs: [
      'dna',
      'genome',
      'chromosome',
      'gene',
      'allele',
      'genotype',
      'read',
      'base-quality-phred-score-q30',
      'paired-end',
      'coverage-depth-e-g-30',
      'fastq',
      'vcf-variant-call-format',
      'filter-pass',
      'ti-tv-ratio',
      'variant',
      'indel',
      'vaf-variant-allele-fraction',
      'allele-balance',
      'zygosity',
      'variant-density',
    ],
  },
  {
    id: 'why-this-child',
    title: 'Why this child',
    forPages: 'Panel, Compare, Phenotype',
    slugs: [
      'recessive',
      'compound-heterozygous-comp-het',
      'phase-phasing',
      '1-2-genotype-multiallelic-site',
      'null-allele',
      'hypomorph-hypomorphic',
      'aneuploidy',
      'mosaic-aneuploidy',
      'mva-mosaic-variegated-aneuploidy',
      'sac-spindle-assembly-checkpoint',
      'bub1b-protein-name-bubr1',
      'hpo-human-phenotype-ontology',
      'information-content-ic-t-log-p-t',
      'gnomad',
      'clinvar',
      'constraint-pli-loeuf-missense-z-score',
      'alphafold',
      'plddt',
    ],
  },
  {
    id: 'decide-and-score',
    title: 'Decide and score',
    forPages: 'Science, Probes',
    slugs: [
      'hypothesis',
      'refutation-condition',
      'evidence',
      'verdict',
      'oracle',
      'submission-probe',
      'probe-ledger',
      'k-mer',
      'precision-recall',
      'f-score',
      'ndcg-mrr-recall-k-top-1',
      'drug-repurposing',
    ],
  },
];
