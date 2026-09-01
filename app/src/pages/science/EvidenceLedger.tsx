import { useMemo, useState } from 'react';

import { useEvidence } from '../../api/hooks';
import type { EvidenceRow } from '../../api/types';
import { TextFilter } from '../../components/Controls';
import { type Column, DataTable } from '../../components/DataTable';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Loaded } from '../../components/QueryState';
import { dec, iso } from '../../lib/format';
import { C } from '../../lib/palette';
import { directionColor, EmptyRegister } from './register';

/**
 * The evidence ledger: one row per sourced observation, tagged with the claim it moves.
 *
 * `source_ref` is monospaced and never truncated, because it is the whole point of the row
 * — an observation whose source cannot be followed is not evidence, and the constructor
 * refuses to record one.
 */
export function EvidenceLedger() {
  const query = useEvidence();
  const [filter, setFilter] = useState('');

  return (
    <Exhibit
      title="Evidence ledger"
      legend={
        <>
          <Chip color={C.good}>green = supports the claim</Chip>,{' '}
          <Chip color={C.broken}>red = refutes it</Chip>,{' '}
          <Chip color={C.absent}>grey = neutral</Chip>. The bar under <em>strength</em> is the human
          judgement of how much the observation moves the claim (0–1), not a measured quantity. A
          dash in <em>lineage</em> means the observation is not tied to one derivation — the
          register carries the gap rather than inventing an edge.
        </>
      }
      reading="Filter by hypothesis id to see one claim's whole case, for and against, in the order it accumulated."
      controls={
        <TextFilter
          value={filter}
          onChange={setFilter}
          label="filter"
          placeholder="hypothesis id, direction, source…"
          width={260}
        />
      }
      data={query.data?.data}
      source={query.data?.source}
      cachedAt={query.data?.cachedAt}
      origin={query.data?.origin}
    >
      <Loaded query={query} height={200}>
        {(register) =>
          register.rows.length === 0 ? (
            <EmptyRegister
              tableExists={register.table_exists}
              title="No evidence yet — nothing has been claimed for it to bear on"
              verb="mva-science evidence-add"
            >
              Evidence is bound to a hypothesis, so the ledger cannot open before the board does.
              Every row that lands here must name its source — a methodology entry, a table, a PMID,
              a ClinVar id or an oracle reply — because an unsourced observation is refused rather
              than recorded.
            </EmptyRegister>
          ) : (
            <Ledger rows={register.rows} filter={filter} />
          )
        }
      </Loaded>
    </Exhibit>
  );
}

function Ledger({ rows, filter }: { rows: EvidenceRow[]; filter: string }) {
  const needle = filter.trim().toLowerCase();
  const shown = useMemo(
    () =>
      needle
        ? rows.filter((r) =>
            [r.hypothesis_id, r.direction, r.kind, r.source_ref, r.claim, r.lineage_ref ?? '']
              .join(' ')
              .toLowerCase()
              .includes(needle),
          )
        : rows,
    [rows, needle],
  );

  const columns: Column<EvidenceRow>[] = [
    {
      key: 'id',
      header: 'id',
      render: (r) => <span className="font-mono text-zinc-500">{r.evidence_id}</span>,
    },
    {
      key: 'hyp',
      header: 'claim',
      render: (r) => <span className="font-mono text-zinc-100">{r.hypothesis_id}</span>,
    },
    {
      key: 'direction',
      header: 'direction',
      render: (r) => (
        <span
          className="inline-flex items-center gap-1.5 font-medium"
          style={{ color: directionColor(r.direction) }}
        >
          <span
            className="h-2 w-2 rounded-sm"
            style={{ background: directionColor(r.direction) }}
          />
          {r.direction}
        </span>
      ),
    },
    {
      key: 'strength',
      header: 'strength',
      render: (r) => (
        <span className="inline-flex items-center gap-2">
          <span className="font-mono text-zinc-300">{dec(r.strength, 2)}</span>
          <span className="inline-block h-1.5 w-14 rounded-sm bg-zinc-800">
            <span
              className="block h-full rounded-sm"
              style={{
                width: `${Math.max(0, Math.min(1, r.strength)) * 100}%`,
                background: directionColor(r.direction),
              }}
            />
          </span>
        </span>
      ),
    },
    {
      key: 'kind',
      header: 'kind',
      render: (r) => <span className="font-mono text-zinc-400">{r.kind}</span>,
    },
    {
      key: 'claim',
      header: 'observation',
      render: (r) => <span className="text-zinc-300">{r.claim}</span>,
    },
    {
      key: 'source',
      header: 'source',
      render: (r) => <span className="font-mono text-[11px] text-blue-300">{r.source_ref}</span>,
    },
    {
      key: 'lineage',
      header: 'lineage',
      render: (r) => (
        <span className="font-mono text-[11px] text-zinc-500">{r.lineage_ref ?? '—'}</span>
      ),
    },
    {
      key: 'at',
      header: 'recorded',
      render: (r) => (
        <span className="font-mono text-[11px] text-zinc-600">{iso(r.recorded_at)}</span>
      ),
    },
  ];

  return (
    <div className="space-y-2">
      <DataTable
        rows={shown}
        columns={columns}
        rowKey={(r) => String(r.evidence_id)}
        maxHeight={420}
        empty={`no evidence row matches "${filter}"`}
      />
      <p className="font-mono text-[11px] text-zinc-600">
        {shown.length} of {rows.length} rows
      </p>
    </div>
  );
}
