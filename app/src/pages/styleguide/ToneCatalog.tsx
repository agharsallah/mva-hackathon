/**
 * The tone vocabulary, rendered: one row per `Tone`, every recipe that tone has, side by side.
 *
 * Everything here is derived from `TONES` — add a seventh tone in `lib/palette/tones.ts` and
 * it appears in this exhibit without an edit, which is the point: the page is the proof that
 * the new tone answers for every recipe, and `src/test/theme-tokens.test.ts` is the proof it
 * answers with the right family.
 */

import { Badge, Chip, EmptyState, Exhibit } from '../../components';
import { type Tone, TONE_FAMILY, TONE_MARK, TONES } from '../../lib/palette';
import { BADGE, BOX, cx, TEXT } from '../../lib/ui';

/** What each tone *means* — the sentence a call site should be able to answer "yes" to. */
const MEANING: Record<Tone, string> = {
  neutral: 'no verdict attached: a plain figure, a gap, app furniture',
  good: 'the outcome we wanted, or the safe state',
  broken: 'broken, dangerous, or a lost point',
  decision: 'a judgement call the reader has to make',
  machinery: 'plumbing: how the system works, not whether it is good',
  raw: 'a value taken straight from delivered input, not computed',
};

export function ToneCatalog() {
  return (
    <Exhibit
      title="The six tones, and every recipe each one carries"
      legend={
        <>
          One row per tone in <code>lib/palette</code>&apos;s <code>Tone</code>. <b>mark</b> is the
          hex a chart draws with (<code>TONE_MARK</code>); <b>BOX</b>, <b>BADGE</b>, <b>TEXT</b> and{' '}
          <b>EMPTY_DASHED</b> are the live Tailwind recipes from <code>lib/ui.ts</code>. Tone is
          semantic ({TONES.length} meanings), family is the hue that renders it — only{' '}
          <code>neutral</code> differs from its own name, drawn in <code>chrome</code>.
        </>
      }
      reading="A component takes a Tone, never a hue. That is what stops a badge and the tile under it from disagreeing about what green means."
      source="src/lib/palette/tones.ts + src/lib/ui.ts"
    >
      <div className="overflow-x-auto">
        <table className="w-full min-w-[56rem] border-collapse text-xs">
          <thead>
            <tr className="text-left text-[11px] uppercase tracking-wider text-chrome-500">
              <th className="pb-2 pr-3 font-medium">tone</th>
              <th className="pb-2 pr-3 font-medium">family</th>
              <th className="pb-2 pr-3 font-medium">mark</th>
              <th className="pb-2 pr-3 font-medium">TEXT</th>
              <th className="pb-2 pr-3 font-medium">BADGE</th>
              <th className="pb-2 pr-3 font-medium">BOX</th>
              <th className="pb-2 font-medium">EMPTY_DASHED</th>
            </tr>
          </thead>
          <tbody>
            {TONES.map((tone) => (
              <tr key={tone} className="border-t border-chrome-800 align-middle">
                <td className="py-2.5 pr-3">
                  <div className="font-mono text-chrome-200">{tone}</div>
                  <div className="mt-0.5 max-w-[13rem] text-[11px] leading-snug text-chrome-500">
                    {MEANING[tone]}
                  </div>
                </td>
                <td className="py-2.5 pr-3 font-mono text-chrome-400">{TONE_FAMILY[tone]}</td>
                <td className="py-2.5 pr-3 font-mono text-[11px] text-chrome-400">
                  <Chip color={TONE_MARK[tone]}>{TONE_MARK[tone]}</Chip>
                </td>
                <td className={cx('py-2.5 pr-3 font-mono', TEXT[tone])}>1.42</td>
                <td className="py-2.5 pr-3">
                  <Badge tone={tone} title={BADGE[tone]}>
                    {tone}
                  </Badge>
                </td>
                <td className="py-2.5 pr-3">
                  <div
                    title={BOX[tone]}
                    className={cx('rounded-lg border px-2.5 py-1.5', BOX[tone])}
                  >
                    callout
                  </div>
                </td>
                <td className="py-2.5">
                  <EmptyState tone={tone}>nothing here</EmptyState>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-[11px] leading-relaxed text-chrome-600">
        Hover any recipe cell to read the class string it renders — e.g.{' '}
        <code className="font-mono">{BADGE.good}</code>.
      </p>
    </Exhibit>
  );
}
