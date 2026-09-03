/**
 * The two wider export scopes, in the header where they apply to whatever is on screen.
 *
 * "Export page" is whatever the mounted exhibits registered; pages are lazy routes, so the
 * count follows navigation on its own. "Export case" ignores the screen entirely and fetches
 * every parameter-free endpoint — the one export that can plausibly outgrow a chat window,
 * which is why its size is always reported back.
 */

import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import { useLocation } from 'react-router-dom';

import { dateStamp, downloadExport, pageSlug } from '../lib/aiExport/download';
import { exhibitBundle } from '../lib/aiExport/markdown';
import { exhibitRegistry } from '../lib/aiExport/registry';
import { buildWholeCaseBundle } from '../lib/aiExport/wholeCase';

const BTN =
  'rounded-control border border-line bg-chrome-900 px-2 py-1 text-micro text-chrome-400 transition ' +
  'enabled:hover:border-line-strong enabled:hover:text-chrome-200 disabled:opacity-40 focus:outline-none ' +
  'focus-visible:border-machinery-700';

function failed(said: string): boolean {
  return said.startsWith('export failed') || said.startsWith('clipboard blocked');
}

export function AiExport() {
  const pathname = useLocation().pathname;
  const version = useSyncExternalStore(exhibitRegistry.subscribe, exhibitRegistry.version);
  const onPage = useMemo(() => {
    // `version` is read, not just listed: the registry is a mutable store, so a bumped
    // version is the only signal that its contents changed. Dropping the dependency
    // would freeze this list at whatever was mounted when the route last changed.
    void version;
    return exhibitRegistry.getByPage(pathname);
  }, [pathname, version]);

  const [said, setSaid] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const timer = useRef<number | null>(null);

  useEffect(() => () => window.clearTimeout(timer.current ?? undefined), []);

  function report(outcome: string) {
    setSaid(outcome);
    window.clearTimeout(timer.current ?? undefined);
    timer.current = window.setTimeout(() => setSaid(null), 6000);
  }

  function exportPage() {
    const scope = `page ${pathname} — ${onPage.length} exhibit${onPage.length === 1 ? '' : 's'}`;
    report(
      downloadExport(
        `mva-case-${pageSlug(pathname)}-${dateStamp()}.md`,
        exhibitBundle(scope, onPage),
      ),
    );
  }

  async function exportCase() {
    setBusy(true);
    try {
      const bundle = await buildWholeCaseBundle();
      report(downloadExport(`mva-case-full-${dateStamp()}.md`, bundle));
    } catch (err) {
      report(`export failed: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex items-center gap-2">
      {said && (
        <span className={`text-micro ${failed(said) ? 'text-broken-400' : 'text-good-400'}`}>
          {said}
        </span>
      )}
      {onPage.length > 0 && (
        <button
          type="button"
          className={BTN}
          onClick={exportPage}
          title="Download every exhibit on this page — legends, provenance and underlying rows — as one Markdown file for an AI chat."
        >
          export page ({onPage.length})
        </button>
      )}
      <button
        type="button"
        className={BTN}
        onClick={exportCase}
        disabled={busy}
        title="Download every dataset in the app, plus the warehouse field dictionary, as one Markdown file for an AI chat."
      >
        {busy ? 'building…' : 'export case'}
      </button>
    </div>
  );
}
