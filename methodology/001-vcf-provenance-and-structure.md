# 001 — What produced this VCF, and what is in its header?

## Question

Before trusting any variant, establish: which caller, which reference build, how the
chromosomes are named, what annotation is already present, and whether structural
variants are included.

## Inputs

`~/ubuntu/data/WGS_EX2312012_HGWCNDSX7.vcf.gz` (315,153,971 bytes)

## Commands

Header parsed directly with Python's `gzip` (before the bioinformatics toolchain was
installed):

```python
import gzip
with gzip.open('WGS_EX2312012_HGWCNDSX7.vcf.gz', 'rt') as f:
    for line in f:
        if not line.startswith('#'):
            break
        ...  # bucket by ##contig / ##INFO / ##FORMAT / ##FILTER
```

Equivalent, now that tooling exists: `bcftools view -h <vcf>`.

## Observed

- 2,618 header lines; 2,580 of them `##contig`.
- `##reference=file://refGenome/GCA_000001405.15_GRCh38_no_alt_analysis_set_plus_hs38d1_maskedGRC_exclusions_v2_no_chr.fasta`
- `##contig=<ID=1,length=248956422,assembly=unknown>` — **no `chr` prefix**.
- Sample column: `WGS_EX2312012` (the lab accession, not `PROBAND01`).
- Provenance: `##SentieonCommandLine.Haplotyper` (sentieon-genomics-202308.02) →
  `##SentieonCommandLine.GVCFtyper` → `##GATKCommandLine=<ID=VariantFiltration>`.
- 6 FILTER definitions: `FS60`, `LowQual`, `MQ40`, `MQRankSum-12.5`, `QD2`, `RPRS-8`.
- 7 FORMAT fields: `AD DP GQ GT PGT PID PL`.
- 17 INFO fields: `AC AF AN BaseQRankSum ClippingRankSum DB DP ExcessHet FS
  InbreedingCoeff MLEAC MLEAF MQ MQRankSum QD ReadPosRankSum SOR`.
- Decoy contigs present (`Un_JTFH01001996v1_decoy` etc.) — the full hs38d1 analysis set.

## Conclusions

1. **Contigs are bare.** The submission format requires `chr15`; the VCF says `15`. The
   scorer compares chromosome strings verbatim, so this must be bridged in exactly one
   place — implemented as `Variant.from_vcf()`.
2. **No SV or CNV caller anywhere in the provenance.** Sentieon Haplotyper is a
   small-variant caller and `VariantFiltration` only annotates FILTER. There are no
   symbolic ALTs and no `SVTYPE` INFO field. A structural second allele is therefore
   absent from this file at every FILTER level.
3. **No functional annotation.** No `CSQ`, no `ANN`, no gnomAD field. `INFO/AF` is
   within-sample: with one sample it is 0.5 or 1.0 and carries no population information.
   Only `DB` (dbSNP membership) is usable raw, as a weak novelty proxy.
4. **`PGT`/`PID` exist**, so some physical phasing is available — quantified in entry 006.
5. The header leaks the lab accession and the provider's DNAnexus job paths; both are
   redacted before the header is committed.
