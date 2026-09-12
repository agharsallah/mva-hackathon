# 087 — Does a reference k-mer bait recover the reads of 792 genes from a billion?

**Written:** 2026-09-12, before the pass; **run:** 2026-09-12. **Step:** `step-2`
(iteration 2). **Hypotheses tested:** H021 (the bait's own recall) — filed before the run.
The claims the recovered reads exist to test (H016, H019, H020, H022, H023) are not
touched here; this entry establishes only that the reads were recovered and that the
recovery can be trusted.

## Inputs

| Source | What was read | Version / receipt |
|---|---|---|
| object store | the Parquet read store, every shard | `s3://mva/reads`, 272 shards, **1,071,835,104 reads** |
| derived | the uniqueness-filtered bait | `derived/it2/step-2/bait.npy`, **36,038,037** canonical 31-mers, entry [085](085-the-bait-and-where-it-runs.md) |
| public | GRCh38 no-alt analysis set + hs38d1, bare contigs | sha256 `fb4243eb…` |
| callset | 120 heterozygous PASS substitutions inside the baited region, seeded draw | `warehouse.variants_raw` (layer 1, unfiltered), seed `20260912` — **H021 only** |

The callset is an allowed input under the blind protocol (`plan.md` §1); no iteration-1
candidate table was read. The witness alleles are drawn by script from a seed, never chosen.

## Hypothesis and prediction — written before the run

**H021.** A reference k-mer bait sampled at a fixed stride recovers the reads that carry a
known alternate allele inside the baited region. *Prediction:* for at least 100
heterozygous PASS substitutions drawn from the delivered callset inside target-gene
intervals, at least **90 %** of the reads the existing 500-probe strike finds carrying the
alternate 31-mer are also present in the sweep's survivor set, at stride 16.

## What would refute it

Recall below 0.90. The pre-registered response is to lower the stride and repeat the pass
**before** any allele the bait produced is interpreted — a recall that low would mean the
survivor set is not a superset of the region's variant-carrying reads, and every downstream
absence would be uninterpretable.

## Commands

```
POST /bait  {bait_key, out_key, stride: 16, workers: 4, spill: true, collect_mates: true}
uv run python tools/check_it2_bait_recall.py
```

## Observed

### The pass

| | |
|---|---|
| reads scanned | **1,071,835,104** (272 of 272 shards) |
| reads matched | **14,657,560** |
| matched fraction | **1.36752 %** |
| bait as a share of the genome | **1.361 %** |
| fragments | 7,886,613 |
| orphans (one mate matched) | 1,115,666 — **14.1 %**, all filled |
| published | 15,773,226 rows = 2 × 7,886,613 — **every fragment complete** |
| wall time | 50.8 min, 4 workers |

**The check that the engine is correct is the third and fourth rows together.** A bait
occupying 1.361 % of the genome should recover 1.361 % of a uniformly sampled read set;
it recovered **1.36752 %**. Nothing forces those to agree — a k-mer kernel with an
off-by-one in its window, a canonical form that missed one strand, or a stride that
skipped the wrong offsets would all produce plausible-looking counts that are not this one.

Per-lane recovery is even across all eight partitions (1.77 M–1.90 M reads), so no lane
contributed disproportionately, which is what a systematic artefact would look like.

### The pre-registered recovery gate

Expected = bait bases × depth ÷ read length = 42,197,689 × 44 ÷ 150 = **12,377,989** reads;
the gate accepts 0.5–2× of it (6,188,994–24,755,978). Observed **14,657,560 = 1.18×**.
**Pass.** The 18 % excess is expected and has a stated cause: the arithmetic assumes reads
fall entirely inside the bait, while a read overlapping a boundary by ≥ 46 bases is
recovered too, and the bait has many boundaries.

### The bait-edge zone, measured rather than assumed

**14.1 % of recovered fragments matched on one mate only.** Every one of those is a
fragment straddling a boundary of the baited region: its other mate lies outside and shares
no bait k-mer. That number is the empirical size of the bait-edge zone, and it is the
number the structural-variant stage needs — a baited alignment has a coverage cliff and
unpaired mates at exactly those boundaries, which is the signature a read-pair caller reads
as a deletion. It is recorded here so H023's edge flag is calibrated against a measurement
rather than a guess.

All 1,115,666 were filled by the second pass, so no fragment entered the aligner
half-present.

### H021 — the bait's recall

250 witness alleles were drawn; **213 sit inside the bait** (their reference 31-mer survived
the uniqueness filter) and 37 were excluded because the bait never covered them — including
those would test entry 085's uniqueness decision rather than the stride. The strike returned
reads for **195** of the 213.

| | |
|---|---|
| witness reads found by the strike | **4,451** |
| also present in the bait's survivors | **4,029** |
| **recall** | **0.9052** |
| probes losing at least one read | 15 of 195 |

**H021 is supported, and only just.** Twenty-four more lost reads would have refuted it.

**The interval says the margin is not real precision.** The correlated unit is the probe —
reads of one allele share its locus, its depth and its k-mer's uniqueness — so the interval
is bootstrapped over probes, not reads: **[0.815, 0.974]**, with **59 %** of replicates
clearing 0.90. The measurement cannot separate 0.85 from 0.95, and resampling reads instead
would have produced a tight interval that meant nothing.

**Where the lost reads are, computed after the verdict and reported beside it.** A
single-copy heterozygous 31-mer is expected in depth × (L − k + 1)/L ÷ 2 = **17.6** reads at
44×; the median witness probe was found in **20**, which is the arithmetic working. Splitting
on twice that expectation:

| Probes | n | Reads | Recall |
|---|---|---|---|
| read count consistent with one locus (≤ 35) | 184 | 3,683 | **0.9832** |
| found in more reads than one locus can supply | 11 | 768 | **0.5312** |

One probe alone was found in 171 reads — ten times what a single-copy allele can produce —
and **none** of them is in the survivor set. That is the signature of an alternate k-mer
matching several places in the genome: the strike has no positions and counts every read
containing the sequence, while the bait was right not to recover reads that came from
somewhere else.

**This is a gap in the witness design, and it is mine.** The witness filter checked each
allele's **reference** k-mer against the bait, because that is what `bait.npy` contains —
but the strike searches for the **alternate** k-mer, whose uniqueness was never checked. An
alternate k-mer can match several loci when its reference counterpart does not. A later run
should filter witnesses on the alternate k-mer's genome-wide count, and the stratification
above is the diagnostic, not a restatement of the result: **the pre-registered number stays
0.9052.**

### Verdict on H021

**Supported at confidence 0.65**, recorded as register revision 2. The transparent heuristic
suggested 0.86 and was overridden down, with the reason stated in the register: the point
estimate clears the line, the interval does not exclude values well below it, and what lifts
the number above the bootstrap's own 0.59 is a post-hoc split that points at the witness
design rather than at the stride. Confidence here is a triage heuristic, not a calibrated
posterior.

## Assumptions and limitations

1. **Stride 16 is a pre-registered trade.** Testing every 16th offset of a read costs ~15×
   less than testing all 120 and can miss a read overlapping the bait by fewer than
   `k + stride − 1` = 46 bases. H021 is the measurement of that cost; a unit test
   demonstrates the failure mode on a toy store so it is visible rather than theoretical.
2. **The pass ran on the server, not on this machine.** Measured from the laptop on
   2026-09-11: 55.8 s per shard whether one shard streams or eight in parallel, so a full
   pass is 4.2 h here against 50.8 min beside the data. This is the one stage of step 2 that
   does not run where the analysis runs, it is a stated limitation of that claim, and the
   verb is a thin wrapper around the same function the CLI exposes — the result is
   reproducible entirely locally by anyone willing to spend the 4.2 hours.
3. **1.18× is not a validation of the depth figure.** 44× is a genome-wide mean and the
   recovery excess has a boundary explanation, so the two should not be read as confirming
   each other. Per-exon depth is where coverage is actually measured.
4. **The target set is an enrichment, not coverage** (recall@300 = 0.36, entry 084), and
   8.79 % of bait k-mers were dropped as repeated (entry 085). A gene absent from these
   reads is not thereby excluded; per-gene bait density is carried in
   `results.it2_bait_density` for exactly this reason.

## Verdict

| Gate | Rule | Observed | |
|---|---|---|---|
| recovery | within 0.5–2× of 12,377,989 | 14,657,560 (1.18×) | **pass** |
| every fragment paired | published rows = 2 × fragments | 15,773,226 = 2 × 7,886,613 | **pass** |
| orphans filled | all, or the shortfall named | 1,115,666 of 1,115,666 | **pass** |
| H021 recall | ≥ 0.90 | 0.9052, interval [0.815, 0.974] | **pass, narrowly** |

## What this hands to the next entry

`build/it2/step-2/baited-reads.parquet` — 15,773,226 reads in 7,886,613 complete pairs,
ready to be written as FASTQ and aligned; `bait-pass.json` with every number above; and the
14.1 % orphan fraction as the measured size of the bait-edge zone.
