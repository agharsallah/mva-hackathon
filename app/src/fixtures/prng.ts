/**
 * Deterministic pseudo-random generator, used only to fill the *shape* of the larger
 * fixture tables (per-Mb bins, flowcell bins, per-cycle quality). Seeded so every
 * reload and every screenshot shows identical numbers.
 */
export function prng(seed: number): () => number {
  let s = seed >>> 0 || 1;
  return () => {
    // xorshift32
    s ^= s << 13;
    s ^= s >>> 17;
    s ^= s << 5;
    s >>>= 0;
    return s / 4294967296;
  };
}

