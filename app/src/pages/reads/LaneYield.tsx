import { useReadRuns } from '../../api/hooks';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Plot } from '../../components/Plot';
import { baseLayout } from '../../components/plotLayout';
import { Loaded } from '../../components/QueryState';
import { bytes, compact, int } from '../../lib/format';
import { C } from '../../lib/palette';

/**
 * Yield per lane. Paired-end sequencing reads each fragment from both ends, so R1 and R2
 * come in exactly equal counts by construction — a mismatch here would mean a truncated
 * or corrupted delivery, which is why the figure is worth drawing even though the answer
 * is boring.
 */
export function LaneYield() {
  const q = useReadRuns();
  return (
    <Exhibit
      title="Yield per lane — R1 against R2"
      legend={
        <>
          Grouped bars, one pair per flowcell lane.{' '}
          <Chip color={C.raw}>R1 (first end of the fragment)</Chip> ·{' '}
          <Chip color={C.machinery}>R2 (second end, sequenced in reverse)</Chip>. Bar height = reads
          delivered. Equal heights within a lane is the correct result for paired-end data.
        </>
      }
      reading="Every lane is exactly balanced: R1 and R2 counts are identical. Lane 1 was verified to the read — 136,586,642 in each direction."
      data={q.data?.data}
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
    >
      <Loaded query={q} height={340}>
        {(rows) => {
          const lanes = [...new Set(rows.map((r) => r.lane))].sort((a, b) => a - b);
          const byRead = (n: number) =>
            lanes.map((l) => rows.find((r) => r.lane === l && r.read_num === n));
          const total = rows.reduce((a, r) => a + r.reads, 0);
          const srcBytes = rows.reduce((a, r) => a + r.source_bytes, 0);
          const pqBytes = rows.reduce((a, r) => a + r.parquet_bytes, 0);
          const imbalanced = lanes.filter((l) => {
            const a = rows.find((r) => r.lane === l && r.read_num === 1)?.reads ?? 0;
            const b = rows.find((r) => r.lane === l && r.read_num === 2)?.reads ?? 0;
            return a !== b;
          });
          return (
            <>
              <Plot
                height={300}
                data={[1, 2].map((n) => ({
                  type: 'bar',
                  name: `R${n}`,
                  x: lanes.map((l) => `lane ${l}`),
                  y: byRead(n).map((r) => r?.reads ?? 0),
                  marker: { color: n === 1 ? C.raw : C.machinery, line: { width: 0 } },
                  hovertemplate: `R${n} %{x}<br>%{y:,} reads<extra></extra>`,
                }))}
                layout={baseLayout({
                  margin: { l: 66, r: 16, t: 8, b: 40 },
                  barmode: 'group',
                  bargap: 0.34,
                  xaxis: {
                    type: 'category',
                    gridcolor: 'rgba(0,0,0,0)',
                    tickfont: { color: C.inkDim, size: 11 },
                  },
                  yaxis: {
                    title: { text: 'reads', font: { color: C.inkDim, size: 12 } },
                    gridcolor: C.grid,
                    tickfont: { color: C.inkDim, size: 11 },
                  },
                  legend: { orientation: 'h', y: 1.12, x: 0, font: { color: C.inkDim, size: 11 } },
                })}
              />
              <div className="mt-2 grid gap-2 text-[11px] text-chrome-500 sm:grid-cols-4">
                <span>
                  total reads <span className="font-mono text-chrome-300">{int(total)}</span> (
                  {compact(total)})
                </span>
                <span>
                  gzip source <span className="font-mono text-raw-400">{bytes(srcBytes)}</span>
                </span>
                <span>
                  parquet store{' '}
                  <span className="font-mono text-machinery-400">{bytes(pqBytes)}</span>
                </span>
                <span className={imbalanced.length ? 'text-broken-400' : 'text-good-400'}>
                  {imbalanced.length
                    ? `R1/R2 mismatch on lane ${imbalanced.join(', ')}`
                    : 'R1/R2 balanced on every lane'}
                </span>
              </div>
            </>
          );
        }}
      </Loaded>
    </Exhibit>
  );
}
