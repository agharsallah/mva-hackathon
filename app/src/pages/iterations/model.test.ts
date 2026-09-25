import { describe, expect, it } from 'vitest';

import type {
  CatalogCoverage,
  IterationCatalog,
  IterationsOverview,
  ResearchIterationOverview,
  SubmissionOverview,
} from '../../api/types';
import { catalogOptions, claimSegments, coverageTone, foldersFor, headline } from './model';

const coverage = (datasets: number, with_lineage: number): CatalogCoverage => ({
  datasets,
  produced: 0,
  with_lineage,
  tables: 0,
  files: 0,
});

const catalog = (datasets = 0): IterationCatalog => ({
  available: true,
  note: '',
  entries: [],
  datasets: [],
  coverage: coverage(datasets, 0),
});

function research(iteration: string, submissions: string[], declared = true) {
  return {
    iteration,
    summary: '',
    declared,
    current: false,
    steps: 0,
    done: 0,
    open: 0,
    tracks: { track1: 0, track2: 0, both: 0 },
    claims: {},
    entries: { count: 0, first: '', last: '' },
    submissions,
    routes: { track1: null, track2: null },
    docs: '',
    catalog: catalog(),
  } satisfies ResearchIterationOverview;
}

function folder(track: string, number: number, extra: Partial<SubmissionOverview> = {}) {
  return {
    key: `${track}/iteration-${number}`,
    track,
    number,
    folder: '',
    state: 'draft',
    standing: '',
    uploaded: false,
    judged_by: track === 'track1' ? 'oracle' : 'panel',
    research: [],
    entries: 0,
    hypotheses: 0,
    figures: 0,
    steps: 0,
    reply: null,
    lineage: { available: true, edges: 0, sources: 0 },
    catalog: coverage(0, 0),
    ...extra,
  } satisfies SubmissionOverview;
}

const overview: IterationsOverview = {
  research: [research('iteration1', ['track1/iteration-1']), research('iteration3', [], false)],
  submissions: [
    folder('track1', 1, { state: 'frozen', uploaded: true }),
    folder('track2', 4, { state: 'ready', uploaded: true }),
  ],
  ledger: { available: true, edges: 0, attributed: 0, note: '' },
};

describe('the iterations model', () => {
  it('stacks settled claims before open ones and drops empty statuses', () => {
    expect(claimSegments({ testing: 1, refuted: 3, supported: 10, proposed: 0 })).toEqual([
      ['supported', 10],
      ['refuted', 3],
      ['testing', 1],
    ]);
  });

  it('lists only the folders of the asked track that the iteration feeds', () => {
    const r = research('iteration2', ['track1/iteration-2', 'track2/iteration-2']);
    const all = [folder('track1', 2), folder('track2', 2), folder('track1', 1)];
    expect(foldersFor(r, 'track1', all).map((f) => f.key)).toEqual(['track1/iteration-2']);
  });

  it('counts only oracle-scored uploads against the oracle budget', () => {
    const h = headline(overview);
    expect(h.uploaded).toBe(1);
    expect(h.planOnly).toEqual(['iteration3']);
    expect(h.byState).toEqual({ frozen: 1, ready: 1 });
  });

  it('offers both numberings as catalogue keys, a folder without its dossier as null', () => {
    const options = catalogOptions(overview, undefined);
    expect(options.map((o) => o.key)).toEqual([
      'iteration1',
      'iteration3',
      'track1/iteration-1',
      'track2/iteration-4',
    ]);
    expect(options.find((o) => o.key === 'track2/iteration-4')?.catalog).toBeNull();
  });

  it('colours coverage: all is green, half or more yellow, less red, empty grey', () => {
    expect(coverageTone(coverage(4, 4))).toBe('good');
    expect(coverageTone(coverage(4, 2))).toBe('decision');
    expect(coverageTone(coverage(4, 1))).toBe('broken');
    expect(coverageTone(coverage(0, 0))).toBe('neutral');
  });
});
