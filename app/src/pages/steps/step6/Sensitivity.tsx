import type { Step6Evidence, Step6Reach, Step6Stability } from '../../../api/types';
import { Badge } from '../../../components/Badge';
import { DataTable } from '../../../components/DataTable';
import { Exhibit } from '../../../components/Exhibit';
import { Plot } from '../../../components/Plot';
import { C } from '../../../lib/palette';
import { count, INPUTS, missingInputs, rowLabel } from './metrics';

/**
 * The three exhibits that argue against the ranking above them.
 *
 * Leave-one-route-out is the one that decides whether "the routes agree" is a sentence this
 * step is allowed to write. If silencing a single instrument moves the leader, the fusion is
 * that instrument wearing three coats, and the page has to say so on the same screen as the
 * leaderboard rather than in a caveat further down.
 */
export function Sensitivity({
  stability,
  reach,
  evidence,
  source,
  cachedAt,
  origin,
}: {
  stability: Step6Stability[];
  reach: Step6Reach[];
  evidence: Step6Evidence[];
  source?: string;
  cachedAt?: string | null;
  origin?: 'api' | 'fixture';
}) {
  const carried = stability.filter((row) => !row.leader_kept_rank_one);
  const leaders = evidence.slice(0, 12);

  return (
    <div className="space-y-4">
      <Exhibit
        title="Leave one route out — does any single instrument carry the result?"
        reading={
          carried.length === 0
            ? 'No single removal moves the leader: every instrument is dispensable.'
            : `Silencing ${carried.map((row) => row.removed).join(' or ')} moves the leader off rank 1. The fusion is carried by that route, not confirmed by all of them.`
        }
        legend={
          <>
            One row per admitted route, re-fusing with that route silenced.{' '}
            <span className="text-good-400">Green</span> — the all-routes leader is still rank 1.{' '}
            <span className="text-broken-400">Red</span> — it is not, and{' '}
            <strong>where it lands</strong> is the size of the loss. &ldquo;—&rdquo; means it fell
            outside the exported rows entirely. <strong>Also at rank 1</strong> counts the pairs
            tied there: a gene-level route ties every pair of a gene, so a large number is fan-out
            rather than agreement.
          </>
        }
        source={source}
        cachedAt={cachedAt}
        origin={origin}
        data={stability}
      >
        <DataTable
          rows={stability}
          rowKey={(row) => row.removed}
          columns={[
            { key: 'removed', header: 'Silenced', render: (row) => row.removed },
            { key: 'unit', header: 'Ordered', render: (row) => row.unit ?? '—' },
            {
              key: 'leader_kept_rank_one',
              header: 'Leader',
              render: (row) => (
                <Badge tone={row.leader_kept_rank_one ? 'good' : 'broken'}>
                  {row.leader_kept_rank_one ? 'still rank 1' : `falls to ${row.leader_rank ?? '—'}`}
                </Badge>
              ),
              sortValue: (row) => (row.leader_kept_rank_one ? 1 : 0),
            },
            {
              key: 'a_new_leader_gene',
              header: 'Rank 1 becomes',
              render: (row) => row.a_new_leader_gene ?? '—',
            },
            {
              key: 'pairs_at_rank_one',
              header: 'Also at rank 1',
              align: 'right',
              render: (row) => `${row.pairs_at_rank_one} pairs · ${row.genes_at_rank_one} genes`,
              sortValue: (row) => row.pairs_at_rank_one,
            },
            {
              key: 'statistic',
              header: 'That route measured',
              render: (row) => row.statistic ?? '—',
            },
          ]}
        />
      </Exhibit>

      <Exhibit
        title="How far down the matched decoys sit"
        reading="The fusion's own decoy null: a ranking that cannot be told apart from one built on size-matched controls has resolved nothing."
        legend={
          <>
            <span className="text-good-400">target</span> — a symptom-nominated gene;{' '}
            <span className="text-broken-400">decoy</span> — a size-matched control run through the
            identical fusion; <span className="text-chrome-400">neither</span> — everything else the
            genome-wide ranking nominated. <strong>Best</strong> and <strong>median</strong> are
            fused ranks, so lower is better. <strong>In top 20</strong> counts pairs at a fused rank
            of 20 or better, ties included.
          </>
        }
        source={source}
        cachedAt={cachedAt}
        origin={origin}
        data={reach}
      >
        <DataTable
          rows={reach}
          rowKey={(row) => row.class}
          columns={[
            {
              key: 'class',
              header: 'Class',
              render: (row) => (
                <Badge
                  tone={
                    row.class === 'target' ? 'good' : row.class === 'decoy' ? 'broken' : 'neutral'
                  }
                >
                  {row.class}
                </Badge>
              ),
            },
            { key: 'genes', header: 'Genes', align: 'right', render: (row) => count(row.genes) },
            { key: 'pairs', header: 'Pairs', align: 'right', render: (row) => count(row.pairs) },
            { key: 'best_rank', header: 'Best', align: 'right', render: (row) => row.best_rank },
            {
              key: 'median_rank',
              header: 'Median',
              align: 'right',
              render: (row) => row.median_rank.toFixed(0),
            },
            {
              key: 'pairs_in_top',
              header: 'In top 20',
              align: 'right',
              render: (row) => `${row.pairs_in_top} pairs · ${row.genes_in_top} genes`,
              sortValue: (row) => row.pairs_in_top,
            },
            {
              key: 'pairs_in_top_sensitivity',
              header: 'In top 20 (w)',
              align: 'right',
              render: (row) => row.pairs_in_top_sensitivity,
            },
          ]}
        />
      </Exhibit>

      <Exhibit
        title="Which witnesses speak for each leading pair"
        reading="Four bars of one colour would be four routes and one source. What is missing matters more than what is present."
        legend={
          <>
            One stack per leading pair, one segment per raw source that speaks for it:{' '}
            <span style={{ color: C.raw }}>■</span> HPO terms ·{' '}
            <span style={{ color: C.machinery }}>■</span> the VCF ·{' '}
            <span style={{ color: C.good }}>■</span> the raw reads ·{' '}
            <span style={{ color: C.decision }}>■</span> the literature. A short stack is a pair
            nominated by routes that all read the same thing.
          </>
        }
        source={source}
        cachedAt={cachedAt}
        origin={origin}
        data={evidence}
      >
        <Plot
          height={Math.max(280, leaders.length * 26 + 110)}
          data={INPUTS.map((input, index) => ({
            type: 'bar',
            orientation: 'h',
            name: input,
            y: leaders.map(rowLabel),
            x: leaders.map((row) => (row.inputs.split(',').includes(input) ? 1 : 0)),
            marker: { color: [C.raw, C.machinery, C.good, C.decision][index] },
            hovertemplate: `%{y} — ${input}<extra></extra>`,
          }))}
          layout={{
            barmode: 'stack',
            margin: { l: 330, r: 16, t: 10, b: 40 },
            xaxis: { title: { text: 'disjoint sources' }, dtick: 1, range: [0, 4] },
            yaxis: { automargin: true, autorange: 'reversed', tickfont: { size: 10 } },
            legend: { orientation: 'h', y: -0.25 },
          }}
        />
        <ul className="mt-3 space-y-1 text-xs text-chrome-400">
          {leaders.slice(0, 4).map((row) => {
            const absent = missingInputs(row);
            return (
              <li key={row.pair_id}>
                <span className="text-chrome-200">
                  #{row.fused_rank} {row.gene}
                </span>{' '}
                — {row.independent_evidence} of 4
                {absent.length > 0 && <> · missing: {absent.join(', ')}</>}
              </li>
            );
          })}
        </ul>
      </Exhibit>
    </div>
  );
}
