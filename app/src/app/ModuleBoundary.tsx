/**
 * Per-module isolation. Each page mounts inside its own error boundary and its own
 * Suspense boundary, so one broken module renders a contained error card instead of
 * blanking the whole app — the way one crashing microservice doesn't take the rest
 * of the site down.
 *
 * Retry re-runs the module's own `load()` (a fresh `lazy()` per attempt), not just a
 * remount of a cached component — a chunk that failed to fetch gets fetched again.
 */

import {
  Component,
  type ComponentType,
  lazy,
  type ReactNode,
  Suspense,
  useMemo,
  useState,
} from 'react';

import { Skeleton } from '../components/QueryState';
import type { FeatureModule } from './modules/types';

interface BoundaryProps {
  moduleId: string;
  children: ReactNode;
  onRetry: () => void;
}

interface BoundaryState {
  error: Error | null;
}

/** Mirrors QueryState's ErrorCard tone/classes without importing it (that file is out of scope). */
class ModuleErrorBoundary extends Component<BoundaryProps, BoundaryState> {
  state: BoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): BoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: { componentStack: string }) {
    console.error(`[module:${this.props.moduleId}] crashed`, error, info.componentStack);
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;
    return (
      <div className="rounded-lg border border-red-900/60 bg-red-950/25 p-4 text-sm">
        <div className="font-semibold text-red-300">
          Module &ldquo;{this.props.moduleId}&rdquo; failed to load
        </div>
        <p className="mt-1 font-mono text-xs text-red-400/80">{error.message}</p>
        <p className="mt-2 text-xs text-zinc-400">
          The rest of the app is unaffected. Retry re-fetches this module only.
        </p>
        <button
          type="button"
          onClick={() => {
            this.setState({ error: null });
            this.props.onRetry();
          }}
          className="mt-3 rounded-md border border-red-800/60 px-2.5 py-1 text-xs text-red-300 transition hover:bg-red-900/30"
        >
          Retry
        </button>
      </div>
    );
  }
}

export function ModuleBoundary({
  moduleId,
  load,
}: {
  moduleId: string;
  load: FeatureModule['load'];
}) {
  const [attempt, setAttempt] = useState(0);
  // Re-creating lazy(load) on retry issues a fresh import() call — a memoized
  // rejected promise from the first failed fetch is never reused.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const Page = useMemo<ComponentType>(() => lazy(load), [attempt]);

  return (
    <ModuleErrorBoundary moduleId={moduleId} onRetry={() => setAttempt((n) => n + 1)}>
      <Suspense key={attempt} fallback={<Skeleton height={480} />}>
        <Page />
      </Suspense>
    </ModuleErrorBoundary>
  );
}
