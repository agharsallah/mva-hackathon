/**
 * Fixtures for the three warehouse tables that existed before anything served them:
 * `results.sequencing_yield`, `warehouse.vcf_fields` and `results.stats_af`.
 *
 * Every row here is MEASURED — read back off the live endpoints, not shaped. That is
 * possible because all three tables are tiny (4, 31 and 2 rows), so the offline app shows
 * the same numbers the live one does rather than a plausible stand-in.
 */

import type { SequencingYieldRow, VcfFieldRow, ZygosityRow } from '../api/types';

/**
 * FIXTURE — MEASURED. `results.sequencing_yield`, all four rows.
 *
 * Reads and bases are **estimates** in the table itself: they come from each FASTQ's
 * compressed size and its first read's length, because counting means decompressing
 * 79 GB. `/api/reads/runs` carries the counted figure.
 */
export const sequencingYieldFixture: SequencingYieldRow[] = [
  { lane: 'L001', est_reads: 276_180_373, est_gbases: 41.15, gigabytes: 21.5, n_files: 2 },
  { lane: 'L002', est_reads: 272_700_071, est_gbases: 40.63, gigabytes: 21.29, n_files: 2 },
  { lane: 'L003', est_reads: 263_619_859, est_gbases: 39.28, gigabytes: 20.82, n_files: 2 },
  { lane: 'L004', est_reads: 267_358_482, est_gbases: 39.84, gigabytes: 21.06, n_files: 2 },
];

/**
 * FIXTURE — MEASURED. `warehouse.vcf_fields`, all 31 rows, descriptions verbatim from the
 * delivered VCF header. 7 FILTER · 17 INFO · 7 FORMAT.
 */
export const vcfFieldsFixture: VcfFieldRow[] = [
  { kind: 'FILTER', id: 'FS60', description: 'FS > 60.0' },
  { kind: 'FILTER', id: 'LowQual', description: 'Low quality' },
  { kind: 'FILTER', id: 'MQ40', description: 'MQ < 40.0' },
  { kind: 'FILTER', id: 'MQRankSum-12.5', description: 'MQRankSum < -12.5' },
  { kind: 'FILTER', id: 'PASS', description: 'All filters passed' },
  { kind: 'FILTER', id: 'QD2', description: 'QD < 2.0' },
  { kind: 'FILTER', id: 'RPRS-8', description: 'ReadPosRankSum < -8.0' },
  { kind: 'INFO', id: 'AC', description: 'Allele count in genotypes, for each ALT allele, in the same order as listed' },
  { kind: 'INFO', id: 'AF', description: 'Allele frequency, for each ALT allele, in the same order as listed' },
  { kind: 'INFO', id: 'AN', description: 'Total number of alleles in called genotypes' },
  { kind: 'INFO', id: 'BaseQRankSum', description: 'Z-score from Wilcoxon rank sum test of Alt Vs. Ref base qualities' },
  { kind: 'INFO', id: 'ClippingRankSum', description: 'Z-score From Wilcoxon rank sum test of Alt vs. Ref number of hard clipped bases' },
  { kind: 'INFO', id: 'DB', description: 'dbSNP membership' },
  { kind: 'INFO', id: 'DP', description: 'Combined depth across samples' },
  { kind: 'INFO', id: 'ExcessHet', description: 'Phred-scaled p-value for exact test of excess heterozygosity' },
  { kind: 'INFO', id: 'FS', description: "Phred-scaled p-value using Fisher's exact test to detect strand bias" },
  { kind: 'INFO', id: 'InbreedingCoeff', description: 'Inbreeding coefficient as estimated from the genotype likelihoods per-sample when compared against the Hardy-Weinberg expectation' },
  { kind: 'INFO', id: 'MLEAC', description: 'Maximum likelihood expectation (MLE) for the allele counts, for each ALT allele, in the same order as listed' },
  { kind: 'INFO', id: 'MLEAF', description: 'Maximum likelihood expectation (MLE) for the allele frequency, for each ALT allele, in the same order as listed' },
  { kind: 'INFO', id: 'MQ', description: 'RMS mapping quality' },
  { kind: 'INFO', id: 'MQRankSum', description: 'Z-score From Wilcoxon rank sum test of Alt vs. Ref read mapping qualities' },
  { kind: 'INFO', id: 'QD', description: 'Variant Confidence/Quality by Depth' },
  { kind: 'INFO', id: 'ReadPosRankSum', description: 'Z-score from Wilcoxon rank sum test of Alt vs. Ref read position bias' },
  { kind: 'INFO', id: 'SOR', description: 'Symmetric Odds Ratio of 2x2 contingency table to detect strand bias' },
  { kind: 'FORMAT', id: 'AD', description: 'Allelic depths for the ref and alt alleles in the order listed' },
  { kind: 'FORMAT', id: 'DP', description: 'Read depth' },
  { kind: 'FORMAT', id: 'GQ', description: 'Genotype quality' },
  { kind: 'FORMAT', id: 'GT', description: 'Genotype' },
  { kind: 'FORMAT', id: 'PGT', description: 'Physical phasing haplotype information, describing how the alternate alleles are phased in relation to one another' },
  { kind: 'FORMAT', id: 'PID', description: 'Physical phasing ID information, where each unique ID within a given sample (but not across samples) connects records within a phasing group' },
  { kind: 'FORMAT', id: 'PL', description: 'The phred-scaled genotype likelihoods rounded to the closest integer' },
];

/**
 * FIXTURE — MEASURED. `results.stats_af`, both rows.
 *
 * `af_bin` is NOT a population frequency: one sample means AN is always 2, so bcftools'
 * two bins are AC=1 and AC=2. Both allele totals match the independent genotype counter
 * exactly — 3,180,797 = 3,047,077 (`0/1`) + 2 × 66,860 (`1/2`), and 1,898,267 = `1/1`.
 */
export const zygositySplitFixture: ZygosityRow[] = [
  {
    af_bin: 0.0,
    zygosity: 'heterozygous',
    n_snps: 2_536_505,
    n_ts: 1_665_690,
    n_tv: 870_815,
    n_indels: 644_292,
    n_alleles: 3_180_797,
    ts_tv: 1.913,
    pct_of_alleles: 62.63,
  },
  {
    af_bin: 0.99,
    zygosity: 'homozygous alternate',
    n_snps: 1_552_121,
    n_ts: 1_032_666,
    n_tv: 519_455,
    n_indels: 346_146,
    n_alleles: 1_898_267,
    ts_tv: 1.988,
    pct_of_alleles: 37.37,
  },
];
