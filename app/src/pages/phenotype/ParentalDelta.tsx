import { usePhenotypeDelta } from '../../api/hooks';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Loaded } from '../../components/QueryState';
import { int } from '../../lib/format';
import { C } from '../../lib/palette';
import { BOX, cx } from '../../lib/ui';

/**
 * What it costs to treat a parental feature as the child's.
 *
 * The roadmap carried this as an open question for weeks — should `HP:0200067`, the
 * parents' recurrent miscarriage, be in the proband's term set? It is a real signal about
 * the family's chromosome instability, and it is also not a feature of this patient.
 *
 * Running it both ways turns the argument into a measurement, and the measurement is
 * one-directional: every curated panel gene rises when the term is removed.
 */
export function ParentalDelta() {
  const q = usePhenotypeDelta();

  return (
    <Exhibit
      title="What the parents' term costs every candidate gene"
      legend={
        <>
          One row per candidate-panel gene, showing its rank with all eight delivered terms against
          its rank on the child&rsquo;s own seven. The bar spans between the two.{' '}
          <Chip color={C.good}>green</Chip> = the gene <strong>rose</strong> when the parental term
          was dropped · <Chip color={C.broken}>red</Chip> = it fell ·{' '}
          <Chip color={C.absent}>grey</Chip> = the gene has no curated features in this HPO release,
          so it has no rank in either — an absence of knowledge, not a low score.
        </>
      }
      reading={
        <>
          Every curated candidate gene rises without the parental term. It is a rare term, so it
          pulls hard — and what it pulls up are recurrent-miscarriage genes, which compete with the
          features that actually describe the child.
        </>
      }
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
      data={q.data?.data}
    >
      <Loaded query={q} height={340}>
        {(data) => {
          const ranked = data.rows.filter((r) => r.proband_only !== null);
          const worst = Math.max(...ranked.map((r) => r.with_parental ?? 0), 1);
          const scale = (rank: number) => `${(rank / worst) * 100}%`;

          return (
            <div className="space-y-4">
              <div className="space-y-1">
                {data.rows.map((row) => {
                  if (row.proband_only === null || row.with_parental === null) {
                    return (
                      <div key={row.gene} className="flex items-center gap-3 text-xs">
                        <span className="w-20 shrink-0">{row.gene}</span>
                        <span className="text-chrome-500">not curated in this HPO release</span>
                      </div>
                    );
                  }
                  const rose = row.moved !== null && row.moved > 0;
                  return (
                    <div key={row.gene} className="flex items-center gap-3 text-xs">
                      <span className="w-20 shrink-0">{row.gene}</span>
                      <div className="relative h-4 flex-1 bg-chrome-900">
                        <div
                          className="absolute top-0 h-full opacity-70"
                          style={{
                            left: scale(row.proband_only),
                            width: `calc(${scale(row.with_parental)} - ${scale(row.proband_only)})`,
                            background: rose ? C.good : C.broken,
                          }}
                        />
                        <div
                          className="absolute top-0 h-full w-0.5"
                          style={{ left: scale(row.proband_only), background: C.ink }}
                        />
                      </div>
                      <span className="w-32 shrink-0 text-right tabular-nums text-chrome-400">
                        {int(row.with_parental)} → {int(row.proband_only)}
                        {row.moved !== null && (
                          <span className={rose ? 'text-good-400' : 'text-broken-400'}>
                            {' '}
                            ({row.moved > 0 ? '+' : ''}
                            {row.moved})
                          </span>
                        )}
                      </span>
                    </div>
                  );
                })}
              </div>

              <div className={cx(BOX.decision, 'text-xs')}>
                <strong>The decision this supports.</strong> {data.parental_label} (
                <code>{data.parental_term}</code>) describes the parents. Dropping it from the
                proband&rsquo;s term set improves every gene the panel cares about, out of{' '}
                {int(data.considered)} considered. The term is still evidence — repeated miscarriage
                is a read-out of the same chromosome instability — but it is evidence about the{' '}
                <em>family</em>, and feeding it to a ranker that assumes every term is the
                patient&rsquo;s costs accuracy on the patient.
              </div>
            </div>
          );
        }}
      </Loaded>
    </Exhibit>
  );
}
