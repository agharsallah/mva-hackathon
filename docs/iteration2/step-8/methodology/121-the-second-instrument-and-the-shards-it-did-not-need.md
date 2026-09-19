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
