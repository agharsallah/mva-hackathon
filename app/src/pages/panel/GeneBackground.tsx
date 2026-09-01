import { useState } from 'react';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Plot, baseLayout } from '../../components/Plot';
import { Loaded } from '../../components/QueryState';
import { Select } from '../../components/Controls';
import { Callout } from '../../components/Explainer';
import { DataTable, type Column } from '../../components/DataTable';
import { usePanelBackground } from '../../api/hooks';
import type { PanelBackgroundRow } from '../../api/types';
import { C } from '../../lib/palette';
import { dec, int } from '../../lib/format';

/**
 * Gene-versus-background: is each panel gene ordinary for where it sits?
 *
 * The per-gene numbers on this page (variants/Mb, PASS share) are uninterpretable alone.
 * 180 variants/Mb is either normal or a hole in the data depending entirely on what the
 * surrounding sequence does, so this exhibit plots the *distance* instead of the value:
 * a z-score against every 1 Mb window of the chromosome, or of the whole callset.
 *
 * The chart is deliberately a dot-and-band, not a bar chart. Bars invite reading the
 * length as a quantity of something; here the only quantity is "how far from ordinary",
 * and the band is the part that carries the meaning.
 */

/** Conventional two-sigma triage line. Matches `Z_NOTABLE` in the derivation. */
const Z_BAND = 2;

/** Beyond three sigma the deviation is no longer a "worth a look" — it is the finding. */
const Z_STRONG = 3;

type Background = 'contig' | 'genome';

/** Grey inside the band, yellow past two sigma, red past three. Null is a visible gap. */
function zColor(z: number | null): string {
  if (z === null) return C.absent;
  const a = Math.abs(z);
  if (a < Z_BAND) return C.machinery;
  if (a < Z_STRONG) return C.decision;
  return C.broken;
}

export function GeneBackground() {
  const q = usePanelBackground();
  const [against, setAgainst] = useState<Background>('contig');

  const zDensity = (r: PanelBackgroundRow) =>
    against === 'contig' ? r.z_density_vs_contig : r.z_density_vs_genome;
  const zPass = (r: PanelBackgroundRow) =>
    against === 'contig' ? r.z_pass_vs_contig : r.z_pass_vs_genome;
  const meanDensity = (r: PanelBackgroundRow) =>
    against === 'contig' ? r.contig_bin_mean_density : r.genome_bin_mean_density;
  const sdDensity = (r: PanelBackgroundRow) =>
    against === 'contig' ? r.contig_bin_sd_density : r.genome_bin_sd_density;
  const meanPass = (r: PanelBackgroundRow) =>
    against === 'contig' ? r.contig_bin_mean_pct_pass : r.genome_bin_mean_pct_pass;
  const sdPass = (r: PanelBackgroundRow) =>
    against === 'contig' ? r.contig_bin_sd_pct_pass : r.genome_bin_sd_pct_pass;

  /** `null` is unmeasurable background, so it renders as the word, never as a number. */
  const orGap = (z: number | null) =>
    z === null ? (
      <span className="text-zinc-600" title="the background had no usable spread">
        no spread
      </span>
    ) : (
      <span style={{ color: zColor(z) }}>{z > 0 ? `+${dec(z, 2)}` : dec(z, 2)}</span>
    );

  const columns: Column<PanelBackgroundRow>[] = [
    { key: 'gene', header: 'gene', render: (r) => <span className="font-mono text-zinc-100">{r.gene}</span> },
    { key: 'chrom', header: 'contig', render: (r) => <span className="text-zinc-400">{r.chrom}</span> },
    {
      key: 'gene_variants_per_mb',
      header: 'gene /Mb',
      align: 'right',
      render: (r) => dec(r.gene_variants_per_mb, 1),
    },
    {
      key: 'bg_density',
      header: 'background /Mb (mean ± sd)',
      align: 'right',
      sortValue: (r) => meanDensity(r),
      render: (r) => (
        <span className="text-zinc-400">
          {dec(meanDensity(r), 0)} ± {sdDensity(r) === null ? '—' : dec(sdDensity(r), 0)}
        </span>
      ),
    },
    {
      key: 'z_density',
      header: 'density z',
      align: 'right',
      sortValue: (r) => zDensity(r),
      render: (r) => orGap(zDensity(r)),
    },
    {
      key: 'gene_pct_pass',
      header: 'gene PASS %',
      align: 'right',
      render: (r) => `${dec(r.gene_pct_pass, 1)} %`,
    },
    {
      key: 'bg_pass',
      header: 'background PASS % (mean ± sd)',
      align: 'right',
      sortValue: (r) => meanPass(r),
      render: (r) => (
        <span className="text-zinc-400">
          {meanPass(r) === null ? '—' : dec(meanPass(r), 1)} ±{' '}
          {sdPass(r) === null ? '—' : dec(sdPass(r), 1)}
        </span>
      ),
    },
    {
      key: 'z_pass',
      header: 'PASS-share z',
      align: 'right',
      sortValue: (r) => zPass(r),
      render: (r) => orGap(zPass(r)),
    },
    {
      key: 'records',
      header: 'records (PASS / all)',
      align: 'right',
      sortValue: (r) => r.n_all,
      render: (r) => (
        <span className="text-zinc-400">
          {int(r.n_pass)} / {int(r.n_all)}
        </span>
      ),
    },
  ];

  return (
    <Exhibit
      title="Every panel gene z-scored against its 1 Mb-window background"
      controls={
        <Select<Background>
          label="background"
          value={against}
          options={[
            { value: 'contig', label: 'its own chromosome' },
            { value: 'genome', label: 'the whole genome' },
          ]}
          onChange={setAgainst}
        />
      }
      legend={
        <>
          One row per gene, x is a <strong>z-score</strong>: how many standard deviations the
          gene&rsquo;s value sits from the mean of the background&rsquo;s 1 Mb windows (one window is one
          megabase, so a window&rsquo;s record count is itself a density in variants/Mb).{' '}
          <Chip color={C.machinery}>circles</Chip> are variant density,{' '}
          <Chip color={C.machinery}>diamonds</Chip> are PASS share. The{' '}
          <span className="text-zinc-500">grey band</span> is |z| &lt; {Z_BAND} — ordinary for this
          background. Outside it a point turns <Chip color={C.decision}>yellow</Chip> (2–{Z_STRONG} σ) and
          then <Chip color={C.broken}>red</Chip> (past {Z_STRONG} σ). A{' '}
          <Chip color={C.absent}>grey point</Chip> would mean the background had no usable spread, so no
          z exists — never a z of zero. Hover carries the raw numbers behind each point.{' '}
          <strong>
            A low PASS-share z is a callability statement — mappability, repeats, telomere-proximal
            sequence — never a pathogenicity one.
          </strong>
        </>
      }
      reading="TRIP13 is the only gene outside the band on PASS share, and the derivation puts it past three sigma. That is a statement about how hard its sequence is to call, not about whether it is causal."
      data={q.data?.data}
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
    >
      <Loaded query={q} height={520}>
        {(rows) => {
          // Most deviant at the top of the plot: Plotly draws a category axis bottom-up,
          // so the array is ordered least-deviant first.
          const ordered = [...rows].sort(
            (a, b) =>
              Math.max(Math.abs(zDensity(a) ?? 0), Math.abs(zPass(a) ?? 0)) -
              Math.max(Math.abs(zDensity(b) ?? 0), Math.abs(zPass(b) ?? 0)),
          );
          const genes = ordered.map((r) => r.gene);
          // Symmetric about zero and padded, so the most deviant marker is never clipped
          // by the axis it defines.
          const extent =
            0.5 +
            Math.max(
              Z_STRONG,
              ...ordered.flatMap((r) => [Math.abs(zDensity(r) ?? 0), Math.abs(zPass(r) ?? 0)]),
            );

          const series = (
            name: string,
            symbol: string,
            z: (r: PanelBackgroundRow) => number | null,
            custom: (r: PanelBackgroundRow) => (string | number)[],
            template: string,
          ) => ({
            type: 'scatter' as const,
            mode: 'markers' as const,
            name,
            x: ordered.map(z),
            y: genes,
            customdata: ordered.map(custom),
            marker: {
              symbol,
              size: 13,
              color: ordered.map((r) => zColor(z(r))),
              line: { color: C.paper, width: 1 },
            },
            hovertemplate: template,
          });

          return (
            <div className="space-y-3">
              <Plot
                height={380}
                data={[
                  series(
                    'variant density',
                    'circle',
                    zDensity,
                    (r) => [
                      r.chrom,
                      r.gene_variants_per_mb,
                      meanDensity(r),
                      sdDensity(r) ?? NaN,
                      r.n_all,
                      r.span_bp / 1e6,
                    ],
                    '<b>%{y}</b> · density<br>%{customdata[1]:.1f} variants/Mb ' +
                      '(%{customdata[4]:,} records over %{customdata[5]:.3f} Mb)<br>' +
                      'background %{customdata[0]} windows: %{customdata[2]:.0f} ± %{customdata[3]:.0f}/Mb<br>' +
                      'z = %{x:+.2f}<extra></extra>',
                  ),
                  series(
                    'PASS share (callability)',
                    'diamond',
                    zPass,
                    (r) => [r.chrom, r.gene_pct_pass, meanPass(r) ?? NaN, sdPass(r) ?? NaN, r.n_pass, r.n_all],
                    '<b>%{y}</b> · PASS share<br>%{customdata[1]:.1f} % ' +
                      '(%{customdata[4]:,} of %{customdata[5]:,} records)<br>' +
                      'background %{customdata[0]} windows: %{customdata[2]:.1f} ± %{customdata[3]:.1f} %<br>' +
                      'z = %{x:+.2f}<extra></extra>',
                  ),
                ]}
                layout={baseLayout({
                  margin: { l: 78, r: 24, t: 8, b: 46 },
                  hovermode: 'closest',
                  xaxis: {
                    title: { text: 'z — standard deviations from the background mean', font: { color: C.inkDim, size: 12 } },
                    range: [-extent, extent],
                    zeroline: false,
                    gridcolor: C.grid,
                    tickfont: { color: C.inkDim, size: 11 },
                  },
                  yaxis: {
                    type: 'category',
                    gridcolor: 'rgba(0,0,0,0)',
                    tickfont: { color: C.ink, size: 12, family: 'ui-monospace, monospace' },
                  },
                  shapes: [
                    // The band is the reference, so it is drawn first and stays neutral:
                    // being inside it is not "good", only ordinary.
                    {
                      type: 'rect',
                      xref: 'x',
                      yref: 'paper',
                      x0: -Z_BAND,
                      x1: Z_BAND,
                      y0: 0,
                      y1: 1,
                      fillcolor: 'rgba(113,113,122,0.14)',
                      line: { width: 0 },
                      layer: 'below',
                    },
                    {
                      type: 'line',
                      xref: 'x',
                      yref: 'paper',
                      x0: 0,
                      x1: 0,
                      y0: 0,
                      y1: 1,
                      line: { color: C.inkDim, width: 1, dash: 'dot' },
                    },
                    ...[-Z_STRONG, Z_STRONG].map((x) => ({
                      type: 'line' as const,
                      xref: 'x' as const,
                      yref: 'paper' as const,
                      x0: x,
                      x1: x,
                      y0: 0,
                      y1: 1,
                      line: { color: C.brokenDim, width: 1, dash: 'dash' as const },
                    })),
                  ],
                  annotations: [
                    {
                      xref: 'x',
                      yref: 'paper',
                      x: 0,
                      y: 1.03,
                      yanchor: 'bottom',
                      text: `ordinary for this background — |z| < ${Z_BAND}`,
                      showarrow: false,
                      font: { color: C.inkDim, size: 10 },
                    },
                  ],
                  legend: { orientation: 'h', y: 1.14, x: 0, font: { color: C.inkDim, size: 11 } },
                })}
              />
              <Callout tone="decision" title="What the numbers actually show">
                Against its own chromosome, <strong>TRIP13</strong> is the only gene whose PASS share
                leaves the band, and it leaves it hard: 50 % of its records pass where chr5&rsquo;s windows
                average 96.3 % ± 11.5, i.e. z = &minus;4.02 (&minus;3.54 against the whole genome). No other
                panel gene is beyond ±0.5 on that axis. This is the predicted result — TRIP13 sits in
                telomere-proximal chr5 sequence and 6 of its 12 records are suppressed, mostly by the
                mapping-quality filter — so read it as <em>the evidence there is thin and hard to trust</em>,
                in either direction, never as evidence of pathogenicity.
                <br />
                <br />
                The density axis says something different and easy to over-read: <em>every</em> panel gene
                sits at or below its chromosome&rsquo;s window mean, and TRIP13 (&minus;3.07) and CEP57 (&minus;2.95)
                are past two sigma. That is mostly a property of gene bodies, not of these genes — a 1 Mb
                window of the genome is mostly intergenic and carries more variation than the coding-plus-intronic
                span of a gene. It is also measured over spans well under one megabase (TRIP13&rsquo;s is 0.067 Mb),
                so the per-Mb figure is an extrapolation from a small interval and noisier than the windows it
                is compared against. The comparison is honest about direction, not about magnitude.
              </Callout>
              <DataTable rows={[...rows]} columns={columns} rowKey={(r) => r.gene} />
            </div>
          );
        }}
      </Loaded>
    </Exhibit>
  );
}
