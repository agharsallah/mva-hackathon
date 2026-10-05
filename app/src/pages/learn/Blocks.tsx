/**
 * One block of the generated dictionary → one element.
 *
 * The generator (`app/tools/gen-dictionary.mjs`) turns `docs/dictionary.md` into chapters of
 * blocks; this file is the only place that knows how each kind is drawn. A new block kind in
 * `src/lib/dictionary/index.ts` fails to compile here until it is given a rendering, which is
 * what keeps the page honest about what the markdown actually contains.
 *
 * HTML comes from the repository's own markdown, generated at build time — never from a
 * request — so `dangerouslySetInnerHTML` carries no untrusted input.
 */

import { lazy, Suspense } from 'react';

import type { Block, EntryBlock } from '../../lib/dictionary';
import { figureUrl } from '../../lib/dictionary';
import { cx } from '../../lib/ui';

const Mermaid = lazy(() => import('./Mermaid'));

const PROSE =
  'max-w-[80ch] font-serif text-reading leading-relaxed text-chrome-300 ' +
  '[&_a]:text-machinery-300 [&_a:hover]:text-machinery-200 ' +
  '[&_code]:font-mono [&_code]:text-micro [&_code]:text-chrome-200 ' +
  '[&_li]:mt-1 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5 ' +
  '[&_table]:w-full [&_table]:text-xs [&_th]:text-left [&_th]:font-medium [&_th]:text-chrome-300 ' +
  '[&_td]:border-t [&_td]:border-line-soft [&_td]:py-1 [&_td]:pr-3';

function Legend({ html }: { html?: string }) {
  if (!html) return null;
  return (
    <p
      className="mt-2 text-xs leading-relaxed text-chrome-400 [&_strong]:text-chrome-300"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

/** The metadata footer: where the term came from, what it leans on, when it first appeared. */
function EntryMeta({ entry }: { entry: EntryBlock }) {
  const related = entry.related ?? [];
  const see = entry.see ?? [];
  if (!entry.source && related.length === 0 && see.length === 0 && !entry.firstSeen) return null;
  return (
    <p className="mt-2 flex flex-wrap items-baseline gap-x-3 gap-y-1 text-micro text-chrome-500">
      {entry.firstSeen && <span>first seen {entry.firstSeen}</span>}
      {entry.source && <span className="font-mono">{entry.source}</span>}
      {related.length > 0 && (
        <span>
          related:{' '}
          {related.map((slug, i) => (
            <span key={slug}>
              {i > 0 && ', '}
              <a href={`#${slug}`} className="text-machinery-300 hover:text-machinery-200">
                {slug}
              </a>
            </span>
          ))}
        </span>
      )}
      {see.length > 0 && (
        <span
          className="[&_a]:text-machinery-300"
          dangerouslySetInnerHTML={{ __html: see.join(' · ') }}
        />
      )}
    </p>
  );
}

function Entry({ entry }: { entry: EntryBlock }) {
  return (
    <article id={entry.slug} className="scroll-mt-28 border-l-2 border-line-soft pl-4">
      <h4 className="text-sm font-semibold tracking-tight text-chrome-100">{entry.term}</h4>
      <div className={cx(PROSE, 'mt-1')} dangerouslySetInnerHTML={{ __html: entry.html }} />
      {entry.exampleHtml && (
        <div
          className="mt-1 max-w-[80ch] text-xs leading-relaxed text-chrome-400 italic [&_code]:font-mono"
          dangerouslySetInnerHTML={{ __html: entry.exampleHtml }}
        />
      )}
      <EntryMeta entry={entry} />
    </article>
  );
}

export function DictionaryBlock({ block }: { block: Block }) {
  switch (block.kind) {
    case 'entry':
      return <Entry entry={block} />;
    case 'subheading':
      return (
        <h3
          id={block.id}
          className="scroll-mt-28 pt-2 text-sm font-semibold tracking-tight text-chrome-200"
        >
          {block.text}
        </h3>
      );
    case 'prose':
      return <div className={PROSE} dangerouslySetInnerHTML={{ __html: block.html }} />;
    case 'figure': {
      const url = figureUrl(block.file);
      if (!url) return null;
      return (
        <figure className="rounded-card border border-line bg-panel p-4">
          <img src={url} alt={block.alt} className="w-full" />
          <figcaption>
            <Legend html={block.legendHtml} />
          </figcaption>
        </figure>
      );
    }
    case 'mermaid':
      return (
        <figure className="rounded-card border border-line bg-panel p-4">
          <Suspense fallback={<p className="text-micro text-chrome-500">drawing the diagram…</p>}>
            <Mermaid source={block.source} />
          </Suspense>
          <figcaption>
            <Legend html={block.legendHtml} />
          </figcaption>
        </figure>
      );
    case 'code':
      return (
        <figure className="rounded-card border border-line bg-panel p-4">
          <pre className="overflow-x-auto font-mono text-micro leading-relaxed text-chrome-300">
            {block.text}
          </pre>
          <figcaption>
            <Legend html={block.legendHtml} />
          </figcaption>
        </figure>
      );
  }
}
