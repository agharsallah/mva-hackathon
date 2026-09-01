import type { ReactNode } from 'react';

import { useReadPartitions, useReadRuns } from '../../api/hooks';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Loaded } from '../../components/QueryState';
import { compact, dec, int } from '../../lib/format';
import { C } from '../../lib/palette';

/**
 * The read store as one catalogue entry.
 *
 * The delivered FASTQ objects are the raw input; this is the single derived artefact built
 * from all eight of them at once — a columnar copy of the same reads. It is too big to be
 * a table row and it is not a chart, so it gets a card: location, size, shape, and the
 * engine that produced it.
 *
 * Both numbers come from the existing reads endpoints; nothing here is a second source of
 * truth for the same figures the Reads page draws.
 */
export function ReadStoreCard() {
  const parts = useReadPartitions();
  const runs = useReadRuns();
  const runRows = runs.data?.data;

  return (
    <Exhibit
      title="Derived read store — the FASTQ delivery, rewritten as parquet"
      legend={
        <>
          One catalogue entry, not a chart. <Chip color={C.raw}>purple = the raw FASTQ input</Chip>{' '}
          · <Chip color={C.machinery}>blue = the derived parquet store</Chip>. A <em>partition</em>{' '}
          is one lane × read direction; a <em>shard</em> is one parquet file inside it.{' '}
          <Chip color={C.decision}>yellow = a field the source table does not carry</Chip>.
        </>
      }
      reading="The store is a format change, not a filter: the same reads, laid out columnar so a query can touch a slice instead of the whole 78.9 GiB stream."
      data={parts.data?.data}
      source={parts.data?.source}
      cachedAt={parts.data?.cachedAt}
      origin={parts.data?.origin}
    >
      <Loaded query={parts} height={160}>
        {(rows) => {
          const shards = rows.reduce((a, r) => a + r.shards, 0);
          const reads = rows.reduce((a, r) => a + r.reads, 0);
          const gib = rows.reduce((a, r) => a + r.gib, 0);
          const engines = [...new Set((runRows ?? []).map((r) => r.engine))];
          const seconds = (runRows ?? []).reduce((a, r) => a + r.seconds, 0);
          const instruments = [...new Set((runRows ?? []).map((r) => r.instrument))];

          const facts: { k: string; v: ReactNode }[] = [
            { k: 'location', v: <span className="font-mono text-zinc-300">s3://mva/reads/</span> },
            {
              k: 'format',
              v: (
                <span className="text-zinc-300">parquet, partitioned by lane × read direction</span>
              ),
            },
            {
              k: 'shape',
              v: (
                <span className="text-zinc-300">
                  <span className="font-mono text-zinc-100">{rows.length}</span> partitions ·{' '}
                  <span className="font-mono text-zinc-100">{int(shards)}</span> shards
                </span>
              ),
            },
            {
              k: 'contents',
              v: (
                <span className="text-zinc-300">
                  <span className="font-mono text-zinc-100">{int(reads)}</span> reads (
                  {compact(reads)})
                </span>
              ),
            },
            {
              k: 'size',
              v: <span className="font-mono text-blue-400">{dec(gib, 2)} GiB</span>,
            },
            {
              k: 'derived from',
              v: (
                <span className="text-zinc-300">
                  <span className="font-mono text-purple-400">s3://mva/source/*.fastq.gz</span>
                  {instruments.length > 0 && (
                    <span className="text-zinc-500"> · {instruments.join(', ')}</span>
                  )}
                </span>
              ),
            },
            {
              k: 'engine',
              v: engines.length ? (
                <span className="text-zinc-300">
                  <span className="font-mono text-zinc-100">{engines.join(', ')}</span>
                  {seconds > 0 && (
                    <span className="text-zinc-500">
                      {' '}
                      · {int(Math.round(seconds / 60))} min of conversion
                    </span>
                  )}
                </span>
              ) : (
                <span className="text-zinc-600">runs table unavailable</span>
              ),
            },
            {
              k: 'converted at',
              v: (
                <span
                  className="rounded bg-amber-500/10 px-1.5 py-px text-[11px] text-amber-400/90"
                  title="runs.parquet records the engine and the wall-clock seconds per file, but no timestamp. The conversion date is not recoverable from this table."
                >
                  not carried by the runs table
                </span>
              ),
            },
          ];

          return (
            <dl className="grid gap-x-6 gap-y-1.5 text-xs sm:grid-cols-2">
              {facts.map((f) => (
                <div key={f.k} className="flex gap-2">
                  <dt className="w-24 shrink-0 text-zinc-600">{f.k}</dt>
                  <dd className="min-w-0 break-words">{f.v}</dd>
                </div>
              ))}
            </dl>
          );
        }}
      </Loaded>
    </Exhibit>
  );
}
