/**
 * "On this page" — the section rail. Lists every mounted `Section` (from the section
 * registry) in document order and marks the one in view, so a long page such as Panel is
 * navigable without scrolling blind. At `xl` and up it is a sticky rail beside the content;
 * below that the same list is a compact "Jump to" select under the page header.
 */

import { useEffect, useState, useSyncExternalStore } from 'react';

import { type SectionEntry, sectionRegistry } from '../lib/sections';
import { CONTROL, cx } from '../lib/ui';

function useSections(): SectionEntry[] {
  const version = useSyncExternalStore(sectionRegistry.subscribe, sectionRegistry.version);
  void version; // read, so a registry change re-runs the list
  return sectionRegistry.list();
}

/** The id of the section currently under the header, tracked with an IntersectionObserver. */
function useActiveSection(sections: SectionEntry[]): string | null {
  const [active, setActive] = useState<string | null>(null);
  useEffect(() => {
    if (sections.length === 0 || typeof IntersectionObserver === 'undefined') return;
    const visible = new Set<string>();
    const pick = () => {
      const first = sections.find((s) => visible.has(s.id));
      if (first) setActive(first.id);
    };
    const io = new IntersectionObserver(
      (records) => {
        for (const r of records) {
          const id = (r.target as HTMLElement).id;
          if (r.isIntersecting) visible.add(id);
          else visible.delete(id);
        }
        pick();
      },
      // The band just under the sticky header: a section is "current" while any of it
      // crosses that band, and the top-most such section wins.
      { rootMargin: '-112px 0px -55% 0px', threshold: 0 },
    );
    sections.forEach((s) => io.observe(s.el));
    return () => io.disconnect();
  }, [sections]);
  return active;
}

function jump(entry: SectionEntry) {
  entry.el.scrollIntoView({ block: 'start' });
  window.history.replaceState(null, '', `#${entry.id}`);
}

export function OnThisPage() {
  const sections = useSections();
  const active = useActiveSection(sections);
  if (sections.length < 2) return null;
  return (
    <nav aria-label="On this page" className="hidden xl:block">
      <p className="text-xs font-medium text-chrome-400">On this page</p>
      <ol className="mt-2 border-l border-line">
        {sections.map((s) => {
          const on = s.id === active;
          return (
            <li key={s.id}>
              <a
                href={`#${s.id}`}
                aria-current={on ? 'location' : undefined}
                onClick={(e) => {
                  e.preventDefault();
                  jump(s);
                }}
                className={cx(
                  '-ml-px block border-l-2 py-1 pl-3 text-xs leading-snug transition',
                  on
                    ? 'border-machinery-500 text-chrome-50'
                    : 'border-transparent text-chrome-400 hover:border-line-strong hover:text-chrome-200',
                )}
              >
                {s.title}
              </a>
            </li>
          );
        })}
      </ol>
      <a
        href="#top"
        onClick={(e) => {
          e.preventDefault();
          window.scrollTo({ top: 0 });
        }}
        className="mt-3 block text-xs text-chrome-500 hover:text-chrome-300"
      >
        Back to top
      </a>
    </nav>
  );
}

/** The same list as a select, for viewports without room for the rail. */
export function JumpToSection() {
  const sections = useSections();
  if (sections.length < 2) return null;
  return (
    <label className="flex items-center gap-2 text-xs text-chrome-500 xl:hidden">
      Jump to
      <select
        aria-label="Jump to section"
        value=""
        onChange={(e) => {
          const target = sections.find((s) => s.id === e.target.value);
          if (target) jump(target);
        }}
        className={cx(CONTROL, 'text-chrome-200')}
      >
        <option value="" disabled>
          a section on this page
        </option>
        {sections.map((s) => (
          <option key={s.id} value={s.id}>
            {s.title}
          </option>
        ))}
      </select>
    </label>
  );
}
