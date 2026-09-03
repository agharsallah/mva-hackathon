import type {
  PhenotypeDelta,
  PhenotypeGeneDetail,
  PhenotypeRanking,
  PhenotypeTerms,
} from '../../api/types';
import type { Entry } from '../loader';
import { rows } from '../loader';

/**
 * Phenotype-domain fixtures — the only fixtures in this app that are **real numbers**.
 *
 * Everywhere else, an offline payload has to be shaped or synthesised, because the real
 * rows carry the proband's genomic coordinates and none of those may enter the repository.
 * This domain has no coordinates at all: it is gene symbols, ontology ids, and scores
 * computed from two public files. So these were captured verbatim from a live run against
 * HPO release `hp/releases/2026-06-23` and committed as they came out.
 *
 * That means the offline page shows the actual result, and `fixtures.test.ts` is checking
 * the real payload shape rather than an invented one.
 */

const RANKINGS: Record<string, string> = {
  'proband-only': 'phenotype-genes-proband-only',
  'with-parental': 'phenotype-genes-with-parental',
};

export const phenotypeEntries: Record<string, Entry> = {
  '/api/phenotype/terms': {
    source: 'src/mva/phenotype/terms.py',
    load: () => rows<PhenotypeTerms>('phenotype-terms'),
  },
  '/api/phenotype/genes': {
    source: 'ressources/reference/hpo_gene_scores.tsv',
    load: (p) => {
      const wanted = (p?.term_set as string | undefined) ?? 'proband-only';
      return rows<PhenotypeRanking>(RANKINGS[wanted] ?? RANKINGS['proband-only']);
    },
  },
  '/api/phenotype/delta': {
    source: 'ressources/reference/hpo_gene_scores.tsv',
    load: () => rows<PhenotypeDelta>('phenotype-delta'),
  },
  '/api/phenotype/gene': {
    source: 'ressources/reference/hpo_gene_scores.tsv',
    // Only the panel genes are captured. A gene outside that set falls back to the leading
    // candidate rather than throwing: offline mode is for reading the page, and an
    // exhibit that errors because a dropdown moved teaches nothing.
    load: async (p) => {
      const symbol = ((p?.symbol as string | undefined) ?? 'BUB1B').toUpperCase();
      const all = await rows<Record<string, PhenotypeGeneDetail>>('phenotype-gene-detail');
      return all[symbol] ?? all['BUB1B'];
    },
  },
};
