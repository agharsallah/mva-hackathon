/**
 * The colour *scales*, rendered as the gradients the charts actually paint.
 *
 * A tone answers "what does this value mean"; a scale answers "where on a range does it sit".
 * Each strip below is built from the same stop list Plotly receives, so what you see is what
 * a heatmap draws — and the stop chips underneath name the ramp entry each stop came from.
 */

import { Exhibit } from '../../components';
import {
  type Colorscale,
  DENSITY_SCALE,
  DEPTH_SCALE,
  DIVERGING_SCALE,
  QUALITY_SCALE,
  RAMP,
  RARITY_SCALE,
  REASON_RAMP,
  SERIES,
} from '../../lib/palette';

/** Reverse lookup: hex -> `family-shade`, so a strip can name its own stops. */
const NAME_OF = new Map<string, string>(
  Object.entries(RAMP).flatMap(([family, ramp]) =>
    Object.entries(ramp).map(([shade, hex]) => [hex, `${family}-${shade}`] as const),
  ),
);

const SCALES: Array<{ name: string; scale: Colorscale; use: string }> = [
  { name: 'DENSITY_SCALE', scale: DENSITY_SCALE, use: 'variants per megabase, genome-wide' },
  { name: 'DEPTH_SCALE', scale: DEPTH_SCALE, use: 'read depth' },
  { name: 'QUALITY_SCALE', scale: QUALITY_SCALE, use: 'base and mapping quality' },
  {
    name: 'DIVERGING_SCALE',
    scale: DIVERGING_SCALE,
    use: 'allele balance — the goal is the middle, both directions away from it are abnormal',
  },
  { name: 'RARITY_SCALE', scale: RARITY_SCALE, use: 'compound-het pair rarity' },
];

const CATEGORICAL: Array<{ name: string; colors: string[]; use: string }> = [
  { name: 'SERIES', colors: SERIES, use: 'one line per lane or read group' },
  { name: 'REASON_RAMP', colors: REASON_RAMP, use: 'suppression reasons, heaviest first' },
];

function gradient(scale: Colorscale): string {
  const stops = scale.map(([position, hex]) => `${hex} ${(position * 100).toFixed(1)}%`);
  return `linear-gradient(to right, ${stops.join(', ')})`;
}

export function ScaleStrips() {
  return (
    <Exhibit
      title="Colour scales, as the charts paint them"
      legend={
        <>
          Each strip is the interpolated gradient Plotly receives; each chip below it is one stop,
          labelled with the ramp entry it resolves to. Sequential strips run dark to hot;{' '}
          <code>DIVERGING_SCALE</code> puts green in the <em>centre</em> because for allele balance
          the midpoint is the goal and both directions away from it are the abnormal outcome.
        </>
      }
      reading="Every stop is a ramp entry, never a hand-picked hex — src/test/theme-tokens.test.ts fails if one wanders off the palette."
      source="src/lib/palette/scales.ts"
    >
      <div className="space-y-4">
        {SCALES.map(({ name, scale, use }) => (
          <div key={name}>
            <div className="mb-1 flex flex-wrap items-baseline gap-2">
              <span className="font-mono text-xs font-semibold text-chrome-200">{name}</span>
              <span className="text-micro text-chrome-500">{use}</span>
            </div>
            <div
              className="h-7 rounded-pill border border-line"
              style={{ background: gradient(scale) }}
            />
            <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 font-mono text-micro text-chrome-600">
              {scale.map(([position, hex]) => (
                <span key={`${position}-${hex}`}>
                  {position} · {NAME_OF.get(hex) ?? hex}
                </span>
              ))}
            </div>
          </div>
        ))}

        {CATEGORICAL.map(({ name, colors, use }) => (
          <div key={name}>
            <div className="mb-1 flex flex-wrap items-baseline gap-2">
              <span className="font-mono text-xs font-semibold text-chrome-200">{name}</span>
              <span className="text-micro text-chrome-500">{use}</span>
            </div>
            <div className="flex gap-1">
              {colors.map((hex, index) => (
                <div
                  key={`${name}-${index}`}
                  className="h-7 flex-1 rounded-pill border border-line"
                  style={{ background: hex }}
                  title={`${name}[${index}] · ${NAME_OF.get(hex) ?? hex}`}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
    </Exhibit>
  );
}
