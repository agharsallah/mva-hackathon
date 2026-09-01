import { Chip, Exhibit } from '../../components/Exhibit';
import { Plot, baseLayout } from '../../components/Plot';
import { Loaded } from '../../components/QueryState';
import { useReadRuns, useSequencingYield } from '../../api/hooks';
import { C } from '../../lib/palette';
import { compact, dec, int } from '../../lib/format';

/**
 * What the delivery was *estimated* to hold, and how close that estimate turned out to be.
 *
 * Two numbers for the same thing, produced by two different methods:
 *
 * - **Estimated** (`results.sequencing_yield`, derived from `warehouse.fastq_profile`):
 *   extrapolated from each gzipped FASTQ's byte size and the length of its first read.
 *   Cheap — a `stat` call and one read — and it is what the pipeline planned capacity
 *   with before a single byte was decompressed.
 * - **Counted** (`/api/reads/runs`, off the parquet store): the exact census, available
 *   only because the conversion decompressed all 79 GB once.
 *
 * The estimate is the interesting half. Gzip's ratio depends on the data, so "bytes ÷
 * bytes-per-read" is a guess whose error nobody knows until the count exists. Here it
 * does, so the error is measurable rather than assumed — which is the whole reason this
 * figure is worth drawing next to the counted one on the same page.
 */

/** Lane strings arrive as the file name spells them (`L001`); the read store uses `1`. */
const laneNumber = (lane: string): number => Number(lane.replace(/\D/g, ''));

export function DeliveredYield() {
  const q = useSequencingYield();
  const counted = useReadRuns();

  return (
    <Exhibit
      title="Delivered yield per lane — the estimate against the count"
      legend={
        <>
          Grouped bars, one pair per flowcell lane.{' '}
          <Chip color={C.raw}>estimated from the delivered bytes</Chip> ·{' '}
          <Chip color={C.machinery}>counted in the parquet store</Chip>. Bar height = reads for the
          whole lane (R1 + R2). The table beneath carries the bases and the compressed size behind each
          bar; the error column is <span style={{ color: C.good }}>green</span> under ±2 % and{' '}
          <span style={{ color: C.decision }}>yellow</span> above it. A grey dash means the read store
          was unreachable, so there is nothing to compare against.
        </>
      }
      reading={
        <>
          The byte-size estimate lands <strong>0.32 % to 1.10 % high</strong>, and{' '}
          <strong>high on all four lanes</strong> — a one-sided bias from gzip&apos;s ratio, not noise.
          Over the whole delivery that is +0.75 %: 1,079,858,785 estimated against 1,071,835,104
          counted. Good enough to size a disk and plan the conversion; not good enough to quote as a
          read count, which is why every read figure elsewhere in this app comes from the counted store.
        </>
      }
      data={q.data?.data}
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
    >
      <Loaded query={q} height={340}>
        {(rows) => {
          const countedByLane = new Map<number, number>();
          for (const run of counted.data?.data ?? []) {
            countedByLane.set(run.lane, (countedByLane.get(run.lane) ?? 0) + run.reads);
          }
          const real = (lane: string) => countedByLane.get(laneNumber(lane));
          const errorPct = (r: (typeof rows)[number]) => {
            const truth = real(r.lane);
            return truth ? ((r.est_reads - truth) / truth) * 100 : null;
          };

          const totalEst = rows.reduce((a, r) => a + r.est_reads, 0);
          const totalGbases = rows.reduce((a, r) => a + r.est_gbases, 0);
          const totalGb = rows.reduce((a, r) => a + r.gigabytes, 0);
          const totalFiles = rows.reduce((a, r) => a + r.n_files, 0);
          const totalCounted = rows.reduce((a, r) => a + (real(r.lane) ?? 0), 0);

          return (
            <>
              <Plot
                height={252}
                data={[
                  {
                    type: 'bar',
                    name: 'estimated',
                    x: rows.map((r) => r.lane),
                    y: rows.map((r) => r.est_reads),
                    marker: { color: C.raw, line: { width: 0 } },
                    hovertemplate: '%{x} estimated<br>%{y:,} reads<extra></extra>',
                  },
                  {
                    type: 'bar',
                    name: 'counted',
                    x: rows.map((r) => r.lane),
                    y: rows.map((r) => real(r.lane) ?? 0),
                    marker: { color: C.machinery, line: { width: 0 } },
                    hovertemplate: '%{x} counted<br>%{y:,} reads<extra></extra>',
                  },
                ]}
                layout={baseLayout({
                  margin: { l: 66, r: 12, t: 8, b: 34 },
                  barmode: 'group',
                  bargap: 0.36,
                  xaxis: { type: 'category', gridcolor: 'rgba(0,0,0,0)', tickfont: { color: C.inkDim, size: 11 } },
                  yaxis: {
                    title: { text: 'reads in the lane', font: { color: C.inkDim, size: 12 } },
                    gridcolor: C.grid,
                    tickfont: { color: C.inkDim, size: 11 },
                  },
                  legend: { orientation: 'h', y: 1.15, x: 0, font: { color: C.inkDim, size: 11 } },
                })}
              />
              <div className="mt-3 overflow-x-auto">
                <table className="w-full border-collapse text-[11px]">
                  <thead className="text-zinc-500">
                    <tr>
                      <th className="border-b border-zinc-800 px-2 py-1 text-left font-medium">lane</th>
                      <th className="border-b border-zinc-800 px-2 py-1 text-right font-medium">files</th>
                      <th className="border-b border-zinc-800 px-2 py-1 text-right font-medium">delivered GB</th>
                      <th className="border-b border-zinc-800 px-2 py-1 text-right font-medium">est. Gbases</th>
                      <th className="border-b border-zinc-800 px-2 py-1 text-right font-medium">est. reads</th>
                      <th className="border-b border-zinc-800 px-2 py-1 text-right font-medium">counted reads</th>
                      <th className="border-b border-zinc-800 px-2 py-1 text-right font-medium">error</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r) => {
                      const err = errorPct(r);
                      const truth = real(r.lane);
                      return (
                        <tr key={r.lane}>
                          <td className="border-b border-zinc-900 px-2 py-1 font-mono text-zinc-300">{r.lane}</td>
                          <td className="border-b border-zinc-900 px-2 py-1 text-right font-mono text-zinc-400">{r.n_files}</td>
                          <td className="border-b border-zinc-900 px-2 py-1 text-right font-mono text-zinc-300">{dec(r.gigabytes, 2)}</td>
                          <td className="border-b border-zinc-900 px-2 py-1 text-right font-mono text-zinc-300">{dec(r.est_gbases, 2)}</td>
                          <td className="border-b border-zinc-900 px-2 py-1 text-right font-mono text-purple-400">{int(r.est_reads)}</td>
                          <td className="border-b border-zinc-900 px-2 py-1 text-right font-mono text-blue-400">
                            {truth === undefined ? <span className="text-zinc-600">—</span> : int(truth)}
                          </td>
                          <td
                            className="border-b border-zinc-900 px-2 py-1 text-right font-mono"
                            style={{ color: err === null ? C.absent : Math.abs(err) <= 2 ? C.good : C.decision }}
                          >
                            {err === null ? '—' : `${err > 0 ? '+' : ''}${dec(err, 2)} %`}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <div className="mt-2 grid gap-2 text-[11px] text-zinc-500 sm:grid-cols-4">
                <span>
                  {totalFiles} FASTQ files · <span className="font-mono text-zinc-300">{dec(totalGb, 2)} GB</span> gzipped
                </span>
                <span>
                  <span className="font-mono text-zinc-300">{dec(totalGbases, 2)}</span> Gbases estimated
                </span>
                <span>
                  <span className="font-mono text-purple-400">{compact(totalEst)}</span> reads estimated
                </span>
                <span>
                  {totalCounted > 0 ? (
                    <>
                      <span className="font-mono text-blue-400">{compact(totalCounted)}</span> reads counted
                    </>
                  ) : (
                    <span className="text-zinc-600">read store unreachable — nothing counted to compare</span>
                  )}
                </span>
              </div>
            </>
          );
        }}
      </Loaded>
    </Exhibit>
  );
}
