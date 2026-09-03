import { useState } from 'react';

import { usePhenotypeGene, usePhenotypeTerms } from '../../api/hooks';
import { Select } from '../../components/Controls';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Loaded } from '../../components/QueryState';
import { dec, int } from '../../lib/format';
import { C } from '../../lib/palette';
import { BOX, cx } from '../../lib/ui';

const GENES = ['BUB1B', 'CEP57', 'TRIP13', 'DICER1', 'TP53', 'CENPE', 'SMC5'].map((g) => ({
  value: g,
  label: g,
}));

/**
 * Why one gene ranked where it did — the arithmetic, not the answer.
 *
 * A rank on its own is unarguable, and an unarguable number has no business in an evidence
 * register. This exhibit opens the score up: which of the child's features matched, how
 * strongly, and whether the gene is curated to that exact feature or merely to something
 * it shares an ancestor with.
 *
 * The two direction numbers are the honest part. Forward asks whether the child is
 * explained by the gene; reverse asks whether the gene is present in the child. They
 * disagree for any well-studied gene, and hiding that behind a single figure would make a
 * heavily curated gene look worse than it is without saying why.
 */
export function MatchBreakdown() {
  const [gene, setGene] = useState('BUB1B');
  const [termSet, setTermSet] = useState('proband-only');
  const q = usePhenotypeGene(gene, termSet);
  const termsQuery = usePhenotypeTerms();
  const labels = new Map(
    (termsQuery.data?.data.terms ?? []).map((t) => [t.hpo_id, t.label] as const),
  );

  return (
    <Exhibit
      title="Why a gene scored what it scored"
      controls={
        <div className="flex gap-2">
          <Select label="gene" value={gene} onChange={setGene} options={GENES} />
          <Select
            label="term set"
            value={termSet}
            onChange={setTermSet}
            options={[
              { value: 'proband-only', label: "child's 7" },
              { value: 'with-parental', label: 'all 8' },
            ]}
          />
        </div>
      }
      legend={
        <>
          The gene&rsquo;s standing in both readings of the term set, and the two directions the
          score is built from. <strong>forward</strong> asks &ldquo;is each of the child&rsquo;s
          features explained by this gene?&rdquo; and ignores everything else the gene does;{' '}
          <strong>reverse</strong> asks &ldquo;is each of the gene&rsquo;s features present in the
          child?&rdquo; and charges a well-studied gene for every feature the child lacks.{' '}
          <Chip color={C.good}>green</Chip> = the better of the two ranks ·{' '}
          <Chip color={C.machinery}>blue</Chip> = the other one.
        </>
      }
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
      data={q.data?.data}
    >
      <Loaded query={q} height={300}>
        {(data) => {
          const rows = Object.entries(data.by_term_set);
          const best = data.delta.proband_only;
          return (
            <div className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2">
                {rows.map(([name, row]) => {
                  const isBest = row.rank === best;
                  return (
                    <div
                      key={name}
                      className={cx(isBest ? BOX.good : BOX.machinery, 'space-y-1 text-xs')}
                    >
                      <div className="flex items-baseline justify-between">
                        <span className="font-medium">{name}</span>
                        <span className="tabular-nums">rank {int(row.rank)}</span>
                      </div>
                      <div className="text-chrome-400">
                        score {dec(row.score, 3)} · forward {dec(row.forward, 2)} · reverse{' '}
                        {dec(row.reverse, 2)}
                      </div>
                      <div className="text-chrome-400">
                        {int(row.curated_terms)} curated features
                        {row.best_term && (
                          <>
                            {' '}
                            · strongest: {labels.get(row.best_term) ?? row.best_term}
                            {row.best_ic !== null && <> (IC {dec(row.best_ic, 2)})</>}
                          </>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>

              {data.delta.moved !== null && (
                <p className="text-xs text-chrome-400">
                  {data.gene} moves{' '}
                  <strong className={data.delta.moved > 0 ? 'text-good-400' : 'text-broken-400'}>
                    {data.delta.moved > 0 ? '+' : ''}
                    {data.delta.moved} places
                  </strong>{' '}
                  when the parental term is dropped.
                  {data.in_panel &&
                    ' This gene is on the candidate panel — which the ranker never saw.'}
                </p>
              )}
            </div>
          );
        }}
      </Loaded>
    </Exhibit>
  );
}
