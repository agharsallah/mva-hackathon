import type { Step1Overlap } from '../../../api/types';
import { Plot } from '../../../components/Plot';
import { C } from '../../../lib/palette';

/**
 * How much two independent rankers agree with ours, over the window each actually filled.
 *
 * The denominator is the service's own window, not the 300 we asked for: one of the two
 * returns fifty rows however many are requested, and dividing that truncation by 300 would
 * print a service limit as scientific disagreement.
 */
export function Overlap({ rows }: { rows: Step1Overlap[] }) {
  const labels = rows.map((r) => `${r.source} (top ${r.window})`);
  return (
    <Plot
      height={240}
      data={[
        {
          type: 'bar',
          orientation: 'h',
          x: rows.map((r) => r.shared),
          y: labels,
          name: 'shared with our ranking',
          marker: { color: C.good },
          text: rows.map((r) => `${r.shared} (${(r.share * 100).toFixed(1)}%)`),
          textposition: 'inside',
          hovertemplate: '%{y}: %{x} shared<extra></extra>',
        },
        {
          type: 'bar',
          orientation: 'h',
          x: rows.map((r) => r.unique),
          y: labels,
          name: 'only that ranker',
          marker: { color: C.broken },
          hovertemplate: '%{y}: %{x} unique<extra></extra>',
        },
      ]}
      layout={{
        barmode: 'stack',
        xaxis: { title: 'genes in that ranker’s window' },
        yaxis: { automargin: true },
        legend: { orientation: 'h', y: -0.3 },
        shapes: rows.map((r, i) => ({
          type: 'line' as const,
          x0: r.window / 2,
          x1: r.window / 2,
          y0: i - 0.4,
          y1: i + 0.4,
          line: { color: C.decision, dash: 'dash' as const },
        })),
      }}
    />
  );
}
