const ORDER = [...Array.from({ length: 22 }, (_, i) => String(i + 1)), 'X', 'Y', 'MT'];

/** Sort key that keeps chromosomes in karyotype order rather than lexicographic order. */
export function chromOrder(chrom: string): number {
  const bare = chrom.replace(/^chr/i, '');
  const i = ORDER.indexOf(bare);
  return i === -1 ? 999 : i;
}

export const CHROM_ORDER = ORDER;
