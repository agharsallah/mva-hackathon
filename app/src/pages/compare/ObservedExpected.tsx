import { useObservedExpected } from '../../api/hooks';
import type { ObservedExpectedRow } from '../../api/types';
import { type Column, DataTable } from '../../components/DataTable';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Plot } from '../../components/Plot';
import { baseLayout } from '../../components/plotLayout';
import { Loaded } from '../../components/QueryState';
import { int } from '../../lib/format';
import { C, oeVerdictColor } from '../../lib/palette';

/**
 * Observed against published healthy-genome expectations.
 *
 * The metrics have wildly different units (a ratio near 2, a depth near 44, a count near
 * five million), so a shared linear axis would be unreadable. Every row is therefore
 * plotted *relative to the midpoint of its own expected band*: 1.0 is dead centre of what
 * a normal genome looks like, and the band draws as a segment around it. The real numbers
 * with their units are in the table underneath and in the hover.
 */
export function ObservedExpected() {
  const q = useObservedExpected();

  const columns: Column<ObservedExpectedRow>[] = [
    {
      key: 'label',
      header: 'metric',
      render: (r) => <span className="text-zinc-200">{r.label}</span>,
    },
    {
      key: 'observed',
      header: 'observed',
      align: 'right',
      render: (r) => (
        <span style={{ color: oeVerdictColor(r.verdict) }}>
          {num(r.observed)} {r.unit}
        </span>
      ),
    },
    {
      key: 'expected',
      header: 'expected',
      align: 'right',
      render: (r) =>
        r.expected_low === r.expected_high ? (
          <span title="point estimate, not a band">{num(r.expected_low)}</span>
        ) : (
          `${num(r.expected_low)} – ${num(r.expected_high)}`
        ),
    },
    {
      key: 'verdict',
      header: 'verdict',
      render: (r) => (
        <span className="font-mono font-semibold" style={{ color: oeVerdictColor(r.verdict) }}>
          {r.verdict}
        </span>
      ),
    },
    {
      key: 'source',
      header: 'where the expectation comes from',
      render: (r) => <span className="text-zinc-400">{r.source}</span>,
    },
  ];

  return (
    <Exhibit
      title="Observed against published healthy-genome expectations"
      legend={
        <>
          One row per QC metric. The <Chip color={C.machineryDim}>grey-blue bar</Chip> is the
          published expected range and the tick <span style={{ color: C.inkDim }}>│</span> marks a
          point estimate (where the range has no width). The marker is what this callset actually
          measured: <Chip color={C.good}>within the band</Chip> ·{' '}
          <Chip color={C.broken}>above or below it</Chip> ·{' '}
          <Chip color={C.absent}>unknown (not measured)</Chip>. The x axis is each metric{' '}
          <em>relative to the midpoint of its own expected band</em> — 1.0 is dead centre — because
          the metrics do not share a unit. Real values and units are in the table below.
        </>
      }
      reading="Agreement is evidence the callset is technically sound and its biology can be believed. A metric outside its band is not automatically wrong, but it has to be explained before any variant call resting on it is trusted."
      data={q.data?.data}
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
    >
      <Loaded query={q} height={420}>
        {(rows) => {
          if (rows.length === 0) {
            return (
              <p className="p-6 text-center text-sm text-zinc-500">
                no comparable metrics returned
              </p>
            );
          }
          const counts = (v: string) => rows.filter((r) => r.verdict === v).length;
          return (
            <div className="space-y-3">
              <Dumbbell rows={rows} />
              <p className="text-[11px] text-zinc-500">
                <span className="text-emerald-400">{int(counts('within'))} within</span> ·{' '}
                <span className="text-red-400">
                  {int(counts('above') + counts('below'))} outside
                </span>{' '}
                · <span className="text-zinc-400">{int(counts('unknown'))} not measured</span>
              </p>
              <DataTable rows={rows} columns={columns} rowKey={(r) => r.metric} />
            </div>
          );
        }}
      </Loaded>
    </Exhibit>
  );
}

/** Midpoint of the expected band. Guards a zero midpoint so the scaling never divides by 0. */
const centre = (r: ObservedExpectedRow): number => {
  const c = (r.expected_low + r.expected_high) / 2;
  return c === 0 || !Number.isFinite(c) ? 1 : c;
};

function Dumbbell({ rows }: { rows: ObservedExpectedRow[] }) {
  // Drawn top-to-bottom in the order the API returns; Plotly's category axis runs the
  // other way, so the list is reversed once here rather than everywhere below.
  const ordered = [...rows].reverse();
  const rel = (v: number, r: ObservedExpectedRow) => v / centre(r);

  const banded = ordered.filter((r) => r.expected_low !== r.expected_high);
  const points = ordered.filter((r) => r.expected_low === r.expected_high);

  // One `lines` trace for every band, using null breaks between segments.
  const bandX: (number | null)[] = [];
  const bandY: (string | null)[] = [];
  for (const r of banded) {
    bandX.push(rel(r.expected_low, r), rel(r.expected_high, r), null);
    bandY.push(r.label, r.label, null);
  }

  const hover =
    '<b>%{customdata[0]}</b><br>observed %{customdata[1]} %{customdata[3]}<br>' +
    'expected %{customdata[2]} %{customdata[3]}<br>verdict: %{customdata[4]}<br>' +
    '<i>%{customdata[5]}</i><extra></extra>';
  const custom = (r: ObservedExpectedRow) => [
    r.label,
    num(r.observed),
    r.expected_low === r.expected_high
      ? num(r.expected_low)
      : `${num(r.expected_low)} – ${num(r.expected_high)}`,
    r.unit,
    r.verdict,
    r.source,
  ];

  return (
    <Plot
      height={Math.max(260, 46 * rows.length + 70)}
      data={[
        {
          type: 'scatter',
          mode: 'lines',
          name: 'expected range',
          x: bandX,
          y: bandY,
          line: { color: C.machineryDim, width: 14 },
          opacity: 0.85,
          hoverinfo: 'skip',
        },
        {
          type: 'scatter',
          mode: 'markers',
          name: 'expected point estimate',
          x: points.map((r) => rel(r.expected_low, r)),
          y: points.map((r) => r.label),
          marker: {
            color: C.inkDim,
            size: 18,
            symbol: 'line-ns-open',
            line: { width: 2, color: C.inkDim },
          },
          hoverinfo: 'skip',
        },
        {
          type: 'scatter',
          mode: 'markers',
          name: 'observed',
          x: ordered.map((r) => rel(r.observed, r)),
          y: ordered.map((r) => r.label),
          marker: {
            color: ordered.map((r) => oeVerdictColor(r.verdict)),
            size: 13,
            symbol: ordered.map((r) => (r.verdict === 'unknown' ? 'circle-open' : 'circle')),
            line: { color: C.paper, width: 1.5 },
          },
          customdata: ordered.map(custom),
          hovertemplate: hover,
        },
      ]}
      layout={baseLayout({
        margin: { l: 210, r: 24, t: 10, b: 48 },
        xaxis: {
          title: {
            text: 'observed ÷ midpoint of the expected band (1.0 = dead centre)',
            font: { color: C.inkDim, size: 12 },
          },
          gridcolor: C.grid,
          zerolinecolor: C.grid,
          tickfont: { color: C.inkDim, size: 11 },
        },
        yaxis: {
          type: 'category',
          automargin: true,
          gridcolor: 'rgba(0,0,0,0)',
          tickfont: { color: C.inkDim, size: 11 },
        },
        shapes: [
          {
            type: 'line',
            yref: 'paper',
            y0: 0,
            y1: 1,
            x0: 1,
            x1: 1,
            line: { color: C.inkDim, width: 1.2, dash: 'dash' },
          },
        ],
        legend: { orientation: 'h', y: 1.1, x: 0, font: { color: C.inkDim, size: 11 } },
      })}
    />
  );
}

/** Compact enough for a hover card, exact enough for a QC number. */
function num(v: number): string {
  if (!Number.isFinite(v)) return '—';
  if (Math.abs(v) >= 100_000) return v.toLocaleString('en-US');
  if (Number.isInteger(v)) return String(v);
  return String(Math.round(v * 1000) / 1000);
}
