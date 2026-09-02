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
      <div className="rounded-lg border border-broken-900/60 bg-broken-950/25 p-4 text-sm">
        <div className="font-semibold text-broken-300">
          Module &ldquo;{this.props.moduleId}&rdquo; failed to load
        </div>
        <p className="mt-1 font-mono text-xs text-broken-400/80">{error.message}</p>
        <p className="mt-2 text-xs text-chrome-400">
          The rest of the app is unaffected. Retry re-fetches this module only.
        </p>
        <button
          type="button"
          onClick={() => {
            this.setState({ error: null });
            this.props.onRetry();
          }}
          className="mt-3 rounded-md border border-broken-800/60 px-2.5 py-1 text-xs text-broken-300 transition hover:bg-broken-900/30"
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
  /**
   * `load` is a real dependency, not decoration.
   *
   * Every route's element is this same component at the same position in the tree, so
   * React reconciles a navigation as a props update on the existing instance rather than a
   * fresh mount. Memoising on `[attempt]` alone therefore handed back the PREVIOUS module's
   * lazy component and the old page stayed on screen — clicking a nav link changed the URL
   * and nothing else, while a hard reload looked fine because it mounted from scratch.
   *
   * `attempt` stays in the list for the retry path: re-creating `lazy(load)` issues a fresh
   * `import()` instead of reusing a memoised rejected promise from a failed fetch.
   */
  const Page = useMemo<ComponentType>(() => {
    // Read, not merely listed: a bumped attempt is the retry signal, and the linter is
    // right that a dependency nothing reads is decoration.
    void attempt;
    return lazy(load);
  }, [load, attempt]);

  return (
    <ModuleErrorBoundary moduleId={moduleId} onRetry={() => setAttempt((n) => n + 1)}>
      <Suspense key={attempt} fallback={<Skeleton height={480} />}>
        <Page />
      </Suspense>
    </ModuleErrorBoundary>
  );
}
