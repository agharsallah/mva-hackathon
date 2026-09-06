import { useZygositySplit } from '../../api/hooks';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Plot } from '../../components/Plot';
import { baseLayout } from '../../components/plotLayout';
import { Loaded } from '../../components/QueryState';
import { dec, int, pct } from '../../lib/format';
import { C } from '../../lib/palette';

/**
 * The `bcftools stats` AF section, which is a trap and therefore worth drawing.
 *
 * The section is labelled "stats by non-reference allele frequency", and on a cohort that
 * is exactly what it is. This callset has **one sample**, so the total allele count at
 * every site (AN) is 2 and the alternate allele count (AC) can only be 1 or 2. bcftools
 * therefore emits two bins, labelled 0.00 and 0.99, and they mean *heterozygous* and
 * *homozygous alternate* — nothing about how common the allele is in the population.
 * `ideation/data-findings.md` §2.5 flags reading INFO/AF as a frequency filter as a
 * serious error; this exhibit exists to make the trap visible instead of leaving it in a
 * footnote.
 *
 * What the split is actually good for is Ts/Tv **per bin**. A random error process
 * produces transitions and transversions in the ratio the four bases allow (~0.5); real
 * biology produces ~2.0. False positives concentrate in heterozygous calls, because one
 * copy's worth of evidence is half the evidence, so a het bin sitting below the hom bin
 * is that contamination showing up where it is expected to.
 */

/** Where a callset-wide Ts/Tv stops looking like biology and starts looking like noise. */
const RANDOM_TSTV = 0.5;

const COLOR: Record<string, string> = {
  heterozygous: C.decision,
  'homozygous alternate': C.machinery,
};

const label = (zygosity: string | null, bin: number): string => zygosity ?? `AF bin ${dec(bin, 2)}`;

export function ZygositySplit() {
  const q = useZygositySplit();
  return (
    <Exhibit
      title="Heterozygous against homozygous — and what each half's Ts/Tv says"
      legend={
        <>
          Left: stacked bars, one per bin, split into{' '}
          <Chip color={C.raw}>SNPs (single-base substitutions)</Chip> and{' '}
          <Chip color={C.absent}>indels (insertions and deletions)</Chip>; bar height = alleles in
          the bin. Right: each bin&apos;s transition/transversion ratio —{' '}
          <Chip color={C.decision}>heterozygous</Chip> ·{' '}
          <Chip color={C.machinery}>homozygous alternate</Chip> — against the{' '}
          <span style={{ color: C.broken }}>dashed line at {RANDOM_TSTV}</span>, where a ratio would
          mean pure random error. Higher is more like real biology.
        </>
      }
      reading={
        <>
          The two bins are a <strong>zygosity split, not a frequency spectrum</strong>: one sample
          means AN is always 2, so bcftools&apos; &ldquo;allele frequency&rdquo; bins are just AC=1
          and AC=2. Both totals match the independent genotype counter exactly. Heterozygous calls
          carry the lower Ts/Tv of the two, which is where false positives are expected to sit — one
          copy&apos;s worth of evidence is half the evidence.
        </>
      }
      data={q.data?.data}
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
    >
      <Loaded query={q} height={320}>
        {(rows) => {
          const names = rows.map((r) => label(r.zygosity, r.af_bin));
          const total = rows.reduce((a, r) => a + r.n_alleles, 0);
          const ratios = rows.map((r) => r.ts_tv ?? 0);
          const top = Math.max(2.2, ...ratios) * 1.15;
          return (
            <>
              <div className="grid gap-3 lg:grid-cols-[1.35fr_1fr]">
                <Plot
                  height={260}
                  data={[
                    {
                      type: 'bar',
                      name: 'SNPs',
                      x: names,
                      y: rows.map((r) => r.n_snps),
                      marker: { color: C.raw, line: { width: 0 } },
                      hovertemplate: '%{x}<br>%{y:,} SNPs<extra></extra>',
                    },
                    {
                      type: 'bar',
                      name: 'indels',
                      x: names,
                      y: rows.map((r) => r.n_indels),
                      marker: { color: C.absent, line: { width: 0 } },
                      hovertemplate: '%{x}<br>%{y:,} indels<extra></extra>',
                    },
                  ]}
                  layout={baseLayout({
                    margin: { l: 66, r: 10, t: 8, b: 36 },
                    barmode: 'stack',
                    bargap: 0.45,
                    xaxis: {
                      type: 'category',
                      gridcolor: 'rgba(0,0,0,0)',
                      tickfont: { color: C.inkDim, size: 11 },
                    },
                    yaxis: {
                      title: { text: 'alleles', font: { color: C.inkDim, size: 12 } },
                      gridcolor: C.grid,
                      tickfont: { color: C.inkDim, size: 11 },
                    },
                    legend: {
                      orientation: 'h',
                      y: 1.14,
                      x: 0,
                      font: { color: C.inkDim, size: 11 },
                    },
                  })}
                />
                <Plot
                  height={260}
                  data={[
                    {
                      type: 'bar',
                      x: names,
                      y: ratios,
                      marker: {
                        color: rows.map((r) => COLOR[r.zygosity ?? ''] ?? C.absent),
                        line: { width: 0 },
                      },
                      text: ratios.map((v) => dec(v, 3)),
                      textposition: 'outside',
                      textfont: { color: C.inkDim, size: 11 },
                      hovertemplate: '%{x}<br>Ts/Tv %{y:.3f}<extra></extra>',
                    },
                  ]}
                  layout={baseLayout({
                    margin: { l: 44, r: 10, t: 8, b: 36 },
                    bargap: 0.55,
                    xaxis: {
                      type: 'category',
                      gridcolor: 'rgba(0,0,0,0)',
                      tickfont: { color: C.inkDim, size: 11 },
                    },
                    yaxis: {
                      title: { text: 'Ts/Tv', font: { color: C.inkDim, size: 12 } },
                      range: [0, top],
                      gridcolor: C.grid,
                      tickfont: { color: C.inkDim, size: 11 },
                    },
                    shapes: [
                      {
                        type: 'line',
                        xref: 'paper',
                        x0: 0,
                        x1: 1,
                        y0: RANDOM_TSTV,
                        y1: RANDOM_TSTV,
                        line: { color: C.broken, width: 1, dash: 'dash' },
                      },
                    ],
                    annotations: [
                      {
                        xref: 'paper',
                        x: 0.02,
                        y: RANDOM_TSTV,
                        yanchor: 'bottom',
                        text: 'random error',
                        showarrow: false,
                        font: { color: C.broken, size: 10 },
                      },
                    ],
                  })}
                />
              </div>
              <div className="mt-3 overflow-x-auto">
                <table className="w-full border-collapse text-micro">
                  <thead className="text-chrome-400">
                    <tr>
                      <th className="border-b border-line px-2 py-1 text-left font-medium">bin</th>
                      <th className="border-b border-line px-2 py-1 text-left font-medium">
                        reading
                      </th>
                      <th className="border-b border-line px-2 py-1 text-right font-medium">
                        SNPs
                      </th>
                      <th className="border-b border-line px-2 py-1 text-right font-medium">
                        indels
                      </th>
                      <th className="border-b border-line px-2 py-1 text-right font-medium">
                        alleles
                      </th>
                      <th className="border-b border-line px-2 py-1 text-right font-medium">
                        share
                      </th>
                      <th className="border-b border-line px-2 py-1 text-right font-medium">
                        Ts/Tv
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r) => (
                      <tr key={r.af_bin}>
                        <td className="border-b border-line-soft px-2 py-1 font-mono text-chrome-400">
                          {dec(r.af_bin, 2)}
                        </td>
                        <td className="border-b border-line-soft px-2 py-1">
                          <span style={{ color: COLOR[r.zygosity ?? ''] ?? C.absent }}>
                            {r.zygosity ?? 'not a single-sample callset — no zygosity reading'}
                          </span>
                        </td>
                        <td className="border-b border-line-soft px-2 py-1 text-right font-mono text-chrome-300">
                          {int(r.n_snps)}
                        </td>
                        <td className="border-b border-line-soft px-2 py-1 text-right font-mono text-chrome-300">
                          {int(r.n_indels)}
                        </td>
                        <td className="border-b border-line-soft px-2 py-1 text-right font-mono text-chrome-300">
                          {int(r.n_alleles)}
                        </td>
                        <td className="border-b border-line-soft px-2 py-1 text-right font-mono text-chrome-400">
                          {pct(r.pct_of_alleles, 2)}
                        </td>
                        <td className="border-b border-line-soft px-2 py-1 text-right font-mono text-chrome-300">
                          {dec(r.ts_tv, 3)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="mt-2 text-micro text-chrome-400">
                <span className="font-mono text-chrome-300">{int(total)}</span> alleles counted in
                total. Counted per <em>allele</em>, so a multi-allelic record contributes more than
                one — which is why this exceeds the 5,012,204 record count.
              </p>
            </>
          );
        }}
      </Loaded>
    </Exhibit>
  );
}
