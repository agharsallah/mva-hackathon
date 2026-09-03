/**
 * The one QueryClient. Exported rather than built inside `main.tsx` because the whole-case
 * export fetches ~30 endpoints from outside React, and going through this client means it
 * reuses whatever the open page already loaded instead of asking the API twice.
 *
 * Retry policy: a network failure or a 5xx is retried twice with a short back-off — the API
 * may be restarting, and the reader should not have to click Retry for that. A 4xx is the
 * API saying no to *this* request; asking again gets the same answer, so it is not retried.
 */

import { QueryClient } from '@tanstack/react-query';

import { ApiError } from '../api/client';

export const FIVE_MIN = 5 * 60 * 1000;

export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (failureCount >= 2) return false;
  if (error instanceof ApiError && error.status < 500) return false;
  return true;
}

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: shouldRetry,
      retryDelay: (attempt) => Math.min(800 * 2 ** attempt, 3000),
      refetchOnWindowFocus: false,
      staleTime: FIVE_MIN,
    },
  },
});
