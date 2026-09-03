import './index.css';

import { createRoot } from 'react-dom/client';

import { AppShell } from './app/AppShell';
import { AppProviders } from './app/providers';
import { initTheme } from './lib/theme';

// Before the first render, not inside it: the theme is a document attribute, and setting
// it after React has painted is a visible dark-to-light flash on every load.
initTheme();

createRoot(document.getElementById('root')!).render(
  <AppProviders>
    <AppShell />
  </AppProviders>,
);
