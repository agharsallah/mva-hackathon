import { useHealthDependencies } from '../../api/hooks';
import { Callout, Section } from '../../components';
import { iso } from '../../lib/format';
import { useRefreshRequested } from './useRefresh';

/**
 * Hidden diagnostics panel — see `statusDebug.ts` for the unlock gate. Renders the raw
 * envelope this page's cards are built from, unmasked and unsummarized: the exact JSON the
 * API returned, plus the react-query request state around it. This is deliberately more
 * than any card shows — it exists for triage when the summarized cards above aren't enough,
 * not for everyday reading.
 */
export function AdvancedPanel() {
  const forced = useRefreshRequested();
  const q = useHealthDependencies(forced);

  return (
    <Section
      title="Advanced (unlocked diagnostics)"
      subtitle="raw payload and request state, unmasked — not shown unless you set the debug key yourself"
    >
      <Callout tone="decision" title="This panel is not access-controlled">
        The unlock is a client-side localStorage flag, not authentication — anyone with console
        access to this browser can set it too. Treat what's below as no more sensitive than the rest
        of this page, addresses included.
      </Callout>

      <div className="mt-3 grid gap-3 lg:grid-cols-2">
        <div>
          <h3 className="mb-1 text-xs font-semibold text-chrome-400">request state</h3>
          <pre className="max-w-full overflow-x-auto whitespace-pre-wrap break-words rounded-control border border-line-strong bg-black/25 p-3 font-mono text-micro leading-relaxed text-chrome-100">
            {JSON.stringify(
              {
                status: q.status,
                fetchStatus: q.fetchStatus,
                dataUpdatedAt: q.dataUpdatedAt
                  ? iso(new Date(q.dataUpdatedAt).toISOString())
                  : null,
                errorUpdatedAt: q.errorUpdatedAt
                  ? iso(new Date(q.errorUpdatedAt).toISOString())
                  : null,
                failureCount: q.failureCount,
                isStale: q.isStale,
                origin: q.data?.origin ?? null,
                source: q.data?.source ?? null,
                cachedAt: q.data?.cachedAt ?? null,
              },
              null,
              2,
            )}
          </pre>
        </div>
        <div>
          <h3 className="mb-1 text-xs font-semibold text-chrome-400">raw payload</h3>
          <pre className="max-h-96 max-w-full overflow-auto whitespace-pre-wrap break-words rounded-control border border-line-strong bg-black/25 p-3 font-mono text-micro leading-relaxed text-chrome-100">
            {q.data ? JSON.stringify(q.data.data, null, 2) : 'no data yet'}
          </pre>
        </div>
      </div>
    </Section>
  );
}
