/**
 * One chapter's blocks, in the order the markdown has them.
 *
 * Every HTML string here was produced at build time by `tools/gen-dictionary.mjs` from
 * `docs/dictionary.md` — a file in this repository, rendered through remark with raw HTML
 * disabled. That is why `dangerouslySetInnerHTML` is acceptable on this page and nowhere
 * else: no user or API text ever reaches these nodes.
 */

import type { ReactNode } from 'react';

import { type Block, type EntryBlock, figureUrl } from '../../lib/dictionary';
import { Mermaid } from './Mermaid';

/** Aliases worth a chip: short alternate names, not a bracketed list of seven databases. */
function chipAliases(entry: EntryBlock): string[] {
  return entry.aliases.filter((a) => a.length <= 24 && a !== entry.term).slice(0, 4);
}

/** The diagram's accessible name: its legend as plain text, or a generic label. */
function diagramLabel(legendHtml?: string): string {
  const plain = legendHtml?.replace(/<[^>]+>/g, '').trim();
  return plain ? `Diagram — ${plain}` : 'Diagram';
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

export function EntryCard({ entry, aside }: { entry: EntryBlock; aside?: ReactNode }) {
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
            className="rounded-pill border border-line px-1.5 font-mono text-micro text-chrome-500"
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
      </div>
      <div className="learn-prose mt-1" dangerouslySetInnerHTML={{ __html: entry.html }} />
      {entry.exampleHtml && (
        <div
          className="learn-prose learn-example mt-1.5 border-l-2 border-line-soft pl-3"
          dangerouslySetInnerHTML={{ __html: entry.exampleHtml }}
        />
      )}
      {aside}
    </article>
  );
}

export function BlockView({
  block,
  aside,
}: {
  block: Block;
  aside?: (e: EntryBlock) => ReactNode;
}) {
  switch (block.kind) {
    case 'entry':
      return <EntryCard entry={block} aside={aside?.(block)} />;
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
              <span className="text-micro text-chrome-500">missing figure {block.file}</span>
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
}: {
  blocks: Block[];
  aside?: (e: EntryBlock) => ReactNode;
}) {
  return (
    <div className="space-y-5">
      {blocks.map((b, i) => (
        <BlockView key={b.kind === 'entry' ? b.slug : `${b.kind}-${i}`} block={b} aside={aside} />
      ))}
    </div>
  );
}
