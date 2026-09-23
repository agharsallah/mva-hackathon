import { useState } from 'react';

import type { ZooAllele, ZooGeneScores } from '../../api/types/zoo';
import { Badge } from '../../components/Badge';
import { TextFilter } from '../../components/Controls';
import { type Column, DataTable } from '../../components/DataTable';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Loaded } from '../../components/QueryState';
import { dec } from '../../lib/format';
import { C } from '../../lib/palette';
import { useZooGene } from './hooks';

/**
 * One gene, every allele of it, every lane's opinion — the case-agnostic way into the zoo.
 *
 * Every other exhibit here is about *this* case. This one takes a gene symbol and answers the
 * same question for any of them, which is what makes the zoo reusable: the next N-of-1 case
 * changes the symbol in this box and nothing else. The symbol is a URL parameter, so one
 * address is one citation.
 *
 * A blank cell is a lane with no opinion on that allele, never a zero — the same rule the rank
 * bars follow, for the same reason.
 */

function scoreOf(record: ZooAllele, model: string): number | null {
  return record.rows.find((r) => r.model === model)?.score ?? null;
}

function GeneTable({ data }: { data: ZooGeneScores }) {
  if (data.records.length === 0) {
    return (
      <p className="text-xs text-chrome-400">
        <strong>{data.gene}</strong> carries no allele record in this callset — so no lane was asked
        about it. That is an answer about the delivery, not a failure of the zoo.
      </p>
    );
  }

  const columns: Column<ZooAllele>[] = [
    {
      key: 'allele_id',
      header: 'allele',
      render: (r) => <code className="text-chrome-400">{r.allele_id}</code>,
    },
    {
      key: 'consequence',
      header: 'consequence',
      sortValue: (r) => r.consequence,
      render: (r) => (
        <span className="flex flex-wrap items-center gap-1">
          <code className="text-chrome-300">{r.consequence}</code>
          {r.is_read_only && <Badge tone="decision">read-only</Badge>}
          {r.clin_sig && <Badge tone="neutral">{r.clin_sig}</Badge>}
        </span>
      ),
    },
    ...data.models.map((model): Column<ZooAllele> => ({
      key: model,
      header: model,
      align: 'right',
      sortValue: (r) => scoreOf(r, model),
      render: (r) => {
        const score = scoreOf(r, model);
        return score === null ? (
          <span className="text-chrome-600" title={`${model} has no opinion on this allele`}>
            no opinion
          </span>
        ) : (
          <span className="tabular-nums text-chrome-200">{dec(score, 4)}</span>
        );
      },
    })),
  ];

  return (
    <div className="space-y-2">
      <DataTable
        rows={data.records}
        columns={columns}
        rowKey={(r) => r.allele_id}
        filterable
        filterLabel="allele or class"
        maxHeight={420}
      />
      <p className="text-micro text-chrome-500">
        {data.records.length} allele record{data.records.length === 1 ? '' : 's'}
        {data.scored_records !== undefined && (
          <>, {data.scored_records} with at least one score</>
        )}{' '}
        · {data.models.length} lane{data.models.length === 1 ? '' : 's'} answered. Scores are on
        each lane&rsquo;s own scale — higher is more damaging within a column, and columns are not
        comparable to each other, which is exactly why the merge ranks rather than averages.
      </p>
    </div>
  );
}

export function GeneScores({ gene, onGene }: { gene: string; onGene: (symbol: string) => void }) {
  const [typed, setTyped] = useState(gene);
  const q = useZooGene(gene || null);

  return (
    <Exhibit
      title={`Every allele of ${gene || 'a gene'}, scored by every lane`}
      id="zoo-gene-view"
      controls={
        <form
          className="flex items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            onGene(typed.trim().toUpperCase());
          }}
        >
          <TextFilter
            label="gene"
            value={typed}
            onChange={setTyped}
            placeholder="gene symbol"
            width={140}
          />
          <button
            type="submit"
            className="rounded-control border border-line-strong bg-chrome-900 px-2 py-1 text-micro text-chrome-300 hover:border-machinery-700"
          >
            show
          </button>
        </form>
      }
      legend={
        <>
          One row per allele record of the gene, one column per lane.{' '}
          <Chip color={C.unmeasured}>&ldquo;no opinion&rdquo;</Chip> = that lane never scored this
          allele — the change is outside its domain, and it is not a score of zero ·{' '}
          <Chip color={C.decision}>read-only</Chip> = an allele the record builder marked as not
          scorable in this pass, and its curated verdict where the record carries one. Scores are
          per-lane scales and are not comparable across columns. The HGVS spellings the live route
          carries are not shown here: they are the patient&rsquo;s own allele spellings.
        </>
      }
      reading={
        <>
          The gene box is the reusable door into this page: type any symbol and the same lanes
          answer for it, which is what makes the zoo a tool rather than a one-case script.
        </>
      }
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
      data={q.data?.data}
    >
      <Loaded query={q} height={360} variant="table">
        {(data) => <GeneTable data={data} />}
      </Loaded>
    </Exhibit>
  );
}
