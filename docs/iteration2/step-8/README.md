# Step 8 — the mosaic aneuploidy bound

**Standing:** **partially complete, 2026-09-18.** Seven claims filed before the run;
**three settled so far — all three supported (H051, H052, H053)**, and H053 by a wider margin
than it predicted. Iteration 2, `step-8`. Contributes a mechanism fact and its limit to
[step 7](../step-7/README.md).

**Goal** (from `src/mva/science/steps.py`):

> Is mosaic aneuploidy detectable in the sequenced sample with a statistic that has power,
> and what cell-fraction bound does the data set per chromosome?

Design: [`plan.md`](../plan.md) §3 step 8, as revised by
[§11.8](../plan.md#118-step-8-revised--and-the-counting-kernel-it-needs).

## The headline

**Iteration 1's answer was right and its evidence was not.** Entry
[037](../../step-0/methodology/037-baf-karyogram.md) reported every autosome flat, using the
**mean** B-allele fraction per megabase. A mosaic gain splits heterozygous sites into two
bands symmetric about the centre, so their mean does not move — flat is what a gain of *any*
size would have produced.

Run through the identical harness on the same depth margins under the same over-dispersion:

| Statistic | Reaches 80 % power on | Power at f = 0.01 → 0.30 (chr1) |
|---|---|---|
| fold-over `\|BAF − centre\|` | **24 of 24** contigs | 0.18 → 1.00 |
| 037's mean B-allele fraction | **0 of 24** contigs | 0.05 → 0.22 |

So the negative result now carries the number that makes it one: **an event present in 2–3 %
of the sequenced cells would have been found on every autosome, eight times in ten.** The
statistic 037 used would not have found one at 30 %.

**Nothing is above its limit.** Four contigs exceed the null built from the genome-wide
over-dispersion, and none of them is mosaicism: X and Y are hemizygous in this male proband —
chrXq carries 0.018 heterozygous calls per PASS call against 0.57–0.62 on the autosomes — and
chr21 and chr22 are acrocentric, with their own fitted over-dispersion **4.15×** and **3.74×**
the genome-wide value the null was built from. Each is identified by a second column rather
than by judgement.

## Results

| | |
|---|---|
| Heterozygous calls reduced to | **127,913** `(chrom, arm, k, n)` rows, reconciled exactly against 037's 2,778,844 |
| Fold centre, measured | **0.49300** — not 0.5; reference reads map more readily |
| Over-dispersion ρ, measured | **0.01620** pooled; **0.0057 – 0.067** per chromosome, twelvefold |
| Detection limit, autosomes | **2 %** of cells (chr1–6), **3 %** (chr7–22) at 80 % power |
| Detection limit, X and Y | 5 %, and the allele route cannot see them at all |
| Depth baseline, leave-one-out | **42.42×** [42.30, 42.64]; **no chromosome's exclusion moves it** |
| Depth ratio, X / Y | 0.5225 / 1.5794 — the expected result for a male, and the check that depth works |
| Contigs above the genome-wide null | 4 — chrY, chr21, chr22, chrX; all explained by repeat content or hemizygosity |
| Autosomes above their own limit | **0** |

## Claims

| Id | Verdict | Conf. | Claim |
|---|---|---|---|
| [H051](hypotheses/h051-step-8.md) | **supported** | 0.80 | No chromosome carries a mosaic aneuploidy above its own detection limit |
| [H052](hypotheses/h052-step-8.md) | **supported** | 0.85 | The detection limit is ≤ 10 % cell fraction for every autosome |
| [H053](hypotheses/h053-step-8.md) | **supported** | 0.95 | Fold-over B-deviation detects at a materially lower fraction than 037's statistic |
| [H054](hypotheses/h054-step-8.md) | open | — | The k-mer dosage route and the allele-balance route agree per chromosome |
| [H055](hypotheses/h055-step-8.md) | open | — | The leave-one-chromosome-out baseline is stable |
| [H056](hypotheses/h056-step-8.md) | open | — | The mixing simulation recovers 2 and 3 affected chromosomes without flagging the rest |
| [H057](hypotheses/h057-step-8.md) | open | — | Mitotic and meiotic trisomy are not separable at ΔBIC ≥ 10 |

### Why the confidences are held down

H051 sits at 0.80 rather than higher for two stated blind spots, not out of caution: the
allele route cannot see X or Y in a male proband, and **position was aggregated away before
these tables existed**, so a sub-arm segment was never tested. H052 at 0.85 because a limit is
a property of the simulation's model of the data, and a real mosaic could be harder to see
than a beta-binomial at the fitted over-dispersion allows.

## What this step read

| From | Measured finding | Where used |
|---|---|---|
| the delivered callset | 2,778,844 heterozygous PASS calls, mean depth 43.85× | every statistic here |
| [037](../../step-0/methodology/037-baf-karyogram.md) | the 1 Mb bins, and the flat map this step re-tests | the arm-geometry check; the comparison |
| `ressources/reference/cytoband_arms.tsv` | the centromere span per contig, from UCSC hg38 | which arm each call sits on |
| the clinical document | **no karyotype, and no term a blood-DNA aneuploid fraction would predict** | stated wherever a fraction is quoted; never equated with the diagnosis |

## Methodology

| Entry | What it did |
|---|---|
| [115](methodology/115-the-callset-reduced-to-what-a-mosaic-model-needs.md) | the three tables, the two constants, and the arm geometry checked against the data |
| [116](methodology/116-the-statistic-that-has-power-and-the-limit-it-buys.md) | the fold-over statistic, the detection limit, and what 037's statistic was worth |

## How to reproduce it

```bash
uv run python tools/build_cytobands.py
uv run mva-warehouse stage && uv run mva-warehouse pg-ingest --tables cytoband_arms
uv run mva-warehouse pg-derive --only it2_mosaic_sites it2_mosaic_depth it2_mosaic_density
uv run python tools/fit_it2_mosaic.py --stages constants bdev baseline models limits multi
uv run mva-warehouse pg-load-it2-step8
uv run python tools/render_it2_step8_figures.py
uv run python tools/capture_step_fixture.py --step step-8
```

The dosage half needs the job service, and the pass is licensed by a timing probe first:

```bash
uv run python tools/build_it2_dosage_probes.py          # prints the projection before anything runs
uv run python tools/run_it2_dosage_pass.py --shards 2   # measure the per-shard cost today
uv run python tools/run_it2_dosage_pass.py --upload --full
```

## What this step cannot tell you

- **Which tissue this is.** Neither the clinical document nor the delivery says what was
  sequenced, and a karyotype's aneuploid fraction is measured in cultured cells. Every result
  is "in the sequenced sample", never equated with the diagnosis and never read as a severity
  statement.
- **Where an event is.** The tables were aggregated to chromosome and arm before they existed,
  so a mosaic confined to part of an arm is invisible. Whole-arm and whole-chromosome events
  are what is testable, and that was the pre-registered scope.
- **Anything about X or Y from allele balance.** One copy means no heterozygous sites to be
  unbalanced. Only dosage can see those contigs, and that route is open (H054).
- **Which trisomy.** Mitotic and meiotic trisomy are nested models — the second is the first
  plus a balanced tract — so their margin is bounded below by one BIC penalty and a trisomy
  can be led but never confidently called.

## Exhibits

`/steps/step-8` on the dashboard, and the re-test panel on `/genome` beside the karyogram it
corrects. Figures in [`figures/track1/iteration2/step-8/`](../../../figures/track1/iteration2/step-8/):
`power-then-and-now` (the headline), `detection-limit`, `bdev-per-chromosome`,
`depth-against-baseline`, `model-margins`, `heterozygous-density`.
