# 118 — Every bound here divides by something. What happens when the divisor is wrong?

**Written:** 2026-09-18. **Step:** `step-8` (iteration 2).
**Hypotheses:** **H055 supported**, **H056 supported**.

**Supersedes nothing.** It reports the two pre-registered defences against the failure mode
this disease is named for, and it is the entry that says whether the bounds in
[116](116-the-statistic-that-has-power-and-the-limit-it-buys.md) survive on a genome where
several chromosomes are abnormal at once.

## Hypothesis and prediction

- **H055** — the leave-one-chromosome-out baseline is stable: no chromosome's exclusion moves
  the genome-wide baseline beyond its bootstrap interval.
- **H056** — the mixing simulation recovers two and three simultaneously affected chromosomes
  at 10 % and 20 % cell fraction, **and does not flag the unaffected ones**. *Predicted:* every
  injected chromosome detected at 80 % power or better, and the false-positive rate among the
  untouched ones at or below the nominal 5 %.

## What would refute them

- **H055** — one chromosome's exclusion shifts the baseline beyond the interval, and every
  median-normalised route is flagged as under strain on this sample.
- **H056** — a design where recovery falls below 80 % power, or where untouched chromosomes
  are flagged above the nominal rate; reported as the bound's blind spot for exactly the
  multi-chromosome case the disease name describes.

## Inputs

| Source | What was read | Version / receipt |
|---|---|---|
| derived | `results.it2_mosaic_sites`, `it2_mosaic_depth` — the histograms every replicate redraws | [115](115-the-callset-reduced-to-what-a-mosaic-model-needs.md) |
| derived | the fitted centre 0.49300 and ρ 0.01620, refitted inside every replicate | [115](115-the-callset-reduced-to-what-a-mosaic-model-needs.md) |
| method | Kong 2018's own caveat: the model degrades when several chromosomes are abnormal at once | PMID 29773658, Discussion |

## Commands

```bash
uv run python tools/fit_it2_mosaic.py --stages baseline multi --replicates 30
```

## Observed — the depth baseline holds

| | |
|---|---|
| Leave-one-out baseline | **42.42×** |
| Bootstrap interval, 1,000 resamples at 95 % | [42.30, 42.64] |
| Widest excursion when one chromosome is held out | chr10 → 42.36×, chr1 → 42.48× |
| Chromosomes whose exclusion leaves the interval | **none** |
| Spread of the per-chromosome depth ratio across autosomes | **± 1.19 %** |

**H055 is supported.** The baseline is the median of the leave-one-out medians, so no single
contig can prop up its own denominator, and on this sample none of them comes close to moving
it. The ± 1.19 % is the number the five-model depth term is judged against — the precision
floor below which a depth shift is not evidence of anything — and it is measured here rather
than assumed. The check that the route works at all: chrX sits at 0.5225× and chrY at 1.5794×,
which is the expected result for a male proband.

## Observed — several chromosomes abnormal at once

Each replicate simulates **the whole genome**, refits the fold centre and the over-dispersion
from its own simulated autosomes exactly as a real run would, and then scores **every**
chromosome — injected and untouched alike — against a null built from those refitted values.
Thirty replicates per design, 22 autosomes scored each time.

| Injected | at f | Recovery of the injected | Untouched chromosomes flagged | refitted ρ |
|---|---|---|---|---|
| chr7 | 0.05 | **1.000** | 0.0048 | 0.01634 |
| chr7, chr18 | 0.05 | **1.000** | 0.0033 | 0.01639 |
| chr7, chr18, chr21 | 0.05 | **1.000** | 0.0035 | 0.01644 |
| chr7 | 0.10 | **1.000** | **0.0000** | 0.01671 |
| chr7, chr18 | 0.10 | **1.000** | **0.0000** | 0.01695 |
| chr7, chr18, chr21 | 0.10 | **1.000** | **0.0000** | 0.01715 |
| chr7 | 0.20 | **1.000** | **0.0000** | 0.01806 |
| chr7, chr18 | 0.20 | **1.000** | **0.0000** | 0.01893 |
| chr7, chr18, chr21 | 0.20 | **1.000** | **0.0000** | 0.01966 |

**H056 is supported**, on both arms and with room to spare: every injected chromosome is
recovered in every replicate, and the false-positive rate among untouched chromosomes is
0.0048 at worst against a nominal 0.05.

**Why the coupling is weak, stated rather than celebrated.** Each arm's null is built from its
*own* depth margin, so one chromosome's event cannot move another's threshold directly — which
would have made the false-positive rate 5 % by construction and the measurement worthless. The
only shared quantities are the two genome-wide constants, and the table's last column is what
they actually did: three chromosomes at a 20 % cell fraction move ρ from 0.01620 to 0.01966,
about a fifth, and the fold centre not at all (0.49300 → 0.49301). Three chromosomes out of
twenty-two is not enough of the genome to drag a median.

**That is a bound on this design, not a general reassurance.** The simulation injects up to
three; a genome with ten abnormal chromosomes was not tested and is not claimed. What the
result does say is that the pre-registered worry — a *variegated* genome poisoning its own
denominator — does not bite at the scale tested here.

## Assumptions, limitations and quality checks

- **Thirty replicates, not two hundred.** The plan asked for 200; each replicate redraws every
  autosome's heterozygous calls and refits ρ on a 127,913-row histogram, at ~95 s per design.
  Thirty gives a false-positive rate resolved to ~0.003 against a 0.05 threshold and every
  recall at exactly 1.000, so more replicates would have refined numbers that are not close to
  their thresholds. Recorded as a reduction, not as the plan's figure.
- **The false-positive rate is below nominal, which is the null being conservative.** ρ is
  genome-wide and most autosomes are less dispersed than the pool (116: chr4 at z = −78), so
  their thresholds sit further away than a per-chromosome null would put them. The direction
  is safe for a negative result and it is why the rejections in 116 are read against each
  contig's own ρ.
- **Only the allele-balance route was tested this way.** The dosage route's denominators —
  the autosomal median and the absolute k-mer mass — have the same shape of exposure and have
  not been simulated, because the pass has not run (H054).
- **The injected contigs were fixed, not sampled.** chr7, chr18 and chr21 span a large, a
  middle and a small chromosome, so the designs cover the site-count range rather than one
  point of it; they are not a random draw and the numbers are not an average over designs.

## Conclusion

Both defences hold on this sample. No chromosome's exclusion moves the depth baseline outside
its bootstrap interval, and the per-chromosome depth ratio varies by ± 1.19 %, which is the
precision floor everything downstream is judged against. Injecting up to three abnormal
chromosomes at once recovers every one of them in every replicate while flagging untouched
chromosomes at 0.0048 or less — because the only quantities the chromosomes share are two
genome-wide constants, and three contigs of twenty-two move ρ by about a fifth and the centre
not at all.

The bound of [116](116-the-statistic-that-has-power-and-the-limit-it-buys.md) therefore
survives the failure mode this disease is named for, **at the scale tested**: up to three
chromosomes, not ten.
