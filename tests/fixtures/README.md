# Test fixtures — synthetic, safe to commit

**Standing:** firm — the rule behind this directory is
[synthetic fixtures](../../docs/notes/synthetic-fixtures.md). Shape re-checked 2026-08-29.

**No patient data is in this directory.** Every base, position and genotype here is
invented. The fixtures reproduce the *shape* of the real challenge data — header
structure, contig naming, FORMAT fields, the specific representational traps — so the
pipeline can be developed and tested without touching the gated 85 GB dataset.

Real patient slices live outside the repo — see the
[data-handling perimeter](../../README.md#data-handling--read-this-first).

## Shape mirrored from the real VCF

Established by profiling the real file (evidence: `ressources/data-profile/`; numbers:
[`ideation/data-findings.md`](../../ideation/data-findings.md)):

| Property | Real VCF | Fixture |
|---|---|---|
| Contig naming | **no `chr` prefix** (`15`) | same |
| Sample column | lab ID `WGS_EX…`, *not* `PROBAND01` | `WGS_TEST0001` |
| Caller | Sentieon Haplotyper → GATK VariantFiltration | same header lines |
| FORMAT | `GT:AD:DP:GQ:PGT:PID:PL` | same |
| FILTER vocabulary | `PASS,LowQual,MQ40,QD2,FS60,MQRankSum-12.5,RPRS-8` | same |
| Multiallelic sites | present ([count](../../ideation/data-findings.md)) | one included |
| Physical phasing | a minority of records carry `PID` ([count](../../ideation/data-findings.md)) | cis, trans and unphased cases |
| No SV/CNV records | SNV+indel only | same |

## The traps each fixture record encodes

`mini.vcf` positions are inside the real BUB1B span (chr15:40,140,984-40,241,137) so
region queries are exercised, but the alleles are fabricated.

| Pos | Encodes |
|---|---|
| 40141000 | plain het SNV, PASS — the baseline |
| 40142000 / 40142100 | same `PID`, both `0\|1` → **cis** pair, must NOT be called compound het |
| 40143000 / 40143500 | same `PID`, `0\|1` and `1\|0` → **trans** pair, IS a compound het |
| 40144000 / 40144800 | two hets, no `PID` → unphased candidate pair |
| 40145000 | hom-alt `1/1` — not a compound-het component |
| 40146000 | multiallelic `1/2` — needs `bcftools norm -m -both` |
| 40147000 | right-aligned indel — needs left-alignment before submission |
| 40148000 | `LowQual;QD2` — non-PASS, the "suppressed second allele" case |
