import { useDerivations, useLineage } from '../../api/hooks';
import type { DerivationRow, LineageRow } from '../../api/types';
import { type Column, DataTable } from '../../components/DataTable';
import { Loaded } from '../../components/QueryState';
import { int, iso } from '../../lib/format';

/**
 * Derivations, each with the question it exists to answer.
 *
 * A derived table with no recorded question is an orphan: nobody can tell later whether it
 * is still needed or whether its answer has been superseded. Storing the question next to
 * the row count is the cheapest defence against that.
 */
export function Derivations() {
  const q = useDerivations();
  const columns: Column<DerivationRow>[] = [
    {
      key: 'derivation',
      header: 'derivation',
      render: (r) => <span className="font-mono text-chrome-100">{r.derivation}</span>,
    },
    {
      key: 'question',
      header: 'the question it answers',
      render: (r) => <span className="text-chrome-300">{r.question}</span>,
    },
    { key: 'rows', header: 'rows', align: 'right', render: (r) => int(r.n_rows) },
    {
      key: 'at',
      header: 'run at',
      render: (r) => <span className="font-mono text-chrome-500">{iso(r.run_at)}</span>,
    },
  ];
  return (
    <div className="space-y-2">
      <Loaded query={q} height={220}>
        {(rows) => (
          <DataTable
            rows={rows}
            columns={columns}
            rowKey={(r) => r.derivation}
            empty="No derivations recorded."
          />
        )}
      </Loaded>
      <p className="text-[11px] text-chrome-600">
        Each row is a table this app reads from. If a derivation cannot state its question, it
        should not exist.
      </p>
    </div>
  );
}

/** The same lineage rows, flat, for anyone who wants the audit trail rather than the picture. */
export function LineageTable() {
  const q = useLineage();
  const columns: Column<LineageRow>[] = [
    {
      key: 'target',
      header: 'produced',
      render: (r) => (
        <span className="font-mono text-chrome-100">
          {r.target_schema}.{r.target_table}
        </span>
      ),
    },
    { key: 'rows', header: 'rows', align: 'right', render: (r) => int(r.target_rows) },
    {
      key: 'source',
      header: 'from',
      render: (r) => (
        <span className="font-mono text-chrome-400" title={r.source_ref}>
          {r.source_ref}
        </span>
      ),
    },
    {
      key: 'hash',
      header: 'source hash',
      render: (r) =>
        r.source_sha256 ? (
          <span className="text-good-400">✓ {r.source_sha256}</span>
        ) : (
          <span className="text-chrome-600">inherited</span>
        ),
    },
    {
      key: 'transform',
      header: 'transform',
      render: (r) => <span className="text-chrome-300">{r.transform}</span>,
    },
    {
      key: 'tool',
      header: 'tool',
      render: (r) => <span className="font-mono text-chrome-500">{r.tool}</span>,
    },
    {
      key: 'at',
      header: 'produced at',
      render: (r) => <span className="font-mono text-chrome-500">{iso(r.produced_at)}</span>,
    },
  ];
  return (
    <Loaded query={q} height={260}>
      {(rows) => (
        <DataTable
          rows={rows}
          columns={columns}
          rowKey={(r, i) => `${r.target_schema}.${r.target_table}:${i}`}
          maxHeight={420}
          empty="No lineage recorded."
        />
      )}
    </Loaded>
  );
}
