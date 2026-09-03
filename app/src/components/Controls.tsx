import { type ReactNode, useEffect, useRef } from 'react';

import { sectionRegistry, slugify } from '../lib/sections';

export function Toggle({
  on,
  onChange,
  children,
}: {
  on: boolean;
  onChange: (v: boolean) => void;
  children: ReactNode;
}) {
  return (
    <button
      onClick={() => onChange(!on)}
      aria-pressed={on}
      className={`rounded-control border px-2 py-1 text-micro transition ${
        on
          ? 'border-machinery-700 bg-machinery-950/60 text-machinery-300'
          : 'border-line-strong bg-chrome-900 text-chrome-400 hover:bg-chrome-800'
      }`}
    >
      {children}
    </button>
  );
}

/** One `<option>`. */
export interface SelectOption<T extends string | number> {
  value: T;
  label: string;
}

/** One `<optgroup>`: a heading over a subset of the options. */
export interface SelectGroup<T extends string | number> {
  label: string;
  options: readonly SelectOption<T>[];
}

/**
 * `groups` is additive: a call site that passes only `options` renders exactly what it
 * always did. Passing `groups` renders `<optgroup>` headings instead — the browser's own
 * grouping affordance, which is what a picker over a set that splits into meaningful
 * classes (an annotated panel vs. fold-only reference genes) needs, and which a flat list
 * of 20 symbols cannot express. Both may be passed; `options` then renders ungrouped
 * *above* the groups.
 */
export function Select<T extends string | number>({
  value,
  options = [],
  groups = [],
  onChange,
  label,
  disabled = false,
}: {
  value: T;
  options?: readonly SelectOption<T>[];
  groups?: readonly SelectGroup<T>[];
  onChange: (v: T) => void;
  label?: string;
  /**
   * For the one honest use of a dead picker: the vocabulary is still in flight, the caller is
   * showing the URL-held value as a single placeholder option, and a change event could not
   * be resolved against anything yet.
   */
  disabled?: boolean;
}) {
  const all = [...options, ...groups.flatMap((g) => g.options)];
  return (
    <label className="inline-flex items-center gap-2 text-micro text-chrome-500">
      {label}
      <select
        value={String(value)}
        // Explicit, even though the wrapping `<label>` already names it: a label that *wraps*
        // its control has the control's own text inside it, so the computed accessible name
        // came out as the label plus every option ("A CEP57 DICER1 BUB1B …"). That is what a
        // screen reader announces, and what a browser-driver locator matches on.
        aria-label={label}
        disabled={disabled}
        onChange={(e) => {
          const raw = e.target.value;
          const found = all.find((o) => String(o.value) === raw);
          if (found) onChange(found.value);
        }}
        className="rounded-control border border-line-strong bg-chrome-900 px-2 py-1 text-micro text-chrome-200 disabled:opacity-60"
      >
        {options.map((o) => (
          <option key={String(o.value)} value={String(o.value)}>
            {o.label}
          </option>
        ))}
        {groups.map((g) => (
          <optgroup key={g.label} label={g.label}>
            {g.options.map((o) => (
              <option key={String(o.value)} value={String(o.value)}>
                {o.label}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
    </label>
  );
}

/** Free-text filter box. Styled as a Select so a control row stays visually one thing. */
export function TextFilter({
  value,
  onChange,
  placeholder,
  label,
  width = 220,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  label?: string;
  width?: number;
}) {
  return (
    <label className="inline-flex items-center gap-2 text-micro text-chrome-500">
      {label}
      <span className="relative inline-flex items-center">
        <input
          type="search"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          spellCheck={false}
          style={{ width }}
          className="rounded-control border border-line-strong bg-chrome-900 px-2 py-1 text-micro text-chrome-200 placeholder:text-chrome-600 focus:border-machinery-700 focus:outline-none"
        />
        {value && (
          <button
            onClick={() => onChange('')}
            aria-label="clear filter"
            className="absolute right-1.5 text-chrome-500 hover:text-chrome-300"
          >
            ×
          </button>
        )}
      </span>
    </label>
  );
}

export function Section({
  title,
  children,
  subtitle,
  id,
}: {
  title: string;
  subtitle?: ReactNode;
  children: ReactNode;
  /**
   * Anchor target, so another page can deep-link to this section with `#id`. Defaults to a
   * slug of the title; either way the section registers itself for the "On this page" rail.
   */
  id?: string;
}) {
  const ref = useRef<HTMLElement>(null);
  const sid = id ?? slugify(title);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    sectionRegistry.register({ id: sid, title, el });
    return () => sectionRegistry.unregister(sid);
  }, [sid, title]);
  return (
    <section ref={ref} id={sid} className="scroll-mt-28 space-y-3">
      <div>
        <h2 className="text-heading font-semibold tracking-tight text-chrome-100">{title}</h2>
        {subtitle && (
          <p className="mt-0.5 max-w-[80ch] font-serif text-sm text-chrome-400 italic">
            {subtitle}
          </p>
        )}
      </div>
      {children}
    </section>
  );
}
