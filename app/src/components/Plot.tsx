/**
 * Thin React wrapper over plotly.js-dist-min.
 *
 * Plotly is loaded with a dynamic import, so the ~4 MB bundle lands in its own chunk and
 * first paint does not wait for it. Plotly.react() diffs on update, so re-renders are cheap.
 * The shared dark template lives in `./plotLayout` (`baseLayout`, `scene3d`), which keeps
 * the visual language identical to the repo's existing Plotly figures.
 */

import { useEffect, useRef, useState } from 'react';

import { baseLayout } from './plotLayout';

export type Trace = Record<string, unknown>;
export type Layout = Record<string, unknown>;

interface PlotlyApi {
  react(el: HTMLElement, data: Trace[], layout: Layout, config?: Layout): Promise<unknown>;
  purge(el: HTMLElement): void;
}

let plotlyPromise: Promise<PlotlyApi> | null = null;

function loadPlotly(): Promise<PlotlyApi> {
  if (!plotlyPromise) {
    plotlyPromise = import('plotly.js-dist-min').then((m) => {
      const mod = m as unknown as { default?: PlotlyApi } & PlotlyApi;
      return mod.default ?? mod;
    });
  }
  return plotlyPromise;
}

export interface PlotProps {
  data: Trace[];
  layout?: Layout;
  height?: number;
  /** Extra Plotly config; responsive + a trimmed modebar are already set. */
  config?: Layout;
}

export function Plot({ data, layout, height = 360, config }: PlotProps) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const el = ref.current;
    if (!el) return;
    loadPlotly()
      .then((Plotly) => {
        if (cancelled || !ref.current) return;
        setReady(true);
        return Plotly.react(
          ref.current,
          data,
          { ...baseLayout(), ...layout },
          {
            responsive: true,
            displaylogo: false,
            modeBarButtonsToRemove: ['select2d', 'lasso2d', 'autoScale2d'],
            ...config,
          },
        );
      })
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
    };
  }, [data, layout, config]);

  useEffect(() => {
    const el = ref.current;
    return () => {
      if (el && ready) loadPlotly().then((Plotly) => Plotly.purge(el));
    };
  }, [ready]);

  return (
    <div className="relative w-full" style={{ height }}>
      <div ref={ref} className="h-full w-full" />
      {!ready && !failed && (
        <div className="absolute inset-0 grid place-items-center text-xs text-chrome-500">
          loading plot engine…
        </div>
      )}
      {failed && (
        <div className="absolute inset-0 grid place-items-center text-xs text-broken-400">
          plot engine failed to load
        </div>
      )}
    </div>
  );
}
