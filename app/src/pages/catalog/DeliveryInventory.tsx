import { useCatalogObjects } from '../../api/hooks';
import type { CatalogObjectRow } from '../../api/types';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Loaded } from '../../components/QueryState';
import { bytes, int, iso } from '../../lib/format';
import { C } from '../../lib/palette';

/**
 * The raw delivery, object by object — what it is, what it contains, when it arrived,
 * where it lives.
 *
 * This is the only data in the platform nothing else produced: everything on every other
 * page is a function of these bytes. So the two things worth showing loudly are the
 * checksum verdict (are our bytes the publisher's bytes?) and the arrival time (which
 * copy of the world is this?).
 */

type Group = 'callset' | 'reads' | 'metadata';

const GROUPS: { key: Group; title: string; note: string }[] = [
  { key: 'callset', title: 'Callset', note: 'the variant records and their index' },
  {
    key: 'reads',
    title: 'Reads (FASTQ)',
    note: 'the raw measurement, one object per lane × read direction',
  },
  {
    key: 'metadata',
    title: 'Metadata and sidecars',
    note: 'summaries and manifests about the two above',
  },
];

function groupOf(r: CatalogObjectRow): Group {
  if (r.role === 'reads' || r.kind.startsWith('fastq')) return 'reads';
  if (r.role.startsWith('callset') && r.role !== 'callset summary') return 'callset';
  return 'metadata';
}

function order(a: CatalogObjectRow, b: CatalogObjectRow): number {
  if (a.lane !== b.lane) return (a.lane ?? 0) - (b.lane ?? 0);
  if (a.read_num !== b.read_num) return (a.read_num ?? 0) - (b.read_num ?? 0);
  return a.file_name.localeCompare(b.file_name);
}

/** The hash claim in words: verified against whom, or not verified at all. */
function verification(r: CatalogObjectRow): { ok: boolean; label: string; title: string } {
  if (!r.hash_verified) {
    return {
      ok: false,
      label: r.sha256 ? 'not verified' : 'no digest',
      title: r.sha256
        ? 'A digest exists but was not recomputed and matched.'
        : 'No sha256 recorded for this object — nothing to check it against.',
    };
  }
  // The live API says "upload" for an own-upload digest, and "" when nothing recorded who.
  const raw = r.sha256_source || null;
  const src = raw === 'upload' ? 'own-upload' : (raw ?? 'unknown source');
  const plain =
    src === 'publisher'
      ? 'recomputed locally and matched the publisher’s manifest — our bytes are their bytes'
      : src === 'own-upload'
        ? 'recomputed after our own upload and matched — the round-trip is intact, but the publisher never asserted this file'
        : `matched a digest recorded as “${src}”`;
  return { ok: true, label: `verified · ${src}`, title: plain };
}

function ObjectCard({ r }: { r: CatalogObjectRow }) {
  const v = verification(r);
  const isReads = groupOf(r) === 'reads';
  const added = r.first_uploaded_at ?? r.last_modified;
  const fromLedger = r.first_uploaded_at !== null;

  return (
    <div
      className={`rounded-card border p-3 ${
        v.ok ? 'border-good-900/50 bg-good-950/10' : 'border-broken-900/60 bg-broken-950/20'
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="truncate font-mono text-xs text-chrome-100" title={r.file_name}>
          {r.file_name}
        </span>
        <span
          className={`shrink-0 rounded-pill px-2 py-px text-micro font-medium ${
            v.ok ? 'bg-good-500/15 text-good-400' : 'bg-broken-500/15 text-broken-400'
          }`}
          title={v.title}
        >
          {v.ok ? '✓' : '✗'} {v.label}
        </span>
      </div>

      <p className="mt-2 text-micro leading-relaxed text-chrome-400">{r.description}</p>

      <div className="mt-2 flex flex-wrap items-center gap-2 text-micro">
        <span
          className="rounded-pill px-1 py-px font-medium"
          style={{
            background: isReads ? 'rgba(168,85,247,0.15)' : 'rgba(59,130,246,0.15)',
            color: isReads ? C.raw : C.machinery,
          }}
        >
          {r.role}
        </span>
        <span className="rounded-pill bg-chrome-800 px-1 py-px font-mono text-chrome-400">
          {r.kind}
        </span>
        {r.lane !== null && (
          <span className="rounded-pill bg-raw-500/15 px-1 py-px font-mono text-raw-300">
            L{r.lane} R{r.read_num}
          </span>
        )}
        {r.flowcell && (
          <span className="rounded-pill bg-chrome-800 px-1 py-px font-mono text-chrome-500">
            {r.flowcell}
          </span>
        )}
        <span className="ml-auto font-mono text-chrome-300">{bytes(r.size_bytes)}</span>
      </div>

      <dl className="mt-2 space-y-1 border-t border-line pt-2 text-micro">
        <div className="flex gap-2">
          <dt className="w-16 shrink-0 text-chrome-600">location</dt>
          <dd className="break-all font-mono text-chrome-400">{r.location}</dd>
        </div>
        <div className="flex gap-2">
          <dt className="w-16 shrink-0 text-chrome-600">sha256</dt>
          <dd className="font-mono text-chrome-400" title={r.sha256 ?? 'no digest recorded'}>
            {r.sha256 ? `${r.sha256.slice(0, 12)}…` : <span className="text-chrome-600">none</span>}
            {r.sha256_source && <span className="ml-2 text-chrome-600">({r.sha256_source})</span>}
          </dd>
        </div>
        <div className="flex gap-2">
          <dt className="w-16 shrink-0 text-chrome-600">added</dt>
          <dd className="font-mono text-chrome-400">
            {iso(added)}
            {fromLedger ? (
              <span className="ml-2 text-chrome-600">(first upload)</span>
            ) : (
              <span
                className="ml-2 rounded-pill bg-decision-500/15 px-1 py-px text-decision-400"
                title="No ingest-ledger row for this object — it predates the ledger. This is the store's last-modified time, which is an upper bound on arrival, not the arrival itself."
              >
                last modified — predates the ledger
              </span>
            )}
          </dd>
        </div>
      </dl>
    </div>
  );
}

export function DeliveryInventory() {
  const q = useCatalogObjects();
  return (
    <Exhibit
      title="Raw delivery — every object we were given"
      legend={
        <>
          One card per object. <Chip color={C.raw}>purple = the raw measurement (FASTQ reads)</Chip>{' '}
          · <Chip color={C.machinery}>blue = callset and sidecars</Chip>.{' '}
          <Chip color={C.good}>green border and ✓ = sha256 recomputed and matched</Chip>, with the
          chip naming <em>whom</em> it matched: <span className="font-mono">publisher</span> (their
          manifest) or <span className="font-mono">own-upload</span> (our own round-trip only).{' '}
          <Chip color={C.broken}>red = unverified or no digest</Chip>.{' '}
          <Chip color={C.decision}>yellow on the date = no ingest-ledger row</Chip>, so the
          store&apos;s last-modified time is shown instead of a real arrival time. The digest is
          truncated to 12 characters; hover for all 64.
        </>
      }
      reading="Raw delivery is immutable: these bytes are never rewritten, only read. A red card, or a yellow date on an object we later reasoned about, is the kind of gap that invalidates everything downstream of it."
      data={q.data?.data}
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
    >
      <Loaded query={q} height={320}>
        {(rows) => {
          const verified = rows.filter((r) => r.hash_verified).length;
          const publisher = rows.filter(
            (r) => r.hash_verified && r.sha256_source === 'publisher',
          ).length;
          const totalBytes = rows.reduce((a, r) => a + r.size_bytes, 0);
          const ledgerless = rows.filter((r) => r.first_uploaded_at === null).length;

          return (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-xs text-chrome-400">
                <span>
                  <span className="font-mono text-chrome-100">{int(rows.length)}</span> objects
                </span>
                <span>
                  total <span className="font-mono text-chrome-100">{bytes(totalBytes)}</span>
                </span>
                <span>
                  <span className="font-mono text-good-400">{verified}</span> hash-verified (
                  {publisher} against the publisher)
                </span>
                {ledgerless > 0 && (
                  <span className="text-decision-400">
                    {ledgerless} with no first-upload record
                  </span>
                )}
              </div>

              {GROUPS.map((g) => {
                const group = rows.filter((r) => groupOf(r) === g.key).sort(order);
                if (group.length === 0) return null;
                return (
                  <div key={g.key}>
                    <div className="mb-2 flex items-baseline gap-2">
                      <h3 className="text-xs font-semibold text-chrome-400">{g.title}</h3>
                      <span className="text-micro text-chrome-600">
                        {g.note} · {group.length} object{group.length === 1 ? '' : 's'} ·{' '}
                        {bytes(group.reduce((a, r) => a + r.size_bytes, 0))}
                      </span>
                    </div>
                    <div className="grid gap-2 lg:grid-cols-2 2xl:grid-cols-3">
                      {group.map((r) => (
                        <ObjectCard key={r.object_key} r={r} />
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          );
        }}
      </Loaded>
    </Exhibit>
  );
}
