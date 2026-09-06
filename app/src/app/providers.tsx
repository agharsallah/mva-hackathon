/**
 * Global providers, composed once so main.tsx stays a bootstrap file:
 * StrictMode > PersistQueryClientProvider > BrowserRouter.
 *
 * The query provider is the persisting one (`src/lib/queryPersistence.ts`): the cache is
 * restored from localStorage before the first render, so a reload paints from what the
 * browser already has instead of refetching every panel. With no storage available the
 * persister is `null` and this is the plain provider it always was.
 */

import { QueryClientProvider } from '@tanstack/react-query';
import { PersistQueryClientProvider } from '@tanstack/react-query-persist-client';
import { type ReactNode, StrictMode } from 'react';
import { BrowserRouter } from 'react-router-dom';

import { queryClient } from '../lib/queryClient';
import { createPersister, persistOptions } from '../lib/queryPersistence';

const persister = createPersister();

function QueryProvider({ children }: { children: ReactNode }) {
  if (!persister) return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  return (
    <PersistQueryClientProvider
      client={queryClient}
      persistOptions={{ persister, ...persistOptions }}
    >
      {children}
    </PersistQueryClientProvider>
  );
}

export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <StrictMode>
      <QueryProvider>
        <BrowserRouter>{children}</BrowserRouter>
      </QueryProvider>
    </StrictMode>
  );
}
