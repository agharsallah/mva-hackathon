import type { ProbeCount, ProbeCountResult } from '../../api/types';
import { type Column, DataTable } from '../../components/DataTable';
import { Chip, Exhibit } from '../../components/Exhibit';
import { baseLayout, Plot } from '../../components/Plot';
import { dec, int } from '../../lib/format';
import { C, verdictColor } from '../../lib/palette';

/**
 * Pull the numeric expectation out of the server's `expected` field. Live, that field is a
 * whole sentence ("expected ~35 reads for a real single-copy 31-mer at this depth …"), so the
 * chart annotation gets the number and the caption keeps the sentence.
 */
function expectedReads(expected: string): number | null {
  const m = expected.match(/(\d+(\.\d+)?)/);
  return m ? Number(m[1]) : null;
}

/**
 * Probe result. A k-mer probe asks the raw reads a literal question: how many reads
 * contain this exact sequence? At ~44× coverage, a real 30-mer present on one of two
 * chromosome copies should be seen by roughly 35 reads. Far fewer means noise; zero means
 * the sequence is genuinely absent.
 */
export function ProbeResults({ result }: { result: ProbeCountResult }) {
  const expectation = expectedReads(result.expected);
  const counts = [...result.counts].sort((a, b) => b.total - a.total);

  const columns: Column<ProbeCount>[] = [
    {
      key: 'probe',
      header: 'probe',
      render: (r) => <span className="font-mono text-zinc-100">{r.probe}</span>,
    },
    { key: 'fwd', header: 'forward', align: 'right', render: (r) => int(r.forward) },
    { key: 'rev', header: 'reverse', align: 'right', render: (r) => int(r.reverse) },
    {
      key: 'total',
      header: 'total',
      align: 'right',
      render: (r) => <strong>{int(r.total)}</strong>,
    },
    { key: 'lanes', header: 'lanes', align: 'right', render: (r) => `${r.lanes}/4` },
    {
      key: 'verdict',
      header: 'verdict',
      render: (r) => (
        <span className="font-medium" style={{ color: verdictColor(r.verdict) }}>
          {r.verdict}
        </span>
      ),
    },
  ];

  return (
    <Exhibit
      title="Probe counts against the whole read store"
      legend={
        <>
          Stacked bars per probe: <Chip color={C.machineryDim}>forward-strand matches</Chip> ·{' '}
          <Chip color={C.machinery}>reverse-complement matches</Chip>; total height is the read
          count. Bar outline gives the verdict — <Chip color={C.good}>present</Chip> ·{' '}
          <Chip color={C.decision}>
            one lane only (suspicious: a real allele appears in every lane)
          </Chip>{' '}
          ·{' '}
          <Chip color={C.broken}>
            error level (a handful of reads, indistinguishable from sequencing noise)
          </Chip>{' '}
          · <Chip color={C.absent}>absent</Chip>. The dashed line is the expectation for a true
          heterozygous allele at this coverage.
        </>
      }
      reading={
        <>
          A probe is convincing when it clears the expectation line <em>and</em> appears in all four
          lanes on both strands. Anything sitting near zero but non-zero is the noise floor, not
          evidence.
        </>
      }
      data={result}
      source={`reads API · ${dec(result.seconds, 1)} s · ${result.root}`}
      origin="api"
    >
      <Plot
        height={Math.max(260, 34 * counts.length + 90)}
        data={[
          {
            type: 'bar',
            orientation: 'h',
            name: 'forward',
            y: counts.map((c) => c.probe).reverse(),
            x: counts.map((c) => c.forward).reverse(),
            marker: {
              color: C.machineryDim,
              line: { color: counts.map((c) => verdictColor(c.verdict)).reverse(), width: 2 },
            },
            hovertemplate: '%{y}<br>%{x:,} forward reads<extra></extra>',
          },
          {
            type: 'bar',
            orientation: 'h',
            name: 'reverse complement',
            y: counts.map((c) => c.probe).reverse(),
            x: counts.map((c) => c.reverse).reverse(),
            marker: {
              color: C.machinery,
              line: { color: counts.map((c) => verdictColor(c.verdict)).reverse(), width: 2 },
            },
            hovertemplate: '%{y}<br>%{x:,} reverse-complement reads<extra></extra>',
          },
        ]}
        layout={baseLayout({
          margin: { l: 140, r: 20, t: 8, b: 44 },
          barmode: 'stack',
          bargap: 0.3,
          xaxis: {
            title: { text: 'reads containing the probe', font: { color: C.inkDim, size: 12 } },
            gridcolor: C.grid,
            tickfont: { color: C.inkDim, size: 11 },
          },
          yaxis: {
            type: 'category',
            gridcolor: 'rgba(0,0,0,0)',
            tickfont: { color: C.inkDim, size: 10 },
          },
          shapes: expectation
            ? [
                {
                  type: 'line',
                  yref: 'paper',
                  y0: 0,
                  y1: 1,
                  x0: expectation,
                  x1: expectation,
                  line: { color: C.good, width: 1.4, dash: 'dash' },
                },
              ]
            : [],
          annotations: expectation
            ? [
                {
                  x: expectation,
                  yref: 'paper',
                  y: 1,
                  text: `expected ≈${expectation} reads`,
                  showarrow: false,
                  xanchor: 'left',
                  yanchor: 'top',
                  font: { color: C.good, size: 10 },
                },
              ]
            : [],
          legend: { orientation: 'h', y: 1.1, x: 0, font: { color: C.inkDim, size: 11 } },
        })}
      />
      <div className="mt-3">
        <DataTable rows={counts} columns={columns} rowKey={(r) => r.probe} maxHeight={320} />
      </div>
      <p className="mt-2 text-[11px] text-zinc-500">
        {counts.length} probes in one pass over the full store · {dec(result.seconds, 1)} s ·{' '}
        expectation from the server:{' '}
        <span className="font-mono text-zinc-300">{result.expected}</span>
      </p>
    </Exhibit>
  );
}
