# 096 — At what multiplicity do the reads carry these alleles, with no aligner and no caller?

**Written:** 2026-09-13. **Step:** `step-3` (iteration 2).
**Hypotheses:** H024, H025, H027, H028, H029 — all five filed before the run, all five
settled here. H026 (copy number) is [097](097-copy-number-without-an-aligner.md).

**Supersedes nothing.** It revises downward what
[090](../../step-2/methodology/090-the-alleles-the-vendor-never-reported.md) could establish
about the 1,199 vendor-unreported alleles, which is what that entry said step 3 would do.

## Inputs

| Source | What was read | Version / receipt |
|---|---|---|
| derived | `build/it2/step-3/probe-counts.npz` — 381,510 probe pairs counted in 15.8 M reads | [095](095-the-probes-and-the-counting-kernel.md) |
| derived | `build/it2/step-3/alleles.tsv` — 164,044 alleles and their sources | [095](095-the-probes-and-the-counting-kernel.md) |
| derived | `results.it2_mapq_profile` — the reachability gate | [093](093-where-the-aligner-was-unsure.md) |
| derived | `results.it2_read_alleles` — what step 2's callers spelled, for the comparison | entry 088 |
| clinical | indirectly, through step 1's target set | [084](../../step-1/methodology/084-the-blind-target-set.md) |

No iteration-1 candidate table was opened. The gene the comparison happens to concentrate on
was nominated by step 2's own blind output (`results.it2_scored_pairs`), not read from
iteration 1.

## Commands

```
uv run python tools/fit_it2_genotypes.py
uv run python tools/export_it2_step3_tables.py
uv run mva-warehouse pg-load-it2-step3
uv run mva-warehouse pg-derive --only it2_kmer_confirmation
uv run mva-warehouse pg-derive --only it2_kmer_reach
uv run mva-warehouse pg-derive --only it2_kmer_pairs
```

## Observed — the fitted model

Fitted on 7,223 heterozygous and 7,481 homozygous-alternate calibration markers from the
delivered callset, all inside the baited intervals, all with a full probe set.

| | |
|---|---|
| per-copy coverage λ (alternate side) | **17.96** |
| the same from the reference side | 18.97 — a 5.6 % gap |
| implied diploid depth | **35.93×** |
| variance-to-mean ratio | **2.91** (Poisson predicts 1) |
| dispersion | 4.68 |
| fitted error rate | 0.000247 |
| minimum alternate count for "present" (p < 10⁻³) | 2 |

**The λ check is the one that licenses the rest.** 35.93× against the 44.08× the baited
alignment measured looks like a 19 % shortfall and is not one: a k-mer is only seen when a
read contains it *whole*, so the expected k-mer depth is `depth × (L − k + 1) / L` =
44.08 × 119/149 = **35.2×**. The fit landed within 2 % of a number computed from the read
length and nothing else. Two instruments, one quantity, agreeing — and it was predicted
before it was measured, in the method survey's own arithmetic.

**Over-dispersion is real and is the reason for the model.** A variance-to-mean ratio of
2.91 means a Poisson model would be roughly three times too confident about every count it
saw, which is exactly the failure mode that turns a thin gene into a false deletion.

## Observed — what the alleles are

164,044 alleles: 20,231 heterozygous, 13,098 homozygous-alternate, 57,648 homozygous-
reference, **73,067 no-calls**. The no-calls are overwhelmingly ClinVar alleles that could
not be given three usable probes; a no-call is an answer here, not a gap.

### H027 — the claim with the most leverage, and it is refuted

Confirmation means: the model put ≥ 0.95 on the same class the caller spelled, with a full
probe set. Split by whether the delivered callset had ever reported the allele.

| Tier | Vendor **reported** | Vendor **never reported** |
|---|---|---|
| core | **0.910** (81/89) | **0.327** (17/52) |
| mechanism-term | **0.954** (83/87) | **0.432** (16/37) |
| net | **0.972** (481/495) | **0.347** (107/308) |
| decoy | **0.948** (754/795) | **0.319** (123/386) |

**H027 said ≥ 80 % of the 1,199 would be confirmed. 27–43 % were.** Refuted, and not
narrowly.

The left-hand column is what makes the right-hand one mean something. The same instrument,
in the same run, over the same genes, confirms 91–97 % of the alleles the vendor's pipeline
*did* report. So the instrument works, and roughly **two thirds of the 1,199 are not
corroborated by a method that shares neither the aligner nor the caller that produced
them**. The pre-registered consequence stands: every step-2 biallelic count that rested on
those alleles is an upper bound, and the read route now carries a measured per-allele error
rate instead of a caveat.

### H024 — refuted at 87.5 %

Of 518 fully-probed step-2 heterozygous calls in reachable target-set genes: **453**
confirmed heterozygous at posterior ≥ 0.95 with all three probes agreeing, **38**
contradicted, **11** no-calls. The claim said *every* one. 87.5 % is a good agreement rate
and is not "every"; the 65 that disagree are the step's most useful output and go to step 6
as measurement, not as noise.

### H025 — supported by one allele, not five

Five ClinVar pathogenic or likely-pathogenic alleles of reachable target genes clear the
fitted error threshold with three agreeing probes. Their allele balance says they are not
five findings:

| Gene | Tier | ref / alt | alternate fraction | called by a caller? |
|---|---|---|---|---|
| `BUB1B` | core | 18 / 16 | **0.471** | yes, 0/1 |
| `FANCA` | mechanism-term | 20 / 2 | 0.091 | no |
| `NBN` | mechanism-term | 31 / 3 | 0.088 | no |
| `ABCC6` | core | 31 / 2 | 0.061 | no |
| `BARD1` | net | 31 / 2 | 0.061 | no |

Exactly one has the balance of a heterozygote, and it is the only one any caller reported.
**The other four are an artefact of the fitted error rate**: at 0.000247 the model expects
0.0089 alternate counts at a homozygous-reference site, so an observed 2 is already
improbable enough to push the posterior onto *het* even when the ratio is a tenth of what a
heterozygote looks like. The claim's letter is met; its spirit is met once. Recorded as a
limitation rather than repaired after the fact — changing the rule now would be choosing it
after seeing the data.

### H028 — supported

The top-ranked biallelic candidate pair step 2 discovered, typed with no aligner and no
caller:

| Allele | Probes | Agreeing | ref / alt | Call | Posterior |
|---|---|---|---|---|---|
| 1 | 3 | 3 | 11 / 12 | **het** | 1.0 |
| 2 | 3 | 3 | 18 / 16 | **het** | 1.0 |

Both at **one copy**, balanced, unanimous across probes. Phasing this pair is impossible
(entry 088: 10,911 bp apart, ~266 bp fragments), so this is the strongest remaining
statement about it — and a caller artefact would not produce two balanced single-copy
dosages. **It is not trans evidence** and this entry does not offer it as any.

### H029 — refuted, and the rule survives as a conservative one

| Genes | Alleles | Confident calls | Rate |
|---|---|---|---|
| 771 reachable | 89,504 | 53,352 | **0.596** |
| 20 excluded (sparse bait) | 1,222 | 215 | **0.176** |
| 1 excluded (sparse bait + aligner refused) | 0 | 0 | — |

The claim said an excluded gene yields *no* confident genotype. It yields 215. Refuted — but
the gate is 3.4× enriched for callable alleles, so it is reported as conservative rather
than dropped, and an absence inside an excluded gene is still not a finding.

## A defect found and fixed before any of this was believed

The first run raised `RuntimeWarning: invalid value encountered in subtract` inside the
posterior normalisation. Chasing it found a real fault: an allele's count is the **median**
over its probes, and the median of an *even* number of probes is `x.5`. The negative
binomial is a distribution over counts and gives a fractional value zero probability under
every class at once, so all three log-likelihoods tied at `-inf`, the max-subtraction
produced `NaN`, and `argmax` read `NaN` as class 0 — **homozygous reference**.

**22,475 alleles (13.7 %) were affected.** Two fixes, at different levels: the per-allele
statistic is rounded to a whole number because it is a count, and `posteriors` now returns a
flat distribution for a row where every class is impossible, which fails any floor and is
reported as a no-call. Both carry the reason inline and both have regression tests.

**It changed none of the numbers above, and that was checked rather than assumed**: every
one of the 22,475 had one or two surviving probes, below the three-probe floor, so all were
already no-calls. It is recorded because it was latent, not harmless — the first time anyone
lowered the probe floor it would have produced thousands of silent homozygous-reference
calls with no warning a reader would see.

## Assumptions, limitations and quality checks

* **Class priors are uniform, and that is a choice.** A population prior is right for a
  genome scan and wrong here: every allele typed was already nominated by an aligner and a
  caller or by a public catalogue, so the question is not "what is a random site".
* **The error rate is fitted too tight**, as H025 shows. It is the systematic miscounting
  rate between a marker's two probes, and it does not model contamination or an
  occasional mismapped read. A future step wanting "present/absent" for published alleles
  should add an allele-balance requirement — pre-registered, not chosen after the fact.
* **The 5.6 % gap between the two λ estimates is reference bias**, small and reported. The
  fit was not retired for it: the gap is well inside the spread of the calibration markers.
* **Reachability travels with every call** and is in `results.it2_kmer_genotypes`, so an
  absence is never quoted without the reason an absence is possible.
* **Targets and decoys went through identical rules.** Their confirmation rates are the same
  to within a few points in both columns, which is consistent with H020's refutation: the
  read route has no discriminating power of its own, and step 3 does not give it any.
* **Unfiltered biallelic counts still favour the decoys** (core 0.237, decoy 0.258, net
  0.265) — the trap step 3's README named. Quoted here only to say the filter is where the
  discrimination lives, exactly as in step 2.
* **No coordinate and no sequence leaves `build/`.** `tools/check_coordinates.py` passes.

## What this hands on

* The read route's measured error: **~1 in 3 vendor-unreported alleles corroborated, ~19 in
  20 vendor-reported ones**. Step 6 weights it with these numbers rather than a band.
* The lead pair at **one copy each**, which is the strongest dosage statement available for
  a pair that cannot be phased — and explicitly not phase evidence.
* A revised reading of step 2: its biallelic counts that rested on vendor-unreported alleles
  are upper bounds, and `results.it2_kmer_pairs` holds the confirmed-only recount.
