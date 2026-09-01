/**
 * How big the bundle is, and whether that is worth saying out loud.
 *
 * Every export path — one exhibit, one page, the whole case — reports through `note`, so a
 * bundle too large for a chat window is never handed over silently. It is a warning and not
 * a block: a truncated export would be worse than a large one.
 */

export const LARGE_EXPORT_BYTES = 5 * 1024 * 1024;

export interface ExportSize {
  bytes: number;
  label: string;
  large: boolean;
}

export function measure(content: string): ExportSize {
  const bytes = new Blob([content]).size;
  return { bytes, label: sizeLabel(bytes), large: bytes > LARGE_EXPORT_BYTES };
}

export function sizeLabel(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** What to tell the user at the moment of the export. */
export function note(verb: string, size: ExportSize): string {
  const tail = size.large ? ' — may exceed an AI chat’s context limit' : '';
  return `${verb} · ${size.label}${tail}`;
}
