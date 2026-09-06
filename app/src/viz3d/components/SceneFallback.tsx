/**
 * The text twin of the canvas — and the only interactive path that is guaranteed to exist.
 *
 * It is three things at once, on purpose: the no-WebGL rendering, the "three is still
 * loading" rendering, and the keyboard affordance for a canvas (which cannot have one — see
 * the note in `Viz3dCanvas.tsx` on why pointer listeners are attached by hand). A real `<ul>`
 * of `<button>`s is what axe audits and what a screen reader reads, and it fires exactly the
 * same `onSelect` a click on a sphere does, so nothing is reachable by mouse only.
 *
 * **Every datum is reachable.** A page-worth is rendered at a time, and the reader can walk to
 * the end with the *show next* button — a real control, not the "filter the scene" advice this
 * used to give (a protein exhibit deliberately renders no filter panel, so that advice named a
 * control that did not exist and left 990 of BUB1B's 1,050 residues off the keyboard path).
 *
 * The order is not the scene's: **highlighted datums first, then the ones carrying an explicit
 * tone** — a candidate allele, a verdict the page has already decided — then the rest in scene
 * order. So the datums a reader came for are on the first page whatever their residue index.
 */

import { useState } from 'react';

import { cx } from '../../lib/ui';
import { sceneDatums } from '../spec/datums';
import { describeDatumLine, type SceneDescription } from '../spec/describe';
import type { Datum3D, Scene3D, Selection3D } from '../spec/types';

/** How many datums one page of the list renders; a point cloud can hold thousands. */
const PAGE = 60;

/** Highlighted, then tone-bearing, then the rest — each group in scene order. */
function ranked(datums: readonly Datum3D[], highlighted: readonly string[]): readonly Datum3D[] {
  const rank = (datum: Datum3D): number =>
    highlighted.includes(datum.id) ? 0 : datum.tone ? 1 : 2;
  return datums
    .map((datum, index) => ({ datum, index, rank: rank(datum) }))
    .sort((a, b) => a.rank - b.rank || a.index - b.index)
    .map((entry) => entry.datum);
}

export function SceneFallback({
  scene,
  description,
  highlighted = [],
  onSelect,
  note,
}: {
  scene: Scene3D;
  description: SceneDescription;
  highlighted?: readonly string[];
  onSelect?: (selection: Selection3D | null) => void;
  /** Why the text version is showing, when it is showing instead of the canvas. */
  note?: string;
}) {
  const [pages, setPages] = useState(1);
  const datums = ranked(sceneDatums(scene), highlighted);
  const shown = datums.slice(0, pages * PAGE);
  const remaining = datums.length - shown.length;
  const field = description.color.field;

  return (
    <div className="space-y-2">
      {note && <p className="text-xs text-decision-300">{note}</p>}
      <p className="text-xs leading-relaxed text-chrome-400">{description.text}</p>
      <ul className="grid gap-1 sm:grid-cols-2">
        {shown.map((datum) => {
          const on = highlighted.includes(datum.id);
          return (
            <li key={datum.id}>
              <button
                type="button"
                aria-pressed={on}
                onClick={() => onSelect?.(on ? null : { id: datum.id, label: datum.label, datum })}
                className={cx(
                  'w-full truncate rounded-pill border px-2 py-1 text-left font-mono text-micro transition',
                  on
                    ? 'border-decision-700 bg-decision-950/50 text-decision-300'
                    : 'border-line bg-chrome-900 text-chrome-400 hover:border-line-strong hover:text-chrome-200',
                )}
              >
                {describeDatumLine(datum, field)}
              </button>
            </li>
          );
        })}
      </ul>
      {remaining > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setPages((n) => n + 1)}
            className="rounded-pill border border-line-strong bg-chrome-900 px-2 py-1 text-micro text-chrome-300 transition hover:border-chrome-600 hover:text-chrome-100"
          >
            show next {Math.min(PAGE, remaining)}
          </button>
          <button
            type="button"
            onClick={() => setPages(Math.ceil(datums.length / PAGE))}
            className="rounded-pill border border-line px-2 py-1 text-micro text-chrome-400 transition hover:border-line-strong hover:text-chrome-300"
          >
            show all {datums.length}
          </button>
          <p className="text-micro text-chrome-600">
            {remaining} more object(s) below — highlighted and candidate objects are listed first.
          </p>
        </div>
      )}
      {remaining === 0 && datums.length > PAGE && (
        <p className="text-micro text-chrome-600">
          all {datums.length} object(s) listed — highlighted and candidate objects first.
        </p>
      )}
    </div>
  );
}
