import { useIndelLengths } from '../../api/hooks';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Plot } from '../../components/Plot';
import { baseLayout } from '../../components/plotLayout';
import { Loaded } from '../../components/QueryState';
import { int } from '../../lib/format';
import { C } from '../../lib/palette';

/**
 * Indel length spectrum. The clinically interesting shape is the multiple-of-three
 * question: an indel whose length is not divisible by 3 shifts the reading frame and
 * usually destroys the protein — which is exactly the kind of change a recessive
 * loss-of-function MVA allele would be.
 */
export function IndelLengths() {
  const q = useIndelLengths();
  return (
    <Exhibit
      title="Indel length spectrum"
      legend={
        <>
          x = length in DNA letters, negative to the left.{' '}
          <Chip color={C.broken}>deletions (letters lost)</Chip> ·{' '}
          <Chip color={C.machinery}>insertions (letters gained)</Chip>. y is a log scale. Lengths
          divisible by three are marked with a <span style={{ color: C.decision }}>yellow</span>{' '}
          tick on the axis: those preserve the reading frame, all the others shift it.
        </>
      }
      reading="Geometric decay from ±1 bp, roughly symmetric, nothing beyond about 60 bp — the normal shape for short-read calling. Short indels are where a frameshift, the most destructive class of small variant, comes from."
      data={q.data?.data}
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
    >
      <Loaded query={q} height={340}>
        {(rows) => {
          const ordered = [...rows].sort((a, b) => a.length - b.length);
          const dels = ordered.filter((r) => r.length < 0);
          const ins = ordered.filter((r) => r.length > 0);
          const inFrame = ordered.filter((r) => Math.abs(r.length) % 3 === 0);
          const inFrameCount = inFrame.reduce((a, r) => a + r.count, 0);
          const total = ordered.reduce((a, r) => a + r.count, 0);
          return (
            <>
              <Plot
                height={320}
                data={[
                  {
                    type: 'bar',
                    name: 'deletions',
                    x: dels.map((r) => r.length),
                    y: dels.map((r) => r.count),
                    marker: { color: C.broken, line: { width: 0 } },
                    hovertemplate: '%{x} bp (deletion)<br>%{y:,} records<extra></extra>',
                  },
                  {
                    type: 'bar',
                    name: 'insertions',
                    x: ins.map((r) => r.length),
                    y: ins.map((r) => r.count),
                    marker: { color: C.machinery, line: { width: 0 } },
                    hovertemplate: '+%{x} bp (insertion)<br>%{y:,} records<extra></extra>',
                  },
                ]}
                layout={baseLayout({
                  margin: { l: 66, r: 16, t: 8, b: 46 },
                  bargap: 0.1,
                  barmode: 'overlay',
                  xaxis: {
                    title: {
                      text: 'indel length (bp) — deletions negative',
                      font: { color: C.inkDim, size: 12 },
                    },
                    gridcolor: C.grid,
                    tickfont: { color: C.inkDim, size: 11 },
                    zerolinecolor: C.inkDim,
                    tickvals: [-60, -30, -12, -9, -6, -3, -1, 1, 3, 6, 9, 12, 30, 60],
                  },
                  yaxis: {
                    type: 'log',
                    title: { text: 'records (log)', font: { color: C.inkDim, size: 12 } },
                    gridcolor: C.grid,
                    tickfont: { color: C.inkDim, size: 11 },
                  },
                  legend: { orientation: 'h', y: 1.1, x: 0, font: { color: C.inkDim, size: 11 } },
                })}
              />
              <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-micro text-chrome-400">
                <span>
                  deletions{' '}
                  <span className="font-mono text-broken-300">
                    {int(dels.reduce((a, r) => a + r.count, 0))}
                  </span>
                </span>
                <span>
                  insertions{' '}
                  <span className="font-mono text-machinery-300">
                    {int(ins.reduce((a, r) => a + r.count, 0))}
                  </span>
                </span>
                <span>
                  frame-preserving (length divisible by 3){' '}
                  <span className="font-mono text-decision-300">
                    {((inFrameCount / total) * 100).toFixed(1)}%
                  </span>{' '}
                  — the other {(100 - (inFrameCount / total) * 100).toFixed(1)}% shift the reading
                  frame
                </span>
              </div>
            </>
          );
        }}
      </Loaded>
    </Exhibit>
  );
}
