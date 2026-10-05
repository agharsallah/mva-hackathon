/**
 * One react-query hook per endpoint. All of them are the same three lines, so the file
 * stays a table of contents for the API rather than logic.
 *
 * Retries are off: a down API should surface immediately, and a 503 from a proxied
 * upstream is a state to render, not to retry.
 */

import { useMutation, useQuery, useQueryClient, type UseQueryOptions } from '@tanstack/react-query';

import { STALE_TIME } from '../lib/queryClient';
import { get, type Params, type Result } from './client';
import type { HealthDependencies } from './types';

/** Long enough that a reload, or a walk back through the section, costs no request. */
const GC_TIME = 24 * 60 * 60 * 1000;

type Opts<T> = Omit<UseQueryOptions<Result<T>, Error>, 'queryKey' | 'queryFn'>;

/**
 * The one hook every endpoint hook is built from: a GET on an enveloped route, keyed by
 * its path and params. A page never calls `useQuery` itself — that is what keeps the
 * cache keys, the retry policy and the stale windows in one place.
 */
export function useEndpoint<T>(path: string, params?: Params, opts?: Opts<T>) {
  return useQuery<Result<T>, Error>({
    queryKey: [path, params ?? null],
    queryFn: ({ signal }) => get<T>(path, params, signal),
    retry: false,
    staleTime: STALE_TIME,
    gcTime: GC_TIME,
    refetchOnWindowFocus: false,
    ...opts,
  });
}

/** Background poll for the status board: quiet, because probing costs real round trips. */
export const HEALTH_POLL_MS = 1_800_000;

/** The endpoint every health control talks to — the board, and the per-card re-probe. */
export const HEALTH_PATH = '/api/health/dependencies';

/**
 * The board's react-query key for a given `refresh` flag.
 *
 * Exported because the per-card re-probe writes its reply straight into this entry
 * (`setQueryData`) instead of invalidating it: the API answers a partial re-probe with the
 * *whole* board — the named check freshly measured, the rest as last measured — so the
 * reply is already the new state of the page. Invalidating would instead throw away the
 * good rows and re-probe all of them, which is the cost the per-card button exists to avoid.
 */
export const healthQueryKey = (refresh: boolean) => [
  HEALTH_PATH,
  refresh ? { refresh: true } : null,
];

/**
 * Dependency health board.
 *
 * Two cadences, on purpose. `staleTime` stays short so *opening* the page always probes
 * rather than rendering a cached "up" from half an hour ago — a stale health card is worse
 * than no card. `refetchInterval` is long because each pass costs real round trips to
 * every backing service; an open tab should not generate traffic all day.
 *
 * `refresh` also bypasses the API's own short probe cache, so `?refresh` re-probes for real
 * instead of being served whatever the server measured last. It changes the query key too,
 * which is what makes navigating to that URL fetch immediately.
 */
export const useHealthDependencies = (refresh = false) =>
  useEndpoint<HealthDependencies>(HEALTH_PATH, refresh ? { refresh: true } : undefined, {
    staleTime: 5_000,
    refetchInterval: HEALTH_POLL_MS,
  });

/**
 * Re-probe **one** dependency, from that dependency's own card.
 *
 * The page-wide re-probe costs a round trip to every backing service at once. After
 * restarting a single service that is several requests nobody asked for, and against a slow
 * dependency it is also the slowest possible way to learn whether the one thing you just
 * fixed came back. `only=<id>&refresh=true` probes that check and serves the rest from the
 * API's per-check cache, so the button costs exactly one probe.
 *
 * A mutation rather than a query: it is an explicit action with a result, not a piece of
 * state the page reads, and `isPending` per id is what the card needs to disable itself.
 */
export function useReprobeCheck(refresh = false) {
  const client = useQueryClient();
  const mutation = useMutation<Result<HealthDependencies>, Error, string>({
    mutationFn: (id) => get<HealthDependencies>(HEALTH_PATH, { only: id, refresh: true }),
    onSuccess: (result) => client.setQueryData(healthQueryKey(refresh), result),
  });
  return {
    reprobe: mutation.mutate,
    /** The id currently in flight, or `null` — one card spins, not the whole board. */
    pendingId: mutation.isPending ? (mutation.variables ?? null) : null,
    error: mutation.error,
  };
}
