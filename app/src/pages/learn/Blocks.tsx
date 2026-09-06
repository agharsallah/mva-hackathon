/**
 * One chapter's blocks, in the order the markdown has them.
 *
 * Every HTML string here was produced at build time by `tools/gen-dictionary.mjs` from
 * `docs/dictionary.md` — a file in this repository, rendered through remark with raw HTML
 * disabled. That is why `dangerouslySetInnerHTML` is acceptable on this page and nowhere
 * else: no user or API text ever reaches these nodes.
 */

import type { ReactNode } from 'react';

import {
  type Block,
  type EntryBlock,
  figureUrl,
  REPO_BLOB,
  termOfSlug,
} from '../../lib/dictionary';
import { Mermaid } from './Mermaid';
import { Star } from './Starred';
import type { StoredSet } from './storedSet';

/** Aliases worth a chip: short alternate names, not a bracketed list of seven databases. */
function chipAliases(entry: EntryBlock): string[] {
  return entry.aliases.filter((a) => a.length <= 24 && a !== entry.term).slice(0, 4);
}

/** The diagram's accessible name: its legend as plain text, or a generic label. */
function diagramLabel(legendHtml?: string): string {
  const plain = legendHtml?.replace(/<[^>]+>/g, '').trim();
  return plain ? `Diagram — ${plain}` : 'Diagram';
}

/** A `source:` that names a file in this repository opens on GitHub; anything else is text. */
function sourceHref(source: string): string | undefined {
  return /^[\w.@-]+\/\S+$/.test(source) ? REPO_BLOB + source : undefined;
}

/** What to call a `see:` target: the term behind an anchor, else the file at the end of a URL. */
function seeLabel(href: string): string {
  if (href.startsWith('#')) return termOfSlug(href.slice(1)) ?? href.slice(1).replace(/-/g, ' ');
  const tail = href.split('#')[0].replace(/\/+$/, '').split('/').pop();
  return tail || href;
}

/**
 * The metadata half of an entry's `*Context:*` line — where the term is used, the file that
 * owns it, the entries it leans on, what to look at, and the day it entered the dictionary.
 *
 * Deliberately quiet: one small row under the definition, so a reader chasing provenance
 * finds it and a reader learning the word never has to step over it.
 */
function Meta({ entry }: { entry: EntryBlock }) {
  const { context, source, related, see, firstSeen } = entry;
  if (!context && !source && !related?.length && !see?.length && !firstSeen) return null;
  const href = source ? sourceHref(source) : undefined;
  return (
    <footer className="mt-1.5 text-micro leading-relaxed text-chrome-400">
      {context && (
        <div
          className="mb-0.5 italic [&_a]:underline [&_p]:inline"
          dangerouslySetInnerHTML={{ __html: context }}
        />
      )}
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        {firstSeen && (
          <span>
            first seen <time dateTime={firstSeen}>{firstSeen}</time>
            {entry.firstSeenProvisional && (
              <span title="written today; not committed yet"> (new)</span>
            )}
          </span>
        )}
        {source && (
          <span>
            source:{' '}
            {href ? (
              <a href={href} className="font-mono hover:text-chrome-300" rel="noreferrer">
                {source}
              </a>
            ) : (
              <span className="font-mono">{source}</span>
            )}
          </span>
        )}
        {related?.length ? (
          <span className="flex flex-wrap items-baseline gap-1">
            related:
            {related.map((slug) => (
              <a
                key={slug}
                href={`#${slug}`}
                className="rounded-pill border border-line px-1.5 transition hover:border-chrome-600 hover:text-chrome-300"
              >
                {termOfSlug(slug) ?? slug}
              </a>
            ))}
          </span>
        ) : null}
        {see?.length ? (
          <span className="flex flex-wrap items-baseline gap-x-2">
            see:
            {see.map((target) => (
              <a key={target} href={target} className="underline hover:text-chrome-300">
                {seeLabel(target)}
              </a>
            ))}
          </span>
        ) : null}
      </div>
    </footer>
  );
}

function Legend({ html }: { html?: string }) {
  if (!html) return null;
  return (
    <figcaption className="learn-legend mt-2 text-xs leading-relaxed text-chrome-400">
      <span className="mr-2 font-semibold text-chrome-300">Legend</span>
      <span dangerouslySetInnerHTML={{ __html: html }} />
    </figcaption>
  );
}

export function EntryCard({
  entry,
  aside,
  stars,
}: {
  entry: EntryBlock;
  aside?: ReactNode;
  /** The reader's starred set; the card shows a star to add or remove itself. */
  stars?: StoredSet;
}) {
  const starred = stars?.has(entry.slug) ?? false;
  return (
    <article
      id={entry.slug}
      className="learn-entry scroll-mt-28 border-l-2 border-line py-0.5 pl-4"
      aria-labelledby={`${entry.slug}-term`}
    >
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <h3
          id={`${entry.slug}-term`}
          className="font-serif text-heading font-medium tracking-tight text-chrome-50"
        >
          {entry.term}
        </h3>
        {chipAliases(entry).map((a) => (
          <span
            key={a}
            className="rounded-pill border border-line px-1.5 font-mono text-micro text-chrome-400"
          >
            {a}
          </span>
        ))}
        <a
          href={`#${entry.slug}`}
          aria-label={`Link to ${entry.term}`}
          className="ml-1 text-micro text-chrome-600 transition hover:text-chrome-300"
        >
          #
        </a>
        {stars && (
          <button
            type="button"
            onClick={() => stars.toggle(entry.slug)}
            aria-pressed={starred}
            aria-label={`${starred ? 'Unstar' : 'Star'} ${entry.term}`}
            title={starred ? 'Remove from starred' : 'Star this definition to come back to it'}
            className="rounded-pill px-1 text-sm leading-none transition hover:bg-chrome-900 focus:outline-none focus-visible:ring-1 focus-visible:ring-focus"
          >
            <Star on={starred} />
          </button>
        )}
      </div>
      <div className="learn-prose mt-1" dangerouslySetInnerHTML={{ __html: entry.html }} />
      {entry.exampleHtml && (
        <div
          className="learn-prose learn-example mt-1.5 border-l-2 border-line-soft pl-3"
          dangerouslySetInnerHTML={{ __html: entry.exampleHtml }}
        />
      )}
      <Meta entry={entry} />
      {aside}
    </article>
  );
}

export function BlockView({
  block,
  aside,
  stars,
}: {
  block: Block;
  aside?: (e: EntryBlock) => ReactNode;
  stars?: StoredSet;
}) {
  switch (block.kind) {
    case 'entry':
      return <EntryCard entry={block} aside={aside?.(block)} stars={stars} />;
    case 'subheading':
      return (
        <h3
          id={block.id}
          className="scroll-mt-28 pt-2 font-serif text-heading font-medium text-chrome-100"
        >
          {block.text}
        </h3>
      );
    case 'prose':
      return <div className="learn-prose" dangerouslySetInnerHTML={{ __html: block.html }} />;
    case 'figure': {
      const src = figureUrl(block.file);
      return (
        <figure className="max-w-[820px]">
          <div className="learn-paper">
            {src ? (
              <img src={src} alt={block.alt} loading="lazy" className="mx-auto block" />
            ) : (
              <span className="text-micro text-chrome-400">missing figure {block.file}</span>
            )}
          </div>
          <Legend html={block.legendHtml} />
        </figure>
      );
    }
    case 'mermaid':
      return (
        <figure className="max-w-[820px]">
          <Mermaid source={block.source} label={diagramLabel(block.legendHtml)} />
          <Legend html={block.legendHtml} />
        </figure>
      );
    case 'code':
      return (
        <figure className="max-w-[820px]">
          <pre className="learn-code">{block.text}</pre>
          <Legend html={block.legendHtml} />
        </figure>
      );
  }
}

export function Blocks({
  blocks,
  aside,
  stars,
}: {
  blocks: Block[];
  aside?: (e: EntryBlock) => ReactNode;
  stars?: StoredSet;
}) {
  return (
    <div className="space-y-5">
      {blocks.map((b, i) => (
        <BlockView
          key={b.kind === 'entry' ? b.slug : `${b.kind}-${i}`}
          block={b}
          aside={aside}
          stars={stars}
        />
      ))}
    </div>
  );
}
