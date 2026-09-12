import type { Step1Payload } from '../../../api/types';
import { StatTile } from '../../../components/StatTile';
import { int } from '../../../lib/format';

/**
 * The decoy set: the null every later step measures itself against.
 *
 * Without it "we found a biallelic candidate in a target gene" has no denominator, because
 * everybody carries two differences in most genes. The decoys are matched to the targets on
 * coding length and exon count, carry no annotation for any of the case's features, and were
 * drawn once from a recorded seed — so the same draw comes back on every re-run and nobody
 * can quietly redraw a null that came out inconvenient.
 */
export function DecoyCard({ payload }: { payload: Step1Payload }) {
  const d = payload.decoys;
  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile
          label="decoy genes"
          value={int(d.genes)}
          tone="broken"
          sub={`against ${int(payload.set_sizes.targets)} targets`}
          hint="a gene set that should find nothing, run through every rule the targets are"
        />
        <StatTile
          label="matched on"
          value={d.matched_on.join(' + ')}
          sub="so a hit rate cannot be a size artefact"
        />
        <StatTile
          label="excluded before the draw"
          value={int(d.excluded_by_annotation)}
          tone="decision"
          sub="genes annotated with any of the child’s features — ineligible as a null"
        />
        <StatTile
          label="draw seed"
          value={d.seed === null ? '—' : String(d.seed)}
          sub="recorded once; the draw is not repeatable-until-convenient"
        />
      </div>
    </div>
  );
}
