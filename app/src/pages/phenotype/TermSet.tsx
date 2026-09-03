import { usePhenotypeTerms } from '../../api/hooks';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Loaded } from '../../components/QueryState';
import { dec } from '../../lib/format';
import { C } from '../../lib/palette';
import { BOX, cx } from '../../lib/ui';

/**
 * The child's eight features, and the one modelling choice hidden inside them.
 *
 * The bar length is the term's information content — how rare it is across every gene HPO
 * curates. That single number decides how much a match on the feature is worth, and the
 * spread here is the reason the ranking looks the way it does: rhabdomyosarcoma carries
 * more than four times the information of short stature, so it dominates the top of the
 * list while the growth terms barely move it.
 */
export function TermSet() {
  const q = usePhenotypeTerms();

  return (
    <Exhibit
      title="The eight features the child was described by"
      legend={
        <>
          One row per delivered HPO term, the bar being its <strong>information content</strong> —
          how surprising the feature is across the curated genome, in nats. Longer means rarer means
          more diagnostic. <Chip color={C.raw}>purple</Chip> = a feature of the child ·{' '}
          <Chip color={C.decision}>yellow</Chip> = a feature of the <em>parents</em>, kept in one
          reading of the term set and dropped in the other. Greyed rows at the bottom are features a
          textbook would expect and the document does not list; they carry no bar because a plain
          HPO term list cannot say &ldquo;asked and not present&rdquo;.
        </>
      }
      reading={
        <>
          Rhabdomyosarcoma is by far the rarest thing about this child, and it is doing most of the
          work in every ranking on this page.
        </>
      }
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
      data={q.data?.data}
    >
      <Loaded query={q} height={320}>
        {(data) => {
          const widest = Math.max(...data.terms.map((t) => t.information_content ?? 0), 1);
          return (
            <div className="space-y-4">
              <div className="space-y-1">
                {data.terms.map((term) => {
                  const ic = term.information_content ?? 0;
                  return (
                    <div key={term.hpo_id} className="flex items-center gap-3 text-xs">
                      <code className="w-24 shrink-0 text-chrome-400">{term.hpo_id}</code>
                      <span className="w-52 shrink-0 truncate" title={term.note}>
                        {term.label}
                      </span>
                      <div className="h-3 flex-1 bg-chrome-900">
                        <div
                          className="h-full"
                          style={{
                            width: `${(ic / widest) * 100}%`,
                            background: term.proband ? C.raw : C.decision,
                          }}
                        />
                      </div>
                      <span className="w-12 shrink-0 text-right tabular-nums text-chrome-400">
                        {dec(ic, 2)}
                      </span>
                    </div>
                  );
                })}
              </div>

              <div className={cx(BOX.decision, 'text-xs')}>
                <strong>Why one term is yellow.</strong> {data.terms.find((t) => !t.proband)?.label}{' '}
                is the <em>parents&rsquo;</em> reproductive history, not a feature of the child.
                Every phenotype ranker assumes each term describes the patient, so including it is a
                modelling choice rather than a data entry — and it is a rare term, so it pulls hard.
                Both readings are computed and the cost is measured further down this page.
              </div>

              <div className="flex flex-wrap gap-4 text-xs text-chrome-400">
                {data.notably_absent.map((absent) => (
                  <span key={absent.hpo_id}>
                    <code>{absent.hpo_id}</code> {absent.label} — not listed
                  </span>
                ))}
              </div>
            </div>
          );
        }}
      </Loaded>
    </Exhibit>
  );
}
