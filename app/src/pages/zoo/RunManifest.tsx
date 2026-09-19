import type { ZooRun, ZooStage } from '../../api/types/zoo';
import { type Column, DataTable } from '../../components/DataTable';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Loaded } from '../../components/QueryState';
import { StatTile } from '../../components/StatTile';
import { dec, int, iso } from '../../lib/format';
import { C } from '../../lib/palette';
import { useZooRuns } from './hooks';

/**
 * The run manifests — what it cost to produce everything else on this page.
 *
 * This is the methods form's compute question answered from a record rather than from memory:
 * wall-clock seconds, dollars spent, the exact artefact version each lane ran, and the venue
 * each one ran at. The configuration's digest is the run id, so the same configuration re-run
 * is the same run: a manifest is therefore a reproduction recipe, not a log line.
 */

const stageColumns: Column<ZooStage>[] = [
  {
    key: 'stage',
    header: 'stage',
    render: (s) => <code className="text-chrome-300">{s.stage}</code>,
  },
  {
    key: 'seconds',
    header: 'seconds',
    align: 'right',
    render: (s) => <span className="tabular-nums">{dec(s.seconds, 2)}</span>,
  },
  {
    key: 'rows',
    header: 'rows',
    align: 'right',
    render: (s) => <span className="tabular-nums">{int(s.rows)}</span>,
  },
  { key: 'note', header: 'note', render: (s) => <span className="text-chrome-400">{s.note}</span> },
];

function RunCard({ run }: { run: ZooRun }) {
  const lanes = Object.keys(run.models);
  return (
    <article className="space-y-3 rounded-control border border-line-strong bg-well p-3">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <code className="text-xs text-chrome-100">{run.run_id}</code>
        <span className="text-micro text-chrome-500">
          {iso(run.started)} → {iso(run.finished)}
        </span>
      </header>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile
          label="Wall clock"
          value={`${dec(run.wall_clock_s, 1)} s`}
          tone="machinery"
          sub="every stage, end to end"
        />
        <StatTile
          label="Spend"
          value={`$${dec(run.dollars, 2)}`}
          tone={run.dollars === 0 ? 'good' : 'decision'}
          sub={run.dollars === 0 ? 'no paid inference in this run' : 'metered inference'}
        />
        <StatTile label="Lanes" value={lanes.length} sub={lanes.join(', ')} />
        <StatTile
          label="Venues"
          value={new Set(Object.values(run.venues)).size}
          sub={[...new Set(Object.values(run.venues))].join(', ')}
        />
      </div>

      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-micro">
        <dt className="text-chrome-500">config digest</dt>
        <dd className="font-mono break-all text-chrome-300">{run.config_digest}</dd>
        {run.config_path && (
          <>
            <dt className="text-chrome-500">config</dt>
            <dd className="font-mono text-chrome-300">{run.config_path}</dd>
          </>
        )}
        {run.mode && (
          <>
            <dt className="text-chrome-500">mode</dt>
            <dd className="text-chrome-300">
              {run.mode}
              {run.merge_method ? ` · merge ${run.merge_method}` : ''}
            </dd>
          </>
        )}
      </dl>

      <div className="overflow-x-auto">
        <table className="w-full text-micro">
          <caption className="sr-only">the version and venue of every lane in this run</caption>
          <thead>
            <tr className="border-b border-line text-chrome-500">
              <th scope="col" className="p-1 text-left font-normal">
                lane
              </th>
              <th scope="col" className="p-1 text-left font-normal">
                version that ran
              </th>
              <th scope="col" className="p-1 text-left font-normal">
                venue
              </th>
            </tr>
          </thead>
          <tbody>
            {lanes.map((key) => (
              <tr key={key} className="border-b border-line-soft">
                <td className="p-1 text-chrome-300">{key}</td>
                <td className="p-1 text-chrome-400">{run.models[key]}</td>
                <td className="p-1 text-chrome-400">{run.venues[key] ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {run.stages && run.stages.length > 0 && (
        <details className="text-micro">
          <summary className="cursor-pointer text-chrome-300">
            {run.stages.length} stages, in order
          </summary>
          <div className="mt-2">
            <DataTable rows={run.stages} columns={stageColumns} rowKey={(s) => s.stage} />
          </div>
        </details>
      )}

      {run.outputs && run.outputs.length > 0 && (
        <p className="text-micro text-chrome-500">
          wrote:{' '}
          {run.outputs.map((o) => (
            <code key={o} className="mr-2">
              {o}
            </code>
          ))}
        </p>
      )}
    </article>
  );
}

export function RunManifest() {
  const q = useZooRuns();

  return (
    <Exhibit
      title="What the run cost, and what exactly ran"
      legend={
        <>
          One card per recorded run. <Chip color={C.machinery}>blue</Chip> = machinery: elapsed
          time, stages, versions and venues · <Chip color={C.good}>green</Chip> = no money was spent
          on inference · <Chip color={C.decision}>yellow</Chip> = a metered run. The{' '}
          <strong>config digest</strong> is the run id: re-running the same configuration is the
          same run, which is what makes every stage safe to repeat.
        </>
      }
      reading={
        <>
          Four models over tens of thousands of alleles, on a laptop, for seconds of wall clock and
          no dollars — because every lane in this run is a lookup against a precomputed table rather
          than an inference pass.
        </>
      }
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
      data={q.data?.data}
    >
      <Loaded query={q} height={380}>
        {(runs) =>
          runs.length === 0 ? (
            <p className="text-xs text-chrome-400">No run manifest has been recorded yet.</p>
          ) : (
            <div className="space-y-3">
              {runs.map((run) => (
                <RunCard key={run.run_id} run={run} />
              ))}
            </div>
          )
        }
      </Loaded>
    </Exhibit>
  );
}
