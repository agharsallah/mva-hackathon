# 073 — Are the candidate alleles spelled the way the scorer will read them?

**Step:** step-1   **Hypotheses tested:** H008
**Written:** 2026-09-05, from the run quoted below. The normalization seam is **still not a
pipeline stage** — this entry records the run and its result, not the tool.

## Question

The scorer matches `(chrom, pos, ref, alt)` by exact string. An indel has several valid
spellings; a multi-allelic record names two ALT alleles in one row that the scorer would
never match. `bcftools norm -m -both -f <reference>` (split multi-allelic sites, left-align
indels against the reference) makes spellings canonical. Does it change the two BUB1B
candidate alleles — and what does it change in the callset at all?

## Hypothesis and prediction — written before the run

**H008:** both candidate alleles are single-nucleotide substitutions at bi-allelic sites, so
their spelling is invariant under normalization. Predicted: `len(REF) = len(ALT) = 1`, a
single ALT per record, and both records byte-identical in CHROM, POS, REF, ALT after
`bcftools norm`.

## What would refute it

Either allele is an indel or sits in a multi-allelic record, or `norm` changes its POS,
REF or ALT.

## Inputs

| Input | Value |
|---|---|
| Callset | `WGS_EX2312012_HGWCNDSX7.vcf.gz` fetched from the object store (315,153,971 bytes, `.tbi` alongside) into a gitignored scratch directory |
| Reference | UCSC `hg38.analysisSet.fa.gz` (949,157,663 bytes), decompressed with the `chr` prefix stripped from every header → 195 contigs, `samtools faidx`. The VCF's own reference is the NCBI no-alt analysis set **plus hs38d1 decoys**, with contig names spelled UCSC-style minus `chr` (`1_KI270706v1_random`, `M`) — identical to the stripped UCSC names for the 195 shared contigs |
| Tools | bcftools 1.24, samtools 1.24 |
| Regions | the 195 contigs present in the reference. The 43,667 records on `*_decoy` contigs have no sequence to normalize against and are not in scope for any scorer |

## Commands

```bash
gzip -dc hg38.analysisSet.fa.gz | sed 's/^>chr/>/' > GRCh38_no_chr.fa && samtools faidx GRCh38_no_chr.fa
REGIONS=$(cut -f1 GRCh38_no_chr.fa.fai | paste -sd, -)
bcftools norm -m -both -c w -f GRCh38_no_chr.fa --threads 4 -r "$REGIONS" \
    WGS_EX2312012_HGWCNDSX7.vcf.gz -Oz -o proband.norm.vcf.gz
bcftools index -t proband.norm.vcf.gz
# candidate rows before/after, BUB1B span before/after, genome-wide key diff (sort + comm)
```

A first attempt without `-r` aborted on the first decoy record
(`The sequence "Un_KN707607v1_decoy" was not found`) — the reason the region list exists.

## Observed

```
records total:             5,012,204
records on decoy contigs:     43,667
records on canonical 25:   4,895,719
Lines total/split/joined/realigned/mismatch_removed/dup_removed/skipped: 4968537/66639/0/39913/0/0/0
REF mismatch warnings: 0
records after norm:        5,035,176
multiallelic after norm:           0
```

`bcftools norm` on 4,968,537 records took **15 s** wall clock (`-c w`: 0 reference
mismatches — the stripped UCSC sequence *is* the callset's reference for these contigs).

| Measured | Value |
|---|---|
| multi-allelic records split | **66,639** (all of the 66,860 counted in [§3](../../../../ideation/data-findings.md) that lie on the 195 contigs), every one of them with exactly two ALTs → 133,278 split rows |
| alleles realigned (left-aligned or trimmed) | **39,913 — all of them split-off alleles of multi-allelic records** |
| bi-allelic records whose spelling changed | **0** |
| `(chrom, pos, ref, alt)` keys present before and absent after | 110,306 = 43,667 decoy records + 66,639 multi-allelic records, exactly |
| keys present after and absent before | 133,278 = 2 × 66,639, exactly |

The arithmetic closes without remainder: Sentieon already emits every bi-allelic record
left-aligned, and normalization changes nothing except splitting multi-allelic sites and
trimming the alleles that split produces.

The candidates:

```
before:  15  <pos>  T  G      15  <pos>  T  G
after:   15  <pos>  T  G      15  <pos>  T  G
```

Both are single-base substitutions with a single ALT; both records are identical before and
after. Across the BUB1B gene span: 15 records before, 15 after, 0 changed.

(The scratch line "SNV keys changed: 40,037" in the run log counts decoy-contig SNVs
dropped by `-r`, not respelled SNVs — the decoy count explains it and it is recorded here
so nobody re-derives it as a finding.)

## Evidence recorded

```
evidence 27  H008 supports 0.8  measurement  methodology/073  — both SNVs, single ALT, unchanged by norm; 0 bi-allelic spellings changed genome-wide
evidence 28  H008 neutral  0.0  absence      methodology/073  — decoy records out of scope; the seam is a run, not yet a stage
```

## Verdict

**H008 — supported, committed at 0.83** (`sigmoid(2 × 0.8)`; the neutral row adds nothing).
The two rows submitted are spelled as the answer key must spell them, up to the `chr`
prefix that `Variant.from_vcf` adds.

Step 1's own goal — *one spelling per variant so the scorer can be trusted with an indel* —
is answered for this callset: **it already has one, except at multi-allelic sites**, and any
indel candidate drawn from a multi-allelic site must be taken from the normalized file.

## Next test

Make the seam a stage: a `normalize` step in `mva.pipeline` with a round-trip test, and a
`variants_norm` layer beside `variants_raw`, so "was this normalized?" is answered by code.
Tooling only; no new claim.
