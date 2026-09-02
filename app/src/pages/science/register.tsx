import type { ReactNode } from 'react';

/**
 * The bits both register widgets share: the confidence caveat and the two designed states
 * (`EmptyRegister`, `Confidence`) every table on this page renders through.
 *
 * The caveat is a constant rather than prose typed twice, because `docs/method.md` requires
 * it to appear wherever a confidence number does, in the same words. The status palette,
 * direction colour and revision-collapsing logic live in `./hypothesis` — a plain `.ts`
 * module carries them so this `.tsx` file can export only components, which is what lets
 * Vite's fast refresh hot-swap it.
 */

/** Repeated verbatim beside every confidence number on this page. */
export const CONFIDENCE_CAVEAT = 'a transparent heuristic for triage, not a calibrated posterior';

/**
 * The empty register, as a designed state.
 *
 * There are two distinct empties and the page must not conflate them: the table has never
 * been written (`table_exists === false`), or it exists and holds nothing. Both mean no
 * claim has been made; only the first also means the register itself does not exist yet.
 */
export function EmptyRegister({
  tableExists,
  title,
  verb,
  children,
}: {
  tableExists: boolean;
  title: string;
  /** The `mva-science` verb that opens this table. */
  verb: string;
  children: ReactNode;
}) {
  return (
    <div className="rounded-lg border border-dashed border-emerald-900/50 bg-emerald-950/10 p-6 text-center">
      <div className="text-sm font-medium text-emerald-400">{title}</div>
      <p className="mx-auto mt-1.5 max-w-2xl text-xs leading-relaxed text-zinc-400">{children}</p>
      <p className="mx-auto mt-2 max-w-2xl text-[11px] leading-relaxed text-zinc-500">
        An empty register is discipline, not absence of work. The method is written down in{' '}
        <span className="font-mono text-zinc-400">docs/method.md</span>, and the register opens the
        moment the first claim is filed with <span className="font-mono text-zinc-400">{verb}</span>
        .
      </p>
      <p className="mt-2 font-mono text-[11px] text-zinc-600">
        {tableExists
          ? 'table exists · 0 rows'
          : 'table not created yet — written on first record, never by a page load'}
      </p>
    </div>
  );
}

/** A confidence number that always carries its caveat. Renders a gap, never a zero. */
export function Confidence({ value, inline = false }: { value: number | null; inline?: boolean }) {
  if (value === null || value === undefined) {
    return (
      <span className="font-mono text-zinc-600" title="no verdict committed yet">
        —
      </span>
    );
  }
  return (
    <span className={inline ? 'inline-flex items-baseline gap-1.5' : 'flex items-baseline gap-1.5'}>
      <span className="font-mono text-amber-400">{value.toFixed(2)}</span>
      <span className="text-[10px] leading-tight text-zinc-500">{CONFIDENCE_CAVEAT}</span>
    </span>
  );
}
