import { Chip, Exhibit } from '../../components/Exhibit';
import { Loaded } from '../../components/QueryState';
import { useSources } from '../../api/hooks';
import { C } from '../../lib/palette';
import { bytes, int } from '../../lib/format';

/**
 * Delivery integrity: one card per delivered object, green only when its sha256 was
 * recomputed locally and matched the vendor's manifest. This is the first thing that has
 * to be true — every downstream number inherits it.
 */
export function DeliveryBoard() {
  const q = useSources();
  return (
    <Exhibit
      title="Delivery integrity — every object, every hash"
      legend={
        <>
          <Chip color={C.good}>✓ sha256 recomputed locally and matched the vendor manifest</Chip> ·{' '}
          <Chip color={C.broken}>✗ mismatch or not verified</Chip> · <Chip color={C.raw}>reads (FASTQ)</Chip> ·{' '}
          <Chip color={C.machinery}>callset and sidecars</Chip>. Card size is uniform; the byte figure is the
          object's own size.
        </>
      }
      reading="Nothing in the app is trustworthy if a card here is red. All of them are green."
      data={q.data?.data}
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
    >
      <Loaded query={q} height={220}>
        {(rows) => {
          const verified = rows.filter((r) => r.hash_verified).length;
          const totalBytes = rows.reduce((a, r) => a + r.size_bytes, 0);
          return (
            <>
              <div className="mb-3 flex flex-wrap items-center gap-x-5 gap-y-1 text-xs text-zinc-400">
                <span>
                  <span className="font-mono text-emerald-400">{verified}</span> / {rows.length} objects verified
                </span>
                <span>
                  total <span className="font-mono text-zinc-200">{bytes(totalBytes)}</span>
                </span>
              </div>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {rows.map((r) => {
                  const isReads = r.role === 'reads';
                  return (
                    <div
                      key={r.file_name}
                      className={`rounded-lg border p-2.5 ${
                        r.hash_verified ? 'border-emerald-900/50 bg-emerald-950/15' : 'border-red-900/60 bg-red-950/25'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <span className="truncate font-mono text-[11px] text-zinc-300" title={r.file_name}>
                          {r.file_name}
                        </span>
                        <span className={r.hash_verified ? 'text-emerald-400' : 'text-red-400'}>
                          {r.hash_verified ? '✓' : '✗'}
                        </span>
                      </div>
                      <div className="mt-1.5 flex items-center justify-between text-[10px]">
                        <span
                          className="rounded px-1 py-px font-medium"
                          style={{
                            background: isReads ? 'rgba(168,85,247,0.15)' : 'rgba(59,130,246,0.15)',
                            color: isReads ? C.raw : C.machinery,
                          }}
                        >
                          {r.role}
                          {r.lane !== null ? ` L${r.lane} R${r.read_num}` : ''}
                        </span>
                        <span className="font-mono text-zinc-500">{bytes(r.size_bytes)}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
              <p className="mt-3 text-[11px] text-zinc-500">
                {int(rows.filter((r) => r.role === 'reads').length)} FASTQ objects ·{' '}
                {int(rows.filter((r) => r.role !== 'reads').length)} callset and sidecar objects
              </p>
            </>
          );
        }}
      </Loaded>
    </Exhibit>
  );
}
