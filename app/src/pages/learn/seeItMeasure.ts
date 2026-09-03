/**
 * See-it links for the measurement half of the dictionary — chapters 2 to 6: reads, files,
 * variants, inheritance, the disease and its symptoms. Merged into `SEE_IT` by `seeIt.ts`.
 */

import { at, method, type SeeIt } from './seeItShared';

const GENOME_AB = '/genome#allele-balance-per-chromosome-the-aneuploidy-screen';
const CALLSET_FUNNEL = '/callset#filtering-funnel-what-the-caller-kept-and-what-it-vetoed';
const READS_QUALITY = '/reads#quality-across-the-read-where-confidence-decays';

export const SEE_IT_MEASURE: Record<string, SeeIt> = {
  // ── chapter 2: reads and files ────────────────────────────────────────────
  read: {
    app: [
      {
        to: '/reads#yield-per-lane-r1-against-r2',
        label: 'every read this case delivered, per lane',
      },
    ],
    docs: [method('005-fastq-structure-and-quality', 'FASTQ structure and quality')],
  },
  'base-quality-phred-score-q30': {
    app: [
      { to: READS_QUALITY, label: 'Q across the read' },
      {
        to: '/reads#base-quality-is-only-four-values-the-novaseq-binning',
        label: 'the four binned values',
      },
    ],
  },
  'paired-end': {
    app: [{ to: '/reads#yield-per-lane-r1-against-r2', label: 'R1 against R2' }],
  },
  'lane-flowcell-instrument': {
    app: [
      {
        to: '/reads#flowcell-occupancy-where-on-the-glass-the-reads-came-from',
        label: 'the flowcell, tile by tile',
      },
    ],
  },
  'coverage-depth-e-g-30': {
    app: [{ to: '/callset#read-depth-across-called-sites', label: 'depth at every called site' }],
    docs: [method('002-callset-quality-and-composition', 'callset quality and composition')],
  },
  fastq: {
    app: [
      {
        to: '/catalog#raw-delivery-every-object-we-were-given',
        label: 'the eight FASTQ files as delivered',
      },
    ],
  },
  'vcf-variant-call-format': {
    app: [
      {
        to: '/callset#the-callset-s-own-schema-every-field-its-vcf-header-declares',
        label: 'this VCF’s header, field by field',
      },
    ],
    docs: [method('001-vcf-provenance-and-structure', 'VCF provenance and structure')],
  },
  'filter-pass': {
    app: [{ to: CALLSET_FUNNEL, label: 'what PASSed and what was vetoed, by reason' }],
  },
  'ti-tv-ratio': {
    app: [
      {
        to: '/callset#substitution-spectrum-which-letter-changes-into-which',
        label: 'the substitution spectrum with Ts/Tv',
      },
    ],
  },
  'quality-binning-quantised-quality': {
    app: [
      {
        to: '/reads#base-quality-is-only-four-values-the-novaseq-binning',
        label: 'the NovaSeq binning',
      },
    ],
  },
  'region-contig-start-end': {
    app: [{ to: '/search', label: 'search a region of the callset' }],
    docs: [method('042-universal-search', 'universal search')],
  },
  // ── chapter 3: variants ───────────────────────────────────────────────────
  indel: {
    app: [{ to: '/callset#indel-length-spectrum', label: 'indel length spectrum' }],
  },
  'indel-length-spectrum': {
    app: [{ to: '/callset#indel-length-spectrum', label: 'this callset’s spectrum' }],
  },
  'substitution-spectrum-mutational-spectrum': {
    app: [
      {
        to: '/callset#substitution-spectrum-which-letter-changes-into-which',
        label: 'which letter changes into which',
      },
    ],
  },
  'vaf-variant-allele-fraction': {
    app: [
      {
        to: '/genome#depth-against-balance-two-axes-that-must-both-agree',
        label: 'depth against VAF',
      },
      { to: GENOME_AB, label: 'VAF per chromosome' },
    ],
  },
  'allele-balance': {
    app: [{ to: GENOME_AB, label: 'the aneuploidy screen' }],
    docs: [
      method(
        '004-sex-and-aneuploidy-from-allele-balance',
        'sex and aneuploidy from allele balance',
      ),
    ],
  },
  'mosaic-mosaicism': {
    app: [{ to: GENOME_AB, label: 'why blood shows no mosaic shift here' }],
  },
  zygosity: {
    app: [
      {
        to: '/callset#heterozygous-against-homozygous-and-what-each-half-s-ts-tv-says',
        label: 'het against hom',
      },
    ],
  },
  'het-hom-ratio': {
    app: [
      {
        to: '/callset#heterozygous-against-homozygous-and-what-each-half-s-ts-tv-says',
        label: 'this callset’s ratio',
      },
    ],
  },
  'variant-density': {
    app: [{ to: '/genome#density-along-each-chromosome-1-mb-bins', label: '1 Mb density strips' }],
  },
  'karyogram-ideogram': {
    app: [
      {
        to: '/genome#karyotype-chromosomes-to-scale-coloured-by-call-density',
        label: 'the ideogram',
      },
      {
        to: at('/genome', 'baf-karyogram-allele-balance-per-megabase'),
        label: 'the BAF karyogram',
      },
    ],
    docs: [method('037-baf-karyogram', 'BAF karyogram')],
  },
  'normalization-left-alignment-bcftools-norm': {
    app: [{ to: '/science', label: 'step 1 — normalize the callset' }],
  },
  // ── chapter 4: inheritance ───────────────────────────────────────────────
  'compound-heterozygous-comp-het': {
    app: [
      {
        to: '/panel#compound-het-pair-matrix-every-candidate-pair-in-one-gene-coloured-by-phase',
        label: 'every candidate pair in one gene',
      },
      {
        to: '/compare#pair-comparator-two-alleles-of-one-gene-held-against-each-other',
        label: 'two alleles held against each other',
      },
    ],
    docs: [
      method('038-pair-matrix', 'the pair matrix'),
      method('050-pair-comparator', 'the pair comparator'),
    ],
  },
  'phase-phasing': {
    app: [
      {
        to: '/panel#compound-het-pair-matrix-every-candidate-pair-in-one-gene-coloured-by-phase',
        label: 'pairs coloured by phase',
      },
    ],
    docs: [method('006-phasing-power-on-bub1b', 'phasing power on BUB1B')],
  },
  '1-2-genotype-multiallelic-site': {
    app: [{ to: '/#genotype-composition', label: 'the 1/2 slice of the genotype donut' }],
  },
  // ── chapter 5: the disease ───────────────────────────────────────────────
  aneuploidy: {
    app: [{ to: GENOME_AB, label: 'is any chromosome in the wrong number of copies?' }],
  },
  'mosaic-aneuploidy': {
    app: [{ to: GENOME_AB, label: 'the screen, per chromosome' }],
    docs: [
      method(
        '004-sex-and-aneuploidy-from-allele-balance',
        'sex and aneuploidy from allele balance',
      ),
    ],
  },
  'bub1b-protein-name-bubr1': {
    app: [
      {
        to: '/panel#mva-candidate-panel-kept-against-suppressed-per-gene',
        label: 'BUB1B on the panel scorecard',
      },
      { to: '/panel', label: 'its fold in 3D, alleles painted on residues' },
    ],
    docs: [method('057-protein-explorer-exhibit', 'the protein explorer')],
  },
  cep57: {
    app: [
      {
        to: '/panel#mva-candidate-panel-kept-against-suppressed-per-gene',
        label: 'CEP57 on the panel',
      },
    ],
  },
  trip13: {
    app: [
      {
        to: '/panel#mva-candidate-panel-kept-against-suppressed-per-gene',
        label: 'TRIP13 on the panel',
      },
    ],
  },
  // ── chapter 6: HPO ────────────────────────────────────────────────────────
  'hpo-human-phenotype-ontology': {
    app: [
      {
        to: '/phenotype#the-eight-features-the-child-was-described-by',
        label: 'the child’s eight terms',
      },
      {
        to: '/phenotype#every-curated-gene-ranked-by-the-child-s-symptoms-alone',
        label: 'genes ranked by symptoms alone',
      },
    ],
    docs: [
      {
        path: 'docs/step-3/methodology/056-phenotype-ranking-without-java.md',
        label: 'phenotype ranking without Java',
      },
    ],
  },
  'information-content-ic-t-log-p-t': {
    app: [
      {
        to: '/phenotype#why-a-gene-scored-what-it-scored',
        label: 'why a gene scored what it scored',
      },
    ],
  },
};
