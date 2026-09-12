import type { Step1Benchmark } from '../../../api/types';
import { Plot } from '../../../components/Plot';
import { C } from '../../../lib/palette';

/**
 * How often the symptom-only ranker finds the causal gene, as a function of the cutoff.
 *
 * One line per run — the 200-disease sample the claim was first tested against, and the
 * full eligible population it was re-tested on — each with its 95% bootstrap band. The
 * cutoff the target set is actually taken at is drawn as a vertical rule, and the 0.90
 * the claim promised as a horizontal one, so the gap between promise and measurement is
 * the figure rather than a caption.
 */
export function RecallCurve({
  sample,
  full,
  targetN,
  promised = 0.9,
}: {
  sample: Step1Benchmark | null;
  full: Step1Benchmark | null;
  targetN: number;
  promised?: number;
}) {
  const candidates: { run: Step1Benchmark | null; color: string; label: string }[] = [
    { run: sample, color: C.machinery, label: 'sampled run' },
    { run: full, color: C.good, label: 'full population' },
  ];
  const runs = candidates.flatMap(({ run, color, label }) => (run ? [{ run, color, label }] : []));

  const traces = runs.flatMap(({ run, color, label }) => {
    const x = run.curve.map((p) => p.n);
    const name = `${label} — ${run.diseases_run.toLocaleString()} diseases`;
    return [
      {
        type: 'scatter' as const,
        mode: 'lines' as const,
        x: [...x, ...[...x].reverse()],
        y: [
          ...run.curve.map((p) => p.interval[1]),
          ...[...run.curve].reverse().map((p) => p.interval[0]),
        ],
        fill: 'toself' as const,
        fillcolor: color,
        opacity: 0.16,
        line: { width: 0 },
        hoverinfo: 'skip' as const,
        showlegend: false,
      },
      {
        type: 'scatter' as const,
        mode: 'lines+markers' as const,
        x,
        y: run.curve.map((p) => p.recall),
        name,
        line: { color, width: 2 },
        marker: { color, size: 6 },
        customdata: run.curve.map((p) => [p.interval[0], p.interval[1]]),
        hovertemplate:
          'N=%{x}: recall %{y:.3f}<br>95% interval [%{customdata[0]:.3f}, %{customdata[1]:.3f}]<extra>' +
          name +
          '</extra>',
      },
    ];
  });

  return (
    <Plot
      height={340}
      data={traces}
      layout={{
        xaxis: { title: 'cutoff N (genes kept)', type: 'log' },
        yaxis: { title: 'held-out recall', range: [0, 1] },
        legend: { orientation: 'h', y: -0.25 },
        shapes: [
          {
            type: 'line',
            x0: targetN,
            x1: targetN,
            yref: 'paper',
            y0: 0,
            y1: 1,
            line: { color: C.decision, dash: 'dash' },
          },
          {
            type: 'line',
            xref: 'paper',
            x0: 0,
            x1: 1,
            y0: promised,
            y1: promised,
            line: { color: C.broken, dash: 'dot' },
          },
        ],
        annotations: [
          {
            x: Math.log10(targetN),
            y: 1,
            yref: 'paper',
            text: `N = ${targetN}, the cutoff taken`,
            showarrow: false,
            xanchor: 'left',
            font: { color: C.decision, size: 11 },
          },
          {
            xref: 'paper',
            x: 0,
            y: promised,
            text: `${promised.toFixed(2)} promised`,
            showarrow: false,
            yanchor: 'bottom',
            xanchor: 'left',
            font: { color: C.broken, size: 11 },
          },
        ],
      }}
    />
  );
}
