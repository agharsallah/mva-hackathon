import { useCandidateFunnel } from '../../api/hooks';
import type { FunnelStageRow } from '../../api/types';
import { type Column, DataTable } from '../../components/DataTable';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Callout } from '../../components/Explainer';
import { baseLayout, Plot, type Trace } from '../../components/Plot';
import { Loaded } from '../../components/QueryState';
import { int, pct } from '../../lib/format';
import { C } from '../../lib/palette';

/**
 * The candidate waterfall — five million records down to a candidate pair set.
 *
 * A funnel is the pipeline's *argument*. Each row is one claim: "this filter is justified,
 * and this is what applying it cost". Read top to bottom it is the whole case-narrowing
 * story, and every stage that cannot be defended is visible as a cliff.
 *
 * Two honesty constraints shape the drawing.
 *
 * **The x axis is logarithmic.** 5,012,204 → 1 spans nearly seven decades. Plotly's own
 * `funnel` trace and any linear bar scale the last five stages to zero pixels, which turns
 * the interesting half of the argument into a blank strip. A log axis is the only encoding
 * where every stage is legible at once; the cost is that bar *length* is no longer
 * proportional to count, so the exact numbers are printed on the bars and tabulated below.
 *
 * **The scope change is drawn, not hidden.** Stages 1–3 are measured over the whole
 * callset. Stages 4–9 are measurable only inside the eight-gene candidate panel, because
 * that is the only region VEP annotation exists for — there is no genome-wide annotation
 * in this repository and therefore no genome-wide ranking. The colour changes at that
 * boundary, a dashed rule crosses it, and the first panel stage carries no "% of previous"
 * because it is not a subset of the row above it.
 */
export function CandidateFunnel() {
  const q = useCandidateFunnel();

  const columns: Column<FunnelStageRow>[] = [
    {
      key: 'no',
      header: '#',
      align: 'right',
      render: (r) => <span className="text-zinc-500">{r.stage_no}</span>,
    },
    {
      key: 'stage',
      header: 'stage',
      render: (r) => <span className="font-medium text-zinc-100">{r.stage}</span>,
    },
    {
      key: 'scope',
      header: 'scope',
      render: (r) => (
        <span className="font-mono font-semibold" style={{ color: scopeColor(r) }}>
          {r.scope}
        </span>
      ),
    },
    {
      key: 'n',
      header: 'n',
      align: 'right',
      render: (r) => <span className="text-zinc-100">{int(r.n)}</span>,
    },
    {
      key: 'prev',
      header: '% of previous',
      align: 'right',
      render: (r) =>
        r.of_previous_pct === null ? (
          <span
            className="text-zinc-600"
            title="not a subset of the row above — no ratio is meaningful"
          >
            n/a
          </span>
        ) : (
          pct(r.of_previous_pct, 2)
        ),
    },
    {
      key: 'note',
      header: 'why the filter is justified',
      render: (r) => <span className="text-zinc-400">{r.note}</span>,
    },
  ];

  return (
    <Exhibit
      title="The candidate waterfall — 5 million records to a candidate pair set"
      legend={
        <>
          One bar per filter stage, top to bottom in the order the pipeline applies them.{' '}
          <Chip color={C.machinery}>blue = genome scope</Chip>, measured over the whole callset ·{' '}
          <Chip color={C.raw}>purple = panel scope</Chip>, measurable only inside the eight-gene
          candidate panel · <Chip color={C.good}>green = the goal</Chip>, the candidate pair set.
          The <span style={{ color: C.decision }}>dashed yellow rule</span> is the scope change:{' '}
          <strong>annotation exists only inside the panel</strong> — 874 VEP-annotated alleles,
          nothing genome-wide — so every stage below it counts panel records only, and no
          genome-wide ranking exists to show. The x axis is <strong>logarithmic</strong>: the span
          is nearly seven decades, so bar length is not proportional to count and the printed number
          is the value — and a stage nothing survives has no position on a log axis, so it is
          written in as <em>0 — nothing survives this stage</em> rather than drawn. Hover a bar for
          its count, its share of the stage above, and why that filter is justified.{' '}
          <span className="text-zinc-500">n/a</span> under &ldquo;% of previous&rdquo; means the row
          is not a subset of the one above it.
        </>
      }
      reading="Each row is a claim the report has to defend: this filter is justified, and this is what it cost. The cliffs are the argument — rarity removes 96% of what the annotation covers, and protein-altering removes 94% of what survives that."
      data={q.data?.data}
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
    >
      <Loaded query={q} height={520}>
        {(rows) => {
          if (rows.length === 0) {
            return (
              <p className="p-6 text-center text-sm text-zinc-500">the funnel table is empty</p>
            );
          }
          const ordered = [...rows].sort((a, b) => a.stage_no - b.stage_no);
          const first = ordered[0];
          const last = ordered[ordered.length - 1];
          const boundary = ordered.findIndex((r) => r.scope === 'panel');

          return (
            <div className="space-y-3">
              <Waterfall rows={ordered} boundary={boundary} />
              <p className="text-[11px] text-zinc-500">
                {int(first.n)} {first.stage} → <span className="text-zinc-200">{int(last.n)}</span>{' '}
                {last.stage} · {ordered.filter((r) => r.scope === 'genome').length} genome-scoped
                stages, {ordered.filter((r) => r.scope === 'panel').length} panel-scoped
              </p>
              <DataTable rows={ordered} columns={columns} rowKey={(r) => String(r.stage_no)} />
              <Callout tone="decision" title="What the funnel does not claim">
                The bottom stage is a <em>shape</em>, not a diagnosis. Nothing here proves{' '}
                <strong>phase</strong> — that the two alleles sit on different parental copies
                rather than both on the same one — and with a single sample and no parents this
                dataset cannot settle it from genotypes alone. Nor is the panel scope a screen of
                the genome: a causal pair outside the eight genes would never enter this funnel,
                because no annotation exists to filter it with.
              </Callout>
            </div>
          );
        }}
      </Loaded>
    </Exhibit>
  );
}

/** Scope → colour. Blue = genome machinery, purple = the panel-scoped raw input. */
function scopeColor(row: FunnelStageRow): string {
  return row.scope === 'genome' ? C.machinery : C.raw;
}

/** Wrap a note so a hover card stays a card rather than one very long line. */
function wrap(text: string, width = 78): string {
  const out: string[] = [];
  let line = '';
  for (const word of text.split(' ')) {
    if (line && line.length + word.length + 1 > width) {
      out.push(line);
      line = word;
    } else {
      line = line ? `${line} ${word}` : word;
    }
  }
  if (line) out.push(line);
  return out.join('<br>');
}

function Waterfall({ rows, boundary }: { rows: FunnelStageRow[]; boundary: number }) {
  // Plotly places category index 0 at the bottom; `autorange: 'reversed'` puts stage 1 at
  // the top, which is the order the pipeline actually runs in.
  const labels = rows.map((r) => `${r.stage_no} · ${r.stage}`);
  const goal = rows[rows.length - 1];

  const hover =
    '<b>%{customdata[0]}</b><br>%{customdata[1]} · %{customdata[2]}<br>' +
    'share of the stage above: %{customdata[3]}<br><br>%{customdata[4]}<extra></extra>';
  // The unit deliberately changes down the funnel — a multi-allelic record carries several
  // alleles, and a gene with k alleles yields k(k−1)/2 pairs — so the note, which names the
  // change where it happens, is the only place the unit is asserted. Nothing is inferred
  // from a stage number here.
  const custom = (r: FunnelStageRow) => [
    r.stage,
    `${int(r.n)} surviving`,
    `${r.scope} scope`,
    r.of_previous_pct === null ? 'n/a — not a subset of the row above' : pct(r.of_previous_pct, 2),
    wrap(r.note),
  ];

  const lane = (name: string, color: string, keep: (r: FunnelStageRow) => boolean): Trace => {
    const picked = rows.filter(keep);
    return {
      type: 'bar',
      orientation: 'h',
      name,
      x: picked.map((r) => r.n),
      y: picked.map((r) => `${r.stage_no} · ${r.stage}`),
      marker: { color, line: { color: C.paper, width: 1 } },
      text: picked.map((r) => int(r.n)),
      textposition: 'outside',
      textfont: { color: C.ink, size: 11 },
      cliponaxis: false,
      customdata: picked.map(custom),
      hovertemplate: hover,
    };
  };

  return (
    <Plot
      height={Math.max(340, 44 * rows.length + 110)}
      data={[
        lane('genome scope', C.machinery, (r) => r.scope === 'genome'),
        lane('panel scope', C.raw, (r) => r.scope === 'panel' && r !== goal),
        lane('candidate pairs (the goal)', C.good, (r) => r === goal),
      ]}
      layout={baseLayout({
        margin: { l: 230, r: 70, t: 46, b: 52 },
        bargap: 0.35,
        xaxis: {
          type: 'log',
          // 0.5 keeps a single-row final stage off the axis line; 10^7.1 leaves room for
          // the printed count outside the widest bar.
          range: [Math.log10(0.5), 7.1],
          title: {
            text: 'surviving records / alleles / pairs (log scale)',
            font: { color: C.inkDim, size: 12 },
          },
          gridcolor: C.grid,
          zerolinecolor: C.grid,
          tickfont: { color: C.inkDim, size: 11 },
        },
        yaxis: {
          type: 'category',
          categoryorder: 'array',
          categoryarray: labels,
          autorange: 'reversed',
          automargin: true,
          gridcolor: 'rgba(0,0,0,0)',
          tickfont: { color: C.inkDim, size: 11 },
        },
        shapes:
          boundary > 0
            ? [
                {
                  type: 'line',
                  xref: 'paper',
                  x0: 0,
                  x1: 1,
                  yref: 'y',
                  y0: boundary - 0.5,
                  y1: boundary - 0.5,
                  line: { color: C.decision, width: 1.4, dash: 'dash' },
                },
              ]
            : [],
        annotations: [
          ...(boundary > 0
            ? [
                {
                  xref: 'paper',
                  yref: 'y',
                  x: 0,
                  y: boundary - 0.5,
                  xanchor: 'left',
                  yanchor: 'bottom',
                  showarrow: false,
                  align: 'left',
                  text:
                    '<b>scope narrows</b> — annotation exists only inside the 8-gene panel;<br>' +
                    'stages below count panel records only',
                  font: { color: C.decision, size: 10.5 },
                },
              ]
            : []),
          // log(0) has no position, so a stage that nothing survives draws no bar at all.
          // An empty stage is a finding, not a rendering gap, so it is written in.
          ...rows
            .filter((r) => r.n === 0)
            .map((r) => ({
              xref: 'paper',
              yref: 'y',
              x: 0,
              y: `${r.stage_no} · ${r.stage}`,
              xanchor: 'left',
              yanchor: 'middle',
              showarrow: false,
              text: '0 — nothing survives this stage',
              font: { color: C.inkDim, size: 11 },
            })),
        ],
        legend: { orientation: 'h', y: 1.14, x: 0, font: { color: C.inkDim, size: 11 } },
      })}
    />
  );
}
