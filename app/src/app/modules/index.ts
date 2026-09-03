/**
 * The module manifest: one entry per page. This list is the only place a page's
 * route, nav label and lazy chunk are declared — AppShell turns it into <Route>s
 * and Header turns it into nav links, so the two can never disagree.
 *
 * Order here is nav order. Paths and labels are copied verbatim from the router
 * and header they replace.
 */

import type { FeatureModule } from './types';

export const modules: FeatureModule[] = [
  {
    id: 'overview',
    path: '/',
    navLabel: 'Overview',
    description: 'Case tiles: delivery board and genotype mix.',
    load: () => import('../../pages/Overview'),
  },
  {
    id: 'genome',
    path: '/genome',
    navLabel: 'Genome',
    description: 'Genome-wide density, depth/VAF, allele balance and karyogram.',
    load: () => import('../../pages/Genome'),
  },
  {
    id: 'callset',
    path: '/callset',
    navLabel: 'Callset',
    description: 'Callset composition: QC funnel, substitutions, indel lengths, zygosity.',
    load: () => import('../../pages/Callset'),
  },
  {
    id: 'panel',
    path: '/panel',
    navLabel: 'Panel',
    description: 'Candidate genes: scorecards, domain lollipop, locus explorer, pair matrix.',
    load: () => import('../../pages/Panel'),
  },
  {
    id: 'compare',
    path: '/compare',
    navLabel: 'Compare',
    description: 'Candidate pair comparison: funnel, rarity, ClinVar presence.',
    load: () => import('../../pages/Compare'),
  },
  {
    id: 'reads',
    path: '/reads',
    navLabel: 'Reads',
    description: 'Read QC: delivered yield, lanes, flowcell, cycle quality.',
    load: () => import('../../pages/Reads'),
  },
  {
    id: 'probes',
    path: '/probes',
    navLabel: 'Probes',
    description: 'Oracle probes: builder, payload, job monitor, ledger, results.',
    load: () => import('../../pages/Probes'),
  },
  {
    id: 'phenotype',
    path: '/phenotype',
    navLabel: 'Phenotype',
    description:
      "The child's symptoms ranked against every curated gene, without reading a variant.",
    load: () => import('../../pages/Phenotype'),
  },
  {
    id: 'science',
    path: '/science',
    navLabel: 'Science',
    description: 'Hypothesis board, evidence ledger, probe budget, loop diagram.',
    load: () => import('../../pages/Science'),
  },
  {
    id: 'provenance',
    path: '/provenance',
    navLabel: 'Provenance',
    description: 'Lineage graph and derivation records.',
    load: () => import('../../pages/Provenance'),
  },
  {
    id: 'catalog',
    path: '/catalog',
    navLabel: 'Catalog',
    description: 'Delivery inventory, warehouse table catalog, read store.',
    load: () => import('../../pages/Catalog'),
  },
  {
    id: 'search',
    path: '/search',
    navLabel: 'Search',
    description: 'Cross-dataset search with a density strip.',
    load: () => import('../../pages/Search'),
  },
  {
    id: 'status',
    path: '/status',
    navLabel: 'Status',
    description: 'Dependency health board: what is working, what is not, and how to fix it.',
    load: () => import('../../pages/Status'),
  },
  {
    id: 'style-guide',
    path: '/style-guide',
    navLabel: 'Style',
    description: 'The design system itself: generated colour tokens, tones, scales, primitives.',
    load: () => import('../../pages/StyleGuide'),
  },
];
