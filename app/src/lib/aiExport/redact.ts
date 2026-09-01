/**
 * The Data Transfer Agreement forbids resharing patient data through any channel, and a
 * downloaded file is a channel. So a payload that carries a variant's chromosome and
 * position has those two fields removed before it is written into an export — the gene name
 * and the consequence say everything a reader needs and neither is a coordinate.
 *
 * See `docs/notes/no-patient-data-in-the-repository.md`. Exhibits whose whole point *is* the
 * coordinate (the locus tracks, the pair matrix, a searched window) export no payload at all.
 */

const COORDINATE_KEYS = new Set(['chrom', 'pos']);

export function withoutCoordinates<T extends object>(rows: T[]): Record<string, unknown>[] {
  return rows.map((row) => {
    const kept: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(row)) {
      if (!COORDINATE_KEYS.has(key)) kept[key] = value;
    }
    return kept;
  });
}
