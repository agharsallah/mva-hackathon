import { Chip, Exhibit } from '../../components/Exhibit';
import { Loaded } from '../../components/QueryState';
import { dec, int } from '../../lib/format';
import { C } from '../../lib/palette';
import { cx } from '../../lib/ui';
import { useZooMerge } from './hooks';

/**
 * Do the lanes agree? — Spearman ρ between every pair of lanes, on the alleles both scored.
 *
 * Two things are on every cell and both matter. **ρ** is how alike the two orderings are
 * (1 = identical order, 0 = unrelated, negative = opposed). **n** is how many alleles the
 * two lanes both scored, which is the only ground the ρ stands on: a ρ of 0.58 over 3,943
 * shared alleles and a ρ of 0.58 over 40 are not the same claim, so n is printed under the
 * number and repeated in the cell's tooltip rather than hidden.
 *
 * Colour encodes |ρ| as opacity over one hue rather than a rainbow: the eye should read
 * "strong / weak", and the sign is carried by the hue (blue agreement, red opposition).
 */

/** The cell's fill: hue says the sign, opacity says the strength. */
function fillFor(rho: number | null): { background: string; opacity: number } {
  if (rho === null) return { background: C.unmeasured, opacity: 0.25 };
  return {
    background: rho < 0 ? C.broken : C.machinery,
    opacity: 0.12 + 0.78 * Math.min(Math.abs(rho), 1),
  };
}

export function AgreementMatrix() {
  const q = useZooMerge();

  return (
    <Exhibit
      title="Agreement between lanes"
      legend={
        <>
          One cell per ordered pair of lanes: <strong>ρ</strong> is the Spearman rank correlation of
          their scores over the alleles <em>both</em> scored, and <strong>n</strong> is how many
          that was. <Chip color={C.machinery}>blue</Chip> = positive agreement, stronger colour is a
          higher ρ · <Chip color={C.broken}>red</Chip> = the orderings run opposite ·{' '}
          <Chip color={C.unmeasured}>grey</Chip> = no overlap, so no ρ exists. The diagonal is a
          lane against itself and is 1.0 by construction — it is drawn only to show each
          lane&rsquo;s own scored count.
        </>
      }
      reading={
        <>
          Weak agreement is the finding, not a fault: lanes built on different evidence, over
          different classes of change, are not supposed to produce the same order, and a consensus
          drawn from four near-identical rankings would carry one opinion wearing four coats.
        </>
      }
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
      data={q.data?.data}
    >
      <Loaded query={q} height={340}>
        {(merge) => {
          const { models, rho, n } = merge.matrix;
          return (
            <div className="overflow-x-auto">
              <table className="text-micro">
                <caption className="sr-only">
                  Spearman rank correlation between every pair of model lanes, with the number of
                  alleles both lanes scored
                </caption>
                <thead>
                  <tr>
                    <th scope="col" className="p-1 text-left font-normal text-chrome-500">
                      lane ↓ / lane →
                    </th>
                    {models.map((m) => (
                      <th
                        key={m}
                        scope="col"
                        className="p-1 text-left font-normal whitespace-nowrap text-chrome-400"
                      >
                        {m}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {models.map((rowModel, i) => (
                    <tr key={rowModel}>
                      <th
                        scope="row"
                        className="p-1 text-left font-normal whitespace-nowrap text-chrome-400"
                      >
                        {rowModel}
                      </th>
                      {models.map((colModel, j) => {
                        const value = rho[i]?.[j] ?? null;
                        const overlap = n[i]?.[j] ?? 0;
                        const self = i === j;
                        const fill = fillFor(value);
                        return (
                          <td key={colModel} className="p-0.5">
                            <div
                              className={cx(
                                'relative flex h-14 w-24 flex-col items-center justify-center rounded-control border',
                                self ? 'border-line-strong' : 'border-line',
                              )}
                              title={`${rowModel} vs ${colModel}: ρ ${dec(value, 4)} over n=${int(overlap)} shared alleles`}
                            >
                              <span
                                className="absolute inset-0 rounded-control"
                                style={fill}
                                aria-hidden="true"
                              />
                              <span className="tabular-nums relative text-xs font-semibold text-chrome-100">
                                {self ? '1.0' : dec(value, 3)}
                              </span>
                              <span className="tabular-nums relative text-micro text-chrome-300">
                                n {int(overlap)}
                              </span>
                            </div>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }}
      </Loaded>
    </Exhibit>
  );
}
