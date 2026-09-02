import { useHealthDependencies } from '../../api/hooks';
import { Callout, ErrorCard, Skeleton, StatTile } from '../../components';
import { int } from '../../lib/format';
import { deriveVerdict, statusLabel, statusTone } from './verdict';

/**
 * The top-of-page answer: what works, what doesn't, and what that costs right now. The
 * cost sentence is built entirely from `powers` on the broken checks — nothing here names
 * a page by hand, so it cannot drift from what the endpoint actually reports.
 */
export function OverallVerdict() {
  const q = useHealthDependencies();

  if (q.isPending) return <Skeleton height={150} />;
  if (q.error) return <ErrorCard error={q.error} />;
  if (!q.data) return <Skeleton height={150} />;

  const payload = q.data.data;
  const v = deriveVerdict(payload.checks, payload.overall);

  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile
          label="overall"
          value={statusLabel(v.overall).toUpperCase()}
          tone={statusTone(v.overall)}
          sub={`checked ${payload.checked_at.replace('T', ' ').slice(0, 19)} UTC`}
        />
        <StatTile
          label="working"
          value={int(v.working.length)}
          tone="good"
          sub={`of ${int(payload.checks.length)} checks`}
        />
        <StatTile
          label="broken or degraded"
          value={int(v.broken.length)}
          tone={v.broken.length > 0 ? 'broken' : 'good'}
          sub="down + degraded"
        />
        <StatTile
          label="not configured"
          value={int(v.skipped.length)}
          tone="neutral"
          sub="optional — not a failure"
        />
      </div>

      {v.broken.length > 0 ? (
        <Callout
          tone={v.overall === 'down' ? 'broken' : 'decision'}
          title="What this costs you right now"
        >
          {v.broken.map((c) => c.name).join(', ')} {v.broken.length === 1 ? 'is' : 'are'} down or
          degraded.{' '}
          {v.affectedPages.length > 0 ? (
            <>
              That leaves <strong>{v.affectedPages.join(', ')}</strong>{' '}
              {v.affectedPages.length === 1 ? 'page' : 'pages'} degraded or unusable until it's
              fixed — see the Remedy on each card below.
            </>
          ) : (
            'No page in this app depends on it directly, so nothing else is affected.'
          )}
        </Callout>
      ) : (
        <Callout tone="good" title="Everything required is working">
          Every internal and upstream dependency answered cleanly.
          {v.skipped.length > 0
            ? ` ${v.skipped.length} optional feature${v.skipped.length === 1 ? '' : 's'} not configured — see below, not a failure.`
            : ''}
        </Callout>
      )}
    </div>
  );
}
