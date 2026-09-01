/**
 * Global providers, composed once so main.tsx stays a bootstrap file. Order and
 * behavior are unchanged from the previous inline nesting in main.tsx:
 * StrictMode > QueryClientProvider > BrowserRouter.
 */

import { StrictMode, type ReactNode } from 'react';
import { BrowserRouter } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
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
