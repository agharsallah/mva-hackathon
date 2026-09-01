import { isValidElement, type ReactNode } from 'react';

/**
 * Flatten a rendered node to the text a reader sees.
 *
 * Shared by the table (filtering, sort fallback) and by the AI export, which has to turn a
 * legend written as JSX back into a sentence. Attribute-only content — a `<Chip>`'s colour,
 * an icon with no children — carries no words and is therefore dropped.
 */
export function nodeText(node: ReactNode): string {
  if (node === null || node === undefined || typeof node === 'boolean') return '';
  if (typeof node === 'string') return node;
  if (typeof node === 'number') return String(node);
  if (Array.isArray(node)) return node.map(nodeText).join(' ');
  if (isValidElement(node)) return nodeText((node.props as { children?: ReactNode }).children);
  return '';
}
