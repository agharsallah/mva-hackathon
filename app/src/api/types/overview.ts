/** GET /api/overview — one object, the whole case in numbers. */
export interface Overview {
  total_variants: number;
  pass_variants: number;
  snps: number;
  indels: number;
  multiallelic_sites: number;
  tstv: number;
  samples: number;
  total_reads: number;
  read_length: number;
  est_coverage_x: number;
  mean_depth_x: number;
  canonical_contigs: number;
  all_contigs: number;
  delivery_objects: number;
  delivery_bytes: number;
  all_hashes_verified: boolean;
  probe_budget_total: number;
  probe_budget_spent: number;
}
