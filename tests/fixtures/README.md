# Test fixtures — synthetic, safe to commit

**No patient data is in this directory.** Every base, position and genotype here is
invented. The fixtures reproduce the *shape* of the real challenge data — header
structure, contig naming, FORMAT fields, the specific representational traps — so the
pipeline can be developed and tested without touching the gated 85 GB dataset.

Real patient slices live in `~/ubuntu/work/` (outside the repo, gitignored, deleted
within 30 days of hackathon close).

## Shape mirrored from the real VCF

Established by profiling the real file (see `ressources/data-profile/`):

| Property | Real VCF | Fixture |
|---|---|---|
| Contig naming | **no `chr` prefix** (`15`) | same |
| Sample column | lab ID `WGS_EX…`, *not* `PROBAND01` | `WGS_TEST0001` |
| Caller | Sentieon Haplotyper → GATK VariantFiltration | same header lines |
| FORMAT | `GT:AD:DP:GQ:PGT:PID:PL` | same |
| FILTER vocabulary | `PASS,LowQual,MQ40,QD2,FS60,MQRankSum-12.5,RPRS-8` | same |
| Multiallelic sites | 66,860 present | one included |
| Physical phasing | 770,458 records carry `PID` | cis, trans and unphased cases |
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
