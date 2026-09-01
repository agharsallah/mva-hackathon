/**
 * GET /api/panel/clinvar-presence — the inward reference join.
 *
 * Every other comparison starts from an allele the callset has and asks what the world
 * knows about it. This one starts from every site the world has already classified
 * **pathogenic or likely pathogenic** (P/LP) inside the candidate panel and asks whether
 * the callset contains it at all. Both answers are results: a P/LP site called
 * heterozygous and PASS is a direct lead, and a gene whose known P/LP records are all
 * absent is an informative negative.
 *
 * `present` is a **lower bound**. The match is exact on (chrom, pos, ref) plus ALT list
 * membership, with no left-alignment on either side, so the same insertion spelled
 * `T -> TA` in ClinVar and `TA -> TAA` in the callset does not join. For single-base
 * substitutions the match is exact; for indels a real hit can be missed.
 */

/** One row per **panel gene**, counted off the panel BED — a gene with nothing classified
 *  in it still appears, with `n_plp = 0`. */
export interface ClinvarPresenceSummary {
  gene: string;
  /** ClinVar P/LP records inside the gene. */
  n_plp: number;
  /** Of those, the ones stating an alternate allele a VCF record could equal. */
  n_comparable: number;
  /** Of those, the ones ClinVar gives no alternate allele for (`alt = '.'`). */
  n_uncomparable: number;
  /** Comparable sites the callset has a record for. A floor, never a ceiling. */
  n_present: number;
  /** Of those, the ones the caller did not suppress. */
  n_present_pass: number;
  /** Of those, the ones the genotype carries exactly one copy of. */
  n_present_het: number;
  /** Comparable sites the callset has no record for. A measured absence. */
  n_absent: number;
}

/**
 * One P/LP site the callset was checked for. The endpoint returns only the rows that are
 * **present** or **uncomparable**; measured absences are carried as counts on the summary,
 * because two thousand rows of "nothing called here" say nothing the counts do not.
 */
export interface ClinvarPresenceSite {
  gene: string;
  chrom: string;
  pos: number;
  ref: string;
  alt: string;
  rsid: string | null;
  /** ClinVar's stable key. 4,442 rows of the extract have no rsID; all have this. */
  variation_id: number;
  /** The germline classification verbatim, e.g. `Pathogenic/Likely_pathogenic`. */
  clnsig: string;
  /** How the assertion was arrived at, e.g. `reviewed_by_expert_panel`. */
  clnrevstat: string | null;
  /** That status as NCBI's gold-star count, 4 down to 0. Null = no status stated,
   *  which is not the same claim as zero stars. */
  review_stars: number | null;
  /** The disease name(s) ClinVar attaches, `|`-joined. */
  condition: string | null;
  /** Whether ClinVar states an alternate allele a VCF record could equal. */
  comparable: boolean;
  /** Null — never false — where the row is not comparable. */
  present: boolean | null;
  gt: string | null;
  filter: string | null;
  qual: number | null;
  dp: number | null;
  /** Which alternate of a comma-packed record this is: 1 biallelic, 2 the second. */
  allele_ix: number | null;
  vaf: number | null;
  /** Whether the genotype actually contains the allele. A `0/1` call on a `G -> A,C`
   *  record carries `A` and not `C`, so this is not implied by `present`. */
  carries_alt: boolean | null;
  /** Exactly one copy of this allele — the shape a recessive candidate must have. */
  is_het: boolean | null;
}

export interface ClinvarPresence {
  summary: ClinvarPresenceSummary[];
  sites: ClinvarPresenceSite[];
}
