/**
 * The page-wide export scope, in the header where it applies to whatever is on screen.
 *
 * "Export page" is whatever the mounted exhibits registered; pages are lazy routes, so the
 * count follows navigation on its own.
 */

import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import { useLocation } from 'react-router-dom';

import { dateStamp, downloadExport, pageSlug } from '../lib/aiExport/download';
import { exhibitBundle } from '../lib/aiExport/markdown';
import { exhibitRegistry } from '../lib/aiExport/registry';

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
        `export-${pageSlug(pathname)}-${dateStamp()}.md`,
        exhibitBundle(scope, onPage),
      ),
    );
  }

  return (
    <div className="flex items-center gap-2">
      {said && (
        <span className={`text-micro ${failed(said) ? 'text-broken-300' : 'text-good-300'}`}>
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
    </div>
  );
}
