/**
 * The small decisions the Iterations page shares, kept out of the components so each one is
 * a pure function readable beside the sentence that explains it — and testable offline.
 *
 * Two numberings meet here. A **research iteration** is `iteration2` (the step maps' word, a
 * route through the case). A **submission folder** is `track2/iteration-4` (the `?it=` value
 * of `/submissions`). The catalogue picker takes either, which is why its keys are the two
 * spellings verbatim: one address, one catalogue, no translation table.
 */

import type {
  CatalogCoverage,
  CatalogDataset,
  ClaimCounts,
  DatasetRole,
  IterationCatalog,
  IterationsOverview,
  LineageStatus,
  ResearchIterationOverview,
  SubmissionIteration,
  SubmissionOverview,
} from '../../api/types';
import type { Tone } from '../../lib/palette';
import { iterationLabel } from '../steps/route';

/** One link of a hub row; `label` is plain text so the row stays a list of words. */
export interface HubLink {
  to: string;
  label: string;
  title?: string;
}

export type TrackKey = 'track1' | 'track2';
export const TRACKS: readonly TrackKey[] = ['track1', 'track2'];

/**
 * A lineage status as a colour. An edge is the goal (a recorded derivation, walkable back to
 * its inputs); a manifest is machinery that answers "where from" for fetched data, which has
 * nothing to derive; none is a gap — a dataset an entry names that no record explains.
 */
export const LINEAGE_TONE: Record<LineageStatus, Tone> = {
  edge: 'good',
  manifest: 'machinery',
  none: 'broken',
};

export const LINEAGE_MEANING: Record<LineageStatus, string> = {
  edge: 'a warehouse.data_lineage row records what produced it',
  manifest: 'a *.provenance.json beside it names its upstream and digests',
  none: 'named by an entry, but no edge or manifest explains it',
};

export const ROLE_MEANING: Record<DatasetRole, string> = {
  produced: 'a ledger edge or manifest attributes it to one of these entries',
  cited: 'the entries name it — which says nothing about whether they read or wrote it',
};

/** The claim statuses in the order a bar stacks them: settled first, then open, then retired. */
const CLAIM_ORDER = ['supported', 'refuted', 'testing', 'proposed', 'superseded'];

/** `{refuted: 3, supported: 10}` → `[['supported', 10], ['refuted', 3]]`, known statuses first. */
export function claimSegments(counts: ClaimCounts): [string, number][] {
  const rank = (s: string) => {
    const i = CLAIM_ORDER.indexOf(s);
    return i < 0 ? CLAIM_ORDER.length : i;
  };
  return Object.entries(counts)
    .filter(([, n]) => n > 0)
    .sort(([a], [b]) => rank(a) - rank(b) || a.localeCompare(b));
}

export const claimTotal = (counts: ClaimCounts): number =>
  Object.values(counts).reduce((n, v) => n + v, 0);

/** `iteration2` → `2`, for the short labels of the matrix and the flow diagram. */
export const iterationNumber = (iteration: string): string => iteration.replace(/\D/g, '');

/** The submission folders one research iteration feeds on one track. */
export function foldersFor(
  research: ResearchIterationOverview,
  track: TrackKey,
  submissions: SubmissionOverview[],
): SubmissionOverview[] {
  return submissions.filter((s) => s.track === track && research.submissions.includes(s.key));
}

/** How many declared steps feed a track: its own plus the ones both tracks quote (Track 1). */
export function stepsFor(research: ResearchIterationOverview, track: TrackKey): number {
  return track === 'track1'
    ? research.tracks.track1 + research.tracks.both
    : research.tracks.track2;
}

/** The facts the headline sentence states, counted off the payload rather than typed. */
export interface Headline {
  research: number;
  declared: number;
  planOnly: string[];
  folders: number;
  byState: Record<string, number>;
  /** Folders uploaded to the oracle — each one spent one of the budget. */
  uploaded: number;
  oracleFolders: number;
  panelFolders: number;
}

export function headline(data: IterationsOverview): Headline {
  const byState: Record<string, number> = {};
  for (const s of data.submissions) byState[s.state] = (byState[s.state] ?? 0) + 1;
  return {
    research: data.research.length,
    declared: data.research.filter((r) => r.declared).length,
    planOnly: data.research.filter((r) => !r.declared).map((r) => r.iteration),
    folders: data.submissions.length,
    byState,
    uploaded: data.submissions.filter((s) => s.uploaded && s.judged_by === 'oracle').length,
    oracleFolders: data.submissions.filter((s) => s.judged_by === 'oracle').length,
    panelFolders: data.submissions.filter((s) => s.judged_by === 'panel').length,
  };
}

/** Oracle uploads the whole project may spend; nothing renews it (CLAUDE.md, the challenge). */
export const ORACLE_BUDGET = 6;

// ── the catalogue picker ─────────────────────────────────────────────────────────────────

export interface CatalogOption {
  /** `iteration2` or `track2/iteration-4` — the `?cat=` value. */
  key: string;
  label: string;
  group: 'research' | 'submission';
  catalog: IterationCatalog | null;
}

/**
 * Every catalogue the explorer can open: research iterations from `/api/iterations`, and
 * submission folders whose catalogue arrives with `/api/submissions`. A folder whose dossier
 * payload has not arrived yet is still listed, with `catalog: null`, so the URL stays valid
 * while the second request is in flight.
 */
export function catalogOptions(
  data: IterationsOverview,
  dossiers: SubmissionIteration[] | undefined,
): CatalogOption[] {
  const byKey = new Map((dossiers ?? []).map((d) => [`${d.track}/iteration-${d.number}`, d]));
  return [
    ...data.research.map<CatalogOption>((r) => ({
      key: r.iteration,
      label: `research ${r.iteration.replace(/(\d+)$/, ' $1')}`,
      group: 'research',
      catalog: r.catalog,
    })),
    ...data.submissions.map<CatalogOption>((s) => ({
      key: s.key,
      label: `folder ${s.key}`,
      group: 'submission',
      catalog: byKey.get(s.key)?.catalog ?? null,
    })),
  ];
}

/** Lineage status counts of one catalogue, for the coverage bar: always all three keys. */
export function lineageCounts(datasets: CatalogDataset[]): Record<LineageStatus, number> {
  const out: Record<LineageStatus, number> = { edge: 0, manifest: 0, none: 0 };
  for (const d of datasets) out[d.lineage] += 1;
  return out;
}

/** `with_lineage / datasets` as a whole percentage, or null for an empty catalogue. */
export function coverageShare(c: CatalogCoverage): number | null {
  return c.datasets === 0 ? null : Math.round((100 * c.with_lineage) / c.datasets);
}

/** A share as a tone: all covered is the goal, most covered needs a look, less is a gap. */
export function coverageTone(c: CatalogCoverage): Tone {
  const share = coverageShare(c);
  if (share === null) return 'neutral';
  if (share === 100) return 'good';
  return share >= 50 ? 'decision' : 'broken';
}

/** `3f9a…` — a digest short enough to sit in a table cell. */
export const shortDigest = (sha: string): string => (sha ? `${sha.slice(0, 10)}…` : '—');

/** The two links every research-iteration page carries: the hub, and this iteration's data. */
export function iterationHubLinks(iteration?: string): HubLink[] {
  const hub: HubLink = {
    to: '/iterations',
    label: 'every iteration, both tracks',
    title: 'research iterations beside submission folders, with their states and lineage',
  };
  if (!iteration) return [hub];
  return [
    hub,
    {
      to: `/iterations?cat=${iteration}#data-catalog`,
      label: `the data ${iterationLabel(iteration)} rests on`,
      title: 'the datasets this iteration’s methodology entries name, with their lineage',
    },
  ];
}

/**
 * The oracle's reply as one phrase: the reply line is `Submission 1 | Rank points … | Full
 * match at rank 1`, and its last field is the verdict a cell has room for. The full line
 * stays available as a title.
 */
export const shortReply = (reply: string): string => reply.split('|').at(-1)?.trim() || reply;

/**
 * The research iteration a folder is *built from*: the newest one it cites. Every folder
 * cites entry 083 (the oracle's reply to submission 1), so research iteration 1 is cited by
 * all of them; "built from" separates the route that made the folder from the ones it quotes.
 */
export function primaryResearch(folder: SubmissionOverview): string | null {
  const sorted = [...folder.research].sort(
    (a, b) => Number(iterationNumber(a)) - Number(iterationNumber(b)),
  );
  return sorted.at(-1) ?? null;
}
