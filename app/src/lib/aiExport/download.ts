/**
 * Getting the bundle out of the browser. Both routes report their size through `note`, so
 * neither can hand over a document too large for a chat window without saying so.
 */

import { measure, note } from './size';

export function downloadMarkdown(filename: string, content: string): void {
  const url = URL.createObjectURL(new Blob([content], { type: 'text/markdown;charset=utf-8' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/** False when the clipboard is unavailable — a sandboxed or insecure context blocks it. */
export async function copyToClipboard(content: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(content);
    return true;
  } catch {
    return false;
  }
}

export async function copyExport(content: string): Promise<string> {
  const ok = await copyToClipboard(content);
  return ok ? note('copied', measure(content)) : 'clipboard blocked by the browser';
}

export function downloadExport(filename: string, content: string): string {
  downloadMarkdown(filename, content);
  return note('downloaded', measure(content));
}

export function dateStamp(): string {
  return new Date().toISOString().slice(0, 10);
}

/** `/` → `overview`, `/panel` → `panel`, `/a/b` → `a-b`. Used in export filenames. */
export function pageSlug(pathname: string): string {
  const trimmed = pathname.replace(/^\/+|\/+$/g, '');
  return trimmed === '' ? 'overview' : trimmed.replace(/\//g, '-');
}
