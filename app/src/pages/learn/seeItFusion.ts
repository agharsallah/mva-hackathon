/**
 * Where the app shows step 6's words — the fusion half of the see-it table.
 *
 * Its own file for the reason the table is split at all: the set grows with the science, and
 * one term one entry is easier to keep true than one file of three hundred lines. Every
 * anchor below is an `Exhibit` title on `/steps/step-6`, and `learn-links.test.tsx` mounts
 * the page and proves it exists, so renaming an exhibit breaks the build rather than the link.
 */

import type { SeeIt } from './seeItShared';

export const SEE_IT_FUSION: Record<string, SeeIt> = {
  'reciprocal-rank-fusion-rrf': {
    app: [
      {
        to: '/steps/step-6#agreement-matrix-routes-against-the-leading-pairs',
        label: 'three orderings merged, and where each route actually put each pair',
      },
      {
        to: '/steps/step-6#the-fused-ranking-with-what-stands-behind-each-pair',
        label: 'the fused leaderboard, with both weightings side by side',
      },
    ],
    docs: [
      {
        path: 'docs/iteration2/step-6/methodology/108-the-ranking-frozen-before-anyone-looked.md',
        label: 'the fusion, its constants, and the digest recorded before the comparison',
      },
    ],
  },
  'rank-inheritance': {
    app: [
      {
        to: '/steps/step-6#agreement-matrix-routes-against-the-leading-pairs',
        label: 'the * cells — a rank copied from the gene onto every pair in it',
      },
    ],
  },
  'independent-evidence-count': {
    app: [
      {
        to: '/steps/step-6#which-witnesses-speak-for-each-leading-pair',
        label: 'four routes, four sources, and which of them is missing for the leader',
      },
    ],
  },
  'route-dependency-graph': {
    app: [
      {
        to: '/steps/step-6#which-route-read-what-and-where-two-of-them-read-the-same-thing',
        label: 'the dashed edges: two instruments reading one source',
      },
    ],
    docs: [
      {
        path: 'docs/iteration2/step-6/methodology/107-the-routes-and-which-of-them-earned-a-rank.md',
        label: 'the graph as declared, with the measurement that admitted each route',
      },
    ],
  },
  'leave-one-route-out': {
    app: [
      {
        to: '/steps/step-6#leave-one-route-out-does-any-single-instrument-carry-the-result',
        label: 'silence one route: the leader falls from rank 1 to rank 62',
      },
    ],
  },
  'agreement-matrix': {
    app: [
      {
        to: '/steps/step-6#agreement-matrix-routes-against-the-leading-pairs',
        label: 'the iteration&rsquo;s headline figure',
      },
    ],
  },
  'frozen-artifact-hash-before-the-comparison': {
    app: [
      {
        to: '/steps/step-6#freeze-receipt-the-ranking-predates-the-comparison',
        label: 'the file, its sha256, and the constants fixed before any route ran',
      },
    ],
    docs: [
      {
        path: 'docs/iteration2/step-6/methodology/109-what-the-mirror-found.md',
        label: 'the unblinding, and what the blind route found',
      },
    ],
  },
  'ranking-route-vs-confirmation-route': {
    app: [
      {
        to: '/steps/step-6#which-instrument-earned-a-vote',
        label: 'three routes admitted, one carried at weight 0 and kept visible',
      },
      {
        to: '/steps/step-6#what-each-instrument-measured-and-on-what',
        label: 'every instrument&rsquo;s measured error rate, side by side',
      },
    ],
  },
  unblinding: {
    app: [
      {
        to: '/steps/step-6#unblinding-what-the-mirror-found',
        label: 'the comparison, the decision row, and why no slot was spent',
      },
    ],
  },
  'decoy-null': {
    app: [
      {
        to: '/steps/step-6#how-far-down-the-matched-decoys-sit',
        label: 'the fusion&rsquo;s own decoy null: a control gene reaches rank 13',
      },
    ],
  },
};
