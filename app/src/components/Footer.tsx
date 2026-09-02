/**
 * App footer: what this app is, the live dependency-status summary, and links to the
 * in-app pages and repo docs a reader would want next. Mounted once by AppShell,
 * replacing the previous inline `<footer>` paragraph — see src/app/AppShell.tsx.
 *
 * Degrades on purpose: the status endpoint (`GET /api/health/dependencies`, contract
 * in scratchpad/health-contract.md) does not exist yet on the Python side, so while
 * the query is pending, errors, or 404s, this renders the footer's static content plus
 * a neutral "status unknown" chip instead of a spinner or a crash.
 */
import { Link } from 'react-router-dom';

import { useHealthDependencies } from '../api/hooks';
import { C } from '../lib/palette';
import { BADGE, cx } from '../lib/ui';
import { type HealthTone, summarizeHealth } from './footerHealth';

const DOT_COLOR: Record<HealthTone, string> = {
  good: C.good,
  decision: C.decision,
  broken: C.broken,
  neutral: C.absent,
};

/** The status badge/entry-point into the Status page. Not exported: keeps this module
 * a components-only export for react-refresh, and it has no use outside this file. */
function DependencyStatusLink() {
  const q = useHealthDependencies();
  const { tone, phrase } = summarizeHealth(q.data?.data.overall, q.data?.data.checks);
  return (
    <Link
      to="/status"
      aria-label={`Dependency status: ${phrase}. Open the Status page.`}
      className={cx(
        'inline-flex w-fit items-center gap-1.5 rounded border px-2 py-1 text-[11px] font-medium transition-opacity hover:opacity-80',
        BADGE[tone],
      )}
    >
      <span
        aria-hidden="true"
        className="h-1.5 w-1.5 rounded-full"
        style={{ backgroundColor: DOT_COLOR[tone] }}
      />
      {phrase}
    </Link>
  );
}

const IN_APP_LINKS = [
  { to: '/status', label: 'Status' },
  { to: '/catalog', label: 'Catalog' },
  { to: '/provenance', label: 'Provenance' },
  { to: '/science', label: 'Science' },
];

// Repo-relative filesystem paths, not app routes — this SPA has no route for them.
// They are a pointer to the source-controlled docs a reader would open next, resolved
// relative to `app/` (this app's own directory) up to the repo-root `docs/` folder.
const REPO_DOCS = [
  { href: '../docs/README.md', label: 'Docs index' },
  { href: '../docs/dictionary.md', label: 'Dictionary' },
];

export function Footer() {
  return (
    <footer className="border-t border-chrome-800">
      <div className="mx-auto flex max-w-[1600px] flex-col gap-6 px-5 py-6 text-[11px] leading-relaxed text-chrome-500 sm:flex-row sm:flex-wrap sm:justify-between">
        <div className="max-w-sm space-y-2">
          <p className="font-medium text-chrome-400">MVA Case Explorer</p>
          <p>
            Understanding tool for one whole-genome case. No genomic coordinate is committed to this
            repository: the locus explorer shows real positions only when served by the live API,
            and its fixture uses a synthetic counter.
          </p>
        </div>

        <div className="space-y-2">
          <p className="uppercase tracking-wide text-chrome-600">Dependency status</p>
          <DependencyStatusLink />
        </div>

        <nav aria-label="More pages" className="space-y-2">
          <p className="uppercase tracking-wide text-chrome-600">Explore</p>
          <ul className="space-y-1">
            {IN_APP_LINKS.map((item) => (
              <li key={item.to}>
                <Link to={item.to} className="hover:text-chrome-300">
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>

        <nav aria-label="Repository documentation" className="space-y-2">
          <p className="uppercase tracking-wide text-chrome-600">Repo docs</p>
          <ul className="space-y-1">
            {REPO_DOCS.map((doc) => (
              <li key={doc.href}>
                <a href={doc.href} className="hover:text-chrome-300">
                  {doc.label}
                </a>
              </li>
            ))}
          </ul>
        </nav>
      </div>
    </footer>
  );
}
