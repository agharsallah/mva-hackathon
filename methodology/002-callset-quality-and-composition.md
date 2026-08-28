# 002 — Is the callset trustworthy, and what is its composition?

## Question

How many variants, of what kinds, at what quality — and how many were suppressed by
filters, since a suppressed call is a candidate hiding place for a hard second allele.

## Inputs

`~/ubuntu/data/WGS_EX2312012_HGWCNDSX7.vcf.gz`

Note: the delivered `.tbi` is older than its VCF and carries no count metadata, so
`bcftools index -n/-s` refuses it. The index was rebuilt in the work directory; the
delivered files were left untouched.

## Commands

```bash
ln -sf ~/ubuntu/data/WGS_EX2312012_HGWCNDSX7.vcf.gz ~/ubuntu/work/proband.vcf.gz
bcftools index -f -t ~/ubuntu/work/proband.vcf.gz
bcftools index -n ~/ubuntu/work/proband.vcf.gz
bcftools index -s ~/ubuntu/work/proband.vcf.gz
bcftools stats -s - ~/ubuntu/work/proband.vcf.gz > stats/vcf_stats.txt

bcftools query -f '%FILTER\t[%GT]\t[%PID]\n' ~/ubuntu/work/proband.vcf.gz \
  | awk -F'\t' '{ filt[$1]++; gt[$2]++; if ($3 != ".") phased++; total++ } END {...}'
```

## Observed

Totals (`bcftools stats`, full pass):

| | |
|---|---|
| records | 5,012,204 |
| SNPs | 4,086,641 |
| indels | 930,181 |
| multiallelic sites | 66,860 |
| ts/tv | 1.94 |

Genotypes (full pass): `0/1` 3,047,077 · `1/1` 1,898,267 · `1/2` 66,860. No `0/0` and no
`./.` — the file holds variant sites only. het:hom-alt = 1.61.

FILTER (full pass): `PASS` 4,740,790 (94.6%). Non-PASS 271,414, the largest being
`MQ40` 177,522, `QD2` 35,402, `LowQual;QD2` 17,000, `MQ40;QD2` 12,541,
`LowQual;MQ40` 9,782, `LowQual;MQ40;QD2` 10,240, `LowQual` 6,081.

Phasing: 770,458 records (15.4%) carry a non-`.` `PID`.

Per-contig counts run from 383,428 (chr1) down to 13 (chrM); all primary contigs present.

## Conclusions

1. **5.01 M records is normal for WGS**, and ts/tv 1.94 is slightly below the 2.0–2.1
   ideal — acceptable, mildly noisy, not a reason to distrust the callset wholesale.
   het:hom 1.61 shows no gross contamination signal.
2. **66,860 multiallelic sites and 930k indels make normalization mandatory** before any
   comparison against an exact-string-matching scorer.
3. **271,414 non-PASS records are a search space, not garbage.** `MQ40` dominating means
   low mapping quality — exactly the filter that fires in segmental duplications and
   repeats, where a real variant can hide. Mining these costs minutes; re-calling from
   FASTQ costs a day. Do the cheap thing first.
4. **15.4% of records carry phasing**, which sounds usable. Entry 006 measures what it
   actually buys.
