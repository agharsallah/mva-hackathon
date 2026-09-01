import './index.css';

import { createRoot } from 'react-dom/client';

import { AppShell } from './app/AppShell';
import { AppProviders } from './app/providers';

createRoot(document.getElementById('root')!).render(
  <AppProviders>
    <AppShell />
  </AppProviders>,
);
