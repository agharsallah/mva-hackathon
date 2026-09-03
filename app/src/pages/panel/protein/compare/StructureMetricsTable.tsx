/**
 * Every gene in the structure set, one row of measured numbers each.
 *
 * The 3D canvas is a *picture of one gene*. This is the table that makes the set legible: how
 * long each protein is, how much of it AlphaFold actually modelled, how much of that is above
 * the confidence floor, how much is helix and strand, how many domains it has — and, for the
 * eight panel genes only, how many of this proband's alleles landed on a modelled residue and
 * how close the closest two of them are.
 *
 * Two things it deliberately does *not* do:
 *
 * - **It never ranks.** Columns are sortable because a reader compares by sorting, but no
 *   column is a score and nothing here is a pathogenicity statement. A high modelled share is
 *   a statement about AlphaFold, not about the gene.
 * - **It never fills an off-panel allele cell.** Those two columns read `n/a — fold only`,
 *   because the callset was annotated over the eight-gene panel BED: a zero there would be a
 *   claim about the patient that no measurement supports.
 *
 * Each row owns its own request pair (`useGeneStructures` / `useProteinStructures` fan out one
 * query per gene), so one gene whose fold is unreachable shows its error in its own row and
 * leaves the rest of the table standing.
 *
 * That fan-out is **23 + 21 = 44 requests**, and this exhibit sits far below the fold on
 * `/panel`. So it is gated on `useInView`: nothing is requested until the section is within
 * 300 px of the viewport, and while it is not, the table says how many genes it is about to
 * ask for rather than pretending to be empty. Spending 44 cold Ensembl/AlphaFold round-trips
 * on a reader who never scrolls this far is the cost the gate exists to refuse.
 */

import { useMemo } from 'react';

import { useGeneStructures, useProteinStructures, useStructureGenes } from '../../../../api/hooks';
import type { StructureGene } from '../../../../api/types';
import { Badge } from '../../../../components/Badge';
import { type Column, DataTable } from '../../../../components/DataTable';
import { Exhibit } from '../../../../components/Exhibit';
import { Plot } from '../../../../components/Plot';
import { baseLayout } from '../../../../components/plotLayout';
import { Skeleton } from '../../../../components/QueryState';
import { dec, int } from '../../../../lib/format';
import { useInView } from '../../../../lib/hooks';
import { C, TONE_MARK } from '../../../../lib/palette';
import { angstromLabel } from '../distances';
import { GROUP_SHORT } from '../geneSet';
import { type StructureRow, structureRow } from './metrics';

/** Group → the tone its bar and badge are drawn in. Panel = green, because it is the goal. */
const GROUP_TONE = {
  panel: TONE_MARK.good,
  'mva-sac': TONE_MARK.machinery,
  extended: TONE_MARK.neutral,
} as const;

const NA = <span className="text-chrome-700">·</span>;

/** A fraction as a percentage cell, or the word that says why there is no number. */
function share(value: number | null | undefined, absent: string) {
  if (value === null || value === undefined) {
    return <span className="text-chrome-600">{absent}</span>;
  }
  return <span className="font-mono text-chrome-200">{dec(value * 100, 1)}</span>;
}

export function StructureMetricsTable({
  onPickGene,
  onCompare,
}: {
  /** Row click — the page decides what it means (jump the explorer to that gene). */
  onPickGene?: (gene: string) => void;
  /** Stage this gene as side A or side B of the comparison exhibit. */
  onCompare?: (gene: string, slot: 'A' | 'B') => void;
}) {
  const set = useStructureGenes();
  // The section, not the page, decides when to spend 44 requests. See the module doc.
  const { ref, inView } = useInView<HTMLDivElement>();
  // Memoised: `?? []` is a fresh array each render, and the row build keys off it. Deduped by
  // symbol, because a repeated row in the reference TSV would otherwise render twice and
  // misalign the per-gene result slots against the gene list.
  const genes = useMemo(() => uniqueBySymbol(set.data?.data ?? []), [set.data]);
  const symbols = useMemo(() => genes.map((gene) => gene.symbol), [genes]);
  // A non-coding gene has no protein endpoint to call; it still gets a row, saying so.
  const coding = useMemo(
    () => genes.filter((gene) => gene.coding).map((gene) => gene.symbol),
    [genes],
  );

  const anatomies = useGeneStructures(symbols, inView);
  const models = useProteinStructures(coding, inView);

  // `useEndpointEach`'s `combine` makes both arrays referentially stable, so this memo
  // actually holds and each row's protein scene is built once per payload change — not once
  // per render of the page. `structureRow` passes its own build down into `structureMetrics`.
  const rows = useMemo<StructureRow[]>(
    () =>
      genes.map((entry, index) => {
        const modelIndex = coding.indexOf(entry.symbol);
        const model = modelIndex < 0 ? undefined : models[modelIndex];
        const anatomy = anatomies[index];
        return structureRow(
          entry,
          { data: model?.data?.data ?? null, error: model?.error ?? null },
          { data: anatomy?.data?.data ?? null, error: anatomy?.error ?? null },
        );
      }),
    [genes, coding, models, anatomies],
  );

  const columns = useMemo(() => buildColumns(onPickGene, onCompare), [onPickGene, onCompare]);

  return (
    <Exhibit
      title="Every gene in the set, as numbers"
      legend={<Legend />}
      reading="Sort by pLDDT ≥ 70 % and read the panel genes against the rest: a fold that is mostly low-confidence supports no spatial argument about any allele on it, however damaging the allele looks."
      source={set.data?.source}
      cachedAt={set.data?.cachedAt}
      origin={set.data?.origin}
      data={inView ? rows.map((row) => ({ gene: row.gene, group: row.group, ...row.metrics })) : []}
    >
      <div ref={ref}>
        {set.isLoading ? (
          <Skeleton height={320} />
        ) : !inView ? (
          <div className="space-y-2">
            <p className="text-[11px] text-chrome-500">
              loading {int(genes.length)} genes — two requests each ({int(symbols.length)} folds,{' '}
              {int(coding.length)} models). Scroll here and the table fills in; it is not requested
              before that, because a cold call reaches Ensembl and AlphaFold once per gene.
            </p>
            <Skeleton height={320} />
          </div>
        ) : (
          <div className="space-y-3">
            <ConfidenceBars rows={rows} />
            <DataTable
              rows={rows}
              columns={columns}
              rowKey={(row) => row.gene}
              empty="the structure gene set is empty — the server read no rows from its reference table."
              pageSize={30}
            />
          </div>
        )}
      </div>
    </Exhibit>
  );
}

/** First occurrence of each symbol wins — the reference TSV is display-ordered. */
function uniqueBySymbol(genes: readonly StructureGene[]): StructureGene[] {
  const seen = new Set<string>();
  const out: StructureGene[] = [];
  for (const gene of genes) {
    if (seen.has(gene.symbol)) continue;
    seen.add(gene.symbol);
    out.push(gene);
  }
  return out;
}

/** The one chart worth drawing off this table: confidence per gene, coloured by group. */
function ConfidenceBars({ rows }: { rows: readonly StructureRow[] }) {
  const ready = rows.filter((row) => row.metrics?.confidentFraction != null);
  if (ready.length < 2) return null;
  const sorted = [...ready].sort(
    (a, b) => (b.metrics?.confidentFraction ?? 0) - (a.metrics?.confidentFraction ?? 0),
  );
  return (
    <Plot
      height={260}
      data={[
        {
          type: 'bar',
          x: sorted.map((row) => row.gene),
          y: sorted.map((row) => (row.metrics?.confidentFraction ?? 0) * 100),
          marker: { color: sorted.map((row) => GROUP_TONE[row.group]) },
          hovertemplate: '%{x}: %{y:.1f} % of modelled residues at pLDDT ≥ 70<extra></extra>',
        },
      ]}
      layout={baseLayout({
        // 64 px on the left, and a short title: the long form ("% of modelled residues at
        // pLDDT ≥ 70") overran the plot area and collided with the tick labels. The full
        // sentence lives in the legend, which is where a definition belongs.
        margin: { l: 64, r: 12, t: 8, b: 78 },
        xaxis: { tickangle: -45, tickfont: { size: 10, color: C.inkDim } },
        yaxis: { title: { text: '% at pLDDT ≥ 70' }, range: [0, 100] },
      })}
    />
  );
}

const SLOT_BUTTON =
  'rounded border border-chrome-700 bg-chrome-900 px-1.5 py-0.5 font-mono text-[10px] ' +
  'text-chrome-400 transition hover:bg-chrome-800 hover:text-chrome-200';

function buildColumns(
  onPickGene?: (gene: string) => void,
  onCompare?: (gene: string, slot: 'A' | 'B') => void,
): Column<StructureRow>[] {
  const compare: Column<StructureRow>[] = onCompare
    ? [
        {
          key: 'compare',
          header: 'compare',
          sortable: false,
          render: (row) => (
            <span className="inline-flex gap-1">
              {(['A', 'B'] as const).map((slot) => (
                <button
                  key={slot}
                  type="button"
                  onClick={() => onCompare(row.gene, slot)}
                  // The visible label is one glyph, so the accessible name has to be written
                  // out: "→B" tells a screen reader nothing about which gene it stages.
                  aria-label={`put ${row.gene} on side ${slot} of the side-by-side comparison`}
                  className={SLOT_BUTTON}
                >
                  →{slot}
                </button>
              ))}
            </span>
          ),
        },
      ]
    : [];
  return [
    {
      key: 'gene',
      header: 'gene',
      sortValue: (row) => row.gene,
      render: (row) =>
        onPickGene ? (
          <button
            type="button"
            onClick={() => onPickGene(row.gene)}
            title={`open ${row.gene} in the 3D explorer above`}
            className="font-mono text-chrome-200 transition hover:text-machinery-300"
          >
            {row.gene}
          </button>
        ) : (
          <span className="font-mono text-chrome-200">{row.gene}</span>
        ),
    },
    {
      key: 'group',
      header: 'group',
      sortValue: (row) => row.group,
      render: (row) => (
        <Badge tone={row.inPanel ? 'good' : row.group === 'mva-sac' ? 'machinery' : 'neutral'}>
          {GROUP_SHORT[row.group]}
        </Badge>
      ),
    },
    {
      key: 'state',
      header: 'state',
      sortValue: (row) => row.kind,
      render: (row) =>
        row.kind === 'ready' ? (
          <span className="text-good-400">ok</span>
        ) : (
          <span
            className={row.kind === 'loading' ? 'text-chrome-500' : 'text-decision-400'}
            title={row.note}
          >
            {row.kind === 'loading' ? 'loading…' : row.note}
          </span>
        ),
    },
    {
      key: 'length',
      header: 'length (aa)',
      align: 'right',
      sortValue: (row) => row.metrics?.length ?? null,
      render: (row) =>
        row.metrics ? (
          <span className="font-mono text-chrome-300">{int(row.metrics.length)}</span>
        ) : (
          NA
        ),
    },
    {
      key: 'modelled',
      header: 'modelled %',
      align: 'right',
      sortValue: (row) => row.metrics?.modelledFraction ?? null,
      render: (row) => (row.metrics ? share(row.metrics.modelledFraction, 'unknown') : NA),
    },
    {
      key: 'confident',
      header: 'pLDDT ≥ 70 %',
      align: 'right',
      sortValue: (row) => row.metrics?.confidentFraction ?? null,
      render: (row) => (row.metrics ? share(row.metrics.confidentFraction, 'not reported') : NA),
    },
    {
      key: 'helix',
      header: 'helix %',
      align: 'right',
      sortValue: (row) => row.metrics?.helixFraction ?? null,
      render: (row) => (row.metrics ? share(row.metrics.helixFraction, 'not annotated') : NA),
    },
    {
      key: 'strand',
      header: 'strand %',
      align: 'right',
      sortValue: (row) => row.metrics?.strandFraction ?? null,
      render: (row) => (row.metrics ? share(row.metrics.strandFraction, 'not annotated') : NA),
    },
    {
      key: 'domains',
      header: 'domains',
      align: 'right',
      sortValue: (row) => row.metrics?.domains.length ?? null,
      render: (row) =>
        row.metrics ? (
          <span className="font-mono text-chrome-400" title={row.metrics.domains.join(' · ')}>
            {int(row.metrics.domains.length)}
          </span>
        ) : (
          NA
        ),
    },
    {
      key: 'alleles',
      header: 'alleles placed',
      align: 'right',
      sortValue: (row) => row.metrics?.allelesPlaced ?? null,
      render: (row) =>
        row.metrics?.allelesPlaced === null || row.metrics === null ? (
          <span className="text-chrome-600">{row.metrics ? 'n/a — fold only' : '·'}</span>
        ) : (
          <span className="font-mono text-chrome-200">{int(row.metrics.allelesPlaced)}</span>
        ),
    },
    {
      key: 'closest',
      header: 'closest pair',
      align: 'right',
      sortValue: (row) => row.metrics?.closestPairAngstrom ?? null,
      render: (row) =>
        row.metrics?.closestPairAngstrom == null ? (
          <span className="text-chrome-600">{row.metrics?.inPanel ? 'under two' : NA}</span>
        ) : (
          <span
            className={
              row.metrics.closestPairConfident
                ? 'font-mono text-chrome-200'
                : 'font-mono text-chrome-500'
            }
            title={row.metrics.closestPairConfident ? '' : 'one end below pLDDT 70 — not quotable'}
          >
            {angstromLabel(row.metrics.closestPairAngstrom)}
          </span>
        ),
    },
    ...compare,
  ];
}

function Legend() {
  return (
    <>
      One row per gene in the curated structure set. The bar chart above is the{' '}
      <strong>pLDDT ≥ 70 %</strong> column, sorted, coloured by group:{' '}
      <span style={{ color: GROUP_TONE.panel }}>green = the annotated panel</span> (the eight genes
      the callset was annotated over, the only ones that can carry an allele),{' '}
      <span style={{ color: GROUP_TONE['mva-sac'] }}>
        blue = other MVA / spindle-checkpoint genes
      </span>{' '}
      and <span style={{ color: GROUP_TONE.extended }}>grey = the extended reference set</span>; the
      last two are <strong>fold only</strong>. Percentages: <strong>modelled %</strong> is residues
      with coordinates over the translation length — the complement is unmeasured, not
      &quot;fine&quot;. <strong>pLDDT ≥ 70 %</strong> is over the residues that carry a confidence
      at all, so an experimental structure reads <em>not reported</em> rather than 0 %.{' '}
      <strong>helix / strand %</strong> are over the translation length and read{' '}
      <em>not annotated</em> when the coordinate file carries no secondary-structure records — never
      &quot;all coil&quot;. The two allele columns read <em>n/a — fold only</em> outside the panel,
      because nothing was annotated there. Click a gene name to open it in the 3D explorer above.
      Nothing in this table is a ranking or a pathogenicity statement.
    </>
  );
}
