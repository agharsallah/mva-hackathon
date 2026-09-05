/**
 * Two small inline-SVG bar charts over the candidate table.
 *
 * Inline SVG rather than the Plot component: both are ranked bars of a dozen categories,
 * which needs no interaction, no axes library and no 900 kB chart chunk — and drawing them
 * by hand keeps them reproducible from this file alone.
 */

import { int } from '../../lib/format';
import { C } from '../../lib/palette';

export interface Bar {
  label: string;
  value: number;
  /** Second, lighter series drawn behind `value` — the total this count is a subset of. */
  total?: number;
}

const ROW_H = 22;
const LABEL_W = 92;
const PAD = 8;

/**
 * A horizontal ranked bar chart. `width` is the viewBox width; the SVG scales to its box,
 * so nothing here depends on the rendered size.
 */
export function BarChart({
  bars,
  color,
  totalColor,
  label,
  width = 560,
  valueSuffix = '',
}: {
  bars: Bar[];
  color: string;
  totalColor?: string;
  /** The SVG's accessible name — required, this is the only description a reader gets. */
  label: string;
  width?: number;
  valueSuffix?: string;
}) {
  const height = PAD * 2 + bars.length * ROW_H;
  const max = Math.max(1, ...bars.map((b) => b.total ?? b.value));
  const plotW = width - LABEL_W - PAD * 2 - 52;
  const scale = (v: number) => (v / max) * plotW;

  return (
    <div className="overflow-x-auto">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        width="100%"
        height={height}
        role="img"
        aria-label={label}
        className="block"
      >
        {bars.map((b, i) => {
          const y = PAD + i * ROW_H;
          return (
            <g key={b.label} data-bar={b.label} data-value={b.value}>
              <text
                x={LABEL_W}
                y={y + ROW_H / 2 + 4}
                textAnchor="end"
                fontSize="11"
                fontFamily="ui-monospace, monospace"
                fill={C.inkDim}
              >
                {b.label.length > 14 ? `${b.label.slice(0, 13)}…` : b.label}
              </text>
              {b.total !== undefined && totalColor && (
                <rect
                  x={LABEL_W + PAD}
                  y={y + 4}
                  width={Math.max(1, scale(b.total))}
                  height={ROW_H - 9}
                  rx={2}
                  fill={totalColor}
                  opacity={0.35}
                />
              )}
              <rect
                x={LABEL_W + PAD}
                y={y + 4}
                width={Math.max(1, scale(b.value))}
                height={ROW_H - 9}
                rx={2}
                fill={color}
              />
              <text
                x={LABEL_W + PAD + Math.max(1, scale(b.total ?? b.value)) + 6}
                y={y + ROW_H / 2 + 4}
                fontSize="11"
                fontFamily="ui-monospace, monospace"
                fill={C.ink}
              >
                {int(b.value)}
                {valueSuffix}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
