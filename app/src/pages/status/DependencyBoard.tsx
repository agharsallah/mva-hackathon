import { useState } from 'react';

import { useHealthDependencies, useReprobeCheck } from '../../api/hooks';
import { Badge, Chip, ErrorCard, Exhibit, Loaded, Toggle } from '../../components';
import { C } from '../../lib/palette';
import { DependencyCard } from './DependencyCard';
import { useCanRevealAddresses } from './statusDebug';
import { useRefreshRequested } from './useRefresh';
import { groupChecks } from './verdict';

/**
 * The board: one card per check, grouped by `kind`, plus the two controls that act on the
 * board as a whole.
 *
 * `reveal addresses` flips every card's host and port from masked to plain in one click —
 * the per-card toggle is for looking at one thing, this is for working. Masked is the
 * default because this page is all infrastructure addresses and it gets screenshotted; see
 * `redact.ts` for what that does and does not protect.
 *
 * Re-probing is per card (`useReprobeCheck`), so restarting one service costs one probe
 * instead of a round trip to Postgres, MinIO, the reads API and Ensembl at once.
 */
export function DependencyBoard() {
  const forced = useRefreshRequested();
  const q = useHealthDependencies(forced);
  const { reprobe, pendingId, error } = useReprobeCheck(forced);
  const [revealAll, setRevealAll] = useState(false);
  const canReveal = useCanRevealAddresses();
  const origin = q.data?.origin ?? 'api';

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
      reading="A red or yellow card carries its Remedy inline — the shell commands a developer would actually run — rather than a status dot. `powers` names the pages that stop working while it stays that way. Each card says when it was last probed and against what timeout budget, and re-probes on its own without touching the other six."
      data={q.data?.data}
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
    >
      <div className="mb-3 flex flex-wrap items-center gap-3">
        {canReveal ? (
          <>
            <Toggle on={revealAll} onChange={setRevealAll}>
              {revealAll ? 'addresses shown' : 'reveal addresses'}
            </Toggle>
            <span className="text-micro text-chrome-600">
              hosts and ports are hidden by default — this page is all infrastructure addresses and
              gets screenshotted
            </span>
          </>
        ) : (
          <span className="text-micro text-chrome-600">
            hosts and ports stay hidden here — unlock the advanced diagnostics panel to reveal them
          </span>
        )}
      </div>
      {error && <ErrorCard error={error} />}

      <Loaded query={q} height={420}>
        {(data) => (
          <div className="space-y-4">
            {groupChecks(data.checks).map((g) => {
              const checks = g.checks;
              return (
                <div key={g.key}>
                  <div className="mb-2 flex items-baseline gap-2">
                    <h3 className="text-xs font-semibold text-chrome-400">{g.title}</h3>
                    <span className="text-micro text-chrome-600">{g.note}</span>
                    <Badge tone="neutral" className="ml-auto">
                      {checks.length} check{checks.length === 1 ? '' : 's'}
                    </Badge>
                  </div>
                  <div className="grid gap-3 lg:grid-cols-2">
                    {checks.map((c) => (
                      <DependencyCard
                        key={c.id}
                        check={c}
                        origin={origin}
                        canReveal={canReveal}
                        revealAll={canReveal && revealAll}
                        reprobing={pendingId === c.id}
                        onReprobe={reprobe}
                      />
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
