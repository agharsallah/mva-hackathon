/**
 * Global providers, composed once so main.tsx stays a bootstrap file:
 * StrictMode > QueryClientProvider > BrowserRouter.
 */

import { QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { StrictMode } from 'react';
import { BrowserRouter } from 'react-router-dom';

import { queryClient } from '../lib/queryClient';

export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>{children}</BrowserRouter>
      </QueryClientProvider>
    </StrictMode>
  );
}
