import { useState } from 'react';

import { Badge } from '../../components/Badge';
import { Toggle } from '../../components/Controls';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Loaded } from '../../components/QueryState';
import { int, pct } from '../../lib/format';
import { C } from '../../lib/palette';
import { BOX, cx } from '../../lib/ui';
import { useZooModels } from './hooks';
import { TIER_WORD } from './route';

/**
 * The roster, one card per model — what it is, what it may be used for, and how much of the
 * callset it could actually score.
 *
 * The coverage bar is the honest half of the card: a lane that scores a quarter of the
 * records is not a broken lane, it is a lane whose domain is a quarter of the records, and
 * the bar says which quarter by naming the fraction rather than averaging it away. A lane
 * that never ran shows **no bar at all** — no coverage was measured, which is a different
 * statement from zero coverage.
 */

function CoverageBar({ fraction }: { fraction: number }) {
  return (
    <div className="h-2 w-full rounded-pill bg-chrome-900" aria-hidden="true">
      <div
        className="h-full rounded-pill"
        style={{ width: `${Math.max(fraction * 100, 1)}%`, background: C.good }}
      />
    </div>
  );
}

export function ModelCards() {
  const q = useZooModels();
  const [showAll, setShowAll] = useState(false);

  return (
    <Exhibit
      title="The roster"
      controls={
        <Toggle on={showAll} onChange={setShowAll}>
          {showAll ? 'every declared lane' : 'lanes that ran'}
        </Toggle>
      }
      legend={
        <>
          One card per model in the registry. <Chip color={C.good}>green</Chip> = the share of
          allele records this lane scored · <Chip color={C.decision}>yellow</Chip> ={' '}
          <strong>catalogue-adjacent</strong>, trained on curated variant verdicts ·{' '}
          <Chip color={C.broken}>red</Chip> = a non-commercial licence, usable here and not in a
          product · <Chip color={C.machinery}>blue</Chip> = machinery (tier, source, adapter). A
          card with no bar did not run in this workflow, so no coverage was measured — which is not
          the same as zero coverage.
        </>
      }
      reading={
        <>
          Every lane is a separate opinion with a separate blind spot: the two missense lanes see
          two thirds of the missense records and nothing else, the splice lane sees most classes,
          and none of them was asked a question outside its own domain.
        </>
      }
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
      data={q.data?.data}
    >
      <Loaded query={q} height={420}>
        {(models) => {
          const shown = showAll ? models : models.filter((m) => m.enabled);
          return (
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {shown.map((m) => (
                <article
                  key={m.key}
                  className={cx(
                    'rounded-control border p-3',
                    m.enabled ? 'border-line-strong bg-well' : 'border-line bg-panel opacity-70',
                  )}
                >
                  <header className="flex flex-wrap items-baseline justify-between gap-2">
                    <h4 className="text-xs font-semibold text-chrome-100">{m.name}</h4>
                    <code className="text-micro text-chrome-500">{m.key}</code>
                  </header>
                  <p className="mt-0.5 text-micro text-chrome-400">{m.version}</p>

                  <div className="mt-2 flex flex-wrap gap-1">
                    <Badge tone="machinery" title={`inference tier ${m.tier}`}>
                      tier {m.tier} · {TIER_WORD[m.tier] ?? 'unclassified'}
                    </Badge>
                    <Badge tone="machinery" title={`adapter ${m.adapter}`}>
                      {m.source}
                    </Badge>
                    {m.catalogue_adjacent && <Badge tone="decision">catalogue-adjacent</Badge>}
                    {m.non_commercial && <Badge tone="broken">non-commercial</Badge>}
                    {!m.enabled && <Badge tone="neutral">{m.scope} · did not run</Badge>}
                  </div>

                  <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-2 gap-y-0.5 text-micro text-chrome-400">
                    <dt>licence</dt>
                    <dd className="truncate text-chrome-300" title={m.licence}>
                      {m.licence_url ? (
                        <a
                          href={m.licence_url}
                          rel="noreferrer"
                          className="underline decoration-chrome-700 underline-offset-2"
                        >
                          {m.licence}
                        </a>
                      ) : (
                        m.licence
                      )}
                    </dd>
                    <dt>adapter</dt>
                    <dd className="font-mono text-chrome-300">{m.adapter}</dd>
                    <dt>reference</dt>
                    <dd className="text-chrome-300">
                      {m.pmid ? (
                        <a
                          href={`https://pubmed.ncbi.nlm.nih.gov/${m.pmid}/`}
                          rel="noreferrer"
                          className="underline decoration-chrome-700 underline-offset-2"
                        >
                          PMID {m.pmid}
                        </a>
                      ) : (
                        'no verified PMID'
                      )}
                    </dd>
                  </dl>

                  {m.coverage ? (
                    <div className="mt-3 space-y-1">
                      <CoverageBar fraction={m.coverage.fraction} />
                      <p className="text-micro text-chrome-400">
                        scored{' '}
                        <span className="tabular-nums text-chrome-200">
                          {int(m.coverage.scored)}
                        </span>{' '}
                        of {int(m.coverage.total)} records ({pct(m.coverage.fraction * 100, 1)})
                      </p>
                    </div>
                  ) : (
                    <p
                      className={cx(
                        BOX.neutral,
                        'mt-3 rounded-control border px-2 py-1 text-micro',
                      )}
                    >
                      declared and licensed, not run — no coverage measured
                    </p>
                  )}
                </article>
              ))}
            </div>
          );
        }}
      </Loaded>
    </Exhibit>
  );
}
