# Methodology log

One entry per analysis actually executed, recording the question, the exact inputs and
commands, the observed output, and the conclusion drawn — enough for someone else to
reproduce it and reach the same conclusion or disagree with it.

**Nothing here is estimated or assumed.** Every number is copied from a run whose output
was seen. Where a value is an estimate from sampling rather than a full count, the entry
says so and gives the sampling parameters.

**No patient variant coordinates appear here.** Entries record counts, distributions and
classifications; the positions themselves stay in `~/ubuntu/work/`, per
[no patient data in the repository](../docs/notes/no-patient-data-in-the-repository.md).

## Environment

All runs below, unless stated otherwise:

| | |
|---|---|
| Machine | 12 cores, 15 GB RAM, Linux 6.6.87.2-microsoft-standard-WSL2 |
| Date | 2026-08-28 |
| Data | `~/ubuntu/data/`, 10 files, 80 GiB, unmodified |
| bcftools / samtools / htslib | 1.24 (micromamba, conda-forge + bioconda) |
| fastp | 1.3.6 |
| Python | 3.12.3 |

Reproduce the environment with `tools/setup-env.sh`, then `source tools/activate.sh`.

## Entries

| # | Question |
|---|---|
| [001](001-vcf-provenance-and-structure.md) | What produced this VCF, and what is in its header? |
| [002](002-callset-quality-and-composition.md) | Is the callset trustworthy, and what is its composition? |
| [003](003-panel-gene-variant-counts.md) | How many variants sit in the MVA candidate genes? |
| [004](004-sex-and-aneuploidy-from-allele-balance.md) | What is the proband's sex, and is mosaic aneuploidy visible? |
| [005](005-fastq-structure-and-quality.md) | What are the raw reads, and what depth do they give? |
| [006](006-phasing-power-on-bub1b.md) | How much of the compound-het search space can phasing resolve? |
