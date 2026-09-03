/**
 * The exhibit's own control row, below the generic `SceneControls` one.
 *
 * `viz3d`'s generic filter panel is deliberately not used here (`filters={false}`): it drops
 * datums, and a dropped residue makes the protein adapter repaint that stretch of tube in a
 * surviving neighbour's colour — a picture that says something false. These controls either
 * *trim* the chain (backbone included, so the camera refits) or *de-emphasise* residues, and
 * both keep the drawn chain honest.
 */

import { Toggle } from '../../../components/Controls';
import { cx } from '../../../lib/ui';
import { IMPACTS, type ProteinFilters as Filters } from './filters';

const NUMBER =
  'w-20 rounded-md border border-chrome-700 bg-chrome-900 px-2 py-1 text-[11px] text-chrome-200';
const BUTTON =
  'rounded-md border border-chrome-700 bg-chrome-900 px-2 py-1 text-[11px] text-chrome-400 transition enabled:hover:bg-chrome-800 enabled:hover:text-chrome-200 disabled:opacity-40';

export function ProteinFilters({
  filters,
  onFocus,
  focusable,
  comparePair,
  compareWhy,
  onUseCompare,
}: {
  filters: Filters;
  /** Trim the chain to the current selection, which is what refits the camera. */
  onFocus: () => void;
  focusable: boolean;
  comparePair: boolean;
  compareWhy: string;
  onUseCompare: () => void;
}) {
  const { length } = filters;
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
      <Toggle on={filters.dim} onChange={filters.setDim}>
        dim low-confidence (pLDDT &lt; 70)
      </Toggle>
      <Toggle on={filters.rareOnly} onChange={filters.setRareOnly}>
        rare alleles only
      </Toggle>
      <Toggle on={filters.onlyCandidates} onChange={filters.setOnlyCandidates}>
        hide non-candidates
      </Toggle>

      <span className="inline-flex items-center gap-1 text-[11px] text-chrome-500">
        impact
        {IMPACTS.map((impact) => {
          const on = !filters.hiddenImpacts.includes(impact);
          return (
            <button
              key={impact}
              type="button"
              aria-pressed={on}
              onClick={() => filters.toggleImpact(impact)}
              className={cx(
                'rounded border px-1.5 py-0.5 text-[11px] transition',
                on
                  ? 'border-chrome-600 bg-chrome-800 text-chrome-200'
                  : 'border-chrome-800 bg-chrome-950 text-chrome-600',
              )}
            >
              {impact}
            </button>
          );
        })}
      </span>

      <span className="inline-flex items-center gap-1 text-[11px] text-chrome-500">
        residues
        <input
          type="number"
          aria-label="first residue shown"
          min={1}
          max={length}
          value={filters.from}
          onChange={(event) => filters.setWindow(Number(event.target.value), filters.to)}
          className={NUMBER}
        />
        <input
          type="number"
          aria-label="last residue shown"
          min={1}
          max={length}
          value={filters.to}
          onChange={(event) => filters.setWindow(filters.from, Number(event.target.value))}
          className={NUMBER}
        />
        <span className="text-chrome-600">of {length} aa</span>
      </span>

      <button type="button" className={BUTTON} disabled={!focusable} onClick={onFocus}>
        focus on selection
      </button>
      <button
        type="button"
        className={BUTTON}
        disabled={filters.from === 1 && filters.to === length}
        onClick={() => filters.setWindow(1, length)}
      >
        whole chain
      </button>
      <button
        type="button"
        className={BUTTON}
        disabled={!comparePair}
        title={compareWhy}
        onClick={onUseCompare}
      >
        use pair from Compare
      </button>
    </div>
  );
}
