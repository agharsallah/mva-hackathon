import { useMemo } from 'react';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Plot, baseLayout } from '../../components/Plot';
import { Loaded } from '../../components/QueryState';
import { Select, Toggle } from '../../components/Controls';
import { StatTile } from '../../components/StatTile';
import { Callout } from '../../components/Explainer';
import { useHetPairs, usePanelGenes } from '../../api/hooks';
import type { PanelHetPair, PanelHetPairs, PanelHetVariant } from '../../api/types';
import { C } from '../../lib/palette';
import { int, pct } from '../../lib/format';
import { known, useUrlState, useUrlToggle } from '../../lib/urlstate';
import { DEFAULT_GENE } from './LocusExplorer';

/**
 * The compound-heterozygous pair matrix — the Track 1 answer space, drawn.
 *
 * Every cell is one candidate pair of heterozygous variants in one gene. The colour is
 * what the callset can say about **phase**: whether the two sit on opposite copies of the
 * chromosome (trans, a real compound heterozygote) or the same copy (cis, excluded).
 *
 * The honest result is that almost nothing is resolved. Physical phasing needs both
 * variants on one read pair, which reaches ~300 bp, so on BUB1B it settles 5 of 1,540
 * pairs. The grid is therefore mostly one colour, and that *is* the finding: rendering it
 * as a wall of unknown with a handful of lit cells shows exactly how much phase evidence
 * the data carries, and exactly where.
 *
 * The unknown cells are not blank — they are shaded by how rare the pair is, so the
 * rare × rare corner (where a causal pair has to live) reads as the hot region even
 * though phase says nothing about it.
 */

/** Floor for the log rarity scale: 1e-6 is below gnomAD's resolution at v4 sample size. */
const AF_FLOOR = 1e-6;
const AF_DECADES = 6;

/** Unknown-pair shading: dark neutral (common) → machinery blue → pale (rare × rare). */
const RARITY_SCALE: [number, string][] = [
  [0, '#161b22'],
  [0.45, '#1e3a8a'],
  [0.75, '#3b82f6'],
  [1, '#bfdbfe'],
];

/** How rare one allele is, as decades below 1. Novel (looked up, absent) is the top. */
function rarityScore(v: PanelHetVariant): number | null {
  if (!v.annotated) return null;
  if (v.gnomad_af === null) return AF_DECADES;
  return Math.min(AF_DECADES, Math.max(0, -Math.log10(Math.max(v.gnomad_af, AF_FLOOR))));
}

/**
 * A pair is only as rare as its **more common** half: a compound heterozygote needs both
 * alleles to be rare, so the commoner one is the binding constraint. That is the minimum
 * of the two rarity scores (equivalently the maximum of the two allele frequencies).
 */
function pairRarity(a: PanelHetVariant, b: PanelHetVariant): number | null {
  const x = rarityScore(a);
  const y = rarityScore(b);
  return x === null || y === null ? null : Math.min(x, y);
}

/** Axis label: the rsID if the variant has one, else the consequence, never a position. */
function label(v: PanelHetVariant): string {
  if (v.rsid) return v.rsid.length > 12 ? `${v.rsid.slice(0, 11)}…` : v.rsid;
  if (!v.consequence) return 'unannotated';
  return v.consequence.replace(/_variant$/, '').replace(/_/g, ' ');
}

function afText(v: PanelHetVariant): string {
  if (!v.annotated) return 'not annotated';
  if (v.gnomad_af === null) return 'absent from gnomAD';
  return v.gnomad_af.toExponential(1);
}

/**
 * The gene picker writes the **same `gene` parameter as {@link LocusExplorer}** — one gene per
 * Panel page, deliberately. Both exhibits answer questions about one gene, and having the
 * locus tracks and the pair grid disagree about which gene is open was never useful: it made
 * `?gene=TRIP13` ambiguous and split one page into two half-selected views. The rare-only
 * filter stays per-exhibit (`pairs.rare`) because it belongs to this grid alone.
 */
export function PairMatrix() {
  const genes = usePanelGenes();
  const [param, setGene] = useUrlState('gene', DEFAULT_GENE);
  const [narrow, setNarrow] = useUrlToggle('pairs.rare');

  const options = (genes.data?.data ?? []).map((g) => ({ value: g.gene, label: g.gene }));
  const gene = known(param, options.map((o) => o.value), DEFAULT_GENE);
  const q = useHetPairs(gene);

  return (
    <Exhibit
      title="Compound-het pair matrix — every candidate pair in one gene, coloured by phase"
      controls={
        <>
          <Select
            value={gene}
            options={options.length > 0 ? options : [{ value: DEFAULT_GENE, label: DEFAULT_GENE }]}
            onChange={setGene}
            label="gene"
          />
          <Toggle on={narrow} onChange={setNarrow}>
            rare + protein-altering only
          </Toggle>
        </>
      }
      legend={
        <>
          One cell = one candidate pair; the axes are the same list of heterozygous PASS alleles, ordered
          along the gene, so only the lower triangle is drawn (the grid is symmetric and a variant cannot
          pair with itself). <Chip color={C.good}>green = resolved trans</Chip> — the two alleles are on
          opposite copies, a proven compound-heterozygous configuration.{' '}
          <Chip color={C.broken}>red = resolved cis</Chip> — both on the same copy, so one intact copy
          remains and the pair is excluded. <Chip color={C.decision}>yellow = auto-trans</Chip> — the two
          ALT alleles of one <span className="font-mono">1/2</span> record: one copy of each, so the
          genotype proves trans with no phasing involved. <Chip color="#3b82f6">blue = unknown</Chip>,
          shaded by pair rarity — pale is rare × rare, dark is common, and a blank cell means one of the
          two alleles has no frequency to rank on. Axis ticks are the rsID or the consequence; genomic
          positions appear in hover only. <strong>On BUB1B, 99.7 % of pairs are unresolved by short-read
          phasing (the tile below gives the figure for the gene on screen) — the grid shows how little
          phase the data carries, and exactly which pairs it does resolve.</strong>
        </>
      }
      reading="Read the pale cells, not the lit ones. Phasing lights up a handful of neighbouring pairs and says nothing about the rest, so the pale rare × rare region is where the causal pair has to be looked for — and the red cells are the only pairs the data lets you strike off."
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
    >
      <Loaded query={q} height={620}>
        {(payload) => <Matrix payload={payload} narrow={narrow} />}
      </Loaded>
    </Exhibit>
  );
}

function Matrix({ payload, narrow }: { payload: PanelHetPairs; narrow: boolean }) {
  const { gene, summary } = payload;

  // Filtering renumbers the axis, so the server's pair indices are remapped rather than
  // reused. A pair whose partner was filtered out simply leaves the grid.
  const view = useMemo(() => {
    const keep = payload.variants
      .map((v, i) => ({ v, i }))
      .filter(({ v }) => !narrow || (v.is_rare_recessive === true && v.is_protein_altering === true));
    const at = new Map(keep.map(({ i }, k) => [i, k]));
    const variants = keep.map(({ v }) => v);
    const pairs = payload.pairs
      .filter((p) => at.has(p.i) && at.has(p.j))
      .map((p) => ({ ...p, i: at.get(p.i)!, j: at.get(p.j)! }));
    return { variants, pairs };
  }, [payload, narrow]);

  const n = view.variants.length;
  if (n < 2) {
    return (
      <p className="p-8 text-center text-sm text-zinc-500">
        {n === 0
          ? `no heterozygous PASS allele in ${gene} matches this filter — there is no pair to draw`
          : `only one heterozygous PASS allele in ${gene} matches this filter, and one allele is not a pair`}
      </p>
    );
  }

  return (
    <>
      <Grid variants={view.variants} pairs={view.pairs} />
      {narrow ? (
        <Callout tone="decision" title={`${gene}: the candidate subset, ${n} allele${n === 1 ? '' : 's'}`}>
          {n === 2 ? (
            <>
              Filtering to alleles that are both <strong>rare</strong> (gnomAD AF &lt; 1 %, the recessive
              cutoff) and <strong>protein-altering</strong> (VEP HIGH or MODERATE) leaves a 2 × 2 grid with
              exactly <strong>one</strong> off-diagonal cell. That single cell is the whole hypothesis this
              gene supports: it is the only pair of alleles here that could disable both copies. Its colour
              is the verdict — unknown means phasing never reached across it, so the pair is neither proven
              nor excluded, and it stays live.
            </>
          ) : (
            <>
              Filtering to alleles that are both <strong>rare</strong> (gnomAD AF &lt; 1 %) and{' '}
              <strong>protein-altering</strong> (VEP HIGH or MODERATE) leaves {int(n)} of{' '}
              {int(summary.n_het)}, and {int((n * (n - 1)) / 2)} of {int(summary.n_pairs)} pairs. This is
              the subset a ranking actually has to order.
            </>
          )}
        </Callout>
      ) : null}
      <p className="mt-3 text-[11px] text-zinc-600">
        {narrow
          ? `counts below are for the whole ${gene} grid, not the filtered view above`
          : `the whole ${gene} grid`}
      </p>
      <div className="mt-1.5 grid grid-cols-2 gap-2 sm:grid-cols-5">
        <StatTile
          label="het alleles"
          value={int(summary.n_het)}
          sub="the axis"
          hint="Heterozygous PASS ALT alleles inside the gene. A 1/2 record contributes two."
        />
        <StatTile
          label="candidate pairs"
          value={int(summary.n_pairs)}
          sub="n(n−1)/2"
          tone="raw"
        />
        <StatTile
          label="resolved trans"
          value={int(summary.n_trans)}
          sub={`${int(summary.n_auto_trans)} of them by 1/2 genotype`}
          tone="good"
        />
        <StatTile label="resolved cis" value={int(summary.n_cis)} sub="excluded" tone="broken" />
        <StatTile
          label="unresolved"
          value={pct(summary.pct_unknown, 2)}
          sub={`${int(summary.n_unknown)} pairs`}
          tone="decision"
          hint="Physical phasing needs both variants on one read pair — about 300 bp here."
        />
      </div>
    </>
  );
}

function Grid({ variants, pairs }: { variants: PanelHetVariant[]; pairs: PanelHetPair[] }) {
  const n = variants.length;
  const labels = variants.map(label);

  // Lower triangle only: row i, column j with j < i. Everything above stays null, which
  // Plotly renders as nothing rather than as a value.
  const z: (number | null)[][] = [];
  const meta: (string[] | null)[][] = [];
  const resolvedAt = new Set(pairs.map((p) => `${p.i}:${p.j}`));
  for (let i = 0; i < n; i++) {
    const zr: (number | null)[] = [];
    const mr: (string[] | null)[] = [];
    for (let j = 0; j < n; j++) {
      const isCell = j < i && !resolvedAt.has(`${Math.min(i, j)}:${Math.max(i, j)}`);
      zr.push(isCell ? pairRarity(variants[i], variants[j]) : null);
      mr.push(
        isCell
          ? [labels[j], labels[i], afText(variants[j]), afText(variants[i]),
             String(variants[j].pos), String(variants[i].pos)]
          : null,
      );
    }
    z.push(zr);
    meta.push(mr);
  }

  const marks = (phase: 'trans' | 'cis', auto: boolean) =>
    pairs.filter((p) => p.phase === phase && p.auto === auto);

  const overlay = (name: string, color: string, chosen: PanelHetPair[]) => ({
    type: 'scatter',
    mode: 'markers',
    name,
    x: chosen.map((p) => p.i),
    y: chosen.map((p) => p.j),
    marker: {
      color,
      size: Math.max(7, Math.min(20, 460 / n)),
      symbol: 'square',
      line: { color: C.paper, width: 1 },
    },
    customdata: chosen.map((p) => [labels[p.i], labels[p.j], variants[p.i].pos, variants[p.j].pos]),
    hovertemplate:
      `<b>${name}</b><br>%{customdata[0]} × %{customdata[1]}` +
      '<br>positions %{customdata[2]} · %{customdata[3]}<extra></extra>',
  });

  // Ticks thin out on a big gene: 163 labels on one axis is a grey smear, not a label.
  const stride = Math.max(1, Math.ceil(n / 34));
  const tickvals = labels.map((_, i) => i).filter((i) => i % stride === 0);
  const axis = {
    tickmode: 'array',
    tickvals,
    ticktext: tickvals.map((i) => labels[i]),
    tickfont: { color: C.inkDim, size: n > 24 ? 8 : 10 },
    gridcolor: 'rgba(0,0,0,0)',
    zeroline: false,
  };

  return (
    // The two axes are the same list, so the grid has to be square. Capping the width
    // keeps it square without leaving half the exhibit empty on a wide screen.
    <div className="mx-auto w-full" style={{ maxWidth: 720 }}>
    <Plot
      height={560}
      data={[
        {
          type: 'heatmap',
          name: 'unknown',
          z,
          customdata: meta,
          colorscale: RARITY_SCALE,
          zmin: 0,
          zmax: AF_DECADES,
          xgap: n > 60 ? 0 : 1,
          ygap: n > 60 ? 0 : 1,
          hoverongaps: false,
          colorbar: {
            title: { text: 'pair rarity', font: { color: C.inkDim, size: 11 } },
            tickvals: [0, 2, 4, 6],
            ticktext: ['1', '1e−2', '1e−4', '≤1e−6'],
            tickfont: { color: C.inkDim, size: 10 },
            thickness: 10,
            len: 0.5,
            y: 0.5,
          },
          hovertemplate:
            '<b>unknown phase</b><br>%{customdata[0]} × %{customdata[1]}' +
            '<br>AF %{customdata[2]} · %{customdata[3]}' +
            '<br>positions %{customdata[4]} · %{customdata[5]}<extra></extra>',
        },
        overlay('trans (phased)', C.good, marks('trans', false)),
        overlay('auto-trans (1/2 genotype)', C.decision, marks('trans', true)),
        overlay('cis (excluded)', C.broken, marks('cis', false)),
      ]}
      layout={baseLayout({
        margin: { l: 96, r: 16, t: 8, b: 108 },
        xaxis: { ...axis, tickangle: -50, range: [-0.5, n - 0.5] },
        // Reversed, so index 0 is top-left and the drawn half is the *lower* triangle —
        // the way a pairwise matrix is conventionally read.
        yaxis: { ...axis, scaleanchor: 'x', scaleratio: 1, range: [n - 0.5, -0.5] },
        legend: { orientation: 'h', y: 1.06, x: 0, font: { color: C.inkDim, size: 11 } },
      })}
    />
    </div>
  );
}
