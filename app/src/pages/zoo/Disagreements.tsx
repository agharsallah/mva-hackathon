import type { ZooDisagreement } from '../../api/types/zoo';
import { type Column, DataTable } from '../../components/DataTable';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Loaded } from '../../components/QueryState';
import { dec, int, pct } from '../../lib/format';
import { C } from '../../lib/palette';
import { useZooMerge } from './hooks';

/**
 * The alleles the lanes argue about most — one row per allele where the highest-ranking lane
 * and the lowest-ranking lane are furthest apart.
 *
 * This table is the point of running a zoo at all. Where every lane agrees there is nothing
 * to learn from having four of them; where they split, the split *is* the information: one
 * instrument is looking at something the others cannot see (a splice effect on a change that
 * leaves the protein sequence almost intact, typically), and the pair behind it deserves a
 * human read rather than an average.
 *
 * `gene` is a link into the per-gene view, which is how a reader gets from "these two lanes
 * disagree" to "here is every allele of that gene and what every lane said about it".
 */

export function Disagreements({ onGene }: { onGene: (symbol: string) => void }) {
  const q = useZooMerge();

  const columns: Column<ZooDisagreement>[] = [
    {
      key: 'allele_id',
      header: 'allele',
      render: (r) => <code className="text-chrome-400">{r.allele_id}</code>,
    },
    {
      key: 'gene',
      header: 'gene',
      render: (r) =>
        r.gene ? (
          <button
            type="button"
            onClick={() => onGene(r.gene as string)}
            className="underline decoration-chrome-600 underline-offset-2 hover:text-chrome-50"
          >
            {r.gene}
          </button>
        ) : (
          <span className="text-chrome-600">—</span>
        ),
    },
    {
      key: 'top_model',
      header: 'ranks it high',
      render: (r) => (
        <span style={{ color: C.good }}>
          {r.top_model} · {pct(r.top_pct, 2)}
          {r.top_score !== undefined && (
            <span className="ml-1 text-chrome-500">(score {dec(r.top_score, 3)})</span>
          )}
        </span>
      ),
    },
    {
      key: 'bottom_model',
      header: 'ranks it low',
      render: (r) => (
        <span style={{ color: C.broken }}>
          {r.bottom_model} · {pct(r.bottom_pct, 2)}
          {r.bottom_score !== undefined && (
            <span className="ml-1 text-chrome-500">(score {dec(r.bottom_score, 3)})</span>
          )}
        </span>
      ),
    },
    {
      key: 'spread',
      header: 'percentile gap',
      align: 'right',
      sortValue: (r) => r.bottom_pct - r.top_pct,
      render: (r) => (
        <span className="tabular-nums text-chrome-300">{dec(r.bottom_pct - r.top_pct, 1)}</span>
      ),
    },
  ];

  return (
    <Exhibit
      title="Where the lanes disagree most"
      legend={
        <>
          One row per allele on which two lanes are furthest apart, ordered by the gap.{' '}
          <Chip color={C.good}>green</Chip> = the lane that ranks the allele near the top of its own
          ordering · <Chip color={C.broken}>red</Chip> = the lane that ranks it near the bottom.
          Percentiles are counted from the top, so a large gap means one instrument sees something
          the other cannot. The gene name opens the per-gene view below.
        </>
      }
      reading={
        <>
          A disagreement here is a question for a human, not an error to be averaged out: the two
          lanes are usually looking at different physics — one at the protein, the other at the
          splice site — on the same change.
        </>
      }
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
      data={q.data?.data}
    >
      <Loaded query={q} height={360} variant="table">
        {(merge) => (
          <div className="space-y-2">
            <DataTable
              rows={merge.disagreements}
              columns={columns}
              rowKey={(r, i) => `${r.allele_id}-${r.top_model}-${r.bottom_model}-${i}`}
              filterable
              filterLabel="gene or lane"
              maxHeight={420}
            />
            {merge.disagreements_total !== undefined && (
              <p className="text-micro text-chrome-500">
                Showing {int(merge.disagreements.length)} of {int(merge.disagreements_total)}{' '}
                disagreeing allele/lane rows the merge recorded.
              </p>
            )}
          </div>
        )}
      </Loaded>
    </Exhibit>
  );
}
