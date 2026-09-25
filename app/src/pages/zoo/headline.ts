/**
 * The iteration's headline, cut out of the merged report the API already serves.
 *
 * The headline is a hand-written `## The headline …` section of `docs/<iteration>/report.md`,
 * above the generated §1 — and `mva.zoo.merge_render` keeps it verbatim on every re-render. So
 * the page reads it from `/api/zoo/reports/merged` instead of typing its numbers in: one text,
 * two places, and the entries each number is quoted from travel with it.
 */

/** The heading that opens the headline section. Matched by prefix, so its subtitle may change. */
const HEADING = /^## The headline\b/;

/** A relative Markdown link — a repo path the dashboard does not serve. Not an image (`![`). */
const RELATIVE_LINK = /(?<!!)\[([^\]]+)\]\((?![a-z]+:)[^)]+\)/g;

export interface Headline {
  /** The heading text, without the `## `. */
  heading: string;
  /** The section body. Relative links are reduced to their text; the entry numbers stay. */
  body: string;
}

/** The headline section of a merged report, or `null` when the report carries none. */
export function headlineOf(markdown: string): Headline | null {
  const chunk = markdown.split(/\n(?=## )/).find((part) => HEADING.test(part));
  if (!chunk) return null;
  const [first, ...rest] = chunk.split('\n');
  return {
    heading: first.slice(3).trim(),
    body: rest.join('\n').replace(RELATIVE_LINK, '$1').trim(),
  };
}
