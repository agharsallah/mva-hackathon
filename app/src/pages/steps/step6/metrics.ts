import type { Step6Evidence, Step6Leader, Step6MatrixCell, Step6Route } from '../../../api/types';

/** The four raw sources a pair can be spoken for by, in the order the exhibits show them. */
export const INPUTS = ['hpo', 'vcf', 'reads', 'literature'] as const;

/** How many fused ranks the matrix and the movement chart show. */
export const TOP_RANKS = 20;

export function count(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : value.toLocaleString();
}

/** A weight or an AUC: three decimals, because the second one is where 0.5 lives. */
export function stat(value: number | null | undefined): string {
  return value === null || value === undefined || Number.isNaN(value) ? '—' : value.toFixed(3);
}

/** An RRF score. Five decimals: the whole ranking lives between 0.01 and 0.05. */
export function score(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : value.toFixed(5);
}

/** `BUB1B|truncating:rs759242053|missense:` → the two alleles, gene stripped, for a cell. */
export function alleles(pairId: string): string {
  const parts = pairId.split('|');
  return parts
    .slice(1)
    .map((part) => part.replace(/:$/, ' (no rsid)'))
    .filter(Boolean)
    .join('  +  ');
}

/**
 * A route's rank for one pair, as the reader must see it.
 *
 * `defaulted` is the whole point: a cell showing 51 because the route never listed the pair
 * is not the route ranking it last, and rendering both the same way would turn silence into
 * agreement.
 */
export function cellLabel(cell: Step6MatrixCell | undefined): string {
  if (!cell) return '—';
  if (cell.defaulted) return 'not listed';
  return cell.inherited ? `${cell.route_rank}*` : String(cell.route_rank);
}

/** Distinct fused ranks, best first, capped — the rows of the agreement matrix. */
export function matrixPairs(cells: Step6MatrixCell[], limit = TOP_RANKS): Step6MatrixCell[] {
  const seen = new Map<string, Step6MatrixCell>();
  for (const cell of cells) {
    if (cell.fused_rank > limit) continue;
    if (!seen.has(cell.pair_id)) seen.set(cell.pair_id, cell);
  }
  return [...seen.values()].sort((a, b) => a.fused_rank - b.fused_rank);
}

/** The routes in the order the matrix columns run: the ones that vote, then the ones that do not. */
export function matrixRoutes(routes: Step6Route[]): Step6Route[] {
  return [...routes].sort((a, b) => Number(b.admitted) - Number(a.admitted));
}

/**
 * Which of the four inputs are missing for a pair.
 *
 * Returned as the absent ones rather than the present ones because that is the sentence the
 * exhibit has to be able to write: "three of four — the literature never nominated it".
 */
export function missingInputs(row: Step6Evidence): string[] {
  return [
    row.has_hpo ? null : 'hpo',
    row.has_vcf ? null : 'vcf',
    row.has_reads ? null : 'reads',
    row.has_literature ? null : 'literature',
  ].filter((name): name is string => name !== null);
}

/** The confirmation triple as three independent flags, because it was measured that way. */
export function triple(row: Pick<Step6Leader, 'read_confirmed' | 'single_copy' | 'no_cn_loss'>) {
  return [
    { label: 'read-confirmed', met: row.read_confirmed },
    { label: 'single copy', met: row.single_copy },
    { label: 'no CN loss', met: row.no_cn_loss },
  ];
}

/**
 * How far a pair moved between the two weightings.
 *
 * Negative means the measured-error-rate weights *promoted* it. A large positive number is
 * the interesting case: a pair that only reaches the top when every route counts equally is
 * being carried by the routes with the worst measured error rates.
 */
export function drift(row: Step6Leader): number | null {
  return row.rank_sensitivity === null ? null : row.rank_sensitivity - row.fused_rank;
}
