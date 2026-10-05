/**
 * The design system, rendered from the generated tokens rather than described in prose.
 *
 * `tools/gen-theme.mjs` emits two halves of one palette — `lib/palette/ramps.generated.ts`
 * (hex, read by charts and SVG) and `src/theme.generated.css` (custom properties, read by
 * Tailwind classes). This page shows what those halves currently hold, plus the primitives
 * every page is built from, so a new page can see the contract instead of guessing it.
 */

import { Badge, Card, Chip, DataTable, Exhibit, Section, Skeleton, StatTile } from '../components';
import type { Family, Tone } from '../lib/palette';
import { C, RAMP, SHADES, TONE_MARK, TONES } from '../lib/palette';
import { cx, WELL } from '../lib/ui';
import { PlotSpecimen, ScenesSpecimen } from './styleguide/Specimens';

const FAMILIES = Object.keys(RAMP) as Family[];

/** One family as a row of its eleven shades, labelled by step. */
function RampRow({ family }: { family: Family }) {
  return (
    <div className="space-y-1">
      <p className="font-mono text-micro text-chrome-400">{family}</p>
      <div className="flex overflow-hidden rounded-control">
        {SHADES.map((shade) => (
          <div
            key={shade}
            title={`${family}-${shade} · ${RAMP[family][shade]}`}
            className="h-8 flex-1"
            style={{ backgroundColor: RAMP[family][shade] }}
          />
        ))}
      </div>
      <div className="flex text-micro text-chrome-600">
        {SHADES.map((shade) => (
          <span key={shade} className="flex-1 text-center">
            {shade}
          </span>
        ))}
      </div>
    </div>
  );
}

interface ToneRow {
  tone: Tone;
  means: string;
  hex: string;
}

const TONE_MEANS: Record<Tone, string> = {
  neutral: 'no verdict attached — app furniture, or a plain number',
  good: 'good, safe, or the goal',
  broken: 'broken, dangerous, or lost points',
  decision: 'a decision point — something the reader must choose',
  machinery: 'neutral machinery — the system doing its job',
  raw: 'the raw input, before anything was derived from it',
};

const TONE_ROWS: ToneRow[] = TONES.map((tone) => ({
  tone,
  means: TONE_MEANS[tone],
  hex: TONE_MARK[tone],
}));

export default function StyleGuide() {
  return (
    <div className="space-y-8">
      <Section
        title="Colour ramps"
        subtitle="Generated, never hand-written: one family per hue, eleven shades each."
      >
        <Card>
          <div className="space-y-4">
            {FAMILIES.map((family) => (
              <RampRow key={family} family={family} />
            ))}
          </div>
        </Card>
      </Section>

      <Section
        title="Tones"
        subtitle="A tone is a meaning, not a hue. Every component that tints something takes one of these."
      >
        <Exhibit
          title="The tone vocabulary"
          legend={
            <span className="flex flex-wrap gap-3">
              {TONES.map((tone) => (
                <Chip key={tone} color={TONE_MARK[tone]}>
                  {tone}
                </Chip>
              ))}
            </span>
          }
          reading="Adding a seventh meaning is a compiler error at every site that maps a tone, never a silent gap."
          source="src/lib/palette/tones.ts"
          data={TONE_ROWS}
        >
          <DataTable
            rows={TONE_ROWS}
            columns={[
              {
                key: 'tone',
                header: 'Tone',
                render: (r) => <Badge tone={r.tone}>{r.tone}</Badge>,
              },
              { key: 'means', header: 'What it means', render: (r) => r.means },
              {
                key: 'hex',
                header: 'Mark colour',
                render: (r) => <span className="font-mono text-micro">{r.hex}</span>,
              },
            ]}
            rowKey={(r) => r.tone}
          />
        </Exhibit>
      </Section>

      <Section title="Primitives" subtitle="What a page composes instead of writing markup.">
        <div className="grid gap-3 lg:grid-cols-2">
          <Card>
            <p className="mb-3 text-xs font-medium text-chrome-300">Stat tiles</p>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
              <StatTile label="Records" value="12,480" sub="after filtering" />
              <StatTile label="Passing" value="97.2%" tone="good" sub="of all records" />
              <StatTile label="Dropped" value="344" tone="broken" sub="failed a check" />
            </div>
          </Card>

          <Card>
            <p className="mb-3 text-xs font-medium text-chrome-300">Badges</p>
            <div className="flex flex-wrap gap-2">
              {TONES.map((tone) => (
                <Badge key={tone} tone={tone}>
                  {tone}
                </Badge>
              ))}
            </div>
            <p className="mt-4 mb-2 text-xs font-medium text-chrome-300">Loading state</p>
            <Skeleton height={80} variant="block" label="Specimen skeleton" />
          </Card>
        </div>
      </Section>

      <Section
        title="Figures"
        subtitle="The two heavy renderers, each behind its own dynamically-imported wrapper."
      >
        <div className="space-y-3">
          <PlotSpecimen />
          <ScenesSpecimen />
        </div>
      </Section>

      <Section
        title="Surfaces"
        subtitle="The three depths a page may use. Everything else is one of these."
      >
        <div className="grid gap-3 sm:grid-cols-3">
          <Card>
            <p className="text-xs text-chrome-300">Card — a panel on the page background.</p>
          </Card>
          <div className={cx(WELL)}>
            <p className="text-xs text-chrome-300">Well — a recess inside a card.</p>
          </div>
          <div className="rounded-card border border-line p-4" style={{ backgroundColor: C.paper }}>
            <p className="text-xs text-chrome-300">Paper — the page itself.</p>
          </div>
        </div>
      </Section>
    </div>
  );
}
