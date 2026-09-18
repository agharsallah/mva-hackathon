# 116 — Entry 037 reported every autosome flat. What was that worth?

**Written:** 2026-09-18. **Step:** `step-8` (iteration 2).
**Hypotheses:** **H051 supported**, **H052 supported**, **H053 supported**.

**Supersedes [037](../../../step-0/methodology/037-baf-karyogram.md)** on one point and one
only: 037's conclusion that no mosaic aneuploidy is visible stands, but it was reached with a
statistic that has **no power for a mosaic gain**, so it was an untested claim rather than a
negative result. 037 is not edited; this entry replaces its conclusion with the same answer
plus the number that makes it a finding.

## Hypothesis and prediction

- **H051** — no chromosome in the sequenced sample carries a mosaic aneuploidy above its own
  detection limit. *Predicted:* every chromosome's fold-over deviation sits inside the fitted
  null, and each result is quoted with the smallest cell fraction its own data could have
  detected at 80 % power.
- **H052** — the detection limit is at most 10 % cell fraction for every autosome.
- **H053** — fold-over B-deviation detects a mosaic gain at a materially lower cell fraction
  than the mean B-allele fraction 037 used, on identical simulated sites. *Predicted:* the
  fold-over statistic's 80 %-power fraction is at least 1 percentage point below the mean
  statistic's on a majority of autosomes.

## What would refute them

- **H051** — one chromosome exceeds its own limit, reported with the estimated fraction, its
  interval and the winning model.
- **H052** — an autosome with a worse limit, named as a blind spot; no absence claim is made
  for it.
- **H053** — the two limits agree within 1 percentage point on most autosomes: 037 was not
  underpowered, and this step's contribution is confirmation rather than correction.

## Inputs

| Source | What was read | Version / receipt |
|---|---|---|
| derived | `results.it2_mosaic_sites`, `it2_mosaic_depth` — the three tables and the two constants | [115](115-the-callset-reduced-to-what-a-mosaic-model-needs.md) |
| method | fold-over B-deviation; Markello 2012's DANFIP relation for the fraction (PMID 22277120) | re-implemented in `mva.mosaic.bdev` |
| clinical | not read; see [115](115-the-callset-reduced-to-what-a-mosaic-model-needs.md) | — |

## Commands

```bash
uv run python tools/fit_it2_mosaic.py --stages bdev baseline limits
uv run python tools/render_it2_step8_figures.py
```

## Observed — why the mean was the wrong statistic

Add a third copy of a chromosome to a fraction *f* of cells. Each heterozygous site now reads
as one of two bands, `centre ± f/(2+f)`, in equal numbers. **Their mean is unchanged.** 037
averaged the B-allele fraction inside each megabase and found every autosome flat, which is
what a mosaic gain of any size would have produced.

Fold first — take `|BAF − centre|` at each site and average that — and the two bands land on
top of each other instead of cancelling. Both statistics were run through the identical
harness: each chromosome's own depth margin, the same beta-binomial over-dispersion, the same
grid of injected fractions, the only difference being the quantity averaged.

| Statistic | Reaches 80 % power on | Power at f = 0.01 → 0.30 (chr1) |
|---|---|---|
| fold-over `\|BAF − centre\|` | **24 of 24** contigs | 0.18 → 1.00 (1.00 from f = 0.03) |
| 037's mean B-allele fraction | **0 of 24** contigs | 0.05 → 0.22 |

The mean statistic is not weaker. It is **flat**: at f = 0.01 it sits at its nominal 0.05 and
the most it reaches anywhere on the grid is 0.23, at a 30 % cell fraction. It is scored
**two-sided**, the generous reading — a mosaic could have moved a mean either way and 037
would have reported either — and it still never approaches the line.

**H053 is supported**, and by a wider margin than it predicted: not "at least 1 percentage
point lower" but "the comparator has no limit at all".

## Observed — the detection limit, per chromosome

| Contigs | Smallest detectable cell fraction, 80 % power |
|---|---|
| chr1–chr6 | **2 %** |
| chr7–chr22 | **3 %** |
| chrX, chrY | 5 %, and the allele route cannot see them at all (below) |

**H052 is supported** with three to five times the margin it asked for. The limit tracks the
heterozygous-call count, which is what it should track: chr1 carries 212,628 calls and chr22
45,014.

## Observed — what the sample shows

Four contigs exceed the null built from the genome-wide over-dispersion:

| Contig | Bdev | null mean | reject above | z | calls | depth |
|---|---|---|---|---|---|---|
| chrY | 0.20197 | 0.08157 | 0.08280 | 161.5 | 7,007 | 78.0× |
| chr21 | 0.10034 | 0.07797 | 0.07842 | 82.5 | 46,876 | 61.7× |
| chr22 | 0.09812 | 0.07911 | 0.07958 | 67.6 | 45,014 | 56.0× |
| chrX | 0.11148 | 0.08851 | 0.08987 | 27.9 | 6,729 | 38.8× |

**None of these is evidence of mosaicism, and the reason is in the same table.** X and Y are
hemizygous in this male proband: their heterozygous calls are mapping artefacts rather than
biology, which the density table states independently — chrXq carries 0.018 heterozygous
calls per PASS call against 0.57–0.62 on the autosomes. chr21 and chr22 are acrocentric, and
their own fitted over-dispersion is **4.15×** and **3.74×** the genome-wide value the null
was built from; a contig dispersed by its own repeats exceeds a genome-wide null without any
allele imbalance at all. Every autosome that is not acrocentric sits **below** its null —
chr4 at z = −78.0, chr5 at −74.3 — because the shared ρ is a compromise no single contig
matches.

**H051 is supported**: no chromosome carries a mosaic aneuploidy above its own detection
limit, and the limit is 2–3 % of cells on every autosome.

## Observed — the published fraction estimator, and its bias

Markello 2012's DANFIP relation, `f = (2·BAF − 1)/(1 − BAF)` on the sites above the centre,
was designed for dense SNP arrays where a site's allele balance is precise. At 44× it is not:
the spread of a *balanced* site is already wider than the band separation a 10 % mosaic
creates, so "the sites above the centre" is mostly the upper half of the noise.

| Contig | DANFIP as published | the same estimator on null draws | corrected |
|---|---|---|---|
| chr1 | 0.30443 | 0.35317 | **0.0** |
| chr21 | 0.35724 | 0.33327 | **0.024** [0.020, 0.028] |

The raw number reads 0.30–0.44 on contigs with nothing wrong with them. Running the identical
estimator on null draws from the same depths and subtracting is what makes it usable, and the
gap between the two columns is a result about the instrument rather than about the child.

## Assumptions, limitations and quality checks

- **The null is conservative for most contigs and anticonservative for none.** ρ is
  genome-wide, so a contig with less dispersion than the genome is judged against a wider
  null than it deserves — it can only fail to reject. That is the safe direction for a
  negative result, and it is why the *positive* rejections above are read against each
  contig's own fitted ρ rather than accepted.
- **The null is computed, not simulated.** The statistic is an average over tens of thousands
  of independent sites, so its distribution is Gaussian with moments available in closed form.
  `tests/test_mosaic_moments.py` asserts the closed form agrees with a Monte Carlo at three
  depths and two over-dispersions — on 50,000 sites at 44× the two give mean 0.082189 against
  0.082169 and a 95th percentile of 0.082643 against 0.082580, in 0.1 ms against 2.3 s.
- **Sites on one arm are not perfectly independent.** A read spanning two nearby heterozygous
  calls correlates them, which inflates the true variance slightly; the fitted ρ absorbs that,
  and the direction is stated rather than assumed away.
- **The depth baseline is stable.** The leave-one-chromosome-out median is 42.42× with a
  bootstrap interval of [42.30, 42.64] and **no chromosome's exclusion moves it outside**
  (H055's condition, settled in [118](118-the-baseline-and-what-a-variegated-genome-does-to-it.md)).
  The spread of the per-chromosome depth ratio across autosomes is ±1.19 %, which is the
  precision floor below which a depth shift is not evidence of anything. chrX sits at 0.5225×
  and chrY at 1.5794× — the expected result for a male, and the check that the depth route
  works at all.
- **Every result is "in the sequenced sample".** The delivery does not say which tissue was
  sequenced; a karyotype's aneuploid fraction is measured in cultured cells. No fraction here
  is read as a severity statement, and the clinical document lists no term that would predict
  one.

## Conclusion

037's answer was right and its evidence was not. The same callset, tested with a statistic
that has power, still shows no mosaic aneuploidy on any autosome — and now that sentence has
a number attached: **an event present in 2–3 % of the sequenced cells would have been found
on every autosome, 8 times in 10.** The statistic 037 used would not have found one at 30 %.

The four contigs above their null are the two hemizygous ones and the two acrocentrics, each
with its own fitted over-dispersion 2.6–11× the genome's, and each identified as repeat
content by a second column rather than by judgement.
