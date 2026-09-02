/**
 * The shell: renders Header + routes from the module manifest instead of a
 * hand-written <Route> list, so nav and routing read from one array and cannot
 * drift. Layout and the catch-all redirect are unchanged from the previous App.tsx;
 * the footer is now the `Footer` component instead of an inline paragraph.
 */

import { Navigate, Route, Routes } from 'react-router-dom';

// Imported by its own path, not through the components barrel: the shell is in the entry
// chunk, and the barrel's single module pulls DataTable, Plot and every other primitive
// into first paint with it (+23 kB raw, measured). Pages are lazy chunks, so they can
// keep using the barrel.
import { Footer } from '../components/Footer';
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
      <Footer />
    </div>
  );
}
