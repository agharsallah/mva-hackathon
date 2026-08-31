import { Suspense, lazy } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { Header } from './components/Header';
import { Skeleton } from './components/QueryState';

// Each page is its own chunk; Plotly then loads once, on the first page that draws.
const Overview = lazy(() => import('./pages/Overview'));
const Genome = lazy(() => import('./pages/Genome'));
const Callset = lazy(() => import('./pages/Callset'));
const Panel = lazy(() => import('./pages/Panel'));
const Compare = lazy(() => import('./pages/Compare'));
const Reads = lazy(() => import('./pages/Reads'));
const Probes = lazy(() => import('./pages/Probes'));
const Science = lazy(() => import('./pages/Science'));
const Provenance = lazy(() => import('./pages/Provenance'));
const Catalog = lazy(() => import('./pages/Catalog'));

export function App() {
  return (
    <div className="min-h-screen bg-zinc-950">
      <Header />
      <main className="mx-auto max-w-[1600px] space-y-6 px-5 py-6">
        <Suspense fallback={<Skeleton height={480} />}>
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/genome" element={<Genome />} />
            <Route path="/callset" element={<Callset />} />
            <Route path="/panel" element={<Panel />} />
            <Route path="/compare" element={<Compare />} />
            <Route path="/reads" element={<Reads />} />
            <Route path="/probes" element={<Probes />} />
            <Route path="/science" element={<Science />} />
            <Route path="/provenance" element={<Provenance />} />
            <Route path="/catalog" element={<Catalog />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </main>
      <footer className="mx-auto max-w-[1600px] px-5 pb-8 text-[11px] leading-relaxed text-zinc-600">
        Understanding tool for one whole-genome case. No genomic coordinate is committed to this
        repository: the locus explorer shows real positions only when served by the live API, and its
        fixture uses a synthetic counter.
      </footer>
    </div>
  );
}
