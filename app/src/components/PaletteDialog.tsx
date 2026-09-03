/**
 * The palette's dialog body — lazy-loaded by `CommandPalette` the first time it opens, so
 * the entry chunk carries only the button and the hotkey.
 */

import { type KeyboardEvent, useEffect, useId, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import { railStore, useRailOpen } from '../lib/rail';
import { sectionRegistry } from '../lib/sections';
import { themeStore, useTheme } from '../lib/theme';
import { cx } from '../lib/ui';
import { useJourney } from './journeyContext';

interface Item {
  id: string;
  group: 'Pages' | 'On this page' | 'Actions';
  label: string;
  hint?: string;
  run: () => void;
}

function useItems(close: () => void): Item[] {
  const groups = useJourney();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const theme = useTheme();
  const railOpen = useRailOpen();
  return useMemo(() => {
    const pages: Item[] = groups.flatMap((g) =>
      g.pages.map((p) => ({
        id: `page:${p.to}`,
        group: 'Pages' as const,
        label: p.title,
        hint: `${g.label} · ${p.label}`,
        run: () => {
          navigate(p.to);
          close();
        },
      })),
    );
    const sections: Item[] = sectionRegistry.list().map((s) => ({
      id: `section:${s.id}`,
      group: 'On this page' as const,
      label: s.title,
      run: () => {
        close();
        s.el.scrollIntoView({ block: 'start' });
        window.history.replaceState(null, '', `#${s.id}`);
      },
    }));
    const actions: Item[] = [
      {
        id: 'action:home',
        group: 'Actions',
        label: 'Go to the overview',
        run: () => {
          navigate('/');
          close();
        },
      },
      {
        id: 'action:theme',
        group: 'Actions',
        label: theme === 'light' ? 'Switch to the dark theme' : 'Switch to the light theme',
        run: () => {
          themeStore.toggle();
          close();
        },
      },
      {
        id: 'action:rail',
        group: 'Actions',
        label: railOpen ? 'Hide the section rail' : 'Show the section rail',
        run: () => {
          railStore.toggle();
          close();
        },
      },
      {
        id: 'action:top',
        group: 'Actions',
        label: 'Back to top',
        run: () => {
          window.scrollTo({ top: 0 });
          close();
        },
      },
    ];
    return [...sections, ...pages, ...actions];
    // pathname is a dependency on purpose: the section list changes with the page.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [groups, navigate, theme, railOpen, close, pathname]);
}

function matches(item: Item, q: string): boolean {
  if (!q) return true;
  const hay = `${item.label} ${item.hint ?? ''} ${item.group}`.toLowerCase();
  return q
    .toLowerCase()
    .split(/\s+/)
    .every((w) => hay.includes(w));
}

export default function PaletteDialog({ close }: { close: () => void }) {
  const [q, setQ] = useState('');
  const [cursor, setCursor] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const listId = useId();
  const items = useItems(close);
  const shown = useMemo(() => items.filter((i) => matches(i, q)), [items, q]);
  const current = shown[Math.min(cursor, Math.max(shown.length - 1, 0))];

  useEffect(() => {
    input.current?.focus();
  }, []);

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setCursor((c) => Math.min(c + 1, shown.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setCursor((c) => Math.max(c - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      current?.run();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      close();
    }
  }

  let lastGroup: Item['group'] | null = null;

  return (
    <div
      role="presentation"
      className="fixed inset-0 z-50 flex items-start justify-center bg-chrome-950/70 px-4 pt-[12vh] backdrop-blur-sm"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) close();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Jump to"
        className="w-full max-w-xl rounded-card border border-line-strong bg-chrome-950 shadow-2xl"
      >
        <input
          ref={input}
          role="combobox"
          aria-expanded="true"
          aria-controls={listId}
          aria-activedescendant={current ? `${listId}-${current.id}` : undefined}
          aria-autocomplete="list"
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setCursor(0);
          }}
          onKeyDown={onKeyDown}
          placeholder="Type a page, a section or an action"
          spellCheck={false}
          className="w-full border-b border-line bg-transparent px-4 py-3 text-sm text-chrome-100 placeholder:text-chrome-500 focus:outline-none"
        />
        <ul
          id={listId}
          role="listbox"
          aria-label="Results"
          className="max-h-[50vh] overflow-y-auto py-2"
        >
          {shown.length === 0 && (
            <li className="px-4 py-3 text-sm text-chrome-500">
              Nothing matches. Try a page name or a word from a section title.
            </li>
          )}
          {shown.map((item) => {
            const heading = item.group !== lastGroup ? item.group : null;
            lastGroup = item.group;
            const on = item.id === current?.id;
            return (
              <li key={item.id} role="presentation">
                {heading && (
                  <div className="px-4 pt-2 pb-1 text-micro font-medium text-chrome-500">
                    {heading}
                  </div>
                )}
                <div
                  id={`${listId}-${item.id}`}
                  role="option"
                  aria-selected={on}
                  tabIndex={-1}
                  onMouseEnter={() => setCursor(shown.indexOf(item))}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={item.run}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') item.run();
                  }}
                  className={cx(
                    'flex cursor-pointer items-baseline justify-between gap-4 px-4 py-1.5 text-sm',
                    on ? 'bg-machinery-950/50 text-chrome-50' : 'text-chrome-200',
                  )}
                >
                  <span>{item.label}</span>
                  {item.hint && (
                    <span className="shrink-0 text-xs text-chrome-500">{item.hint}</span>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
        <div className="flex gap-4 border-t border-line px-4 py-2 text-micro text-chrome-500">
          <span>Up and down to move</span>
          <span>Enter to go</span>
          <span>Esc to close</span>
        </div>
      </div>
    </div>
  );
}
