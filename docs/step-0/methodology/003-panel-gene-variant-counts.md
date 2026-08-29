# 003 — How many variants sit in the MVA candidate genes?

## Question

The first targeted strike: do the known MVA genes contain variants at all, and does any
gene stand out by count or by filter rate?

## Inputs

- `~/ubuntu/work/proband.vcf.gz` (re-indexed, see entry 002)
- `ressources/data-profile/mva_panel_grch38.bed` — MVA genes plus rhabdomyosarcoma
  differentials, GRCh38 spans with 20 kb padding, fetched from the Ensembl REST API by
  `tools/mva_panel_bed.py`

## Commands

The BED is `chr`-prefixed and the VCF's contigs are not, so the prefix is stripped for
the region query:

```bash
grep -v '^#' mva_panel_grch38.bed \
  | awk 'BEGIN{OFS="\t"}{ sub(/^chr/,"",$1); print $1,$2,$3,$4 }' | sort -k1,1 -k2,2n \
  > panel_nochr.bed

while IFS=$'\t' read -r c s e sym; do
  bcftools view -H        -r "${c}:$((s+1))-${e}" proband.vcf.gz | wc -l
  bcftools view -H -f PASS -r "${c}:$((s+1))-${e}" proband.vcf.gz | wc -l
done < panel_nochr.bed
```

## Observed

| Gene | Chrom | All | PASS |
|---|---|---|---|
| CEP57 | chr11 | 13 | 13 |
| DICER1 | chr14 | 87 | 87 |
| BUB1B | chr15 | 80 | 76 |
| TP53 | chr17 | 120 | 118 |
| CEP192 | chr18 | 255 | 251 |
| CENPE | chr4 | 169 | 166 |
| TRIP13 | chr5 | 12 | **6** |
| SMC5 | chr9 | 125 | 124 |

861 variants across the panel. In BUB1B, inspection of the individual records showed the
large majority carry the `DB` (dbSNP) flag; six do not.

## Conclusions

1. **Every candidate gene contains variants** — no gene is a coverage hole, so nothing is
   ruled out by absence at this stage.
2. **TRIP13 is the outlier: 6 of 12 records are non-PASS**, mostly `MQ40`, with low alt
   depths. TRIP13 sits near the chr5 telomere in difficult sequence. This is a mappability
   statement, not evidence of absence, and it means TRIP13 needs read-level inspection
   rather than VCF-level dismissal.
3. **Counts alone cannot narrow 861 variants.** The spans include introns and the majority
   are common dbSNP entries. Rarity and consequence are required, and neither is in the
   file — this is what makes annotation the critical path rather than a refinement.
