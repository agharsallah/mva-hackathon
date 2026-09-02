/**
 * The token pipeline as a diagram: one source, one generator, two halves, two gates.
 *
 * Drawn with the app's own boxes rather than an SVG so it cannot go stale — the labels are
 * plain text and the tints are the same `BOX` recipes the rest of the app uses.
 */

import { Exhibit } from '../../components';
import { BOX, cx } from '../../lib/ui';

interface Stage {
  /** What the box is called. */
  title: string;
  /** The file or command it names. */
  path: string;
  /** Why it exists, in one line. */
  note: string;
  tint: keyof typeof BOX;
}

const STAGES: Stage[][] = [
  [
    {
      title: 'source',
      path: 'node_modules/tailwindcss/theme.css',
      note: 'the installed dependency, in oklch — the numbers nobody in this repo types',
      tint: 'raw',
    },
  ],
  [
    {
      title: 'generator',
      path: 'tools/gen-theme.mjs  ·  pnpm theme',
      note: 'picks the seven families this app paints with, converts oklch to sRGB hex once',
      tint: 'machinery',
    },
  ],
  [
    {
      title: 'the canvas half',
      path: 'src/lib/palette/ramps.generated.ts',
      note: 'RAMP.good[500] — what Plotly, SVG and inline style read',
      tint: 'good',
    },
    {
      title: 'the DOM half',
      path: 'src/theme.generated.css',
      note: '--color-good-500 — what bg-good-500 and lib/ui.ts read',
      tint: 'good',
    },
  ],
  [
    {
      title: 'the gates',
      path: 'pnpm theme:check  ·  theme-tokens.test.ts  ·  eslint local/*',
      note: 'drift between the halves, an unnamed shade, a raw hex, a Tailwind hue: all errors',
      tint: 'decision',
    },
  ],
];

export function TokenPipeline() {
  return (
    <Exhibit
      title="How one number reaches both a chart and a class"
      legend={
        <>
          <span className="text-raw-400">purple</span> = the raw input (the dependency),{' '}
          <span className="text-machinery-400">blue</span> = machinery (the generator),{' '}
          <span className="text-good-400">green</span> = the two generated artifacts,{' '}
          <span className="text-decision-400">yellow</span> = the checks that fail if they disagree.
          Arrows read top to bottom.
        </>
      }
      reading="The DOM and a canvas cannot share a mechanism, so they share a source instead — that is the whole design."
      source="src/lib/palette/index.ts"
    >
      <div className="space-y-2">
        {STAGES.map((row, index) => (
          <div key={row[0].title}>
            {index > 0 && (
              <div aria-hidden className="mb-2 text-center text-xs text-chrome-600">
                &darr;
              </div>
            )}
            <div className={row.length > 1 ? 'grid gap-2 sm:grid-cols-2' : ''}>
              {row.map((stage) => (
                <div key={stage.title} className={cx('rounded-lg border p-3', BOX[stage.tint])}>
                  <div className="text-[11px] font-semibold uppercase tracking-wider">
                    {stage.title}
                  </div>
                  <div className="mt-1 break-all font-mono text-[11px] text-chrome-200">
                    {stage.path}
                  </div>
                  <div className="mt-1 text-[11px] leading-snug text-chrome-400">{stage.note}</div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </Exhibit>
  );
}
