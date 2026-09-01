import type { ReactNode } from 'react';

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
      className={`rounded-md border px-2 py-1 text-[11px] transition ${
        on
          ? 'border-blue-700 bg-blue-950/60 text-blue-300'
          : 'border-zinc-700 bg-zinc-900 text-zinc-400 hover:bg-zinc-800'
      }`}
    >
      {children}
    </button>
  );
}

export function Select<T extends string | number>({
  value,
  options,
  onChange,
  label,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
  label?: string;
}) {
  return (
    <label className="inline-flex items-center gap-1.5 text-[11px] text-zinc-500">
      {label}
      <select
        value={String(value)}
        onChange={(e) => {
          const raw = e.target.value;
          const found = options.find((o) => String(o.value) === raw);
          if (found) onChange(found.value);
        }}
        className="rounded-md border border-zinc-700 bg-zinc-900 px-2 py-1 text-[11px] text-zinc-200"
      >
        {options.map((o) => (
          <option key={String(o.value)} value={String(o.value)}>
            {o.label}
          </option>
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
    <label className="inline-flex items-center gap-1.5 text-[11px] text-zinc-500">
      {label}
      <span className="relative inline-flex items-center">
        <input
          type="search"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          spellCheck={false}
          style={{ width }}
          className="rounded-md border border-zinc-700 bg-zinc-900 px-2 py-1 text-[11px] text-zinc-200 placeholder:text-zinc-600 focus:border-blue-700 focus:outline-none"
        />
        {value && (
          <button
            onClick={() => onChange('')}
            aria-label="clear filter"
            className="absolute right-1.5 text-zinc-500 hover:text-zinc-300"
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
}: {
  title: string;
  subtitle?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-base font-semibold tracking-tight text-zinc-100">{title}</h2>
        {subtitle && <p className="mt-0.5 text-xs text-zinc-500">{subtitle}</p>}
      </div>
      {children}
    </section>
  );
}
