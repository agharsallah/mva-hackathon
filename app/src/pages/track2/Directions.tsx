/**
 * The four repurposing directions: the therapeutic angles the mechanism allows, each with
 * the genes it would act on.
 *
 * A direction is the unit that makes a drug list arguable. Every candidate row downstream
 * inherits the direction ids of the target it was found against, so "why this drug" always
 * resolves to a named angle rather than to a search hit.
 */

import type { RepurposingDirection, Track2Summary } from '../../api/types';
import { Badge } from '../../components/Badge';
import { DataTable } from '../../components/DataTable';
import { Chip, Exhibit } from '../../components/Exhibit';
import { C } from '../../lib/palette';
import { T } from './Term';

export function Directions({
  directions,
  summary,
  candidatesPerDirection,
  source,
}: {
  directions: RepurposingDirection[];
  summary: Track2Summary;
  /** Direction id → how many approved candidate rows carry it. */
  candidatesPerDirection: Record<string, number>;
  source?: string;
}) {
  const seedCount = (id: string) =>
    summary.card.directions.find((d) => d.id === id)?.seed_targets ?? 0;

  return (
    <Exhibit
      title="Repurposing directions — the angles the mechanism allows"
      legend={
        <>
          One row per direction. <Chip color={C.machinery}>blue = neutral machinery</Chip> — the{' '}
          <T
            slug="seed-target-target-set"
            term="seed targets"
            plain="the genes the card names by hand, before any expansion"
          />{' '}
          the direction names. <Chip color={C.good}>green = the goal</Chip> — how many{' '}
          <T
            slug="market-approved-max-phase-4"
            term="market-approved"
            plain="already licensed for some disease, so it can be prescribed today"
          />{' '}
          drug-target rows currently sit under it. A count of 0 is a real answer, not a gap.
        </>
      }
      reading={`${directions.length} directions over ${summary.targets.seed} distinct seed targets. D1 reinforces what is weakened; D2 and D3 exploit or repair the consequence; D4 addresses the tumour the child already has — so the four are not alternatives, they are different points on the same causal chain.`}
      data={directions}
      source={source}
    >
      <DataTable<RepurposingDirection>
        rows={directions}
        rowKey={(r) => r.id}
        columns={[
          {
            key: 'id',
            header: 'id',
            render: (r) => <Badge tone="machinery">{r.id}</Badge>,
          },
          {
            key: 'name',
            header: 'direction',
            render: (r) => <span className="text-chrome-100">{r.name}</span>,
          },
          {
            key: 'rationale',
            header: 'why it follows from the mechanism',
            render: (r) => (
              <span className="text-chrome-400 max-w-[60ch] inline-block">{r.rationale}</span>
            ),
          },
          {
            key: 'seed_targets',
            header: 'seed targets',
            align: 'right',
            sortValue: (r) => seedCount(r.id),
            render: (r) => (
              <span className="tabular-nums font-mono text-xs text-machinery-400">
                {seedCount(r.id)}
              </span>
            ),
          },
          {
            key: 'symbols',
            header: 'genes',
            sortable: false,
            render: (r) => (
              <span className="flex flex-wrap gap-1">
                {r.seed_targets.map((s) => (
                  <span key={s} className="font-mono text-micro text-chrome-400">
                    {s}
                  </span>
                ))}
              </span>
            ),
          },
          {
            key: 'approved',
            header: 'approved rows',
            align: 'right',
            sortValue: (r) => candidatesPerDirection[r.id] ?? 0,
            render: (r) => (
              <span className="tabular-nums font-mono text-xs text-good-400">
                {candidatesPerDirection[r.id] ?? 0}
              </span>
            ),
          },
        ]}
      />
    </Exhibit>
  );
}
