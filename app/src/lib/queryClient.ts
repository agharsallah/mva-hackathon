/**
 * The one QueryClient. Exported rather than built inside `main.tsx` because the whole-case
 * export fetches ~30 endpoints from outside React, and going through this client means it
 * reuses whatever the open page already loaded instead of asking the API twice.
 */

import { QueryClient } from '@tanstack/react-query';

export const FIVE_MIN = 5 * 60 * 1000;

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false, refetchOnWindowFocus: false, staleTime: FIVE_MIN },
  },
});
