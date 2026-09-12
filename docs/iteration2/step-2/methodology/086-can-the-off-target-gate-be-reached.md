# 086 — Could any parameter have passed the off-target gate, and at what cost?

**Written:** 2026-09-12, after [085](085-the-bait-and-where-it-runs.md) reported the gate
failed. **Step:** `step-2` (iteration 2). **Hypotheses:** none — this measures the
instrument, it does not test a claim about the child.

**Supersedes nothing.** 085 stands as written; this entry answers a question it raised.

## Inputs

| Source | What was read | Version / receipt |
|---|---|---|
| derived (step 1) | `targets.tsv`, `decoys.tsv` | `build/it2/step-1/`, entry 084 |
| public | `ressources/reference/coding_regions.tsv` | Ensembl 116 |
| public | GRCh38 no-alt analysis set + hs38d1, bare contigs | sha256 `fb4243eb…`, 195 contigs |

No patient data of any kind. The bait is reference sequence and this entry only re-cuts it.

## Question, and why it is a dangerous one

The pre-registered gate is *"bait k-mers also present elsewhere in GRCh38 are dropped and
counted; off-target < 5 % of bait"*. It failed at **8.79 %**. The obvious next move — try
other values of k or the padding until one lands under 5 %, then report a passing gate — is
the one move that must not be made. A threshold that moves after seeing its own result is
not a threshold, and the same discipline is what makes step 1's refutation of H012 worth
reading: that gate was allowed to fail, and the iteration is better for it.

The defensible version of the question is different: **not "how do we pass", but "what
surface does this number sit on".** Two levers exist in principle — how much sequence is
baited (padding) and how long a k-mer is (k) — and each can be measured without changing
anything.

## Commands

```
uv run python tools/sweep_it2_bait_uniqueness.py --k 25 32
```

## Observed

### Padding is not the lever

The bait is split into the zone every gene shares (coding intervals ± 2 kb) and the extra
reach the wide tiers add (core and mechanism-term ± 50 kb), and each is measured on its own
against the whole genome, at k = 31:

| Zone | Bases | k-mers | Repeated | Off-target |
|---|---|---|---|---|
| exon-proximal (±2 kb, all 792 genes) | 27,331,140 | 25,899,296 | 2,169,610 | **8.38 %** |
| wide-tier reach (±50 kb, 128 genes) | 19,223,855 | 18,000,336 | 1,916,477 | **10.65 %** |
| the bait as built | 42,197,689 | 39,508,982 | 3,470,945 | **8.79 %** |

The intronic and intergenic reach *is* more repetitive, as expected — 10.65 % against
8.38 %. But the finding is the other number: **removing the ±50 kb padding entirely would
move the off-target load from 8.79 % to 8.38 %.** The repetitiveness is not in the
structural-variant reach, it is in the sequence around these genes at any padding. Padding
would have to be abandoned altogether to buy 0.4 percentage points, and abandoning it costs
the only thing step 2 has that can find an exon-scale deletion: the breakpoints of such a
deletion lie in the introns, not the exons.

**So the first lever does not reach 5 %, and the version of it that moves the number at all
trades a capability for four tenths of a percentage point.**

### k, within the representation

A longer k-mer is more unique, so k is the only lever left once padding is ruled out. It is
also bounded: a k-mer is packed two bits per base into one `uint64`, so **32 is the ceiling
of this representation**, and reaching past it is a change to the engine rather than a
change to a parameter.

| k | bait k-mers | repeated | off-target | gate |
|---|---|---|---|---|
| 25 | 38,307,240 | 3,926,649 | **10.25 %** | fail |
| 31 (as built) | 39,508,982 | 3,470,945 | **8.79 %** | fail |
| 32 | 39,672,612 | 3,398,048 | **8.57 %** | fail |

**Within the representation, no value of k passes.** The curve is shallow and close to
linear over the measured range — 0.243 percentage points per base from 25 to 31, 0.220 from
31 to 32 — so a straight-line extrapolation puts 5 % at **k ≈ 48**, sixteen bases beyond
what a single `uint64` can hold.

**And the extrapolation is optimistic, for a reason the data already showed.** Entry 085's
per-gene profile named the genes carrying the off-target load: TBC1D3, GOLGA6, NBPF, POTE,
HNRNPCL, SPDYE, FRG2B, LIMS4 — segmental-duplication families, where a gene has
near-identical copies spanning tens to hundreds of kilobases. A k-mer inside a 100 kb
duplicated block has an exact second copy at k = 31, at k = 48 and at k = 1000; **no k
escapes a repeat longer than k.** The measured slope is therefore the easy part of the
curve — the short and diverged repeats — and there is a floor beneath it that lengthening
k cannot reach. Whether that floor is above or below 5 % is not measured here, and the
honest statement is that the linear extrapolation is an upper bound on how well raising k
would do, not an estimate of it.

The zone split reproduces at k = 25 (exon-proximal 9.68 %, wide-tier reach 12.68 %, against
8.38 % and 10.65 % at k = 31), so the two levers are independent, both move the number by
about the same small amount, and neither rescues the other. Every figure labels the k each
bar was measured at, because two of these numbers are not comparable without it.

### Both levers, together

| Lever | Best reachable value | Off-target | Cost of taking it |
|---|---|---|---|
| padding | drop the ±50 kb entirely | 8.38 % | the only reach step 2 has for an exon-scale deletion |
| k | 32, the representation ceiling | 8.57 % | breaks the parameter step 3's genotyping is specified in |
| neither | as built | 8.79 % | — |

**No combination of the available parameters reaches 5 %**, and the two that move the number
at all move it by fractions of a point while costing a capability each. The gate did not
fail because the bait was built carelessly; it failed because the genes the child's
symptoms nominated sit in repetitive neighbourhoods, which is a fact about the genome and
about step 1's output, not about step 2's engine.

## What this does not change

k stays at **31**. Beyond the argument above there is a hard dependency: k = 31 is shared
with step 3's alignment-free genotyping, where the probe design and the retention band
taken from FastGT are stated in terms of it. Changing k here to satisfy a step-2 gate would
silently move a parameter another step is built on, and the two would then be measuring
different things while appearing to agree.

## The gate was also mis-specified, which is a separate point

Worth stating plainly, and worth not confusing with moving a threshold. The gate thresholds
a quantity the design **already corrects for**: repeated k-mers are dropped before the pass
runs, so the bait that does the work is unique by construction whatever this percentage is.
What the number actually measures is how repetitive the genes step 1 nominated — an input
step 2 does not choose and cannot change. A gate on an uncontrolled input is a description,
not a test.

The quantity the gate was reaching for is per-gene reachability, measured in 085: **21 of
792 genes fall below half the median bait density, and none is `core` or `mechanism-term`.**
That is the number a later "no second allele in this gene" has to be read against, and it is
the one carried into `results.it2_bait_density`.

**Recorded, for any iteration that reuses this design:** the uniqueness gate should be
specified per gene, not as a genome-wide average — "no gene in the reasoning tier below X %
of median bait density" — because that is the failure a bait can actually cause. The
average was the wrong statistic, and it was chosen before anyone had built one of these.

## Assumptions and limitations

1. The zone split double-counts where a wide-tier gene's ±2 kb sits inside its own ±50 kb;
   the two zones are measured independently against the genome, not partitioned, so their
   k-mer counts sum to more than the merged bait's. Each percentage is correct for its own
   zone, which is what the comparison needs.
2. Both zones are measured at k = 31 only. The k dependence is the second half of this
   entry and is not assumed from the first.
3. "Repeated" means an exact second occurrence of the canonical 31-mer anywhere in the
   analysis set, decoys and unplaced contigs included. That is deliberately strict: a bait
   k-mer that also occurs on a decoy contig is exactly as off-target as one on another
   chromosome.
