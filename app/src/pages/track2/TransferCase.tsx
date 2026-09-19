/**
 * The transfer case — does this pipeline work on anyone else?
 *
 * The decoy control above answers *specificity*: how much of the drug list a wrong gene
 * would also have produced. It cannot answer *portability*, because it keeps the child —
 * the disease query, the clinical terms, the tumour, the standard-of-care exclusions are
 * all still the proband's.
 *
 * A **transfer card** swaps the whole case. A different disease with its own OMIM and MONDO
 * identifiers, its own HPO terms read out of the public `phenotype.hpoa` release rather
 * than typed, its own tumour context and its own chemotherapy list. The same code then
 * runs, with no edit and no hand-written query, and this panel is the two cases side by
 * side.
 *
 * The one boundary, stated on the panel and not only here: a transfer card carries no
 * alleles and no hand-curated evidence file, so only the **automated** rungs (1, 4 and 5)
 * exist for it. Rungs 2 and 3 are read by a person and are structurally absent — which is
 * why `curated evidence rows` is drawn, at zero, instead of being left out.
 */

import type { TransferCard, TransferComparisonRow } from '../../api/types';
import { Badge } from '../../components/Badge';
import { DataTable } from '../../components/DataTable';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Plot, type Trace } from '../../components/Plot';
import { baseLayout } from '../../components/plotLayout';
import { int } from '../../lib/format';
import { C } from '../../lib/palette';
import { T } from './Term';

/** What the chart plots, in reading order. Candidate rows are left out: an order of
 *  magnitude above everything else, they would flatten every bar that matters. */
const METRICS: { key: keyof TransferComparisonRow; label: string }[] = [
  { key: 'targets', label: 'target genes' },
  { key: 'approved_drugs', label: 'approved drugs' },
  { key: 'drugs_rung_5', label: 'drugs at best rung 5' },
  { key: 'drugs_rung_1', label: 'drugs at best rung 1' },
  { key: 'shortlist', label: 'shortlist rows' },
  { key: 'do_not', label: 'do-not rows' },
  { key: 'curated_rows', label: 'curated evidence rows' },
];

const count = (row: TransferComparisonRow, key: keyof TransferComparisonRow): number =>
  Number(row[key] ?? 0);

function identifiers(card: TransferCard): string[] {
  const block = card.card.case ?? {};
  return [
    block.omim_phenotype ? `OMIM:${block.omim_phenotype}` : '',
    block.mondo ?? '',
    block.orphanet ?? '',
    card.card.gene?.uniprot ? `UniProt:${card.card.gene.uniprot}` : '',
  ].filter(Boolean);
}

export function TransferCase({
  comparison,
  transfers,
  source,
}: {
  comparison: TransferComparisonRow[];
  transfers: TransferCard[];
  source?: string;
}) {
  const moved = comparison.filter((r) => r.role === 'transfer case');
  const colors = [C.machinery, C.raw];

  const traces: Trace[] = comparison.map((row, i) => ({
    type: 'bar',
    name: row.case,
    orientation: 'h',
    y: METRICS.map((m) => m.label),
    x: METRICS.map((m) => count(row, m.key)),
    marker: {
      color: colors[i] ?? C.machinery,
      line: { color: colors[i] ?? C.machinery, width: 1.5 },
    },
    hovertemplate: '%{y}: %{x}<extra>' + row.case + '</extra>',
  }));

  const cost = moved[0];
  const reading = cost
    ? `The same code ran on ${cost.disease} with no edit and no hand-written query: ${int(
        cost.targets,
      )} target genes, ${int(cost.approved_drugs)} approved drugs, ${int(
        cost.shortlist,
      )} shortlist rows and ${int(cost.do_not)} do-not rows, for ${int(
        cost.live_requests,
      )} live requests and ${int(cost.cached_replies)} cached replies in ${
        cost.wall_seconds || '—'
      } s. Its curated evidence rows are 0 by construction, so only the automated rungs (1, 4 and 5) may be compared — rungs 2 and 3 are read by a person and a demonstration case has nobody reading for it.`
    : 'No transfer case has been run.';

  return (
    <Exhibit
      id="transfer-case"
      title="The transfer case — the same pipeline on a different case, not just a different gene"
      legend={
        <>
          <Chip color={C.machinery}>blue = the real case</Chip> (the proband&apos;s card — the
          machinery this was built for); <Chip color={C.raw}>purple = the transfer case</Chip> (a
          second case supplied as raw public input). Bars are counts on a linear axis, unnormalised,
          so the two cases are compared as they came out and not as ratios.
        </>
      }
      reading={reading}
      data={comparison}
      source={source}
    >
      <div className="space-y-4">
        <p className="max-w-[95ch] font-serif text-note leading-relaxed text-chrome-300">
          A{' '}
          <T
            slug="transfer-mechanism-card"
            term="transfer mechanism card"
            plain="the same pipeline, a different disease, a different child — nothing of this case kept"
          />{' '}
          is the portability test a decoy cannot give: the decoy keeps the patient and swaps the
          gene, so every clinical query stays the same. Here the disease, its{' '}
          <T
            slug="hpo-human-phenotype-ontology"
            term="HPO terms"
            plain="the standard vocabulary of clinical features; read here from the public annotation file, never typed"
          />
          , the tumour context and the standard-of-care exclusions are all the second case&apos;s —
          the equivalent of running the same service against a completely different tenant&apos;s
          data and checking the output still has the right shape.
        </p>

        <Plot
          height={360}
          data={traces}
          layout={baseLayout({
            barmode: 'group',
            bargap: 0.35,
            margin: { l: 170, r: 30, t: 16, b: 44 },
            xaxis: {
              title: { text: 'rows / genes / drugs', font: { color: C.inkDim, size: 11 } },
              gridcolor: C.grid,
              tickfont: { color: C.inkDim, size: 10 },
              rangemode: 'tozero',
            },
            yaxis: {
              gridcolor: C.grid,
              tickfont: { color: C.inkDim, size: 11 },
              autorange: 'reversed',
            },
          })}
        />

        {transfers.map((card) => (
          <div key={card.case} className="flex flex-wrap items-center gap-2">
            <Badge tone="raw">{card.case}</Badge>
            <span className="text-micro text-chrome-300">
              {card.card.case?.disease ?? 'disease not recorded'}
            </span>
            {identifiers(card).map((id) => (
              <Badge key={id} tone="machinery">
                {id}
              </Badge>
            ))}
            <span className="text-micro text-chrome-500">
              tumour context: {card.card.case?.tumour_context ?? '—'}
            </span>
            <span className="text-micro text-chrome-500">
              {card.card.case?.hpo_terms?.length ?? 0} HPO terms read from{' '}
              {String(card.card.transfer?.hpo_source?.path ?? 'the public annotation')} (release{' '}
              {String(card.card.transfer?.hpo_source?.version ?? 'unrecorded')})
            </span>
          </div>
        ))}

        <DataTable<TransferComparisonRow>
          rows={comparison}
          rowKey={(r) => r.case}
          pageSize={0}
          columns={[
            {
              key: 'case',
              header: 'case',
              render: (r) => (
                <Badge tone={r.role === 'transfer case' ? 'raw' : 'machinery'}>{r.gene}</Badge>
              ),
            },
            {
              key: 'disease',
              header: 'disease',
              sortable: false,
              render: (r) => (
                <span className="inline-block max-w-[34ch] text-micro text-chrome-400">
                  {r.disease}
                </span>
              ),
            },
            ...METRICS.map((m) => ({
              key: m.key as string,
              header: m.label,
              align: 'right' as const,
              sortValue: (r: TransferComparisonRow) => count(r, m.key),
              render: (r: TransferComparisonRow) => (
                <span className="tabular-nums font-mono text-xs text-chrome-300">
                  {int(count(r, m.key))}
                </span>
              ),
            })),
            {
              key: 'live_requests',
              header: 'live requests',
              align: 'right',
              sortValue: (r) => Number(r.live_requests ?? 0),
              render: (r) => (
                <span className="tabular-nums font-mono text-xs text-chrome-300">
                  {int(r.live_requests)}
                </span>
              ),
            },
            {
              key: 'cached_replies',
              header: 'cached replies',
              align: 'right',
              sortValue: (r) => Number(r.cached_replies ?? 0),
              render: (r) => (
                <span className="tabular-nums font-mono text-xs text-chrome-300">
                  {int(r.cached_replies)}
                </span>
              ),
            },
            {
              key: 'wall_seconds',
              header: 'wall seconds',
              align: 'right',
              sortable: false,
              render: (r) => (
                <span className="tabular-nums font-mono text-xs text-chrome-300">
                  {r.wall_seconds || 'not run here'}
                </span>
              ),
            },
          ]}
        />

        <p className="max-w-[95ch] text-micro text-chrome-500">
          Only the automated rungs are comparable. A transfer card asserts no allele in any person
          and carries no hand-read <code>evidence.tsv</code>, so rungs 2 and 3 cannot appear for it
          at all, and nothing on this panel is a drug recommendation for the second disease — it is
          a measurement of the pipeline.
        </p>
      </div>
    </Exhibit>
  );
}
