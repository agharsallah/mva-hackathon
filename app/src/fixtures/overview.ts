import type { Overview } from '../api/types';

/**
 * FIXTURE. Every field here is a measured aggregate from the repo's executed
 * exploration runs (counts and ratios only — no patient sequence, no coordinates).
 * The live API serves the same numbers from pg.results / the delivery manifest.
 */
export const overviewFixture: Overview = {
  total_variants: 5_012_204,
  pass_variants: 4_740_790,
  snps: 4_086_641,
  indels: 930_181,
  multiallelic_sites: 66_860,
  tstv: 1.94,
  samples: 1,
  total_reads: 1_071_835_104,
  read_length: 149,
  est_coverage_x: 51.9,
  mean_depth_x: 44.3, // the live API's computed value
  canonical_contigs: 25,
  all_contigs: 1690,
  delivery_objects: 12,
  // 78.9 GiB of gzipped FASTQ plus the VCF and sidecars.
  delivery_bytes: 84_703_196_774,
  all_hashes_verified: true,
  probe_budget_total: 18,
  probe_budget_spent: 0,
};
