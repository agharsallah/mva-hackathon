/**
 * The shell: renders Header + routes from the module manifest instead of a
 * hand-written <Route> list, so nav and routing read from one array and cannot
 * drift. Layout, footer text and the catch-all redirect are unchanged from the
 * previous App.tsx.
 */

import { Navigate, Route, Routes } from 'react-router-dom';

import { Header } from '../components/Header';
import { ModuleBoundary } from './ModuleBoundary';
import { modules } from './modules';

export function AppShell() {
  return (
    <div className="min-h-screen bg-zinc-950">
      <Header items={modules.map((m) => ({ to: m.path, label: m.navLabel, preload: m.load }))} />
      <main className="mx-auto max-w-[1600px] space-y-6 px-5 py-6">
        <Routes>
          {modules.map((m) => (
            <Route
              key={m.id}
              path={m.path}
              element={<ModuleBoundary moduleId={m.id} load={m.load} />}
            />
          ))}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      <footer className="mx-auto max-w-[1600px] px-5 pb-8 text-[11px] leading-relaxed text-zinc-600">
        Understanding tool for one whole-genome case. No genomic coordinate is committed to this
        repository: the locus explorer shows real positions only when served by the live API, and
        its fixture uses a synthetic counter.
      </footer>
    </div>
  );
}
