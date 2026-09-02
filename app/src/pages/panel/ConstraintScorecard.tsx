import { usePanelConstraint } from '../../api/hooks';
import type { PanelConstraintRow } from '../../api/types';
import { type Column, DataTable } from '../../components/DataTable';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Callout } from '../../components/Explainer';
import { Plot } from '../../components/Plot';
import { baseLayout } from '../../components/plotLayout';
import { Loaded } from '../../components/QueryState';
import { dec, int } from '../../lib/format';
import { C } from '../../lib/palette';

/** The conventional line below which a gene is called loss-of-function intolerant. */
const LOEUF_CONSTRAINED = 0.35;

/**
 * Constraint scorecard — deliberately shown as *context, not as a ranking*.
 *
 * Constraint asks: across ~800k mostly-healthy people, does this gene carry fewer
 * protein-truncating variants than chance predicts? A gene that does is "constrained",
 * and for a *dominant* disease that is a strong prior for causality.
 *
 * MVA is **recessive**. A single broken copy of BUB1B or CEP57 produces a perfectly
 * healthy carrier, so those variants are not selected against and the genes score as
 * unconstrained. Using constraint to rank recessive candidates would therefore rank the
 * two established MVA genes last. That failure mode is the reason this exhibit exists.
 */
export function ConstraintScorecard() {
  const q = usePanelConstraint();

  /** null is missing data, so it renders as the word, never as a number. */
  const orUnknown = (v: number | null, render: (n: number) => string) =>
    v === null ? (
      <span className="text-chrome-600" title="no row in the constraint source">
        unknown
      </span>
    ) : (
      render(v)
    );

  const columns: Column<PanelConstraintRow>[] = [
    {
      key: 'gene',
      header: 'gene',
      render: (r) => <span className="font-mono text-chrome-100">{r.gene}</span>,
    },
    {
      key: 'loeuf',
      header: 'LOEUF',
      align: 'right',
      render: (r) =>
        r.loeuf === null ? (
          <span className="text-chrome-600" title="no row in the constraint source">
            unknown
          </span>
        ) : (
          <span style={{ color: r.loeuf < LOEUF_CONSTRAINED ? C.machinery : C.inkDim }}>
            {dec(r.loeuf, 2)}
          </span>
        ),
    },
    {
      key: 'pli',
      header: 'pLI',
      align: 'right',
      render: (r) => orUnknown(r.pli, (n) => dec(n, 2)),
    },
    {
      key: 'misz',
      header: 'missense z',
      align: 'right',
      render: (r) => orUnknown(r.mis_z, (n) => dec(n, 2)),
    },
    {
      key: 'oe',
      header: 'o/e LoF',
      align: 'right',
      render: (r) => orUnknown(r.oe_lof, (n) => dec(n, 3)),
    },
    {
      key: 'lof',
      header: 'LoF obs / exp',
      align: 'right',
      render: (r) =>
        r.lof_obs === null || r.lof_exp === null ? (
          <span className="text-chrome-600">unknown</span>
        ) : (
          `${int(r.lof_obs)} / ${dec(r.lof_exp, 1)}`
        ),
    },
    {
      key: 'plp',
      header: 'ClinVar P/LP',
      align: 'right',
      render: (r) => <span className="text-broken-400">{int(r.clinvar_plp)}</span>,
    },
    {
      key: 'vus',
      header: 'VUS',
      align: 'right',
      render: (r) => <span className="text-decision-400">{int(r.clinvar_vus)}</span>,
    },
    {
      key: 'ben',
      header: 'benign',
      align: 'right',
      render: (r) => <span className="text-good-400">{int(r.clinvar_benign)}</span>,
    },
    {
      key: 'note',
      header: 'how to read this gene',
      render: (r) => <span className="text-chrome-400">{r.note}</span>,
    },
  ];

  return (
    <Exhibit
      title="Constraint and ClinVar burden per panel gene — context, not a ranking"
      legend={
        <>
          Left axis, <Chip color={C.machinery}>blue bars</Chip>: LOEUF, how strongly the healthy
          population avoids losing a copy of this gene — <strong>lower is more intolerant</strong>.
          The <span style={{ color: C.decision }}>dashed yellow line at {LOEUF_CONSTRAINED}</span>{' '}
          is the conventional cut-off for calling a gene loss-of-function constrained. Right axis,{' '}
          <Chip color={C.broken}>red bars</Chip>: how many variants ClinVar already classes
          Pathogenic or Likely-pathogenic in that gene. A gene with{' '}
          <span className="text-chrome-500">no bar and an &ldquo;unknown&rdquo; tag</span> has no
          row in the constraint source — that is missing data, never a score of zero and never
          &ldquo;unconstrained&rdquo;.
        </>
      }
      reading="Read this as gene background, not as a candidate ranking. The two established MVA genes sit on the wrong side of the constraint line, and that is expected — see the callout."
      data={q.data?.data}
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
    >
      <Loaded query={q} height={460}>
        {(rows) => {
          const known = rows.filter((r) => r.loeuf !== null);
          const ordered = [...rows].sort((a, b) => (a.loeuf ?? Infinity) - (b.loeuf ?? Infinity));
          const missing = ordered.filter((r) => r.loeuf === null);
          const maxLoeuf = Math.max(1.4, ...known.map((r) => r.loeuf as number));

          return (
            <div className="space-y-3">
              <Plot
                height={340}
                data={[
                  {
                    type: 'bar',
                    name: 'LOEUF (lower = more intolerant)',
                    x: ordered.map((r) => r.gene),
                    y: ordered.map((r) => r.loeuf),
                    marker: { color: C.machinery, line: { width: 0 } },
                    hovertemplate: '%{x}<br>LOEUF %{y:.2f}<extra></extra>',
                  },
                  {
                    type: 'bar',
                    name: 'ClinVar P/LP variants',
                    yaxis: 'y2',
                    x: ordered.map((r) => r.gene),
                    y: ordered.map((r) => r.clinvar_plp),
                    marker: { color: C.broken, line: { width: 0 }, opacity: 0.85 },
                    hovertemplate: '%{x}<br>%{y:,} ClinVar P/LP<extra></extra>',
                  },
                ]}
                layout={baseLayout({
                  margin: { l: 60, r: 62, t: 8, b: 46 },
                  barmode: 'group',
                  bargap: 0.3,
                  xaxis: {
                    type: 'category',
                    gridcolor: 'rgba(0,0,0,0)',
                    tickfont: { color: C.inkDim, size: 11 },
                  },
                  yaxis: {
                    title: { text: 'LOEUF', font: { color: C.machinery, size: 12 } },
                    range: [0, maxLoeuf * 1.15],
                    gridcolor: C.grid,
                    tickfont: { color: C.machinery, size: 11 },
                  },
                  yaxis2: {
                    title: { text: 'ClinVar P/LP variants', font: { color: C.broken, size: 12 } },
                    overlaying: 'y',
                    side: 'right',
                    gridcolor: 'rgba(0,0,0,0)',
                    tickfont: { color: C.broken, size: 11 },
                  },
                  shapes: [
                    {
                      type: 'line',
                      xref: 'paper',
                      x0: 0,
                      x1: 1,
                      y0: LOEUF_CONSTRAINED,
                      y1: LOEUF_CONSTRAINED,
                      line: { color: C.decision, width: 1.2, dash: 'dash' },
                    },
                  ],
                  annotations: [
                    {
                      xref: 'paper',
                      x: 0.01,
                      y: LOEUF_CONSTRAINED,
                      yanchor: 'bottom',
                      text: `LOEUF ${LOEUF_CONSTRAINED} — constrained below this line`,
                      showarrow: false,
                      font: { color: C.decision, size: 10 },
                    },
                    // Missing constraint is labelled in place, so an absent bar can never be
                    // read as a bar of height zero.
                    ...missing.map((r) => ({
                      x: r.gene,
                      y: 0,
                      yanchor: 'bottom' as const,
                      text: 'unknown',
                      showarrow: false,
                      font: { color: C.absent, size: 10 },
                      textangle: -90,
                    })),
                  ],
                  legend: { orientation: 'h', y: 1.14, x: 0, font: { color: C.inkDim, size: 11 } },
                })}
              />
              <Callout
                tone="decision"
                title="Why the two known MVA genes look unconstrained — and why that is correct"
              >
                Constraint measures selection against losing <em>one</em> copy. MVA is{' '}
                <strong>recessive</strong>: a person with one broken copy of BUB1B or CEP57 is a
                healthy carrier, so those variants persist in the population and the gene scores
                near pLI 0 with a LOEUF well above {LOEUF_CONSTRAINED}. The dominant genes on this
                panel (TP53, DICER1) score the opposite way for the same reason. So a candidate
                ranking that sorts by constraint would put the two established MVA genes at the
                bottom. <strong>Constraint must not be used to rank recessive candidates.</strong>{' '}
                It is shown here because knowing the ranking is inverted is itself a result.
              </Callout>
              <DataTable rows={ordered} columns={columns} rowKey={(r) => r.gene} />
            </div>
          );
        }}
      </Loaded>
    </Exhibit>
  );
}
