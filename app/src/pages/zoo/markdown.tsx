import { type ReactNode } from 'react';

/**
 * A small, safe Markdown renderer for the reports the API serves.
 *
 * Why not `dangerouslySetInnerHTML`: the dictionary's HTML is produced at build time from a
 * file in this repository, which is why `pages/learn/Blocks.tsx` may inject it. A zoo report
 * arrives over the network at runtime, so it is treated as data — parsed into React elements,
 * never into HTML. Nothing here can execute a tag.
 *
 * It handles what the generated reports actually contain and nothing more: ATX headings,
 * GitHub pipe tables, unordered and ordered lists, block quotes, fenced code, images, HTML
 * comments (dropped, but see `interpretationMarker`), horizontal rules and paragraphs, with
 * `**bold**`, `*italic*`, `` `code` `` and `[link](href)` inline.
 */

/** `![alt](src)` — an image is handed back to the caller instead of being rendered inline. */
const IMAGE = /^!\[([^\]]*)\]\(([^)]+)\)$/;
const INLINE = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/g;

function inline(text: string, keyPrefix = 'i'): ReactNode[] {
  return text.split(INLINE).map((part, i) => {
    const key = `${keyPrefix}-${i}`;
    if (part.startsWith('**') && part.endsWith('**'))
      return <strong key={key}>{part.slice(2, -2)}</strong>;
    if (part.startsWith('`') && part.endsWith('`') && part.length > 1)
      return (
        <code key={key} className="rounded-sm bg-chrome-900 px-1 text-chrome-200">
          {part.slice(1, -1)}
        </code>
      );
    if (part.startsWith('*') && part.endsWith('*') && part.length > 1)
      return <em key={key}>{part.slice(1, -1)}</em>;
    const link = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(part);
    if (link)
      return (
        <a
          key={key}
          href={link[2]}
          rel="noreferrer"
          className="underline decoration-chrome-600 underline-offset-2 hover:text-chrome-50"
        >
          {link[1]}
        </a>
      );
    return <span key={key}>{part}</span>;
  });
}

const HEADING_CLASS: Record<number, string> = {
  1: 'text-sm font-semibold text-chrome-100',
  2: 'mt-4 text-xs font-semibold tracking-wide text-chrome-100 uppercase',
  3: 'mt-3 text-xs font-semibold text-chrome-200',
  4: 'mt-2 text-micro font-semibold text-chrome-300',
};

function Table({ lines, id }: { lines: string[]; id: string }) {
  const cells = (line: string): string[] =>
    line
      .replace(/^\||\|$/g, '')
      .split('|')
      .map((c) => c.trim());
  const [head, , ...body] = lines;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-micro">
        <thead>
          <tr className="border-b border-line">
            {cells(head).map((c, i) => (
              <th
                key={`${id}-h${i}`}
                scope="col"
                className="p-1 text-left font-medium text-chrome-400"
              >
                {inline(c, `${id}-h${i}`)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {body.map((line, r) => (
            <tr key={`${id}-r${r}`} className="border-b border-line-soft">
              {cells(line).map((c, i) => (
                <td key={`${id}-r${r}c${i}`} className="p-1 align-top text-chrome-300">
                  {inline(c, `${id}-r${r}c${i}`)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Everything the renderer knows how to draw, in the order the source had it. */
type Block =
  | { kind: 'heading'; level: number; text: string }
  | { kind: 'para'; text: string }
  | { kind: 'list'; ordered: boolean; items: string[] }
  | { kind: 'quote'; text: string }
  | { kind: 'code'; text: string }
  | { kind: 'table'; lines: string[] }
  | { kind: 'image'; alt: string; src: string }
  | { kind: 'rule' };

function parseBlocks(markdown: string): Block[] {
  const lines = markdown.replace(/\r\n/g, '\n').split('\n');
  const blocks: Block[] = [];
  let i = 0;
  let para: string[] = [];

  const flush = () => {
    if (para.length) blocks.push({ kind: 'para', text: para.join(' ') });
    para = [];
  };

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    if (trimmed === '' || trimmed.startsWith('<!--')) {
      flush();
      i++;
      continue;
    }
    if (/^(-{3,}|_{3,})$/.test(trimmed)) {
      flush();
      blocks.push({ kind: 'rule' });
      i++;
      continue;
    }
    const heading = /^(#{1,6})\s+(.*)$/.exec(trimmed);
    if (heading) {
      flush();
      blocks.push({ kind: 'heading', level: heading[1].length, text: heading[2] });
      i++;
      continue;
    }
    if (trimmed.startsWith('```')) {
      flush();
      const body: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith('```')) body.push(lines[i++]);
      i++;
      blocks.push({ kind: 'code', text: body.join('\n') });
      continue;
    }
    const image = IMAGE.exec(trimmed);
    if (image) {
      flush();
      blocks.push({ kind: 'image', alt: image[1], src: image[2] });
      i++;
      continue;
    }
    if (trimmed.startsWith('|')) {
      flush();
      const table: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith('|')) table.push(lines[i++].trim());
      blocks.push({ kind: 'table', lines: table });
      continue;
    }
    if (/^[-*]\s+/.test(trimmed) || /^\d+\.\s+/.test(trimmed)) {
      flush();
      const ordered = /^\d+\.\s+/.test(trimmed);
      const items: string[] = [];
      while (i < lines.length && /^\s*([-*]|\d+\.)\s+/.test(lines[i])) {
        items.push(lines[i].trim().replace(/^([-*]|\d+\.)\s+/, ''));
        i++;
      }
      blocks.push({ kind: 'list', ordered, items });
      continue;
    }
    if (trimmed.startsWith('>')) {
      flush();
      const body: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith('>'))
        body.push(lines[i++].trim().replace(/^>\s?/, ''));
      blocks.push({ kind: 'quote', text: body.join(' ') });
      continue;
    }
    para.push(trimmed);
    i++;
  }
  flush();
  return blocks;
}

export function Markdown({
  markdown,
  renderImage,
}: {
  markdown: string;
  /** How to draw an image — the caller owns it, because only it knows the figure's URL. */
  renderImage?: (alt: string, src: string) => ReactNode;
}) {
  return (
    <div className="space-y-2 text-xs leading-relaxed text-chrome-300">
      {parseBlocks(markdown).map((block, index) => {
        const key = `b${index}`;
        switch (block.kind) {
          case 'heading': {
            const Tag = `h${Math.min(block.level + 2, 6)}` as 'h3';
            return (
              <Tag key={key} className={HEADING_CLASS[block.level] ?? HEADING_CLASS[4]}>
                {inline(block.text, key)}
              </Tag>
            );
          }
          case 'table':
            return <Table key={key} lines={block.lines} id={key} />;
          case 'list':
            return block.ordered ? (
              <ol key={key} className="list-decimal space-y-0.5 pl-5">
                {block.items.map((item, i) => (
                  <li key={`${key}-${i}`}>{inline(item, `${key}-${i}`)}</li>
                ))}
              </ol>
            ) : (
              <ul key={key} className="list-disc space-y-0.5 pl-5">
                {block.items.map((item, i) => (
                  <li key={`${key}-${i}`}>{inline(item, `${key}-${i}`)}</li>
                ))}
              </ul>
            );
          case 'quote':
            return (
              <blockquote key={key} className="border-l-2 border-line-strong pl-3 text-chrome-400">
                {inline(block.text, key)}
              </blockquote>
            );
          case 'code':
            return (
              <pre
                key={key}
                className="overflow-x-auto rounded-control border border-line-soft bg-chrome-950/60 p-2 font-mono text-micro"
              >
                {block.text}
              </pre>
            );
          case 'image':
            return <div key={key}>{renderImage?.(block.alt, block.src) ?? null}</div>;
          case 'rule':
            return <hr key={key} className="border-line" />;
          default:
            return <p key={key}>{inline(block.text, key)}</p>;
        }
      })}
    </div>
  );
}
