/**
 * The generated ramps, rendered. Seven semantic families x eleven shades, each swatch
 * labelled with the shade it answers to and the hex it resolves to.
 *
 * This is the exhibit that makes the token system checkable by eye: if `pnpm theme` ever
 * writes a different number, the swatch and its printed hex both move together, and a
 * screenshot of this grid diffs against the previous one.
 */

import { Exhibit } from '../../components';
import { type Family, RAMP, SHADES } from '../../lib/palette';

/** What each family is *for*, in the repo's colour legend. Keyed by family, not by tone:
 * `chrome` and `severity` are families no tone claims. */
const MEANING: Record<Family, string> = {
  chrome: 'app furniture — borders, panels, body and label text',
  good: 'good / safe / the goal',
  broken: 'broken / dangerous / lost points',
  decision: 'a decision point',
  machinery: 'neutral machinery',
  raw: 'the raw input',
  severity: 'the extra severity step between broken and decision (chart ramps only)',
};

/** Text drawn on the swatch itself: dark on the pale end, light on the dark end. */
function labelClass(shade: number): string {
  return shade <= 400 ? 'text-chrome-950' : 'text-chrome-100';
}

export function RampGrid() {
  const families = Object.keys(RAMP) as Family[];
  return (
    <Exhibit
      title="The generated ramps"
      legend={
        <>
          One row per semantic family, one column per shade. Every value is written by{' '}
          <code>tools/gen-theme.mjs</code> into both <code>lib/palette/ramps.generated.ts</code>{' '}
          (the hex a chart draws with) and <code>theme.generated.css</code> (the{' '}
          <code>--color-*</code> property a Tailwind class reads), so the swatch below and the class{' '}
          <code>bg-good-500</code> are the same number.
        </>
      }
      reading="Shades 300/400 are text, 800/900 are borders, 950 is a tinted background — the roles lib/ui.ts's recipes stick to."
      source="src/lib/palette/ramps.generated.ts"
    >
      <div className="space-y-3 overflow-x-auto">
        {families.map((family) => (
          <div key={family} className="min-w-[52rem]">
            <div className="mb-1 flex items-baseline gap-2">
              <span className="font-mono text-xs font-semibold text-chrome-200">{family}</span>
              <span className="text-[11px] text-chrome-500">{MEANING[family]}</span>
            </div>
            <div className="grid grid-cols-11 gap-1">
              {SHADES.map((shade) => (
                <div
                  key={shade}
                  className="rounded"
                  style={{ background: RAMP[family][shade] }}
                  title={`${family}-${shade} · ${RAMP[family][shade]}`}
                >
                  <div
                    className={`px-1 pt-1 font-mono text-[10px] leading-none ${labelClass(shade)}`}
                  >
                    {shade}
                  </div>
                  <div
                    className={`px-1 pb-1 pt-0.5 font-mono text-[9px] leading-none opacity-70 ${labelClass(shade)}`}
                  >
                    {RAMP[family][shade].slice(1)}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </Exhibit>
  );
}
