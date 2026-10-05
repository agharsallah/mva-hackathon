/**
 * The dictionary, as a course.
 *
 * `docs/dictionary.md` is the one glossary in the repository and it is never copied: this
 * page renders what `app/tools/gen-dictionary.mjs` generated from it. Whatever chapters the
 * markdown happens to contain is what appears here — the page knows block kinds, never terms.
 *
 * The JSON is large, so it is loaded on demand (`loadDictionary()` is a dynamic import) and
 * this page is itself a lazy route: a reader who never opens it downloads none of it.
 */

import { useEffect, useMemo, useState } from 'react';

import { EmptyState, Section, Skeleton, TextFilter } from '../components';
import type { Chapter, Dictionary } from '../lib/dictionary';
import { entriesOf, loadDictionary } from '../lib/dictionary';
import { cx } from '../lib/ui';
import { DictionaryBlock } from './learn/Blocks';

/** A chapter keeps only the blocks that match, plus every heading, so the shape stays readable. */
function filterChapter(chapter: Chapter, needle: string): Chapter | null {
  if (!needle) return chapter;
  const blocks = chapter.blocks.filter((b) => {
    if (b.kind === 'entry') {
      return (
        b.term.toLowerCase().includes(needle) ||
        b.aliases.some((a) => a.toLowerCase().includes(needle))
      );
    }
    return false;
  });
  if (blocks.length === 0) return null;
  return { ...chapter, blocks };
}

function ChapterRail({ chapters, active }: { chapters: Chapter[]; active: string | null }) {
  if (chapters.length === 0) return null;
  return (
    <nav
      aria-label="Chapters"
      className="sticky top-28 hidden max-h-[80vh] overflow-y-auto xl:block"
    >
      <p className="mb-2 text-micro font-medium tracking-wide text-chrome-500 uppercase">
        Chapters
      </p>
      <ol className="space-y-1">
        {chapters.map((c) => (
          <li key={c.id}>
            <a
              href={`#${c.id}`}
              aria-current={active === c.id ? 'true' : undefined}
              className={cx(
                'block rounded-control px-2 py-1 text-xs transition',
                active === c.id
                  ? 'bg-chrome-900 font-medium text-chrome-100'
                  : 'text-chrome-400 hover:bg-chrome-900 hover:text-chrome-200',
              )}
            >
              <span className="mr-2 text-chrome-500">{c.number}</span>
              {c.title}
            </a>
          </li>
        ))}
      </ol>
    </nav>
  );
}

export default function Learn() {
  const [dictionary, setDictionary] = useState<Dictionary | null>(null);
  const [failed, setFailed] = useState(false);
  const [query, setQuery] = useState('');

  useEffect(() => {
    let cancelled = false;
    void loadDictionary().then(
      (d) => !cancelled && setDictionary(d),
      () => !cancelled && setFailed(true),
    );
    return () => {
      cancelled = true;
    };
  }, []);

  const needle = query.trim().toLowerCase();
  const chapters = useMemo(() => {
    if (!dictionary) return [];
    return dictionary.chapters
      .map((c) => filterChapter(c, needle))
      .filter((c): c is Chapter => c !== null);
  }, [dictionary, needle]);

  if (failed) {
    return (
      <EmptyState tone="broken" title="The dictionary could not be loaded">
        Run <code className="font-mono">pnpm dictionary</code> in{' '}
        <code className="font-mono">app/</code> to regenerate it from{' '}
        <code className="font-mono">docs/dictionary.md</code>.
      </EmptyState>
    );
  }
  if (!dictionary) return <Skeleton height={480} framed label="Loading the dictionary" />;

  const entryCount = entriesOf(dictionary).length;
  const active = chapters[0]?.id ?? null;

  return (
    <div className="xl:grid xl:grid-cols-[14rem_minmax(0,1fr)] xl:items-start xl:gap-10">
      <ChapterRail chapters={chapters} active={active} />

      <div className="min-w-0 space-y-8">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-chrome-400">
            {dictionary.counts.chapters} chapters · {entryCount} definitions · generated from{' '}
            <code className="font-mono text-chrome-300">{dictionary.source}</code>
          </p>
          <TextFilter value={query} onChange={setQuery} placeholder="filter definitions" />
        </div>

        {chapters.length === 0 ? (
          <EmptyState title={`Nothing matches “${query}”`}>
            Clear the filter to read the dictionary in order.
          </EmptyState>
        ) : (
          chapters.map((chapter) => (
            <Section key={chapter.id} id={chapter.id} title={`${chapter.number}. ${chapter.title}`}>
              <div className="space-y-4">
                {chapter.blocks.map((block, i) => (
                  <DictionaryBlock key={i} block={block} />
                ))}
              </div>
            </Section>
          ))
        )}
      </div>
    </div>
  );
}
