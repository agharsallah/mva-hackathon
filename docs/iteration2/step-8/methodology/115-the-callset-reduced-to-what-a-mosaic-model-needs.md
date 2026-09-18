# 115 — What does a mosaic model actually need from five million VCF rows?

**Written:** 2026-09-18. **Step:** `step-8` (iteration 2).
**Hypotheses:** none settled here. This is the input entry: it fixes the three tables every
later stage reads and the two constants they are all scored against. H051–H057 were filed
before it ran.

**Supersedes nothing.** It is the first entry of step 8. It does not supersede
[037](../../../step-0/methodology/037-baf-karyogram.md) either — that correction is
[116](116-the-statistic-that-has-power-and-the-limit-it-buys.md), and this entry is careful
to reproduce 037's parsing rules exactly so the two can be reconciled by a number.

## What this entry decides

Step 8 asks whether any chromosome in the sequenced sample is present in the wrong number of
copies in some of the cells. Every statistic that can answer it is a function of two things:
how the reads at a heterozygous call split between the two alleles, and how deep the reads
are. Neither needs a genomic position, and both are wanted **per chromosome arm** — a
mosaic event that takes one arm disappears into a whole-chromosome mean.

So the question this entry settles is: what is the smallest table that loses nothing a model
can see? The answer is a **sufficient statistic**. For any likelihood that treats an arm's
calls as exchangeable — binomial, beta-binomial, a mixture of either — the counts

```
(chromosome, arm, k alternate reads, n total reads) → how many calls
```

carry the entire likelihood. Two point eight million calls become 127,913 rows, every fit
becomes vectorised arithmetic over a small array, and **no genomic position is ever loaded**.
That is not a redaction applied afterwards: there is nothing on these rows to withhold.

The cost is stated where it is paid, here and on every page that quotes the result: **a
mosaic event confined to part of an arm is invisible to everything downstream.** Whole-arm
and whole-chromosome events are what is testable.

## Inputs

| Source | What was read | Version / receipt |
|---|---|---|
| callset | `warehouse.variants_raw` — the lossless all-text ingest layer, 5,012,204 rows | the delivered VCF ([data-findings §1](../../../../ideation/data-findings.md)) |
| reference | `warehouse.cytoband_arms` — 24 rows, the centromere span per contig | `tools/build_cytobands.py` from UCSC hg38 `cytoBand.txt.gz`, digest in `ressources/reference/cytoband_arms.provenance.json` |
| derived | `results.baf_bins` — the 1 Mb bins of entry 037, read only for the arm-geometry check | [037](../../../step-0/methodology/037-baf-karyogram.md) |
| clinical | **not read, and the absence is the point.** `Challenge_Clinical_Phenotype_1.md` lists no karyotype and no term a blood-DNA aneuploid fraction would predict, and the delivery never says which tissue was sequenced | [the clinical document](../../../../ressources/hackathon-rules/Challenge_Clinical_Phenotype_1.md) |

Step 8 names no candidate gene and is not blind; nothing here reads an iteration-1 table.

## Commands

```bash
uv run python tools/build_cytobands.py
uv run mva-warehouse stage
uv run mva-warehouse pg-ingest --tables cytoband_arms
uv run mva-warehouse pg-derive --only it2_mosaic_sites it2_mosaic_depth it2_mosaic_density
uv run python tools/fit_it2_mosaic.py --stages constants
```

## Observed — the three tables

| Table | Rows | What one row is |
|---|---|---|
| `results.it2_mosaic_sites` | 127,913 | a `(chrom, arm, k, n)` pair and how many heterozygous PASS calls showed it |
| `results.it2_mosaic_depth` | 11,867 | a depth and how many PASS calls — **all** of them, not only the heterozygous ones |
| `results.it2_mosaic_density` | 72 | an arm's heterozygous calls per megabase and per PASS call |

**The reconciliation gate passes exactly.** `sum(sites)` over `it2_mosaic_sites` is
**2,778,844** — the same number of surviving heterozygous calls entry 037 reported from the
same predicate (`PASS`, unphased `0/1`, exactly two allele depths, FORMAT located by key and
never by position). 037's derivation is frozen iteration-1 evidence and was deliberately not
edited to share code with this one; the two are tied together by that number instead.

**Depth needs its own table, and that is not tidiness.** Depth at a *heterozygous* call is
conditioned on that call existing. It is truncated at the low end, and the event most in need
of a depth signal — a monosomy — is exactly the one that removes heterozygous calls. The
negative-binomial half of the model reads `it2_mosaic_depth`, over every PASS call.

## Observed — the two constants, fitted once for the whole sample

| Constant | Value | Why it is not the nominal value |
|---|---|---|
| fold centre | **0.49300** | reads carrying the reference allele map slightly more readily, so a balanced site does not sit at 0.5. Folding around 0.5 would turn that constant offset into a constant deviation on every chromosome. 037 measured 0.4954–0.4984 per autosome from bin medians; this is the site-weighted mean over the pooled autosomal arms |
| over-dispersion ρ | **0.01620** | allele balance is wider than binomial. At ρ = 0 the model is binomial and every arm would be significant |

Fitted on 2,708,898 heterozygous calls at a mean depth of 43.85×, pooling the autosomal
**p and q arms only**: the centromeric rows are where allele balance is least trustworthy,
and X and Y are hemizygous in this male proband, so neither describes a balanced autosome.

ρ is fitted genome-wide and held fixed for every arm, deliberately. A genuinely mosaic arm
is exactly an arm whose spread is inflated, so fitting each arm's own null would absorb the
signal it is being tested for. (Model *selection* needs the opposite convention, and
[117](117-five-models-and-the-two-it-cannot-separate.md) says why.)

## Observed — the arm geometry, checked against the data

The committed centromere is reference geometry from UCSC. The check is where the
heterozygous calls actually stop, read off 037's own megabase bins: the widest run of bins
with no call. **All 24 contigs agree** under the rule finally used, which is *overlap* — and
arriving at that rule is itself a result:

| Rule tried | Failed on | Why the failure was the rule's, not the data's |
|---|---|---|
| midpoint distance ≤ 3 Mb | chr1, chr9, chr16 | constitutional heterochromatin sits beside the centromere and is equally callable-free, so the gap is the centromere *plus* that block and its midpoint is 5.7–11.1 Mb off |
| gap contains the centromere | chr5, chr19 | the calls do not vanish across the whole acen span; the observed gap is 1–2 Mb *inside* it |
| the two **overlap** (± 1 Mb) | none | what both correct cases share. A gap on the other arm would still fail |

The acrocentric contigs (13, 14, 15, 21, 22) are exempt by their own flag — their largest
gap is the short arm by construction — and X and Y by a hemizygous flag. Both exemptions are
read off a column, never from a list of five numbers.

## Assumptions, limitations and quality checks

- **Position is gone, so segmentation is gone.** A focal or sub-arm mosaic segment cannot be
  found by anything downstream of these tables. Pre-registered scope, restated at every use.
- **`het_per_mb` is not mappability-corrected.** An arm's callable fraction is unknown here,
  which is why the raw count and the per-PASS-call share travel beside it in the same table.
- **The centromeric rows are kept, not merged.** A call inside the centromere is labelled
  `cen` rather than pushed to one side, so a caller can exclude it; folding it silently into
  `p` would hide the least trustworthy sites in the most trusted column.
- **Every result here is "in the sequenced sample".** The delivery does not say which tissue
  was sequenced and a karyotype's aneuploid fraction is measured in cultured cells, so no
  number in this step is equated with the diagnosis or read as a severity statement.
- Lineage: each table carries a `warehouse.data_lineage` row naming `variants_raw` and
  `cytoband_arms`, written by `pg-derive` from the derivation's declared `depends_on`.

## Conclusion

The callset reduces to 127,913 + 11,867 + 72 rows that contain no genomic position and lose
nothing a model of allele balance or depth can see, and the reduction is verified against
037 by an exact count. The sample's own centre is 0.49300 and its own over-dispersion is
0.01620 — both measured, both held fixed, both printed beside every number that depends on
them. The arm geometry the tables are keyed on agrees with where the calls actually stop on
all 24 contigs, under a rule two stricter versions had to fail first to find.
