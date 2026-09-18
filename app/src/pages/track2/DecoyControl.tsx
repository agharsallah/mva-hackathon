/**
 * The decoy control — how much of this drug list the mechanism actually earned.
 *
 * Track 1 has permutation nulls: shuffle the labels, re-run, see what the pipeline returns
 * by chance. Track 2 had none, which is the gap this exhibit closes. A **decoy card** keeps
 * the child, the clinical terms and the pipeline, and swaps the gene for one that is not the
 * answer. Whatever comes out for the decoy as readily as for the real gene was nominated by
 * the clinical queries or by how densely a target is covered in drug databases — not by the
 * mechanism.
 *
 * The measure is the Jaccard overlap of the approved drug names, and the line at 0.10 was
 * registered as claim H049 before the decoys were run.
 */

import type { DecoyCard, DecoyComparisonRow } from '../../api/types';
import { Badge } from '../../components/Badge';
import { DataTable } from '../../components/DataTable';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Plot, type Trace } from '../../components/Plot';
import { baseLayout } from '../../components/plotLayout';
import { int } from '../../lib/format';
import { C } from '../../lib/palette';
import { JACCARD_LINE } from './ladderModel';
import { T } from './Term';

/** `all` and `pathway` are roll-ups, not directions: the chart draws the directions. */
const isDirection = (id: string): boolean => /^D\d+$/.test(id);

const above = (row: DecoyComparisonRow): boolean => Number(row.jaccard) > JACCARD_LINE;

export function DecoyControl({
  comparison,
  decoys,
  source,
}: {
  comparison: DecoyComparisonRow[];
  decoys: DecoyCard[];
  source?: string;
}) {
  const rows = comparison.filter((r) => isDirection(r.direction_id));
  const directions = [...new Set(rows.map((r) => r.direction_id))].sort();
  const names = [...new Set(rows.map((r) => r.decoy))].sort();
  const colors = [C.machinery, C.raw];

  const traces: Trace[] = names.map((decoy, i) => {
    const mine = directions.map((d) => rows.find((r) => r.decoy === decoy && r.direction_id === d));
    return {
      type: 'bar',
      name: decoy,
      x: directions,
      y: mine.map((r) => (r ? Number(r.jaccard) : 0)),
      marker: {
        color: mine.map((r) => (r && above(r) ? C.broken : (colors[i] ?? C.machinery))),
        line: { color: colors[i] ?? C.machinery, width: 1.5 },
      },
      hovertemplate: '%{x} vs ' + decoy + ': Jaccard %{y:.4f}<extra></extra>',
    };
  });

  const nonSpecific = [...new Set(rows.filter(above).map((r) => r.direction_id))].sort();
  const specific = directions.filter((d) => !nonSpecific.includes(d));

  return (
    <Exhibit
      id="decoy-control"
      title="The decoy control — how much of this list a wrong gene would also have produced"
      legend={
        <>
          One bar per direction per decoy card. <Chip color={C.machinery}>blue and</Chip>{' '}
          <Chip color={C.raw}>purple = one decoy each</Chip> — a bar below the line is a direction
          the decoy did <em>not</em> reproduce, which is the good outcome.{' '}
          <Chip color={C.broken}>red = above the line</Chip>: the decoy returned much the same
          approved drugs, so that direction is non-specific. The dashed rule is the pre-registered
          threshold <strong>0.10</strong>, fixed in claim H049 before either decoy was run — not
          chosen after seeing these bars.
        </>
      }
      reading={
        nonSpecific.length > 0
          ? `${nonSpecific.join(', ')} sits above the 0.10 line and is non-specific: it is the tumour-context direction, and a decoy gene reaches the same approved drugs through the same rhabdomyosarcoma queries. ${specific.join(', ')} stay below it, so their drug sets came from the mechanism rather than from the clinical context. Only the automated stages are comparable — a decoy gets no hand-read literature.`
          : 'No direction crosses the 0.10 line.'
      }
      data={comparison}
      source={source}
    >
      <div className="space-y-4">
        <p className="max-w-[95ch] font-serif text-note leading-relaxed text-chrome-300">
          A{' '}
          <T
            slug="decoy-mechanism-card"
            term="decoy mechanism card"
            plain="the same pipeline, the same child, a gene that is not the answer"
          />{' '}
          is the negative control a drug search normally lacks — the equivalent of running your test
          suite against a stubbed-out implementation to see how many tests still pass. The overlap
          is measured with the{' '}
          <T
            slug="jaccard-index"
            term="Jaccard index"
            plain="shared drugs divided by all the drugs in either set; 0 is disjoint, 1 is identical"
          />{' '}
          over{' '}
          <T
            slug="base-name-salt-folding"
            term="base names"
            plain="drug names with the salt or formulation words removed, so one molecule is counted once"
          />
          , and only the{' '}
          <T
            slug="automated-versus-curated-rung"
            term="automated stages"
            plain="approval, labels, trials and literature counts — what a program looks up for any card"
          />{' '}
          are comparable at all.
        </p>

        <Plot
          height={320}
          data={traces}
          layout={baseLayout({
            barmode: 'group',
            bargap: 0.35,
            margin: { l: 60, r: 20, t: 16, b: 44 },
            yaxis: {
              title: {
                text: 'Jaccard overlap with the decoy',
                font: { color: C.inkDim, size: 11 },
              },
              gridcolor: C.grid,
              tickfont: { color: C.inkDim, size: 10 },
              rangemode: 'tozero',
            },
            xaxis: { gridcolor: C.grid, tickfont: { color: C.inkDim, size: 11 } },
            shapes: [
              {
                type: 'line',
                xref: 'paper',
                x0: 0,
                x1: 1,
                yref: 'y',
                y0: JACCARD_LINE,
                y1: JACCARD_LINE,
                line: { color: C.broken, width: 1.5, dash: 'dash' },
              },
            ],
            annotations: [
              {
                xref: 'paper',
                yref: 'y',
                x: 1,
                y: JACCARD_LINE,
                xanchor: 'right',
                yanchor: 'bottom',
                showarrow: false,
                text: 'pre-registered 0.10 line (H049)',
                font: { color: C.broken, size: 10 },
              },
            ],
          })}
        />

        <DataTable<DecoyCard>
          rows={decoys}
          rowKey={(d) => d.symbol}
          pageSize={0}
          columns={[
            {
              key: 'symbol',
              header: 'decoy gene',
              render: (d) => <Badge tone="raw">{d.symbol}</Badge>,
            },
            {
              key: 'picked_by',
              header: 'how it was picked',
              sortable: false,
              render: (d) => (
                <span className="inline-block max-w-[52ch] text-micro text-chrome-400">
                  {d.card.decoy?.picked_by ?? 'not recorded'}
                </span>
              ),
            },
            {
              key: 'targets',
              header: 'targets',
              align: 'right',
              sortValue: (d) => d.snapshot.targets?.total ?? null,
              render: (d) => (
                <span className="tabular-nums font-mono text-xs text-chrome-300">
                  {int(d.snapshot.targets?.total)}
                </span>
              ),
            },
            {
              key: 'approved',
              header: 'approved drugs',
              align: 'right',
              sortValue: (d) => d.snapshot.candidates?.distinct_approved_drugs ?? null,
              render: (d) => (
                <span className="tabular-nums font-mono text-xs text-chrome-300">
                  {int(d.snapshot.candidates?.distinct_approved_drugs)}
                </span>
              ),
            },
            {
              key: 'comparable',
              header: 'what may be compared',
              sortable: false,
              render: (d) => (
                <span className="inline-block max-w-[50ch] text-micro text-chrome-500">
                  {d.card.decoy?.comparable ?? '—'}
                </span>
              ),
            },
          ]}
        />
      </div>
    </Exhibit>
  );
}
