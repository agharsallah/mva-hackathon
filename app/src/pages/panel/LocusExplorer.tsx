import { useGeneStructure, useLocus, usePanelGenes } from '../../api/hooks';
import type { GeneStructure, LocusVariant } from '../../api/types';
import { Select } from '../../components/Controls';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Plot } from '../../components/Plot';
import { baseLayout } from '../../components/plotLayout';
import { Loaded } from '../../components/QueryState';
import { dec, int } from '../../lib/format';
import { C } from '../../lib/palette';
import { known, useUrlState } from '../../lib/urlstate';
import { DomainLollipop } from './DomainLollipop';
import { geneAxis, geneTrack } from './locus/geneTrack';

const GT_SYMBOL: Record<string, string> = { '0/1': 'circle', '1/1': 'square', '1/2': 'star' };

/** The gene the Panel page opens on, and what an unknown `?gene=` falls back to. */
export const DEFAULT_GENE = 'BUB1B';

function filterColor(f: string): string {
  return f === 'PASS' ? C.good : C.broken;
}

/**
 * Locus explorer: every record inside one candidate gene, laid out along the gene.
 *
 * Three stacked tracks share the x axis, the way a genome browser does it. The top track
 * is the caller's confidence, the middle is the allele balance — a heterozygous record
 * whose VAF is far off 0.5 is either a mosaic event or an artefact, and either way it is
 * worth a second look — and the bottom is the gene's own structure from Ensembl, so a
 * record can be read against the exon it falls in instead of against a bare number line.
 *
 * Positions on the x axis are real patient coordinates when the live API is answering, so
 * they are never persisted. The offline fixture uses a synthetic 1000, 2000, 3000 ladder.
 * Exon coordinates are public reference data and *are* committed in the fixture.
 *
 * Under the tracks, {@link DomainLollipop} re-plots the same gene in amino-acid space —
 * always the same gene, because it is handed the one this exhibit selected.
 *
 * The selection is the `gene` URL parameter, deliberately **shared with {@link PairMatrix}**
 * further down the Panel page: "which gene are we looking at" is a property of the page, not
 * of one exhibit, so `?gene=TRIP13` moves the whole page and links to a coherent view.
 */
export function LocusExplorer() {
  const genes = usePanelGenes();
  const [param, setGene] = useUrlState('gene', DEFAULT_GENE);
  const options = (genes.data?.data ?? []).map((g) => ({
    value: g.gene,
    label: `${g.gene} (${g.n_all})`,
  }));
  // A gene the panel does not contain reads as the default rather than driving a doomed query.
  const gene = known(
    param,
    options.map((o) => o.value),
    DEFAULT_GENE,
  );
  const q = useLocus(gene);
  const anatomy = useGeneStructure(gene);
  const structure = anatomy.data?.data;

  return (
    <div className="space-y-4">
      <Exhibit
        title="Locus explorer — every record inside one candidate gene"
        controls={
          <>
            <Select
              value={gene}
              options={
                options.length > 0 ? options : [{ value: DEFAULT_GENE, label: DEFAULT_GENE }]
              }
              onChange={setGene}
              label="gene"
            />
            <span className="text-micro text-chrome-600">live query ≈5 s, then cached</span>
          </>
        }
        legend={
          <>
            Top track: y = QUAL, the caller's confidence in the site. Middle track: y = VAF, with a
            dashed line at <span className="font-mono">0.5</span>. Bottom track: the gene itself —{' '}
            <Chip color={C.machinery}>filled boxes are exons</Chip> (the stretches that survive into
            the protein), the thin line between them is intron (spliced out and discarded), and the
            arrow marks the TSS (transcription start site) pointing the way the gene is read. Hover
            an exon for its number and span. All three share the x axis (position along the gene).
            Marker colour = <Chip color={C.good}>PASS</Chip> vs{' '}
            <Chip color={C.broken}>suppressed</Chip>. Marker shape = genotype: ● 0/1 heterozygous, ■
            1/1 homozygous variant, ★ 1/2 two different variant alleles (compound het by genotype).
            Marker size ∝ read depth.
          </>
        }
        reading="Suppressed records are usually the low-QUAL ones, as expected — but check whether any ★ (1/2) record is suppressed, and whether it sits over an exon. A suppressed 1/2 record inside an exon is a compound-heterozygous coding site hidden behind a heuristic."
        source={q.data?.source}
        cachedAt={q.data?.cachedAt}
        origin={q.data?.origin}
      >
        {!gene ? (
          <p className="p-6 text-center text-sm text-chrome-500">pick a gene</p>
        ) : (
          <>
            <Loaded query={q} height={560}>
              {(rows) => <Tracks rows={rows} gene={gene} structure={structure} />}
            </Loaded>
            <GeneTrackNote gene={gene} structure={structure} failed={anatomy.error} />
          </>
        )}
      </Exhibit>
      {gene && <DomainLollipop gene={gene} />}
    </div>
  );
}

/** One line under the tracks: what the gene track is showing, or honestly why it is not. */
function GeneTrackNote({
  gene,
  structure,
  failed,
}: {
  gene: string;
  structure?: GeneStructure;
  failed: Error | null;
}) {
  if (failed) {
    return (
      <p className="mt-2 text-micro text-broken-400">
        gene track unavailable — {failed.message}. Nothing is drawn rather than a guessed structure.
      </p>
    );
  }
  if (!structure) return null;
  return (
    <p className="mt-2 text-micro text-chrome-500">
      gene track: <span className="font-mono text-chrome-300">{structure.transcript}</span>, the
      canonical transcript of {gene} — {int(structure.exons.length)} exons on the{' '}
      {structure.strand >= 0 ? 'forward (+)' : 'reverse (−)'} strand,{' '}
      {int(structure.protein_length ?? 0)} amino acids. Exon 1 is the first one <em>transcribed</em>
      , which on the reverse strand is the rightmost box.
    </p>
  );
}

function Tracks({
  rows,
  gene,
  structure,
}: {
  rows: LocusVariant[];
  gene: string;
  structure?: GeneStructure;
}) {
  if (rows.length === 0) {
    return (
      <p className="p-6 text-center text-sm text-chrome-500">no records returned for {gene}</p>
    );
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

  // The gene track is additive: without it the two original tracks simply take the space.
  const anatomy = structure ? geneTrack(structure) : null;

  return (
    <>
      <Plot
        height={520}
        data={[
          ...(anatomy?.traces ?? []),
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
            customdata: g.rows.map((r) => [
              r.gt,
              r.filter,
              r.dp ?? 0,
              r.ad_alt ?? 0,
              r.ad_ref ?? 0,
            ]),
            hovertemplate:
              'VAF %{y:.3f}<br>%{customdata[0]} · %{customdata[1]}<br>' +
              '%{customdata[3]} alt / %{customdata[4]} ref reads<extra></extra>',
          })),
        ]}
        layout={baseLayout({
          margin: { l: 62, r: 16, t: 8, b: 46 },
          grid: {
            rows: anatomy ? 3 : 2,
            columns: 1,
            pattern: 'coupled',
            roworder: 'top to bottom',
          },
          barmode: 'overlay',
          annotations: anatomy?.annotations ?? [],
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
            domain: anatomy ? [0.62, 1] : [0.56, 1],
          },
          yaxis2: {
            title: { text: 'VAF', font: { color: C.inkDim, size: 12 } },
            gridcolor: C.grid,
            tickfont: { color: C.inkDim, size: 10 },
            domain: anatomy ? [0.16, 0.56] : [0, 0.44],
            range: [0, 1.05],
          },
          // `yaxis3` is the axis id GENE_AXIS ('y3') refers to; the track is only laid
          // out when the structure actually arrived.
          yaxis3: anatomy ? geneAxis([0, 0.1]) : undefined,
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
      <div className="mt-2 grid gap-2 text-micro text-chrome-500 sm:grid-cols-4">
        <span>
          records <span className="font-mono text-chrome-300">{int(rows.length)}</span>
        </span>
        <span>
          suppressed <span className="font-mono text-broken-400">{int(suppressed.length)}</span>
        </span>
        <span>
          1/2 sites <span className="font-mono text-decision-400">{int(multi.length)}</span>
          {suppressedMulti.length > 0 && (
            <span className="text-broken-400"> ({suppressedMulti.length} of them suppressed)</span>
          )}
        </span>
        <span>
          median depth{' '}
          <span className="font-mono text-chrome-300">
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
