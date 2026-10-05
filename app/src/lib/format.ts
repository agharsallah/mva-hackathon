export const int = (n: number | null | undefined): string =>
  n === null || n === undefined ? '—' : n.toLocaleString('en-US');

export const dec = (n: number | null | undefined, d = 2): string =>
  n === null || n === undefined ? '—' : n.toFixed(d);

export const pct = (n: number | null | undefined, d = 2): string =>
  n === null || n === undefined ? '—' : `${n.toFixed(d)}%`;

export function bytes(n: number | null | undefined): string {
  if (n === null || n === undefined) return '—';
  const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB'];
  let v = n;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(v < 10 && i > 0 ? 2 : 1)} ${units[i]}`;
}

/** 1_071_835_104 → "1.07 B". For stat tiles where the exact figure sits in the caption. */
export function compact(n: number | null | undefined): string {
  if (n === null || n === undefined) return '—';
  const abs = Math.abs(n);
  if (abs >= 1e9) return `${(n / 1e9).toFixed(2)} B`;
  if (abs >= 1e6) return `${(n / 1e6).toFixed(2)} M`;
  if (abs >= 1e3) return `${(n / 1e3).toFixed(1)} K`;
  return String(n);
}

/**
 * Format an instant for display. Handles both shapes the services actually return:
 * ISO 8601 strings (the Postgres-backed endpoints) and Unix epoch seconds as a float
 * (the reads-API job records).
 */
export function iso(s: string | number | null | undefined): string {
  if (s === null || s === undefined || s === '') return '—';
  if (typeof s === 'number') {
    if (!Number.isFinite(s)) return '—';
    return new Date(s * 1000).toISOString().replace('T', ' ').slice(0, 19);
  }
  return s.replace('T', ' ').replace(/(\.\d+)?(Z|[+-]\d\d:\d\d)?$/, '');
}
