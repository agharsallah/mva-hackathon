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
 *   because the callset was annotated over the panel BED: a zero there would be a claim
 *   about the patient that no measurement supports. That test is `in_panel`, never a group
 *   id — group ids, labels, order and colours all come from the payload (see `geneSet.ts`),
 *   so a foreign reference table renames every group and this table still reads correctly.
 *
 * Each row owns its own request pair (`useGeneStructures` / `useProteinStructures` fan out one
 * query per gene), so one gene whose fold is unreachable shows its error in its own row and
 * leaves the rest of the table standing.
 *
 * That fan-out is **one gene-structure + one protein request per gene** (23 + 21 = 44 for
 * this case's table), and this exhibit sits far below the fold on
 * `/panel`. So it is gated on `useInView`: nothing is requested until the section is within
 * 300 px of the viewport, and while it is not, the table says how many genes it is about to
 * ask for rather than pretending to be empty. Spending that many cold Ensembl/AlphaFold
 * round-trips on a reader who never scrolls this far is the cost the gate exists to refuse.
 */

import { useMemo } from 'react';

import { useGeneStructures, useProteinStructures, useStructureGenes } from '../../../../api/hooks';
import type { StructureGene } from '../../../../api/types';
import { DataTable } from '../../../../components/DataTable';
import { Exhibit } from '../../../../components/Exhibit';
import { Plot } from '../../../../components/Plot';
import { baseLayout } from '../../../../components/plotLayout';
import { Skeleton } from '../../../../components/QueryState';
import { int } from '../../../../lib/format';
import { useInView } from '../../../../lib/hooks';
import { C, type Tone, TONE_MARK } from '../../../../lib/palette';
import { type GeneGroup, geneGroupings, groupTones } from '../geneSet';
import { type StructureRow, structureRow } from './metrics';
import { buildColumns } from './metricsColumns';

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

  // Group id -> tone, assigned by the group's rank in the set. Nothing here names a group.
  const tones = useMemo(() => groupTones(genes), [genes]);
  const groups = useMemo(() => geneGroupings(genes), [genes]);
  const columns = useMemo(
    () => buildColumns(tones, onPickGene, onCompare),
    [tones, onPickGene, onCompare],
  );

  return (
    <Exhibit
      title="Every gene in the set, as numbers"
      legend={<Legend groups={groups} tones={tones} />}
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
            <ConfidenceBars rows={rows} tones={tones} />
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
function ConfidenceBars({
  rows,
  tones,
}: {
  rows: readonly StructureRow[];
  tones: ReadonlyMap<string, Tone>;
}) {
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
          marker: {
            color: sorted.map((row) => TONE_MARK[tones.get(row.group) ?? 'neutral']),
          },
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

function Legend({
  groups,
  tones,
}: {
  groups: readonly GeneGroup[];
  tones: ReadonlyMap<string, Tone>;
}) {
  return (
    <>
      One row per gene in the curated structure set. The bar chart above is the{' '}
      <strong>pLDDT ≥ 70 %</strong> column, sorted, coloured by group — the groups, their wording
      and their order all come from the reference table, not from this component:{' '}
      {groups.map((group, index) => (
        <span key={group.id}>
          {index > 0 ? (index === groups.length - 1 ? ' and ' : ', ') : ''}
          <span style={{ color: TONE_MARK[tones.get(group.id) ?? 'neutral'] }}>{group.label}</span>
        </span>
      ))}
      . Only the genes flagged <strong>in_panel</strong> carry the proband&apos;s annotated alleles;
      every other row is <strong>fold only</strong>, whatever its group is called. Percentages:{' '}
      <strong>modelled %</strong> is residues with coordinates over the translation length — the
      complement is unmeasured, not &quot;fine&quot;. <strong>pLDDT ≥ 70 %</strong> is over the
      residues that carry a confidence at all, so an experimental structure reads{' '}
      <em>not reported</em> rather than 0 %. <strong>helix / strand %</strong> are over the
      translation length and read <em>not annotated</em> when the coordinate file carries no
      secondary-structure records — never &quot;all coil&quot;. The two allele columns read{' '}
      <em>n/a — fold only</em> outside the panel, because nothing was annotated there. Click a gene
      name to open it in the 3D explorer above. Nothing in this table is a ranking or a
      pathogenicity statement.
    </>
  );
}
