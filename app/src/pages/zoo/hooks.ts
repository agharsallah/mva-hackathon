import { useEndpoint } from '../../api/hooks';
import type {
  ZooCase,
  ZooGeneScores,
  ZooLineage,
  ZooMerge,
  ZooModel,
  ZooRanks,
  ZooReport,
  ZooRun,
} from '../../api/types/zoo';

/**
 * One hook per `/api/zoo/*` route, over the app's own `useEndpoint` — so the zoo gets the
 * same envelope, the same cache policy, the same fixture fallback and the same
 * `{source, cachedAt, origin}` provenance line every other exhibit in this app gets.
 *
 * Nothing here names the case. A gene symbol and a model key are always *arguments*; the
 * defaults come from the payload (`ZooRanks.case`), never from a constant, because the whole
 * point of the zoo is that the next illness changes the config and not the code.
 */

/** The configured case: which gene is confirmed, which iteration, read from the zoo config. */
export const useZooCase = () => useEndpoint<ZooCase>('/api/zoo/case');

export const useZooModels = () => useEndpoint<ZooModel[]>('/api/zoo/models');

export const useZooRanks = (runId?: string) =>
  useEndpoint<ZooRanks>('/api/zoo/ranks', runId ? { run_id: runId } : undefined);

export const useZooMerge = (runId?: string) =>
  useEndpoint<ZooMerge>('/api/zoo/merge', runId ? { run_id: runId } : undefined);

export const useZooRuns = () => useEndpoint<ZooRun[]>('/api/zoo/runs');

export const useZooLineage = (table?: string) =>
  useEndpoint<ZooLineage>('/api/zoo/lineage', table ? { table } : undefined);

/** One rendered report: a lane's key, or `merged` for the cross-lane one. */
export const useZooReport = (key: string | null) =>
  useEndpoint<ZooReport>(`/api/zoo/reports/${key ?? 'merged'}`, undefined, { enabled: !!key });

/** Every allele of one gene with every lane's row — the case-agnostic entry point. */
export const useZooGene = (symbol: string | null) =>
  useEndpoint<ZooGeneScores>(`/api/zoo/scores/gene/${symbol ?? ''}`, undefined, {
    enabled: !!symbol,
  });
