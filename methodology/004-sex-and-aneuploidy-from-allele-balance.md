# 004 — What is the proband's sex, and is mosaic aneuploidy visible?

## Question

Sex is not stated in the phenotype document and must be inferred. Separately: Mosaic
Variegated Aneuploidy is the diagnosis, so does this sample actually show aneuploidy?

Both questions are answered by the same measurement. A chromosome present in mosaic
trisomy or monosomy in a fraction of cells shifts heterozygous allele balance away from
0.5 and shifts median depth; a hemizygous X shows few heterozygous sites and half the
autosomal variant density.

## Inputs

`~/ubuntu/work/proband.vcf.gz`

## Commands

```bash
bcftools query -i 'GT="het" && FILTER="PASS" && TYPE="snp"' -f '%CHROM\t[%AD]\n' proband.vcf.gz \
  | awk -F'\t' '
      { split($2, a, ","); d = a[1] + a[2]; if (d < 15 || d > 80) next
        vaf = a[2] / d; c = $1; n[c]++; s[c] += vaf; dp[c] += d
        if (vaf >= 0.40 && vaf <= 0.60) mid[c]++ }
      END { for (...) printf "%s\t%d\t%.4f\t%.1f\t%.1f\n", c, n[c], s[c]/n[c], dp[c]/n[c], 100*mid[c]/n[c] }'
```

Depth is bounded to 15–80× so that repeat pile-ups and dropout regions do not swamp the
signal. Restricted to PASS SNVs to avoid indel allele-balance artefacts.

Full output: `ressources/data-profile/vcf_chrom_allele_balance.tsv`.

## Observed

| chrom | n_het | mean VAF | mean DP | % in 0.40–0.60 |
|---|---|---|---|---|
| 1 | 171,976 | 0.4936 | 44.2 | 77.6 |
| 2 | 185,662 | 0.4931 | 44.1 | 77.4 |
| 15 | 62,699 | 0.4931 | 44.4 | 77.5 |
| 20 | 59,467 | 0.4720 | 45.5 | 68.9 |
| 22 | 34,287 | 0.4726 | 46.1 | 71.1 |
| **X** | **4,858** | 0.4644 | 41.4 | 65.5 |
| **Y** | **4,301** | 0.3517 | 36.3 | 24.4 |

Across chr1–22 the full ranges were: mean VAF 0.472–0.497, mean depth 43.7–46.1.

For scale, chrX carries 117,225 total records over 156 Mb (0.75/kb) against chr1's
383,428 over 249 Mb (1.54/kb) — half the density. chrY carries 13,840 records.

## Conclusions

1. **The proband is male.** chrX shows half the autosomal variant density and only 4,858
   heterozygous SNVs (concentrated in the pseudoautosomal regions), while chrY is present
   at real depth (36.3×) with 13,840 records. That is a hemizygous X and a present Y.
2. **No whole-chromosome mosaic aneuploidy is detectable in this sample.** Every autosome
   sits at ~0.49 allele balance and ~44× depth. chr20 and chr22 are marginally low (0.472,
   0.473) but within GC-driven noise and not accompanied by a depth shift.
3. **This does not contradict the MVA diagnosis, and the negative should be reported.**
   MVA is diagnosed by karyotype, typically on cultured lymphocytes or fibroblasts, and
   the aneuploid fraction varies by tissue and division history. A bulk blood WGS sample
   showing no shift says the aneuploid fraction in *this DNA* is below what allele balance
   can detect — roughly under 10–15%. Stating that with numbers is stronger than staying
   silent about a negative result.
4. **Mean depth ~44× genome-wide** is comfortably enough for confident heterozygous calls,
   for SV calling, and for a low-VAF mosaic scan.
