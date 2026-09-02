import { useHealthDependencies } from '../../api/hooks';
import type { DependencyCheck } from '../../api/types';
import { Badge, Callout, Chip, Exhibit, FieldList, Loaded } from '../../components';
import { int } from '../../lib/format';
import { C } from '../../lib/palette';
import { endpointFor } from './configured';
import { useRefreshRequested } from './useRefresh';
import { groupChecks, statusLabel, statusTone } from './verdict';

/**
 * One card per check, grouped by `kind`. This is the point of the page: a broken
 * dependency has to leave behind a message a developer can act on, not a red dot. So the
 * card's `remedy` — multi-line shell advice from the endpoint — is rendered as
 * preformatted, wrapping text inside the card itself, not tucked behind a hover or a link.
 */
function DependencyCard({ check, origin }: { check: DependencyCheck; origin: 'api' | 'fixture' }) {
  const tone = statusTone(check.status);
  // Offline, the committed fixture cannot know this checkout's hosts, so the address comes
  // from the repo-root .env instead and says so — a loopback placeholder would be a lie
  // for anyone whose services run on a server.
  const endpoint = endpointFor(check.id, check.endpoint, origin);
  const fields = [
    {
      key: 'latency',
      label: 'latency',
      value: check.latency_ms === null ? '—' : `${int(check.latency_ms)} ms`,
    },
    {
      key: 'endpoint',
      label: 'endpoint',
      value: endpoint
        ? `${endpoint.value}${endpoint.fromEnv ? '  (configured in .env)' : ''}`
        : '—',
    },
    {
      key: 'powers',
      label: 'powers',
      value: check.powers.length > 0 ? check.powers.join(', ') : '— (no page depends on this)',
    },
  ];

  return (
    <Callout tone={tone} title={`${check.name} — ${statusLabel(check.status)}`}>
      <div className="space-y-3">
        <p>{check.detail}</p>
        <FieldList fields={fields} labelWidth={64} />
        {check.remedy && (
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-wider text-chrome-200">
              {check.status === 'skipped' ? 'How to enable it (optional)' : 'Remedy'}
            </div>
            <pre className="mt-1 max-w-full overflow-x-auto whitespace-pre-wrap break-words rounded-md border border-chrome-700/60 bg-black/25 p-3 font-mono text-[11px] leading-relaxed text-chrome-100">
              {check.remedy}
            </pre>
          </div>
        )}
      </div>
    </Callout>
  );
}

export function DependencyBoard() {
  const q = useHealthDependencies(useRefreshRequested());

  return (
    <Exhibit
      title="Dependency board — every backing service, probed live"
      legend={
        <>
          One card per check, grouped by kind. <Chip color={C.good}>green = up</Chip> ·{' '}
          <Chip color={C.decision}>yellow = degraded</Chip> — answering, but not cleanly ·{' '}
          <Chip color={C.broken}>red = down</Chip> ·{' '}
          <Chip color={C.absent}>grey = not configured</Chip>, which is a deliberate choice (e.g. no
          S3 credentials), never a failure. Groups run <strong>internal</strong> (ours, required) →{' '}
          <strong>upstream</strong> (ours, optional) → <strong>third-party</strong> (someone
          else&apos;s service) → <strong>snapshot</strong> (ingested reference data, not a live
          service).
        </>
      }
      reading="A red or yellow card carries its Remedy inline — the shell commands a developer would actually run — rather than a status dot. `powers` names the pages that stop working while it stays that way."
      data={q.data?.data}
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
    >
      <Loaded query={q} height={420}>
        {(data) => (
          <div className="space-y-5">
            {groupChecks(data.checks).map((g) => {
              const checks = g.checks;
              return (
                <div key={g.key}>
                  <div className="mb-2 flex items-baseline gap-2">
                    <h4 className="text-xs font-semibold uppercase tracking-wider text-chrome-300">
                      {g.title}
                    </h4>
                    <span className="text-[11px] text-chrome-600">{g.note}</span>
                    <Badge tone="neutral" className="ml-auto">
                      {checks.length} check{checks.length === 1 ? '' : 's'}
                    </Badge>
                  </div>
                  <div className="grid gap-3 lg:grid-cols-2">
                    {checks.map((c) => (
                      <DependencyCard key={c.id} check={c} origin={q.data?.origin ?? 'api'} />
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Loaded>
    </Exhibit>
  );
}
