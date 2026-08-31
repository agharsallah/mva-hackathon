import { useState } from 'react';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Plot, baseLayout } from '../../components/Plot';
import { Loaded } from '../../components/QueryState';
import { Select } from '../../components/Controls';
import { useLocus, usePanelGenes } from '../../api/hooks';
import type { LocusVariant } from '../../api/types';
import { C } from '../../lib/palette';
import { dec, int } from '../../lib/format';

const GT_SYMBOL: Record<string, string> = { '0/1': 'circle', '1/1': 'square', '1/2': 'star' };

function filterColor(f: string): string {
  return f === 'PASS' ? C.good : C.broken;
}

/**
 * Locus explorer: every record inside one candidate gene, laid out along the gene.
 *
 * Two stacked tracks share the x axis, the way a genome browser does it. The top track is
 * the caller's confidence, the bottom is the allele balance — a heterozygous record whose
 * VAF is far off 0.5 is either a mosaic event or an artefact, and either way it is worth a
 * second look.
 *
 * Positions on the x axis are real patient coordinates when the live API is answering, so
 * they are never persisted. The offline fixture uses a synthetic 1000, 2000, 3000 ladder.
 */
export function LocusExplorer() {
  const genes = usePanelGenes();
  const [gene, setGene] = useState<string>('BUB1B');
  const q = useLocus(gene);

  const options = (genes.data?.data ?? []).map((g) => ({ value: g.gene, label: `${g.gene} (${g.n_all})` }));

  return (
    <Exhibit
      title="Locus explorer — every record inside one candidate gene"
      controls={
        <>
          <Select
            value={gene}
            options={options.length > 0 ? options : [{ value: 'BUB1B', label: 'BUB1B' }]}
            onChange={setGene}
            label="gene"
          />
          <span className="text-[11px] text-zinc-600">live query ≈5 s, then cached</span>
        </>
      }
      legend={
        <>
          Top track: y = QUAL, the caller's confidence in the site. Bottom track: y = VAF, with a dashed line at{' '}
          <span className="font-mono">0.5</span>. Both share the x axis (position along the gene). Colour ={' '}
          <Chip color={C.good}>PASS</Chip> vs <Chip color={C.broken}>suppressed</Chip>. Marker shape = genotype:
          ● 0/1 heterozygous, ■ 1/1 homozygous variant, ★ 1/2 two different variant alleles (compound het by
          genotype). Marker size ∝ read depth.
        </>
      }
      reading="Suppressed records are usually the low-QUAL ones, as expected — but check whether any ★ (1/2) record is suppressed. That would be a compound-heterozygous site inside a candidate gene, hidden behind a heuristic."
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
    >
      {!gene ? (
        <p className="p-6 text-center text-sm text-zinc-500">pick a gene</p>
      ) : (
        <Loaded query={q} height={520}>
          {(rows) => <Tracks rows={rows} gene={gene} />}
        </Loaded>
      )}
    </Exhibit>
  );
}

function Tracks({ rows, gene }: { rows: LocusVariant[]; gene: string }) {
  if (rows.length === 0) {
    return <p className="p-6 text-center text-sm text-zinc-500">no records returned for {gene}</p>;
  }
  const maxDp = Math.max(...rows.map((r) => r.dp ?? 1));
  const size = (r: LocusVariant) => 7 + 11 * Math.sqrt((r.dp ?? 1) / maxDp);
  const suppressed = rows.filter((r) => r.filter !== 'PASS');
  const multi = rows.filter((r) => r.gt === '1/2');
  const suppressedMulti = multi.filter((r) => r.filter !== 'PASS');

  const groups = [
    { name: 'PASS', rows: rows.filter((r) => r.filter === 'PASS') },
    { name: 'suppressed', rows: suppressed },
  ].filter((g) => g.rows.length > 0);

  const hover =
    'QUAL %{y:.1f}<br>%{customdata[0]} · %{customdata[1]}<br>depth %{customdata[2]}×' +
    '<br>VAF %{customdata[3]}<extra></extra>';

  return (
    <>
      <Plot
        height={480}
        data={[
          ...groups.map((g) => ({
            type: 'scatter',
            mode: 'markers',
            name: g.name,
            legendgroup: g.name,
            x: g.rows.map((r) => r.pos),
            y: g.rows.map((r) => r.qual),
            marker: {
              color: filterColor(g.name === 'PASS' ? 'PASS' : 'X'),
              size: g.rows.map(size),
              symbol: g.rows.map((r) => GT_SYMBOL[r.gt] ?? 'circle'),
              line: { color: C.paper, width: 1 },
              opacity: 0.9,
            },
            customdata: g.rows.map((r) => [r.gt, r.filter, r.dp ?? 0, r.vaf ?? 0]),
            hovertemplate: hover,
          })),
          ...groups.map((g) => ({
            type: 'scatter',
            mode: 'markers',
            name: g.name,
            legendgroup: g.name,
            showlegend: false,
            xaxis: 'x',
            yaxis: 'y2',
            x: g.rows.map((r) => r.pos),
            y: g.rows.map((r) => r.vaf),
            marker: {
              color: filterColor(g.name === 'PASS' ? 'PASS' : 'X'),
              size: g.rows.map(size),
              symbol: g.rows.map((r) => GT_SYMBOL[r.gt] ?? 'circle'),
              line: { color: C.paper, width: 1 },
              opacity: 0.9,
            },
            customdata: g.rows.map((r) => [r.gt, r.filter, r.dp ?? 0, r.ad_alt ?? 0, r.ad_ref ?? 0]),
            hovertemplate:
              'VAF %{y:.3f}<br>%{customdata[0]} · %{customdata[1]}<br>' +
              '%{customdata[3]} alt / %{customdata[4]} ref reads<extra></extra>',
          })),
        ]}
        layout={baseLayout({
          margin: { l: 62, r: 16, t: 8, b: 46 },
          grid: { rows: 2, columns: 1, pattern: 'coupled', roworder: 'top to bottom' },
          xaxis: {
            title: { text: 'position along the gene', font: { color: C.inkDim, size: 12 } },
            gridcolor: C.grid,
            tickfont: { color: C.inkDim, size: 10 },
            domain: [0, 1],
          },
          yaxis: {
            title: { text: 'QUAL', font: { color: C.inkDim, size: 12 } },
            gridcolor: C.grid,
            tickfont: { color: C.inkDim, size: 10 },
            domain: [0.56, 1],
          },
          yaxis2: {
            title: { text: 'VAF', font: { color: C.inkDim, size: 12 } },
            gridcolor: C.grid,
            tickfont: { color: C.inkDim, size: 10 },
            domain: [0, 0.44],
            range: [0, 1.05],
          },
          shapes: [
            {
              type: 'line',
              xref: 'paper',
              yref: 'y2',
              x0: 0,
              x1: 1,
              y0: 0.5,
              y1: 0.5,
              line: { color: C.inkDim, width: 1.2, dash: 'dash' },
            },
          ],
          legend: { orientation: 'h', y: 1.08, x: 0, font: { color: C.inkDim, size: 11 } },
        })}
      />
      <div className="mt-2 grid gap-2 text-[11px] text-zinc-500 sm:grid-cols-4">
        <span>
          records <span className="font-mono text-zinc-300">{int(rows.length)}</span>
        </span>
        <span>
          suppressed <span className="font-mono text-red-400">{int(suppressed.length)}</span>
        </span>
        <span>
          1/2 sites <span className="font-mono text-amber-400">{int(multi.length)}</span>
          {suppressedMulti.length > 0 && (
            <span className="text-red-400"> ({suppressedMulti.length} of them suppressed)</span>
          )}
        </span>
        <span>
          median depth{' '}
          <span className="font-mono text-zinc-300">
            {dec(median(rows.map((r) => r.dp ?? 0)), 0)}×
          </span>
        </span>
      </div>
    </>
  );
}

function median(xs: number[]): number {
  if (xs.length === 0) return 0;
  const s = [...xs].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}
