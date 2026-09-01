import { useMemo } from 'react';

import { usePanelAnnotations } from '../../api/hooks';
import type { PanelAnnotationRow } from '../../api/types';
import { Select } from '../../components/Controls';
import { Chip, Exhibit } from '../../components/Exhibit';
import { baseLayout, Plot } from '../../components/Plot';
import { Loaded } from '../../components/QueryState';
import { withoutCoordinates } from '../../lib/aiExport/redact';
import { int } from '../../lib/format';
import { C, impactColor } from '../../lib/palette';
import { known, useUrlState } from '../../lib/urlstate';
import { af, geneOptions, IMPACT_ORDER, isPathogenic, matchesGene } from './rarity';

/** Where rows with no defined VAF (`1/2` multiallelic) are parked, below the 0 line. */
const VAF_NA = -0.06;

/**
 * Rarity against the patient's own evidence.
 *
 * x is how common the variant is in ~800k mostly-healthy people; y is how much of the
 * patient's own reads carry it. A causal recessive variant has to sit at the far left —
 * and the very leftmost lane is the one that matters most, because "absent from gnomAD"
 * is rarer than any measurable frequency. Novel variants are therefore given their own
 * lane rather than being dropped for having no x value.
 */
export function RarityScatter() {
  const q = usePanelAnnotations();
  // Same `gene` key as the Panel page's exhibits — one word for one idea across the app. The
  // default differs (here: every gene at once), and a default writes no parameter, so the two
  // pages never inherit each other's selection by accident. See lib/urlstate.
  const [param, setGene] = useUrlState('gene', 'ALL');
  const options = q.data ? geneOptions(q.data.data) : [{ value: 'ALL', label: 'All genes' }];
  const gene = known(
    param,
    options.map((o) => o.value),
    'ALL',
  );
  // The rows carry the proband's real chromosome and position; an export must not.
  const exportData = useMemo(
    () =>
      q.data ? withoutCoordinates(q.data.data.filter((r) => matchesGene(r, gene))) : undefined,
    [q.data, gene],
  );

  return (
    <Exhibit
      title="Rarity in the healthy population against the patient's own allele fraction"
      controls={<Select value={gene} options={options} onChange={setGene} label="gene" />}
      legend={
        <>
          One point per annotated panel record. x = gnomAD allele frequency on a log axis (left =
          rarer); y = VAF, the fraction of the patient&apos;s reads carrying the variant. Colour =
          VEP impact: <Chip color={C.broken}>HIGH (truncates the protein)</Chip> ·{' '}
          <Chip color={C.decision}>MODERATE (changes an amino acid)</Chip> ·{' '}
          <Chip color={C.machinery}>LOW / MODIFIER (silent or non-coding)</Chip>. A{' '}
          <span style={{ color: C.ink }}>white ring</span> marks a ClinVar pathogenic assertion. Two
          lanes sit outside the normal grid: the <strong>novel lane</strong> left of the dashed
          vertical rule holds variants <em>absent from gnomAD</em> (no frequency exists — they are
          not frequency zero), and the <strong>VAF n/a lane</strong> below the dashed horizontal
          rule holds <span className="font-mono">1/2</span> multiallelic records, where a single
          alternate fraction is undefined.
        </>
      }
      reading="Read right to left. Everything on the right is common in healthy people and therefore cannot cause a rare recessive disease on its own. The candidates live in the far-left column and the novel lane, and a red or yellow point there with a VAF near 0.5 is a heterozygous, protein-altering, population-absent variant — the shape a compound-het partner has to have."
      data={exportData}
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
    >
      <Loaded query={q} height={480}>
        {(rows) => <Scatter rows={rows.filter((r) => matchesGene(r, gene))} />}
      </Loaded>
    </Exhibit>
  );
}

function Scatter({ rows }: { rows: PanelAnnotationRow[] }) {
  const view = useMemo(() => build(rows), [rows]);
  if (rows.length === 0) {
    return (
      <p className="p-6 text-center text-sm text-zinc-500">no annotated records for this gene</p>
    );
  }
  const { traces, novelX, divider, novels, noVaf } = view;

  return (
    <>
      <Plot
        height={440}
        data={traces}
        layout={baseLayout({
          margin: { l: 62, r: 20, t: 10, b: 52 },
          xaxis: {
            type: 'log',
            title: {
              text: 'gnomAD allele frequency (log) — rarer to the left',
              font: { color: C.inkDim, size: 12 },
            },
            range: [Math.log10(novelX / 2.4), Math.log10(1.4)],
            gridcolor: C.grid,
            tickfont: { color: C.inkDim, size: 11 },
          },
          yaxis: {
            title: {
              text: 'VAF (fraction of the patient’s reads)',
              font: { color: C.inkDim, size: 12 },
            },
            range: [VAF_NA - 0.05, 1.06],
            gridcolor: C.grid,
            tickfont: { color: C.inkDim, size: 11 },
          },
          shapes: [
            {
              type: 'line',
              yref: 'paper',
              y0: 0,
              y1: 1,
              x0: Math.log10(divider),
              x1: Math.log10(divider),
              line: { color: C.inkDim, width: 1.2, dash: 'dash' },
            },
            {
              type: 'line',
              xref: 'paper',
              x0: 0,
              x1: 1,
              y0: VAF_NA / 2,
              y1: VAF_NA / 2,
              line: { color: C.inkDim, width: 1, dash: 'dot' },
            },
            {
              type: 'line',
              xref: 'paper',
              x0: 0,
              x1: 1,
              y0: 0.5,
              y1: 0.5,
              line: { color: C.inkDim, width: 1, dash: 'dash' },
            },
          ],
          annotations: [
            {
              x: Math.log10(novelX),
              y: 1.04,
              text: `novel · absent from gnomAD (${novels})`,
              showarrow: false,
              font: { color: C.raw, size: 10 },
              textangle: 0,
            },
            {
              xref: 'paper',
              x: 1,
              y: VAF_NA,
              xanchor: 'right',
              text: `VAF n/a — 1/2 multiallelic (${noVaf})`,
              showarrow: false,
              font: { color: C.inkDim, size: 10 },
            },
            {
              xref: 'paper',
              x: 0.995,
              y: 0.5,
              xanchor: 'right',
              yanchor: 'bottom',
              text: 'VAF 0.50 — one of two copies',
              showarrow: false,
              font: { color: C.inkDim, size: 10 },
            },
          ],
          legend: { orientation: 'h', y: 1.12, x: 0, font: { color: C.inkDim, size: 11 } },
        })}
      />
      <p className="mt-2 text-[11px] text-zinc-500">
        {int(rows.length)} records · <span className="text-purple-400">{int(novels)}</span> absent
        from gnomAD ·{' '}
        <span className="text-zinc-300">
          {int(rows.filter((r) => isPathogenic(r.clin_sig)).length)}
        </span>{' '}
        with a ClinVar pathogenic assertion
      </p>
    </>
  );
}

/** Deterministic small spread so the novel lane does not collapse to one overplotted dot. */
function jitter(r: PanelAnnotationRow, i: number): number {
  const h = (r.pos + i * 2654435761) % 1000;
  return 0.72 + (h / 1000) * 0.56;
}

function build(rows: PanelAnnotationRow[]) {
  const positive = rows.map((r) => r.gnomad_af).filter((v): v is number => v !== null && v > 0);
  const minAf = positive.length > 0 ? Math.min(...positive) : 1e-5;
  // The novel lane sits a full decade below the rarest measured frequency, so it can never
  // be misread as "a very small AF" — there is a visible gap and a rule between them.
  const novelX = Math.max(1e-9, minAf / 12);
  const divider = Math.sqrt(novelX * minAf);

  const x = (r: PanelAnnotationRow, i: number) =>
    r.gnomad_af === null || r.gnomad_af === 0 ? novelX * jitter(r, i) : r.gnomad_af;
  const y = (r: PanelAnnotationRow) => (r.vaf === null ? VAF_NA : r.vaf);
  const custom = (r: PanelAnnotationRow) => [
    r.gene ?? 'no gene (intergenic)',
    r.consequence,
    r.rsid ?? 'no rsID',
    af(r.gnomad_af),
    r.clin_sig ?? 'no ClinVar record',
    r.vaf === null ? 'n/a (1/2)' : r.vaf.toFixed(3),
    r.filter,
  ];
  const traces: Record<string, unknown>[] = IMPACT_ORDER.filter((imp) =>
    rows.some((r) => r.impact === imp),
  ).map((imp) => {
    const g = rows.filter((r) => r.impact === imp);
    return {
      type: 'scatter',
      mode: 'markers',
      name: imp,
      x: g.map(x),
      y: g.map(y),
      marker: {
        color: impactColor(imp),
        size: 8,
        opacity: 0.72,
        line: { color: C.paper, width: 0.5 },
      },
      customdata: g.map(custom),
      hovertemplate:
        '<b>%{customdata[0]}</b> · %{customdata[1]}<br>%{customdata[2]}<br>' +
        'gnomAD AF %{customdata[3]}<br>ClinVar: %{customdata[4]}<br>' +
        'VAF %{customdata[5]} · FILTER %{customdata[6]}<extra></extra>',
    };
  });

  const path = rows.filter((r) => isPathogenic(r.clin_sig));
  if (path.length > 0) {
    traces.push({
      type: 'scatter',
      mode: 'markers',
      name: 'ClinVar pathogenic',
      x: path.map(x),
      y: path.map(y),
      marker: {
        color: 'rgba(0,0,0,0)',
        size: 17,
        symbol: 'circle-open',
        line: { color: C.ink, width: 2 },
      },
      // The filled point underneath already carries the full hover card.
      hoverinfo: 'skip',
    });
  }

  return {
    traces,
    novelX,
    divider,
    novels: rows.filter((r) => r.gnomad_af === null).length,
    noVaf: rows.filter((r) => r.vaf === null).length,
  };
}
