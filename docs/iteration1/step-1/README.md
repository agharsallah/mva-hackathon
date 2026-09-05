# Step 1 — Normalize the callset

**Standing:** open. H008 filed and tested 2026-09-05 ([073](methodology/073-normalization-of-the-candidates.md)); the normalization seam is still not a pipeline stage.
Everything below is the plan for the step, not a result. The method this step follows is
[`../method.md`](../../method.md); the sequencing argument is [`../roadmap.md`](../../roadmap.md)
§1. Last checked 2026-09-04.

---

## The goal

> **Does every variant in the callset have exactly one spelling, so that an
> exact-string-matching scorer can be trusted with an indel?**

This is the first *research* step. Step 0 built the platform; this is the first question
about the data whose answer is not known in advance.

## Why it comes first

The scorer matches a submitted variant against the answer key by **exact string equality**
on `(chrom, pos, ref, alt)`. An indel has more than one valid spelling — the same deletion
can be written at different positions with different flanking bases, and two tools that
agree on the biology can disagree on the text. Until the callset has one canonical spelling
per variant, every indel candidate is a coin flip against the scorer, and a correct answer
can score zero.

The delivered VCF also carries multiallelic sites (one record holding several alternate
alleles). A submission row names one alternate allele, so a multiallelic record has to be
split before it can be submitted at all. Counts for both are in
[`../../ideation/data-findings.md`](../../../ideation/data-findings.md).

## What it will take

```bash
# The reference must be the no-chr analysis set, matching the VCF's contigs.
# <scratch>/ is a gitignored local scratch dir, materialized from the warehouse via the
# reads/viz API — bcftools needs real file bytes regardless of the backing store.
bcftools norm -m -both -f GRCh38_no_chr.fa <scratch>/proband.vcf.gz \
  -Oz -o <scratch>/proband.norm.vcf.gz
bcftools index -t <scratch>/proband.norm.vcf.gz
```

Needs the reference FASTA (~3 GB) fetched first.

**It is also a code step.** Normalization currently happens outside the pipeline, which
makes "was this normalized?" a question answered by remembering which shell command was
run. It should become a tested seam so the answer is in code.

## The record

| | |
|---|---|
| Hypotheses | H008 — [`hypotheses/`](hypotheses/), written by `mva-science export` |
| Tests | [073](methodology/073-normalization-of-the-candidates.md) |
| Rendered | `figures/science-report.html` |

Opening the first claim:

```bash
uv run mva-science hypothesis-add --step step-1 \
    --statement '…' --prediction '…' --refuted-by '…'
```

The register refuses a claim with no refutation condition, so the sentence saying what
would prove this step wrong has to be written before the run — which is the whole point of
writing it down.

## What this step unblocks

Step 2 (annotate the callset) and step 4 (mine the suppressed calls) — the goals for both
are in [`../method.md`](../../method.md), the sequencing in [`../roadmap.md`](../../roadmap.md).
Both join against variant coordinates, and a join against two spellings of the same variant
silently loses rows.
