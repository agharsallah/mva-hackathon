import { useStep8 } from '../../api/hooksSteps';
import { Callout } from '../../components/Explainer';
import { Loaded } from '../../components/QueryState';
import { Deviation } from '../steps/step8/Deviation';
import { Limits } from '../steps/step8/Limits';
import { fraction } from '../steps/step8/metrics';

/**
 * Step 8's re-test, rendered beside the karyogram it corrects.
 *
 * The map above this panel is entry 037's: the mean B-allele fraction per megabase, flat on
 * every autosome. That flatness is what a mosaic gain of *any* size would have produced —
 * the two bands are symmetric about the centre, so their mean does not move — which makes it
 * an untested claim rather than a negative result. Putting the re-test on a different page
 * would leave the original where a reader meets it first and the correction where they might
 * not go.
 *
 * The exhibits are the step-8 page's own components, not copies: one payload, one set of
 * captions, two places they are read.
 */
export function MosaicRetest() {
  const q = useStep8();

  return (
    <Loaded query={q} height={460}>
      {(data, meta) => {
        const chrome = { source: meta.source, cachedAt: meta.cachedAt, origin: meta.origin };
        const folded = data.limits.filter((row) => row.statistic === 'bdev');
        const reached = folded.filter((row) => row.f80 !== null);
        const meanReached = data.limits.filter(
          (row) => row.statistic === 'mean_baf' && row.f80 !== null,
        );
        const worst = reached.length ? Math.max(...reached.map((row) => row.f80 as number)) : null;

        return (
          <div className="space-y-4">
            <Callout tone="decision" title="What the map above is worth">
              The karyogram uses the <strong>mean</strong> B-allele fraction. A mosaic gain splits
              heterozygous sites into two bands symmetric about the centre, so the mean does not
              move — flat is what a gain of any size would have produced. Scored through the
              identical harness, that statistic reaches 80% power on{' '}
              <strong>{meanReached.length}</strong> of {folded.length} contigs; taking the distance
              from the centre <em>before</em> averaging reaches it on{' '}
              <strong>{reached.length}</strong>
              {worst !== null && (
                <>
                  , and puts a number on the flatness: an event present in{' '}
                  <strong>{fraction(worst)}</strong> of the sequenced cells would have been found on
                  every autosome
                </>
              )}
              .
            </Callout>
            <Limits limits={data.limits} {...chrome} />
            <Deviation
              bdev={data.bdev}
              fractions={data.fractions}
              models={data.models}
              constants={data.constants}
              {...chrome}
            />
          </div>
        );
      }}
    </Loaded>
  );
}
