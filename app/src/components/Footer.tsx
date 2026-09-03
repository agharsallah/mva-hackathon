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
import { useJourney } from './journeyContext';

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
        'inline-flex w-fit items-center gap-2 rounded-pill border px-2 py-1 text-micro font-medium transition-opacity hover:opacity-80',
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

// Repo-relative filesystem paths, not app routes — this SPA has no route for them.
// They are a pointer to the source-controlled docs a reader would open next, resolved
// relative to `app/` (this app's own directory) up to the repo-root `docs/` folder.
const REPO_DOCS = [
  { href: '../docs/README.md', label: 'Docs index' },
  { href: '../docs/dictionary.md', label: 'Dictionary' },
];

/**
 * The four questions with their pages — the same manifest the header reads, so the footer
 * is a sitemap rather than a second, hand-picked nav. Empty outside the shell.
 */
function SectionIndex() {
  const groups = useJourney();
  if (groups.length === 0) return null;
  return (
    <nav aria-label="All pages" className="flex flex-wrap gap-8">
      {groups.map((g) => (
        <div key={g.id} className="space-y-2">
          <p className="font-medium text-chrome-400" title={g.question}>
            {g.label}
          </p>
          <ul className="space-y-1">
            {g.pages.map((p) => (
              <li key={p.to}>
                <Link to={p.to} onPointerEnter={p.preload} className="hover:text-chrome-300">
                  {p.label}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  );
}

export function Footer() {
  return (
    <footer className="border-t border-line">
      <div className="mx-auto flex max-w-[1600px] flex-col gap-6 px-5 py-6 text-micro leading-relaxed text-chrome-500 sm:flex-row sm:flex-wrap sm:justify-between">
        <div className="max-w-sm space-y-2">
          <p className="font-medium text-chrome-400">MVA Case Explorer</p>
          <p>
            Understanding tool for one whole-genome case. No genomic coordinate is committed to this
            repository: the locus explorer shows real positions only when served by the live API,
            and its fixture uses a synthetic counter.
          </p>
        </div>

        <div className="space-y-2">
          <p className="font-medium text-chrome-400">Dependency status</p>
          <DependencyStatusLink />
        </div>

        <SectionIndex />

        <nav aria-label="Repository documentation" className="space-y-2">
          <p className="font-medium text-chrome-400">Repo docs</p>
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
