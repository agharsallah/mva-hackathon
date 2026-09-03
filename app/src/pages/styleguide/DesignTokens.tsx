/**
 * The role tokens, rendered by the tokens themselves.
 *
 * Colour has its own exhibits (`RampGrid`, `ToneCatalog`, `ScaleStrips`); this one covers the
 * other four axes a page is never allowed to pick by hand — type size, radius, hairline weight,
 * surface — plus the spacing grid and the `Card` variants built on them.
 *
 * Nothing below is drawn from a number typed here. Each specimen is a real element carrying the
 * real utility class, and the measurement beside it is read back off that element with
 * `getComputedStyle` after mount. Change `--text-heading` in `src/index.css` and this page says
 * the new size without an edit; the declared value in the table is only the fallback for an
 * environment with no stylesheet (jsdom, in the smoke tests).
 */

import { type ReactNode, useEffect, useRef, useState } from 'react';

import { Badge, Card, Exhibit } from '../../components';
import { cx } from '../../lib/ui';

/**
 * Read one computed CSS property off the element once it is in the document. Returns `null`
 * until measured, and in any environment where the stylesheet never loaded.
 */
function useMeasured<T extends HTMLElement>(property: string) {
  const ref = useRef<T>(null);
  const [value, setValue] = useState<string | null>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const raw = window.getComputedStyle(el).getPropertyValue(property).trim();
    setValue(raw === '' ? null : raw);
  }, [property]);
  return [ref, value] as const;
}

/** A titled block inside the exhibit — the six axes read as six labelled groups. */
function Group({ title, note, children }: { title: string; note: string; children: ReactNode }) {
  return (
    <section className="space-y-2">
      <div className="flex flex-wrap items-baseline gap-2">
        <h4 className="text-sm font-semibold text-chrome-100">{title}</h4>
        <span className="text-micro text-chrome-500">{note}</span>
      </div>
      {children}
    </section>
  );
}

/** The class name itself, rendered as the mark a reader copies. */
function Token({ children }: { children: ReactNode }) {
  return (
    <Badge className="font-mono" tone="machinery">
      {children}
    </Badge>
  );
}

// ─── a. type ────────────────────────────────────────────────────────────────────────────────

interface TypeRole {
  role: string;
  cls: string;
  /** The size declared in `@theme`, shown only where the DOM cannot be measured. */
  declared: string;
  use: string;
  /** Serif roles are the reading voice and must be specimened in it. */
  serif?: boolean;
}

const TYPE_ROLES: TypeRole[] = [
  { role: 'micro', cls: 'text-micro', declared: '11px', use: 'chips, badges, provenance lines' },
  { role: 'label', cls: 'text-xs', declared: '12px', use: 'table headers, legends, controls' },
  {
    role: 'footnote',
    cls: 'text-note',
    declared: '13px',
    use: 'caveats, definitions, a reading line',
    serif: true,
  },
  { role: 'body', cls: 'text-sm', declared: '14px', use: 'the default — nav, labels, tables' },
  {
    role: 'reading',
    cls: 'text-reading',
    declared: '15px',
    use: 'prose — an explainer intro, a callout body',
    serif: true,
  },
  { role: 'heading', cls: 'text-heading', declared: '17px', use: 'a Section h2' },
  { role: 'figure', cls: 'text-figure', declared: '26px', use: 'the number on a StatTile' },
  { role: 'title', cls: 'text-title', declared: '30px', use: 'the page h1' },
];

const SPECIMEN = 'Compound heterozygote in BUB1B';

function TypeRow({ role }: { role: TypeRole }) {
  const [ref, size] = useMeasured<HTMLParagraphElement>('font-size');
  return (
    <tr className="border-t border-line align-baseline">
      <td className="py-3 pr-3 font-mono text-xs text-chrome-200">{role.role}</td>
      <td className="py-3 pr-3">
        <Token>{role.cls}</Token>
      </td>
      <td className="py-3 pr-3 text-right font-mono text-xs tabular-nums text-chrome-400">
        {size ?? role.declared}
      </td>
      <td className="py-3">
        <p ref={ref} className={cx(role.cls, role.serif ? 'font-serif' : 'font-sans')}>
          {SPECIMEN}
        </p>
        <p className="mt-2 text-micro text-chrome-500">{role.use}</p>
      </td>
    </tr>
  );
}

// ─── b. radii ───────────────────────────────────────────────────────────────────────────────

const RADII = [
  { cls: 'rounded-pill', declared: '4px', use: 'a badge, a chip, a tag' },
  { cls: 'rounded-control', declared: '6px', use: 'a button, a select, an input' },
  { cls: 'rounded-card', declared: '8px', use: 'a card, an exhibit, a callout' },
];

function RadiusSwatch({ cls, declared, use }: (typeof RADII)[number]) {
  const [ref, radius] = useMeasured<HTMLDivElement>('border-radius');
  return (
    <Card variant="well" padding="sm" className="space-y-2">
      <div
        ref={ref}
        className={cx('h-14 border border-line-strong bg-panel-raised', cls)}
        aria-hidden
      />
      <div className="flex flex-wrap items-center gap-2">
        <Token>{cls}</Token>
        <span className="font-mono text-micro tabular-nums text-chrome-400">
          {radius ?? declared}
        </span>
      </div>
      <p className="text-micro text-chrome-500">{use}</p>
    </Card>
  );
}

// ─── c. hairlines ───────────────────────────────────────────────────────────────────────────

const LINES = [
  { cls: 'border-line-soft', behind: 'chrome-900', use: 'the edge of a well, the softest step' },
  { cls: 'border-line', behind: 'chrome-800', use: 'the default — every card and table rule' },
  { cls: 'border-line-strong', behind: 'chrome-700', use: 'a hover edge, an emphasised divider' },
];

function LineSwatch({ cls, behind, use }: (typeof LINES)[number]) {
  return (
    <Card variant="well" padding="sm" className="space-y-2">
      <div className={cx('h-14 rounded-control border bg-panel', cls)} aria-hidden />
      <div className="flex flex-wrap items-center gap-2">
        <Token>{cls}</Token>
        <span className="font-mono text-micro text-chrome-500">{behind}</span>
      </div>
      <p className="text-micro text-chrome-500">{use}</p>
    </Card>
  );
}

function FocusSwatch() {
  return (
    <Card variant="well" padding="sm" className="space-y-2">
      <div className="h-14 rounded-control bg-panel ring-2 ring-focus" aria-hidden />
      <div className="flex flex-wrap items-center gap-2">
        <Token>ring-focus</Token>
        <span className="font-mono text-micro text-chrome-500">machinery-600</span>
      </div>
      <p className="text-micro text-chrome-500">
        the keyboard focus ring — never removed, only recoloured
      </p>
    </Card>
  );
}

// ─── e. spacing ─────────────────────────────────────────────────────────────────────────────

const STEPS = [
  { cls: 'w-2', step: '2', declared: '8px', use: 'tight — between two chips on one row' },
  { cls: 'w-3', step: '3', declared: '12px', use: 'inner rhythm — rows inside a card' },
  { cls: 'w-4', step: '4', declared: '16px', use: 'card padding' },
  { cls: 'w-6', step: '6', declared: '24px', use: 'between sections on a page' },
];

function SpacingBar({ cls, step, declared, use }: (typeof STEPS)[number]) {
  const [ref, width] = useMeasured<HTMLDivElement>('width');
  return (
    <div className="flex items-center gap-3">
      <span className="w-6 shrink-0 font-mono text-xs text-chrome-200">{step}</span>
      <div
        ref={ref}
        className={cx('h-4 shrink-0 rounded-pill bg-machinery-600', cls)}
        aria-hidden
      />
      <span className="w-14 shrink-0 font-mono text-micro tabular-nums text-chrome-400">
        {width ?? declared}
      </span>
      <span className="text-micro text-chrome-500">{use}</span>
    </div>
  );
}

// ─── f. card variants ───────────────────────────────────────────────────────────────────────

const VARIANTS = [
  { variant: 'panel', use: 'the default — a bordered card on the page' },
  { variant: 'well', use: 'recessed, for a block inside a card' },
  { variant: 'plain', use: 'the padding rhythm with no border' },
] as const;

// ─── the exhibit ────────────────────────────────────────────────────────────────────────────

export function DesignTokens() {
  return (
    <Exhibit
      title="The tokens"
      legend={
        <>
          Every specimen carries the real utility class and the size beside it is read back off that
          element with <code>getComputedStyle</code>, so nothing here is a number typed twice.{' '}
          <span className="text-machinery-400">blue</span> = machinery (the class names, the spacing
          bars), grey = app furniture (the <code>chrome</code> family every hairline and surface is
          drawn from). Serif specimens are the reading voice, sans the operating voice.
        </>
      }
      reading="A page names a role — text-heading, rounded-card, border-line, bg-well — and never a pixel, a radius or a grey. That is what keeps eleven pages looking like one app, and what makes the light theme a shade mirror rather than a second stylesheet."
      source="src/index.css (@theme) + src/lib/ui.ts"
    >
      <div className="space-y-6">
        <Group title="Type" note="eight roles, two voices">
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="text-xs text-chrome-500">
                <th className="pb-2 pr-3 font-medium">role</th>
                <th className="pb-2 pr-3 font-medium">class</th>
                <th className="pb-2 pr-3 text-right font-medium">size</th>
                <th className="pb-2 font-medium">specimen</th>
              </tr>
            </thead>
            <tbody>
              {TYPE_ROLES.map((role) => (
                <TypeRow key={role.cls} role={role} />
              ))}
            </tbody>
          </table>
        </Group>

        <Group title="Radii" note="three, chosen by what the shape is">
          <div className="grid gap-3 sm:grid-cols-3">
            {RADII.map((r) => (
              <RadiusSwatch key={r.cls} {...r} />
            ))}
          </div>
        </Group>

        <Group title="Hairlines" note="three weights and the focus ring">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {LINES.map((l) => (
              <LineSwatch key={l.cls} {...l} />
            ))}
            <FocusSwatch />
          </div>
        </Group>

        <Group title="Surfaces" note="each one lifts off the one behind it">
          <div className="rounded-card bg-chrome-950 p-4">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <span className="text-micro text-chrome-500">the page</span>
              <Token>bg-chrome-950</Token>
            </div>
            <div className="rounded-card border border-line bg-panel p-4">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <span className="text-micro text-chrome-500">a card or an exhibit</span>
                <Token>bg-panel</Token>
                <span className="rounded-control border border-line bg-panel-raised px-2 py-0.5 font-mono text-micro text-chrome-400">
                  bg-panel-raised — a control on it
                </span>
              </div>
              <div className="rounded-control border border-line-soft bg-well p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-micro text-chrome-500">a well inside the card</span>
                  <Token>bg-well</Token>
                </div>
              </div>
            </div>
          </div>
        </Group>

        <Group title="Spacing" note="a strict 4px grid; only a chip may use a half step">
          <Card variant="well" padding="sm" className="space-y-3">
            {STEPS.map((s) => (
              <SpacingBar key={s.cls} {...s} />
            ))}
          </Card>
        </Group>

        <Group title="Card variants" note="the three surfaces, as the component that carries them">
          <div className="grid gap-3 sm:grid-cols-3">
            {VARIANTS.map(({ variant, use }) => (
              <Card key={variant} variant={variant} className="space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <Token>variant=&quot;{variant}&quot;</Token>
                </div>
                <p className="text-micro text-chrome-500">{use}</p>
              </Card>
            ))}
          </div>
          <p className="text-micro text-chrome-500">
            Padding is a second prop on the same three: <code>md</code> is the card step,{' '}
            <code>sm</code> the dense one, <code>none</code> for a table flush to the edge.
          </p>
        </Group>
      </div>
    </Exhibit>
  );
}
