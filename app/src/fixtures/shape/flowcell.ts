import type { FlowcellBinRow } from '../../api/types';
import { prng } from '../prng';

/**
 * FIXTURE — flowcell occupancy for one shard, binned at x//1000, y//1000.
 *
 * MEASURED extents: 27 tiles, x 1,009–32,949, y 1,000–37,059. The per-bin counts are
 * generated to that envelope (a shard is one contiguous slice of the flowcell surface);
 * the live API reads a real shard, column-pruned.
 */
export function flowcellFixture(lane: number, read: number, shard: number): FlowcellBinRow[] {
  const rand = prng(31 * lane + 7 * read + shard + 1);
  const out: FlowcellBinRow[] = [];
  const tiles = Array.from({ length: 27 }, (_, i) => 1101 + i);
  for (const tile of tiles) {
    for (let xb = 1; xb <= 32; xb++) {
      for (let yb = 1; yb <= 37; yb++) {
        // Edge lanes of the flowcell are less densely clustered.
        const edge = Math.min(xb, 33 - xb, yb, 38 - yb);
        const falloff = Math.min(1, 0.45 + edge / 6);
        const n = Math.round(70 * falloff * (0.7 + rand() * 0.6));
        if (n > 0) out.push({ tile, xb, yb, n });
      }
    }
  }
  return out;
}
