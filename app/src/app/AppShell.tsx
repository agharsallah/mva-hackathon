/**
 * The shell: Header + routes from the module manifest instead of a hand-written <Route>
 * list, so nav and routing read from one array and cannot drift. Every route renders
 * inside `PageFrame`, which adds the h1 and the journey links from the same manifest.
 */

import { Navigate, Route, Routes, useLocation } from 'react-router-dom';

// Imported by their own paths, not through the components barrel: the shell is in the entry
// chunk, and the barrel's single module pulls DataTable, Plot and every other primitive
// into first paint with it (+23 kB raw, measured). Pages are lazy chunks, so they can
// keep using the barrel.
import { Footer } from '../components/Footer';
import { Header, type HeaderNavItem, type HeaderSection } from '../components/Header';
import { JourneyProvider } from '../components/journey';
import type { JourneyGroup, JourneyPage } from '../components/journeyContext';
import { useTheme } from '../lib/theme';
import { ModuleBoundary } from './ModuleBoundary';
import { modules } from './modules';
import { childrenOf, topLevelIn } from './modules/journey';
import { NAV_GROUPS } from './modules/types';
import { PageFrame } from './PageFrame';
import { ScrollToTop } from './ScrollToTop';

const home = modules[0];
// A page and everything declared under it, to any depth. The research subtree is three
// levels — Track ▸ Iteration ▸ Step — and the shell builds it by following `parent` rather
// than by knowing how deep it goes, so a fourth level would need no change here.
const page = (m: (typeof modules)[number]): JourneyPage => {
  const children = childrenOf(m.id).map(page);
  return {
    to: m.path,
    label: m.navLabel,
    title: m.title,
    description: m.description,
    preload: () => void m.load(),
    ...(children.length > 0 ? { children } : {}),
  };
};

// A tree, not one flat list: a page that declares a parent is nested under it, so the section
// row stays a navigation instead of becoming an inventory of every step page.
const groups: JourneyGroup[] = NAV_GROUPS.map((g) => ({
  id: g.id,
  label: g.label,
  question: g.question,
  pages: topLevelIn(g.id).map(page),
  // A group the demo build has no page in (Decide, Platform) is dropped, not drawn empty.
})).filter((g) => g.pages.length > 0);
const navItem = (p: JourneyPage): HeaderNavItem => ({
  to: p.to,
  label: p.label,
  title: p.title,
  preload: p.preload,
  ...(p.children ? { children: p.children.map(navItem) } : {}),
});
const sections: HeaderSection[] = groups.map((g) => ({
  id: g.id,
  label: g.label,
  question: g.question,
  pages: g.pages.map(navItem),
}));

/**
 * Where the flat step routes used to live. `/steps` and `/steps/step-4` were iteration 2's
 * pages before the tree existed; a link to one, in a commit message or a methodology entry,
 * must still land on the page it meant.
 */
const MOVED: [string, string][] = [
  ['/steps', '/track1'],
  ...['1', '2', '3', '4', '5', '6', '8'].map((n): [string, string] => [
    `/steps/step-${n}`,
    `/track1/iteration2/step-${n}`,
  ]),
  // The zoo was a top-level Decide tab until it moved under the iteration that built it.
  ['/zoo', '/track1/iteration4/zoo'],
];

/** A moved address keeps its query and fragment: `/zoo?model=esm1b` must land on that lane. */
function Moved({ to }: { to: string }) {
  const { search, hash } = useLocation();
  return <Navigate to={{ pathname: to, search, hash }} replace />;
}

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
              {MOVED.map(([from, to]) => (
                <Route key={from} path={from} element={<Moved to={to} />} />
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
