# 121 — The second instrument, and the shards it did not need

**Written:** 2026-09-19. **Step:** `step-8` (iteration 2).
**Hypotheses:** **H054** — verdict below.

**Supersedes nothing.** It is the second of step 8's two routes to the same question. Entry
[116](116-the-statistic-that-has-power-and-the-limit-it-buys.md) asked the **reads that were
already called** whether any chromosome is present in the wrong number of copies, by the shape
of the allele balance at heterozygous sites. This entry asks the **raw reads**, by counting
how much sequence each chromosome contributed — a measurement that shares no step, no file and
no failure mode with the first past the FASTQ.

That independence is the point. A dosage route sees a chromosome the allele route is blind to
(X and Y in a male proband have almost no heterozygous sites, entry
[116](116-the-statistic-that-has-power-and-the-limit-it-buys.md)); the allele route sees an
event the dosage route is blind to (copy-neutral loss of heterozygosity — two copies, wrong
parents — moves no sequence at all). Where both can see, they must agree, and H054 is that
claim.

## Hypothesis and prediction

- **H054** — the k-mer dosage route and the VCF allele-balance route agree on every chromosome
  within their stated intervals. *Predicted:* for each chromosome the dosage bootstrap interval
  and the allele-balance estimate either overlap, or both are consistent with no event.

## What would refute it

- A chromosome where the two intervals do not overlap. The step then names **which instrument
  is wrong and why** — it does not average them. Two instruments that disagree are one
  measurement and one bug, and reporting their mean hides both.

## Inputs

| Source | What was read | Version / receipt |
|---|---|---|
| raw | the 272-shard read store, 1,071,835,104 reads | `ideation/data-findings.md` |
| reference | GRCh38 primary contigs, for the probe set only — no patient sequence enters the design | `mva.kmer.fasta` |
| derived | the allele-balance estimates and intervals this route is compared against | [116](116-the-statistic-that-has-power-and-the-limit-it-buys.md) |
| clinical | 8 HPO terms; no karyotype, no term a blood aneuploidy fraction would predict | `ressources/hackathon-rules/Challenge_Clinical_Phenotype_1.md` |

## Method

**The probe set.** A *k-mer* is a fixed-length window of sequence; here k = 31. For each
chromosome the build draws 10,000 candidate 31-mers from the reference and keeps only those
that occur **exactly once in the whole genome** — a window that also appears on chromosome 7
cannot testify about chromosome 3. 249,599 candidates were considered and **201,028
memberships over 193,029 distinct 31-mers** survived, 7,330–8,699 per contig (chrY 4,787,
which is short and repetitive) plus a 7,999-mer genome-wide **calibration** set.

Memberships exceed distinct k-mers because the calibration set is drawn from the same pool, so
~8,000 windows belong to two groups. The uploaded array holds each window once — that is what
a lookup structure can hold — and `mva.kmer.dosage` maps the design onto it by `searchsorted`.

**The measurement.** Every read in the store is scanned for every probe, and each probe's hits
are tallied. A chromosome present in more copies contributed more sequence, so its probes are
hit more often, in proportion. At 44× depth each probe expects ~22 hits.

**Two denominators, deliberately.** A dosage is a ratio and a ratio needs a divisor:

| Denominator | What it assumes | Why it is here |
|---|---|---|
| autosomal median | most autosomes are normal | the standard normalisation, and the one entry [118](118-the-baseline-and-what-a-variegated-genome-does-to-it.md) stress-tested |
| absolute k-mer mass | nothing — the total sequence observed is the scale | *variegated* means several chromosomes abnormal at once, which is exactly when a median denominator fails |

Both are reported. Where they disagree the disagreement is its own column, not a footnote.

## The shards it did not need

The full pass is 272 shards. Two timing probes were run against the live service before
committing to it, and they priced it very differently from the projection:

| Job | Shards | Workers | Wall clock | Per shard | Full pass |
|---|---|---|---|---|---|
| `272ceb9bc7e2` | 2 | 2 | 416.6 s | 208 s | 15.8 h |
| `0ff66d495fe0` | 4 | 8 | 500 s | 125 s | 9.4 h |

Four times the workers bought 1.66×, not 4×: the pass is bound by reading shards, not by
tallying them. The tool's own guard fired and refused to write a dosage from a partial count —
correctly, and it is the guard that made the next step visible rather than blocking it.

The projection the probe build printed said 49.9 min. It was wrong by an order of magnitude,
and the reason is worth recording: `SECONDS_PER_SHARD` held 11.0 s, measured under step 2's
**bait** sweep. A bait sweep asks whether a read contains *any* probe, so it strides one window
in sixteen; a tally needs each probe's *multiplicity*, so it reads all ~477 M windows per
shard. Same store, same reads, sixteen times the work. **A constant measured under one verb
does not transfer to another** — the constant is now the measured counting figure, and its
docstring says which verb measured it.

**The way out was the shard boundary.** Shards are **flowcell partitions** — lane and read
number — not genomic ones. Any subset of them is therefore a *uniform sample of the library
with respect to the genome*: no chromosome is over- or under-represented in shard 7. Dosage is
a **ratio between chromosomes**, and a uniform thinning multiplies every chromosome's expected
count by the same factor, so the ratio is **unbiased** and only its variance rises. The cost
of thinning is precision, and precision is something this measurement has to spare:

```
subsample 11.6 % of reads -> 2.56 observations per probe
per contig 20,451 observations -> relative standard error 0.70 %
a 10 % mosaic trisomy shifts dosage 5 %  ->  7.2 sigma
```

| Shards | Wall clock | Observations / contig | Relative SE | Sigma against a 10 % trisomy |
|---|---|---|---|---|
| 16 | 33 min | 10,353 | 0.98 % | 5.1 |
| **32** | **67 min** | **20,706** | **0.69 %** | **7.2** |
| 64 | 133 min | 41,412 | 0.49 % | 10.2 |
| 272 † | 9.4 h | 176,000 | 0.24 % | 21 |

† The first three rows are what the sizing tool printed. The 272-shard row is arithmetic from the same measured inputs (22 hits per probe at full depth, ~8,000 probes per contig) — the full pass was never run, and this entry does not claim it was.

32 shards were run. Going to the full 272 would buy 21 σ instead of 7.2 σ against an effect
the step only needs to *bound*, for eight more hours — precision that changes no conclusion.

**This argument does not transfer to genotyping.** `mva.kmer.count` needs absolute
multiplicity at one site, where a thinned count is simply wrong, which is why that module's own
docstring says a sampled count is not a count. The difference is the ratio: a thinning that
cancels in a quotient does not cancel in a value. `--subsample N` is a separate flag from
`--shards N` for exactly this reason — the latter still means "timing probe" and still refuses
to write a dosage — and the thinning fraction is recorded in `dosage.json` and on every row.

## Commands

```bash
uv run python tools/build_it2_dosage_probes.py --reuse-filter     # the probe set
uv run python tools/run_it2_dosage_pass.py --upload --shards 4 --workers 8   # timing probe
uv run python tools/run_it2_dosage_pass.py --subsample 32 --workers 8        # the pass
uv run mva-warehouse pg-load-it2-step8
```

```bash
uv run python tools/analyse_it2_dosage.py     # composition, robustness, the table
```

## Observed

**The pass.** 32 shards, 8 workers, 124,544,402 reads, 14,819,092,635 windows, 2,803.8 s
(46.7 min). 183,893 of 193,029 probes were seen; 9,136 (4.7 %) never were. Mean 4.4853 hits
per probe.

**It reproduces exactly.** The pass was run a second time — the first discarded its count
array, which is a tool flaw now fixed — and every published number came back identical:
`mean_count` 4.4853, `silent` 9,136, and all 24 dosages to four decimals. Two independent
47- and 50-minute passes over the same 32 shards agree bit for bit.

**The sex chromosomes are the positive control.**

| Contig | Dosage (÷ autosomal median) | Interval | Expected in a male proband |
|---|---|---|---|
| X | **0.4873** | [0.4790, 0.4958] | 0.5 — one copy |
| Y | **0.5083** | [0.4959, 0.5201] | 0.5 — one copy |

Neither is a finding about this child; both are a finding about the **instrument**. The
allele route has no opinion on either — entry
[116](116-the-statistic-that-has-power-and-the-limit-it-buys.md) measured chrXq at 0.018
heterozygous calls per PASS call against 0.57–0.62 on an autosome — so this is the only
route in the step that can see them, and it lands on the right answer to within 2.5 %.

**The autosomes span 0.978 to 1.045**, and eight of the 22 have a bootstrap interval that
excludes 1.0. That is not eight aneuploidies. It is the reason the next section exists.

## The interval was measuring the wrong thing

The bootstrap resamples **probes**, so it measures how much of a chromosome's estimate
depends on which k-mers survived the uniqueness filter. It is blind by construction to a bias
that *every* probe on the chromosome shares — and GC content is exactly such a bias. Library
preparation and amplification favour some compositions by a few per cent across a whole
chromosome, which is the same size as the mosaic gain this step is looking for.

So dosage was regressed on GC and the residual reported. **Which GC** turned out to decide
the result:

| Regressor | Pearson | Variance explained | Autosomal spread | chr21 |
|---|---|---|---|---|
| probe GC | 0.872 | 76.0 % | 1.876 % → 0.919 % | z **4.03**, Bonferroni p **0.0012** |
| **chromosome GC** (reported) | **0.904** | **81.7 %** | 1.876 % → **0.802 %** | z **2.33**, Bonferroni p **0.43** |

The chromosome's own GC, measured from GRCh38 over called bases only, is the right regressor
on two grounds, **both settled before any residual was read**:

1. **Scale.** GC bias acts on fragments of a few hundred bases. A 31-mer's own GC is not the
   quantity the chemistry responds to.
2. **Sampling.** A probe set is what the uniqueness filter left, and repetitive sequence is
   not composed like the chromosome around it. chr21's probes read 0.3835 against chr21's
   actual 0.4107 — understating it by **2.7 points, the largest gap of any autosome**. A
   chromosome whose probes understate its GC is under-predicted by a probe-GC fit, which
   hands it a positive residual it never earned.

It also simply fits better on every measure in the table. Both fits are written to
`composition.json` and rendered side by side on `/steps/step-8`, because *"we chose the
better regressor"* is a claim a reader should be able to check rather than accept.

The correction is not absorbing whatever is in front of it: chr19 and chr22, the two most
GC-rich autosomes and the two highest raw dosages at 1.0431 and 1.0451, land at 0.9957 and
1.0032.

## chr21, and why it is not a finding

chr21 is the largest residual at +1.87 %, an implied 3.74 % of cells. Four things were asked
of it, and none supports calling it:

| Check | Result |
|---|---|
| Multiple testing | z 2.33 over 22 autosomes: Bonferroni p **0.43**. Roughly one autosome clears 2 σ on a genome with nothing wrong with it |
| Trim 10 % from each tail | z 2.33 → **1.60**. About a third of it was tail |
| Split-half over its probes | halves differ by **0.77 %** against a median autosomal 0.76 % — spread across the probe set, not localised |
| Depth, independently | mean 61.68× against a 42.42× baseline, but **median 45 against 43** and **p99 247 against 66–69** on clean autosomes |

The depth row is the one that would have misled. chr21's *mean* depth at called sites is 45 %
above baseline, which read alone looks like a substantial gain. Its median is 4.7 % above, and
its 99th percentile is nearly four times a normal autosome's: the excess is a **tail of
mismapping pileups**, which the acrocentric chromosomes (13, 14, 15, 21, 22) attract from each
other. The k-mer route is built from reference-unique 31-mers and is not exposed to it, which
is why the two disagree — and why the dosage figure of +1.9 %, not the depth figure of +45 %,
is the one that means anything.

The same mismapping explains what entry
[116](116-the-statistic-that-has-power-and-the-limit-it-buys.md) had to explain away: chr21
and chr22 exceeded the genome-wide deviation null, and their own over-dispersion was 4.15×
and 3.74× the genome-wide value. Pileups inflate over-dispersion and inflate mean depth for
one reason, and a second instrument built to avoid them reports neither.

**There is no positional version of any of this.** The probe set is coordinate-free by
design, so the step can say whether a signal is spread across a chromosome and never where on
it. A gain confined to part of an arm is outside what either route here can localise.

## The honest precision floor

**1.6 % of cells**, which is twice the 0.802 % residual spread — not the ±1 % the bootstrap
interval suggests. For a single pre-specified chromosome at 2 σ that is 3.2 % of cells; across
all 22 at once it is about 4.8 %.

That sits alongside the allele route's 2–3 % on autosomes from entry
[116](116-the-statistic-that-has-power-and-the-limit-it-buys.md). Two routes sharing nothing
past the FASTQ, built on different physics, arrive at limits of the same order — and the
dosage route covers the two chromosomes the allele route cannot see at all.

## Assumptions, limitations and quality checks

- **Assumed:** a uniform thinning of shards is uniform with respect to the genome. It rests
  on shards being flowcell partitions, which `ideation/data-findings.md` establishes; it
  would fail on a genomically-partitioned store, and the flag's docstring says so.
- **Assumed:** dosage maps to cell fraction as `f = 2(ratio − 1)`. That inverts a *gain*. The
  value is left signed so a loss reads negative rather than being folded into a gain.
- **Limitation:** copy-neutral loss of heterozygosity is invisible to this route by
  construction — it changes whose copy is present, not how much sequence there is.
- **Limitation:** 4.7 % of probes were never seen. Reported as `silent_share` per contig
  rather than averaged away, because a silent probe set would otherwise read as a dosage of
  zero.
- **Limitation:** a median estimator was tried as a robustness check and rejected. At 4.5
  counts per probe the integer quantisation puts nearly every contig on the same whole number
  and the spread goes to 5 % — resolution loss, not robustness.
- **Checked:** the pass reproduces bit for bit across two independent runs.
- **Checked:** X and Y recover one copy to within 2.5 %.
- **Checked:** the correction returns chr19 and chr22 to 1.00 rather than flattening
  everything.
- **Clinical cross-reference:** the clinical document lists no karyotype and no term that a
  blood-DNA aneuploidy fraction would predict. The sequenced tissue is not stated anywhere in
  the delivery, so every number here is "in the sequenced sample" and is never equated with a
  karyotype fraction or read as a severity statement.

## Verdict

**H054 — supported.** The two routes agree on every chromosome where both can see. Neither
reports an event: the allele route puts no chromosome above its own detection limit (2–3 % of
cells), and the dosage route puts no chromosome beyond its composition-corrected null after
multiple testing (largest chr21, Bonferroni p 0.43). Where only one route can see, it answers
and says so — X and Y read one copy on dosage, and the allele route is silent there by
construction.

The agreement is worth more than the individual results, because the two share nothing past
the FASTQ. A shared artefact would have to survive alignment, calling, allele balance and
over-dispersion on one side, and k-mer uniqueness, counting and GC regression on the other.

One correction to the pre-registration: the claim was written expecting the comparison to be
interval-against-interval. The dosage interval turned out to be the wrong yardstick — it
measures counting noise, not the composition bias that dominates this measurement — so the
comparison is made against the residual spread instead. That is a change to the *test*, made
because the original statistic was measuring something other than what the claim was about,
and it is recorded here rather than applied quietly.
