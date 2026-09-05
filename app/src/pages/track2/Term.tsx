import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

/**
 * `term (plain meaning)`, the term linked to its entry in the one dictionary.
 *
 * The house pattern, shared by every panel on this page: the jargon is never removed, only
 * paired with its translation, because the reader has to recognise the real word in a tool
 * flag, an API field or a paper later.
 */
export function T({ slug, term, plain }: { slug: string; term: string; plain: ReactNode }) {
  return (
    <span>
      <Link
        to={`/learn#${slug}`}
        className="font-medium text-machinery-400 underline decoration-machinery-800 underline-offset-2 hover:text-machinery-200"
      >
        {term}
      </Link>{' '}
      <span className="text-chrome-400">({plain})</span>
    </span>
  );
}
