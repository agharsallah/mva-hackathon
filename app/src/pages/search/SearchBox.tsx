/**
 * The one free-text control in the app.
 *
 * Styled to match `TextFilter` in `components/Controls.tsx` — same border, same focus
 * ring, same clear affordance — but it is a *submit* control, not a live filter: every
 * keystroke here would be a scan of a five-million-row table, so the query only leaves
 * the box on Enter. That difference is why this is its own component rather than a wider
 * `TextFilter`.
 */

import { useEffect, useState, type FormEvent } from 'react';

export const PLACEHOLDER = 'gene symbol (BUB1B) · region (15:40100000-40200000) · rsID (rs137852899)';

/** The three forms, as one-click examples. Kept in step with the server's `EXAMPLES`. */
export const EXAMPLES: { q: string; what: string }[] = [
  { q: 'BUB1B', what: 'a panel gene' },
  { q: 'TTN', what: 'an off-panel gene, resolved by Ensembl' },
  { q: 'chr15:40140983-40241137', what: 'a region, either chr spelling' },
  { q: 'rs1042522', what: 'an rsID the callset carries' },
  { q: 'rs137852899', what: 'an rsID dbSNP knows and this callset never called' },
];

export function SearchBox({
  value,
  onSubmit,
  busy,
}: {
  value: string;
  onSubmit: (q: string) => void;
  busy?: boolean;
}) {
  const [draft, setDraft] = useState(value);

  // The URL is the source of truth (a /search?q=… link has to land on its results), so a
  // navigation — back button, shared link, example chip — rewrites the box.
  useEffect(() => setDraft(value), [value]);

  function submit(e: FormEvent) {
    e.preventDefault();
    onSubmit(draft.trim());
  }

  return (
    <form onSubmit={submit} className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className="relative flex-1 basis-[420px]">
          <input
            type="search"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={PLACEHOLDER}
            spellCheck={false}
            autoFocus
            aria-label="search the callset by gene, region or rsID"
            className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2.5 font-mono text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-blue-700 focus:outline-none"
          />
          {draft && (
            <button
              type="button"
              onClick={() => setDraft('')}
              aria-label="clear the query"
              className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300"
            >
              ×
            </button>
          )}
        </span>
        <button
          type="submit"
          disabled={!draft.trim() || busy}
          className="rounded-lg border border-blue-700 bg-blue-950/60 px-4 py-2.5 text-sm text-blue-300 transition hover:bg-blue-900/60 disabled:cursor-not-allowed disabled:border-zinc-800 disabled:bg-zinc-900 disabled:text-zinc-600"
        >
          {busy ? 'searching…' : 'Search'}
        </button>
      </div>
      <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-zinc-600">
        <span>try</span>
        {EXAMPLES.map((e) => (
          <button
            key={e.q}
            type="button"
            onClick={() => onSubmit(e.q)}
            title={e.what}
            className="rounded-md border border-zinc-800 bg-zinc-900 px-2 py-0.5 font-mono text-zinc-400 transition hover:border-zinc-700 hover:text-zinc-200"
          >
            {e.q}
          </button>
        ))}
      </div>
    </form>
  );
}
