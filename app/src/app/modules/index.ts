/**
 * The module manifest: one entry per page. This list is the only place a page's
 * route, nav label, title, group, parent and lazy chunk are declared — AppShell turns it
 * into <Route>s, Header into the three-tier nav, PageFrame into the h1 and journey links.
 *
 * Order here is journey order: within a group, the order a reader should walk the
 * pages; groups follow `NAV_GROUPS` (learn → data → case → decide → platform). Overview is
 * first and belongs to no group.
 *
 * A page that declares a `parent` is a *detail* of that page: it keeps its place in the
 * reading order but leaves the section row, appearing instead in the third row while its
 * branch is open. The seven step pages are details of `/steps`; without that, `decide`
 * listed twelve equal tabs and the shape of the journey was invisible.
 */

import { STEP_MODULES } from './steps.generated';
import type { FeatureModule } from './types';

/**
 * The generated research nodes under one track, in the order the generator emitted them:
 * each iteration followed by its steps. Spliced into the manifest rather than appended, so
 * journey order stays the order a reader should walk.
 */
const under = (track: string): FeatureModule[] =>
  STEP_MODULES.filter((m) => m.id === track || m.id.startsWith(`${track}-`));

export const modules: FeatureModule[] = [
  {
    id: 'overview',
    path: '/',
    navLabel: 'Overview',
    title: 'One child, one whole genome',
    description: 'The case in numbers, and the map of the five questions this app answers.',
    load: () => import('../../pages/Overview'),
  },

  // ── Learn: what do the words mean? ───────────────────────────────────────────
  {
    id: 'learn',
    path: '/learn',
    navLabel: 'Learn',
    title: 'The dictionary, as a course',
    group: 'learn',
    description:
      'Every domain word in the repository, chapter by chapter, ordered so each one only uses words defined before it — with its diagrams, and a link to where the app shows it.',
    load: () => import('../../pages/Learn'),
  },

  // ── Data: is the measurement trustworthy? ────────────────────────────────────
  {
    id: 'reads',
    path: '/reads',
    navLabel: 'Reads',
    title: 'Raw reads',
    group: 'data',
    description: 'Delivered yield, lanes, flowcell and per-cycle quality of the sequencing run.',
    load: () => import('../../pages/Reads'),
  },
  {
    id: 'callset',
    path: '/callset',
    navLabel: 'Callset',
    title: 'The callset',
    group: 'data',
    description:
      'What survived the caller’s filters, and whether the result looks like a healthy genome.',
    load: () => import('../../pages/Callset'),
  },
  {
    id: 'genome',
    path: '/genome',
    navLabel: 'Genome',
    title: 'Genome-wide view',
    group: 'data',
    description:
      'Allele balance, depth against VAF and the karyogram: is any chromosome in the wrong number of copies?',
    load: () => import('../../pages/Genome'),
  },

  // ── Case: which gene, and which pair inside it, is causal? ───────────────────
  {
    id: 'panel',
    path: '/panel',
    navLabel: 'Panel',
    title: 'Candidate gene panel',
    group: 'case',
    description:
      'Scorecards, constraint, suppressed calls, one gene opened at locus and protein level, and its pair matrix.',
    load: () => import('../../pages/Panel'),
  },
  {
    id: 'compare',
    path: '/compare',
    navLabel: 'Compare',
    title: 'Against the population',
    group: 'case',
    description:
      'Rarity in gnomAD, the candidate funnel, ClinVar presence and the two-variant pair comparator.',
    load: () => import('../../pages/Compare'),
  },
  {
    id: 'phenotype',
    path: '/phenotype',
    navLabel: 'Phenotype',
    title: 'Symptoms alone',
    group: 'case',
    description:
      'The child’s symptoms ranked against every curated gene, without reading a variant.',
    load: () => import('../../pages/Phenotype'),
  },
  {
    id: 'search',
    path: '/search',
    navLabel: 'Search',
    title: 'Search the callset',
    group: 'case',
    description: 'Look up a gene, region or record you chose yourself, with a density strip.',
    load: () => import('../../pages/Search'),
  },

  // ── Decide: what do we believe, and what has it cost to find out? ───────────
  // Science and Probes are the register and the budget; Track 1 and Track 2 are the two
  // deliverables, each opening onto its iterations and their steps (that subtree is
  // generated from the step maps, below); Submissions is what would be uploaded.
  {
    id: 'science',
    path: '/science',
    navLabel: 'Science',
    title: 'The research register',
    group: 'decide',
    description:
      'Hypothesis board, evidence ledger and the loop a claim goes through before it is believed.',
    load: () => import('../../pages/Science'),
  },
  {
    id: 'probes',
    path: '/probes',
    navLabel: 'Probes',
    title: 'Oracle probes',
    group: 'decide',
    description: 'Build and submit probes, watch jobs, and account for the 6-query budget.',
    load: () => import('../../pages/Probes'),
  },
  {
    id: 'track1',
    path: '/track1',
    navLabel: 'Track 1',
    title: 'Track 1 — which two broken copies, and of which gene',
    group: 'decide',
    description:
      'The question answered more than once on purpose: one card per iteration, each opening onto that iteration\u2019s own steps, claims, methodology entries and figures.',
    load: () => import('../../pages/Track1'),
  },
  ...under('track1'),
  {
    id: 'track2',
    path: '/track2',
    navLabel: 'Track 2',
    title: 'Track 2 — drug repurposing',
    group: 'decide',
    description:
      'The mechanism hand-off from Track 1, the market-approved candidates it implies, the trials and literature behind them, and the strategy that ends in one final suggestion.',
    load: () => import('../../pages/Track2'),
  },
  ...under('track2'),
  {
    id: 'zoo',
    path: '/zoo',
    navLabel: 'Zoo',
    title: 'The model zoo — several opinions, kept apart',
    group: 'decide',
    description:
      'Independent variant-effect models asked the same question: what each one could score, where they agree, where the merge puts the case pair, what the run cost, and the same view for any gene.',
    load: () => import('../../pages/Zoo'),
  },
  {
    id: 'submissions',
    path: '/submissions',
    navLabel: 'Submissions',
    title: 'The submission dossier',
    group: 'decide',
    description:
      'Every upload-ready iteration: what would be sent, the decode table it was designed against, the coordinate-free rows behind it, and what it has cost.',
    load: () => import('../../pages/Submissions'),
  },
  // ── Platform: what exists, where did it come from, and is it up? ─────────────
  {
    id: 'catalog',
    path: '/catalog',
    navLabel: 'Catalog',
    title: 'Data catalog',
    group: 'platform',
    description: 'Delivery inventory, the warehouse table catalog and the read store.',
    load: () => import('../../pages/Catalog'),
  },
  {
    id: 'provenance',
    path: '/provenance',
    navLabel: 'Provenance',
    title: 'Provenance',
    group: 'platform',
    description: 'Lineage graph, public reference inputs and every derivation record.',
    load: () => import('../../pages/Provenance'),
  },
  {
    id: 'status',
    path: '/status',
    navLabel: 'Status',
    title: 'Dependency status',
    group: 'platform',
    description: 'What is working, what is not, and the command that fixes it.',
    load: () => import('../../pages/Status'),
  },
  {
    id: 'style-guide',
    path: '/style-guide',
    navLabel: 'Style',
    title: 'Design system',
    group: 'platform',
    description:
      'Generated colour tokens, tones, scales and the primitives every page is built from.',
    load: () => import('../../pages/StyleGuide'),
  },
];
