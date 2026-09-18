import type { Step6Route } from '../../../api/types';
import { Badge } from '../../../components/Badge';
import { DataTable } from '../../../components/DataTable';
import { Exhibit } from '../../../components/Exhibit';
import { StatTile } from '../../../components/StatTile';
import { stat } from './metrics';

/**
 * The four instruments, and the measurement that admitted or disqualified each one.
 *
 * A route measured to order nothing is rendered **red and kept**, never hidden. That is the
 * exhibit's whole argument: the read route's discrimination of exactly zero is a result of
 * this iteration, and a fusion that quietly dropped it would be reporting three routes while
 * claiming four instruments looked at the case.
 */
export function Routes({
  rows,
  source,
  cachedAt,
  origin,
}: {
  rows: Step6Route[];
  source?: string;
  cachedAt?: string | null;
  origin?: 'api' | 'fixture';
}) {
  const voting = rows.filter((row) => row.admitted);

  return (
    <div className="space-y-4">
      <Exhibit
        title="Which instrument earned a vote"
        reading={
          voting.length === rows.length
            ? 'Every route was admitted.'
            : `${voting.length} of ${rows.length} routes rank. The rest confirm at weight 0 — kept in every table so the measurement that disqualified them stays visible.`
        }
        legend={
          <>
            <strong className="text-good-400">Green</strong> — admitted: the route separates its
            targets from matched decoys and reorders a trivial baseline.{' '}
            <strong className="text-broken-400">Red</strong> — measured to order nothing; carried at
            weight 0. <strong>w (equal)</strong> is the pre-registered primary weighting;{' '}
            <strong>w (measured)</strong> is the route&rsquo;s own measured error rate, used in the
            second sensitivity analysis only.
          </>
        }
        source={source}
        cachedAt={cachedAt}
        origin={origin}
        data={rows}
      >
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {rows.map((row) => (
            <StatTile
              key={row.route}
              label={`${row.route} · ${row.unit}`}
              tone={row.admitted ? 'good' : 'broken'}
              value={row.admitted ? 'ranks' : 'confirms only'}
              chip={
                <Badge tone={row.admitted ? 'good' : 'broken'}>w {stat(row.weight_primary)}</Badge>
              }
              sub={
                <>
                  {row.statistic}
                  <div className="mt-1 text-chrome-500">
                    {row.source_step} · {row.measured_by}
                  </div>
                </>
              }
              hint={row.reason}
            />
          ))}
        </div>
      </Exhibit>

      <Exhibit
        title="What each instrument measured, and on what"
        reading="One place to read every route's error rate side by side, with the entry that measured it."
        legend={
          <>
            <strong>Statistic</strong> is the number the admission rule was applied to, with its
            interval where it has one. <strong>Inputs</strong> are the raw sources the route read —
            two routes sharing one are not two witnesses. The badge in the first column says whether
            the route votes or is carried at weight 0.
          </>
        }
        source={source}
        cachedAt={cachedAt}
        origin={origin}
        data={rows}
      >
        <DataTable
          rows={rows}
          rowKey={(row) => row.route}
          columns={[
            {
              key: 'admitted',
              header: '',
              render: (row) => (
                <Badge tone={row.admitted ? 'good' : 'broken'}>
                  {row.admitted ? 'ranks' : 'weight 0'}
                </Badge>
              ),
              sortValue: (row) => row.admitted,
            },
            { key: 'route', header: 'Route', render: (row) => row.route },
            { key: 'unit', header: 'Orders', render: (row) => row.unit },
            { key: 'source_step', header: 'From', render: (row) => row.source_step },
            { key: 'statistic', header: 'Measured', render: (row) => row.statistic },
            {
              key: 'weight_primary',
              header: 'w (equal)',
              align: 'right',
              render: (row) => stat(row.weight_primary),
            },
            {
              key: 'weight_sensitivity',
              header: 'w (measured)',
              align: 'right',
              render: (row) => stat(row.weight_sensitivity),
            },
            { key: 'inputs', header: 'Inputs', render: (row) => row.inputs.split(',').join(' · ') },
            { key: 'measured_by', header: 'Entries', render: (row) => row.measured_by },
          ]}
        />
      </Exhibit>
    </div>
  );
}
