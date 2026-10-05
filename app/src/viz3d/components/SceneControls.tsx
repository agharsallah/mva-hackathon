/**
 * The generic explorer control row: camera preset, colour-by, layer toggles, per-field
 * filters, reset. Built to drop into an `Exhibit`'s `controls` slot, or above the canvas.
 *
 * It renders whatever the *scene* declared — `encodings`, `layers`, and the fields
 * `useSceneExplorer` classified out of `Datum3D.meta`. Nothing here names a domain entity
 * or a metric, which is the property that lets another problem reuse it unchanged.
 *
 * Why the little `<select>`/`<button>` primitives are re-implemented here rather than
 * imported from `src/components/Controls.tsx`: `viz3d` may import `lib` only (see
 * `../README.md`). Importing `components` would give this module the right to reach `api`,
 * which is exactly the coupling that would make it non-transferable. The classes are copied
 * from `Controls.tsx` on purpose, so the two rows look identical.
 */

import { useState } from 'react';

import { cx } from '../../lib/ui';
import type { SceneExplorer } from '../hooks/useSceneExplorer';
import { num } from '../spec/describe';
import { CAMERA_PRESETS, type CameraPreset } from '../spec/types';

const LABEL = 'inline-flex items-center gap-2 text-micro text-chrome-400';
const INPUT =
  'rounded-control border border-line-strong bg-chrome-900 px-2 py-1 text-micro text-chrome-200';

export function SceneControls({
  explorer,
  view,
  onViewChange,
  filters = true,
}: {
  explorer: SceneExplorer;
  view: CameraPreset;
  onViewChange: (view: CameraPreset) => void;
  /** Set false for a compact row with no per-field filtering. */
  filters?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const filterable = explorer.fields.filter(
    (field) => field.kind === 'numeric' || field.values.length > 1,
  );

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
      <label className={LABEL}>
        view
        <select
          // See `components/Controls.tsx`: a wrapping label's text includes the select's own
          // options, so the accessible name has to be stated.
          aria-label="view"
          value={view}
          onChange={(event) => onViewChange(event.target.value as CameraPreset)}
          className={INPUT}
        >
          {CAMERA_PRESETS.map((preset) => (
            <option key={preset} value={preset}>
              {preset}
            </option>
          ))}
        </select>
      </label>

      <label className={LABEL}>
        colour by
        <select
          aria-label="colour by"
          value={explorer.encoding.id}
          onChange={(event) => explorer.setEncoding(event.target.value)}
          className={INPUT}
        >
          {explorer.encodings.map((encoding) => (
            <option key={encoding.id} value={encoding.id}>
              {encoding.label}
            </option>
          ))}
        </select>
      </label>

      {explorer.layers.map((layer) => (
        <button
          key={layer.id}
          type="button"
          aria-pressed={layer.on}
          onClick={() => explorer.toggleLayer(layer.id)}
          className={cx(
            'rounded-control border px-2 py-1 text-micro transition',
            layer.on
              ? 'border-machinery-700 bg-machinery-950/60 text-machinery-300'
              : 'border-line-strong bg-chrome-900 text-chrome-400 hover:bg-chrome-800',
          )}
        >
          {layer.label}
        </button>
      ))}

      <span className="text-micro text-chrome-600">
        {num(explorer.visible)} / {num(explorer.total)} shown
      </span>

      {filters && filterable.length > 0 && (
        <button
          type="button"
          aria-expanded={open}
          onClick={() => setOpen(!open)}
          className={cx(INPUT, 'text-chrome-400 hover:text-chrome-200')}
        >
          {open ? 'hide filters' : 'filter…'}
        </button>
      )}

      <button
        type="button"
        onClick={explorer.reset}
        className={cx(INPUT, 'text-chrome-400 hover:text-chrome-200')}
      >
        reset view
      </button>

      {open && filters && (
        <div className="w-full space-y-2 rounded-control border border-line bg-chrome-950/60 p-2">
          {filterable.map((field) =>
            field.kind === 'numeric' ? (
              <div key={field.name} className="flex flex-wrap items-center gap-2">
                <span className="w-28 truncate font-mono text-micro text-chrome-400">
                  {field.name}
                </span>
                <input
                  type="number"
                  aria-label={`${field.name} minimum`}
                  className={cx(INPUT, 'w-24')}
                  value={explorer.ranges[field.name]?.[0] ?? field.min}
                  onChange={(event) =>
                    explorer.setRange(field.name, [
                      Number(event.target.value),
                      explorer.ranges[field.name]?.[1] ?? field.max,
                    ])
                  }
                />
                <input
                  type="number"
                  aria-label={`${field.name} maximum`}
                  className={cx(INPUT, 'w-24')}
                  value={explorer.ranges[field.name]?.[1] ?? field.max}
                  onChange={(event) =>
                    explorer.setRange(field.name, [
                      explorer.ranges[field.name]?.[0] ?? field.min,
                      Number(event.target.value),
                    ])
                  }
                />
                <span className="text-micro text-chrome-600">
                  data {num(field.min)} … {num(field.max)}
                </span>
              </div>
            ) : (
              <div key={field.name} className="flex flex-wrap items-center gap-2">
                <span className="w-28 truncate font-mono text-micro text-chrome-400">
                  {field.name}
                </span>
                {field.values.map((value) => {
                  const on = !(explorer.excluded[field.name] ?? []).includes(value);
                  return (
                    <button
                      key={value}
                      type="button"
                      aria-pressed={on}
                      onClick={() => explorer.toggleValue(field.name, value)}
                      className={cx(
                        'rounded-pill border px-2 py-0.5 text-micro transition',
                        on
                          ? 'border-chrome-600 bg-chrome-800 text-chrome-200'
                          : 'border-line bg-chrome-950 text-chrome-600',
                      )}
                    >
                      {value}
                    </button>
                  );
                })}
              </div>
            ),
          )}
        </div>
      )}
    </div>
  );
}
