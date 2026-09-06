/**
 * The shell: Header + routes from the module manifest instead of a hand-written <Route>
 * list, so nav and routing read from one array and cannot drift. Every route renders
 * inside `PageFrame`, which adds the h1 and the journey links from the same manifest.
 */

import { Navigate, Route, Routes } from 'react-router-dom';

// Imported by their own paths, not through the components barrel: the shell is in the entry
// chunk, and the barrel's single module pulls DataTable, Plot and every other primitive
// into first paint with it (+23 kB raw, measured). Pages are lazy chunks, so they can
// keep using the barrel.
import { Footer } from '../components/Footer';
import { Header, type HeaderSection } from '../components/Header';
import { JourneyProvider } from '../components/journey';
import type { JourneyGroup } from '../components/journeyContext';
import { useTheme } from '../lib/theme';
import { ModuleBoundary } from './ModuleBoundary';
import { modules } from './modules';
import { pagesIn } from './modules/journey';
import { NAV_GROUPS } from './modules/types';
import { PageFrame } from './PageFrame';
import { ScrollToTop } from './ScrollToTop';

const home = modules[0];
const groups: JourneyGroup[] = NAV_GROUPS.map((g) => ({
  id: g.id,
  label: g.label,
  question: g.question,
  pages: pagesIn(g.id).map((m) => ({
    to: m.path,
    label: m.navLabel,
    title: m.title,
    description: m.description,
    preload: () => void m.load(),
  })),
}));
const sections: HeaderSection[] = groups.map((g) => ({
  id: g.id,
  label: g.label,
  question: g.question,
  pages: g.pages.map((p) => ({ to: p.to, label: p.label, preload: p.preload })),
}));

export function AppShell() {
  // Keyed by theme: every exhibit builds its Plotly layout / SVG / three.js scene from `C`,
  // which is read at render time and never re-read on its own. Remounting the frame is what
  // makes a theme switch reach the canvas half. React Query keeps the data, so nothing refetches.
  const theme = useTheme();
  return (
    <JourneyProvider groups={groups}>
      <ScrollToTop />
      <div className="min-h-screen bg-chrome-950">
        <Header
          home={{ to: home.path, label: home.navLabel, preload: home.load }}
          sections={sections}
        />
        <main className="mx-auto max-w-[1600px] space-y-6 px-5 py-6">
          <PageFrame key={theme}>
            <Routes>
              {modules.map((m) => (
                <Route
                  key={m.id}
                  path={m.path}
                  // Keyed by module id so a navigation remounts the boundary rather than
                  // updating it in place: without it, one module's caught error would keep
                  // showing on the next module's route.
                  element={<ModuleBoundary key={m.id} moduleId={m.id} load={m.load} />}
                />
              ))}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </PageFrame>
        </main>
        <Footer />
      </div>
    </JourneyProvider>
  );
}
