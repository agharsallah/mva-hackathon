import { useState } from 'react';

import { usePhenotypeGenes } from '../../api/hooks';
import type { PhenotypeGene } from '../../api/types';
import { Select } from '../../components/Controls';
import { type Column, DataTable } from '../../components/DataTable';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Loaded } from '../../components/QueryState';
import { dec, int } from '../../lib/format';
import { C } from '../../lib/palette';
import { BADGE, cx } from '../../lib/ui';

const TERM_SETS = [
  { value: 'proband-only', label: "The child's 7 features" },
  { value: 'with-parental', label: 'All 8 delivered terms' },
];

/**
 * The ranking, and the only exhibit in this app whose rows never touched the callset.
 *
 * Everything else here starts from what the sequencer produced and narrows it. This starts
 * from what the doctor wrote down, and it has no access to the variants, the panel, or the
 * candidate list at all. So the panel marks in this table are a *result*: nobody told the
 * scorer those eight genes mattered, and it put five of them near the top of five thousand
 * anyway.
 */
export function GeneRanking() {
  const [termSet, setTermSet] = useState('proband-only');
  const q = usePhenotypeGenes(termSet, 40);

  const columns: Column<PhenotypeGene>[] = [
    { key: 'rank', header: '#', align: 'right', render: (r) => int(r.rank) },
    {
      key: 'gene',
      header: 'gene',
      render: (r) => (
        <span className="flex items-center gap-2">
          <span className={r.in_panel ? 'text-good-400' : undefined}>{r.gene}</span>
          {r.in_panel && <span className={cx(BADGE.good, 'text-micro')}>panel</span>}
        </span>
      ),
    },
    {
      key: 'score',
      header: 'score',
      align: 'right',
      render: (r) => dec(r.score, 3),
    },
    {
      key: 'best_term',
      header: 'strongest feature match',
      render: (r) =>
        r.best_term ? (
          <span className="text-chrome-400">
            <code>{r.best_term}</code>
            {r.best_common_ancestor && r.best_common_ancestor !== r.best_term ? (
              <> via {r.best_common_ancestor}</>
            ) : (
              <> (exact)</>
            )}
          </span>
        ) : (
          <span className="text-chrome-500">no informative match</span>
        ),
    },
    {
      key: 'curated_terms',
      header: 'curated features',
      align: 'right',
      render: (r) => int(r.curated_terms),
    },
  ];

  return (
    <Exhibit
      title="Every curated gene, ranked by the child's symptoms alone"
      controls={
        <Select label="term set" value={termSet} onChange={setTermSet} options={TERM_SETS} />
      }
      legend={
        <>
          One row per gene, best match first, out of every gene the Human Phenotype Ontology
          curates. <Chip color={C.good}>green</Chip> = a gene that also happens to be on the
          candidate panel — a label added <em>after</em> the ranking, never an input to it.{' '}
          <strong>score</strong> is the symmetric similarity divided by the best score these terms
          could achieve, so 1.0 would mean a gene curated to exactly this child.{' '}
          <strong>exact</strong> means the gene is curated to the feature itself; otherwise the
          match happened at the named shared ancestor. <strong>curated features</strong> is how many
          phenotypes HPO records for the gene — context for why a well-studied gene scores below a
          narrowly described one.
        </>
      }
      reading={
        <>
          The scorer was never shown the candidate panel, and it still put the leading candidate
          gene in the top ten of more than five thousand.
        </>
      }
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
      data={q.data?.data}
    >
      <Loaded query={q} height={520}>
        {(data) => (
          <div className="space-y-3">
            <p className="text-xs text-chrome-400">
              {int(data.considered)} genes considered · {int(data.scored)} scored above zero ·
              showing {data.rows.length}. A gene with no curated features is absent rather than
              last: that is missing knowledge, not evidence against it.
            </p>
            <DataTable rows={data.rows} columns={columns} rowKey={(r) => r.gene} />
          </div>
        )}
      </Loaded>
    </Exhibit>
  );
}
