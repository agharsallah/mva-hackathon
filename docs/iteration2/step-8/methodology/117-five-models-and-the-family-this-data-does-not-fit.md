# 117 — Five models per chromosome. Which mechanism does the data name?

**Written:** 2026-09-18. **Step:** `step-8` (iteration 2).
**Hypotheses:** **H057 supported**, and by a stronger route than it predicted.

**Supersedes nothing.** It reports the second half of the allele-balance route: after
[116](116-the-statistic-that-has-power-and-the-limit-it-buys.md) established that no
chromosome exceeds its own limit, this asks whether the five-model comparison can name a
mechanism anywhere — and answers no, for a reason worth more than the answer.

## Hypothesis and prediction

**H057** — mitotic and meiotic trisomy are not separable at ΔBIC ≥ 10 from arm-stratified
allele-fraction band structure at cell fractions up to 20 %, at this sample's depth and
heterozygous-site counts. *Predicted:* on simulated trisomies injected at 5, 10 and 20 %, the
comparison assigns the correct mechanism at ΔBIC ≥ 10 in fewer than half the replicates, so
the mechanism is reported as not identifiable rather than called.

## What would refute it

The comparison separates the two at ΔBIC ≥ 10 in a majority of replicates — the mechanism
call is then a real measurement and goes to step 7's Track 2 card.

## Inputs

| Source | What was read | Version / receipt |
|---|---|---|
| derived | `results.it2_mosaic_sites`, `it2_mosaic_depth` | [115](115-the-callset-reduced-to-what-a-mosaic-model-needs.md) |
| derived | the leave-one-out depth baseline, 42.42× ± 1.19 % | [116](116-the-statistic-that-has-power-and-the-limit-it-buys.md) |
| method | Kong 2018's five-model comparison (PMID 29773658), re-implemented from the paper | `mva.mosaic.models`, `mva.mosaic.madseq` |

## Commands

```bash
uv run python tools/fit_it2_mosaic.py --stages models
uv run python tools/fit_it2_mosaic.py --stages verdicts   # re-decide, without refitting
uv run pytest tests/test_mosaic_models.py -q
```

## Observed — on simulation, the implementation works and its limits are three

At 8,000 simulated sites at 44× with ρ = 0.02 (`tests/test_mosaic_models.py`):

| Injected | Leading model | ΔBIC | fitted fraction |
|---|---|---|---|
| normal | normal | 9.0 | — |
| mitotic trisomy 20 % | mitotic trisomy | 9.0 | 0.202 |
| mitotic trisomy 30 % | mitotic trisomy | 7.2 | 0.298 |
| copy-neutral LOH 20 % | **cnloh, called** | 25.0 | 0.201 |
| monosomy 20 % | **monosomy, called** | 16.3 | 0.201 |
| meiotic trisomy 30 %, tract 0.5 | meiotic trisomy | 1.2 | 0.300 |

Three limits, each now an assertion rather than a hope:

1. **Below about 15 % a mixture is absorbed by a single wider band.** With the
   over-dispersion fitted per chromosome, a two-band mixture and one wider band are nearly
   the same distribution and the simpler wins on the penalty. That is the identifiability
   floor of *model selection* — and it is why 116's detection limit reaches 2–3 %: that test
   compares against a null fitted **outside** the family, which a nested comparison cannot do.
2. **Mitotic and meiotic trisomy are nested**, so their margin is bounded below by one BIC
   penalty. **H057 is supported**: across injected fractions 0.20 and 0.30 at two tract sizes,
   the comparison never assigns the mechanism at ΔBIC ≥ 10.
3. **A trisomy is therefore led but never confidently called.** The `call` column says
   *not distinguishable*, and the page renders that column rather than the ranking.

## Observed — on the real callset, the family does not fit at all

The comparison put `meiotic_trisomy` first on **21 of 24 contigs**, at ΔBIC from 10.2 to
3,122 and fitted cell fractions of 0.20 to 0.65. None of it is credible, and the evidence is
measured rather than argued:

| Diagnostic | Value |
|---|---|
| Spearman(fitted cell fraction, fitted noise share), autosomes | **0.938** |
| Spearman(ΔBIC, fitted noise share) | 0.874 |
| Spearman(fold-over Bdev z, fitted noise share) | 0.913 |
| Winning fits with the balanced tract pinned at its bound (0.900) | **every autosomal non-normal call** |
| Winning fits with the over-dispersion driven to zero | 13 of 19 |

The fitted "cell fraction" is a function of the tail burden. And **every** winning fit sits
against a bound: the optimiser reporting *as much as you let me*, which says the shape the
data wants is outside the family rather than inside it at that value.

Why the family loses: real allele balance is not a beta-binomial. A few per cent of
heterozygous calls come from collapsed repeats, unflagged copy number, or one allele mapping
better than the other, and at 45,000–226,000 calls per contig that mis-specification is worth
thousands of BIC units. The most flexible member of the family takes them all. A shared noise
component was added for exactly this reason and it was not enough — it moved the problem from
"which model has a spare parameter" to "which model has a spare *band*".

`Verdict.degenerate` now checks every parameter the winning model actually fits, and the
verdict for this sample is:

| Call | Contigs |
|---|---|
| **model family not usable** | 19 |
| **not measurable** (noise share past the 10 % ceiling) | 3 — chr21 (0.244), chr22 (0.226), chrX (0.170) |
| normal | 1 — chr18 |
| `meiotic_trisomy` | 1 — **chrY**, and see below |

**chrY is the one contig the gate lets through, and it is exactly the one this route cannot
see.** The proband is male: chrY's heterozygous calls are mapping artefacts, not biology —
the density table gives chrXq 0.018 heterozygous calls per PASS call against 0.57–0.62 on the
autosomes — so a "meiotic trisomy at 70 % of cells" there is a model fitted to noise, not a
finding. It is left in the table rather than suppressed, because a gate that silently deleted
the row would hide that the family will happily fit anything. The pre-registered position
stands and is repeated everywhere the number appears: **no allele-balance result applies to X
or Y in this proband.**

**chr18 is the one contig the family fits, and it fits it entirely in the interior**:
ρ = 0.00321, tract 0, noise 0.019, no parameter near a bound. The family can describe exactly
one chromosome of this genome, and it is the one it calls normal.

## Assumptions, limitations and quality checks

- **No mechanism is reported for any chromosome.** §4b's gate said "no ΔBIC < 10 call is
  reported as a mechanism"; that rule as written would have passed these margins, which are
  enormous. The stronger rule the data forced — a fit at a bound is not an estimate — is
  recorded here as a revision of that gate, and it is what the `call` column implements.
- **This does not weaken 116.** The allele-balance test compares an arm against a null fitted
  from *other* chromosomes, so a family that cannot describe the shape of the data is not the
  instrument being used there. The two routes fail in opposite directions, which is why both
  are reported.
- **MCMC was not the difference.** Kong 2018 fits by sampling and this is bounded maximum
  likelihood, a stated simplification — but a sampler would have found the same boundary
  region, because the likelihood is what puts it there. The simplification is not what failed.
- **Kong 2018's > 99 % sensitivity at 5 % fraction is a simulation figure** (2,000 het sites,
  100×), as the plan said to quote it. This entry reproduces the simulation behaviour and then
  reports what happens on real data, which is the comparison the figure cannot make.
- **Re-deciding is not re-measuring.** The rule for reading the fits changed twice after the
  hour-long fitting stage had run. The `verdicts` stage re-decides from the fits on disk, so
  no number was re-measured in order to be re-interpreted.

## Conclusion

The re-implementation reproduces Kong 2018's behaviour on simulated data — copy-neutral loss
of heterozygosity and monosomy are called outright at 20 %, the fitted fraction recovers an
injected one to within 0.002 — and on this callset the five-model family **does not fit at
all**. Nineteen of twenty-four contigs end at a parameter bound, the fitted fraction tracks the
tail burden at Spearman 0.94, and the single contig fitted in the interior is the one called
normal.

So step 8 names **no mechanism on any chromosome**, and the reason is a property of the model
family against this data rather than a property of the child. H057 is supported on its own
pre-registered simulation test, and the real-data finding is stronger than the claim it was
filed against: the two trisomies are not merely inseparable from each other here — no member
of the family is usable.
