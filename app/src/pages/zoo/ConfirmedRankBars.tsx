import type { ZooConsensus, ZooLaneRank } from '../../api/types/zoo';
import { Badge } from '../../components/Badge';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Loaded } from '../../components/QueryState';
import { int, pct } from '../../lib/format';
import { C } from '../../lib/palette';
import { BOX, cx } from '../../lib/ui';
import { useZooMerge, useZooRanks } from './hooks';

/**
 * Where each lane put the case pair — and, drawn as its own thing, where a lane refused to
 * put it at all.
 *
 * The one rule this exhibit exists to enforce: **"no opinion" is never drawn as zero.** A
 * pair is scored by its weaker half, so a lane that scored one half and not the other has no
 * pair score; plotting that as a bar at the bottom of the axis would turn "outside my domain"
 * into "not damaging", which is the single most expensive mistake available on this page. A
 * silent lane gets a hatched strip and the percentile of the half it *did* see, labelled as
 * exactly that.
 */

const AXIS = [0, 25, 50, 75, 100];

/** A bar whose length is the percentile counted from the top: shorter is more damaging. */
function RankBar({ lane }: { lane: ZooLaneRank }) {
  const confirmed = lane.confirmed;
  const percentile = confirmed?.percentile ?? null;
  const half = confirmed?.right_percentile ?? confirmed?.left_percentile ?? null;

  return (
    <div className="grid grid-cols-[9rem_minmax(0,1fr)_11rem] items-center gap-3 text-micro">
      <div className="flex items-center gap-1.5">
        <span className="truncate text-chrome-300">{lane.model}</span>
        {lane.catalogue_adjacent && <Badge tone="decision">adjacent</Badge>}
      </div>

      <div className="relative h-5 rounded-control bg-chrome-900">
        {percentile === null ? (
          <div
            className="absolute inset-y-0 left-0 w-full rounded-control border border-dashed border-chrome-600"
            style={{
              backgroundImage: `repeating-linear-gradient(45deg, ${C.unmeasured} 0 4px, transparent 4px 10px)`,
            }}
            title="no opinion: one half of the pair is outside this lane's domain"
          />
        ) : (
          <div
            className="absolute inset-y-0 left-0 rounded-control"
            style={{
              width: `${Math.max(percentile, 0.6)}%`,
              background: percentile <= 1 ? C.good : C.machinery,
            }}
            title={`rank ${int(confirmed?.rank)} of ${int(lane.n_ranked)} pairs — top ${pct(percentile, 2)}`}
          />
        )}
        {half !== null && percentile === null && (
          <span
            className="absolute inset-y-0 w-0.5"
            style={{ left: `${Math.max(half, 0.4)}%`, background: C.raw }}
            title={`the half this lane did score sits at ${pct(half, 2)}`}
          />
        )}
      </div>

      <div className="tabular-nums text-right text-chrome-400">
        {percentile === null ? (
          <span className="text-chrome-500">
            no opinion · {int(lane.unscored_pairs)} pairs unscored
          </span>
        ) : (
          <span>
            rank {int(confirmed?.rank)} of {int(lane.n_ranked)} · {pct(percentile, 2)}
          </span>
        )}
      </div>
    </div>
  );
}

function ConsensusLine({ label, consensus }: { label: string; consensus: ZooConsensus }) {
  const percentile = consensus.percentile ?? null;
  return (
    <div className="grid grid-cols-[9rem_minmax(0,1fr)_11rem] items-center gap-3 text-micro">
      <span className="text-chrome-200">{label}</span>
      <div className="relative h-5 rounded-control border border-line bg-chrome-900">
        <div
          className="absolute inset-y-0 left-0 rounded-control"
          style={{
            width: `${Math.max(percentile ?? 0, 0.6)}%`,
            background: C.raw,
          }}
        />
      </div>
      <span className="tabular-nums text-right text-chrome-300">
        rank {int(consensus.rank)} of {int(consensus.n)} · {pct(percentile, 2)}
      </span>
    </div>
  );
}

export function ConfirmedRankBars() {
  const ranks = useZooRanks();
  const merge = useZooMerge();

  return (
    <Exhibit
      title="Where each lane put the case pair"
      legend={
        <>
          One bar per lane; the bar&rsquo;s length is the pair&rsquo;s{' '}
          <strong>percentile from the top</strong> of that lane&rsquo;s own ranking, so{' '}
          <em>shorter is more damaging</em>. <Chip color={C.good}>green</Chip> = inside the top 1 %
          · <Chip color={C.machinery}>blue</Chip> = ranked, below the top 1 % ·{' '}
          <Chip color={C.unmeasured}>hatched grey</Chip> = <strong>no opinion</strong>, one half of
          the pair was outside the lane&rsquo;s domain, never a score of zero ·{' '}
          <Chip color={C.raw}>purple</Chip> = the consensus rows, and the tick inside a hatched bar
          marking the one half that lane did score. <Badge tone="decision">adjacent</Badge> marks a
          catalogue-adjacent lane, which is why the consensus is drawn twice.
        </>
      }
      reading={
        <>
          The consensus row without the catalogue-adjacent lane is the honest one to quote: it is
          built only from lanes that never saw a curated verdict about any variant, so it cannot be
          repeating a catalogue back at us.
        </>
      }
      source={ranks.data?.source}
      cachedAt={ranks.data?.cachedAt}
      origin={ranks.data?.origin}
      data={ranks.data?.data}
    >
      <Loaded query={ranks} height={320}>
        {(data) => (
          <div className="space-y-3">
            <div className="space-y-1.5">
              {data.per_model.map((lane) => (
                <RankBar key={lane.model} lane={lane} />
              ))}
            </div>

            <div className="grid grid-cols-[9rem_minmax(0,1fr)_11rem] gap-3 text-micro text-chrome-600">
              <span />
              <div className="flex justify-between">
                {AXIS.map((tick) => (
                  <span key={tick}>{tick}%</span>
                ))}
              </div>
              <span />
            </div>

            {merge.data && (
              <div className="space-y-1.5 border-t border-line pt-3">
                <ConsensusLine
                  label="consensus — catalogue-free"
                  consensus={merge.data.data.consensus.catalogue_free}
                />
                <ConsensusLine
                  label="consensus — all lanes"
                  consensus={merge.data.data.consensus.all_lanes}
                />
                <p className={cx(BOX.decision, 'rounded-control border px-2 py-1 text-micro')}>
                  Both consensus rows are <strong>reciprocal rank fusion</strong> (k ={' '}
                  {merge.data.data.rrf_k ?? '—'}, method <code>{merge.data.data.method}</code>):
                  each lane contributes 1/(k + its rank), and a lane with no opinion on a pair
                  contributes nothing to it rather than a bottom rank. Excluding{' '}
                  {merge.data.data.consensus.catalogue_free.excluded_lanes?.join(', ') || 'no lane'}{' '}
                  moves the case pair from rank {int(merge.data.data.consensus.all_lanes.rank)} to{' '}
                  {int(merge.data.data.consensus.catalogue_free.rank)}.
                </p>
              </div>
            )}

            <p className="text-micro text-chrome-500">
              {int(data.pairs_total)} candidate pairs were considered in total · genes skipped:{' '}
              {data.skipped_genes_recorded === false ? (
                <span className="text-decision-300">
                  not recorded by this run — an empty list here would be a claim the run cannot
                  support
                </span>
              ) : data.skipped_genes.length > 0 ? (
                data.skipped_genes.join(', ')
              ) : (
                'none'
              )}
              .
            </p>
          </div>
        )}
      </Loaded>
    </Exhibit>
  );
}
