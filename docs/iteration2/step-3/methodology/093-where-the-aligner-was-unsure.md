# 093 — Where do the off-target reads pile up, and which genes may step 3 report on at all?

**Written:** 2026-09-12, opening step 3. **Step:** `step-3` (iteration 2).
**Hypotheses:** none — like [089](../../step-2/methodology/089-the-instruments-and-the-gate-that-was-skipped.md)
and [092](../../step-2/methodology/092-depth-per-exon-and-the-phasing-drawn.md) this is a
measurement and a gate, not a test. Step 3's six claims (H024–H029) are filed **after** it,
because this run decides which genes they may be evaluated on.

**Supersedes nothing.** It *completes* [086](../../step-2/methodology/086-can-the-off-target-gate-be-reached.md),
which measured how much bait the repeats cost and could not say what they cost the reads.

## Why this ran

Step 2 dropped **8.79 %** of its bait k-mers as occurring more than once in GRCh38, and
[086](../../step-2/methodology/086-can-the-off-target-gate-be-reached.md) showed no
available parameter reaches the pre-registered 5 % — the surface bottoms out at 8.38 %.
That number is about **bait k-mers**. It says nothing about the reads that survived.

The worry it leaves behind is specific. A gene whose sequence also occurs in a paralogue
collects reads from the paralogue too. The aligner knows this and writes it down as
`MAPQ 0` — the value every short-read aligner reserves for *"this sequence occurs in more
than one place and I picked one at random"*. A k-mer counter has no such notion: it sees a
31-mer and increments. So if the off-target reads pile at MAPQ 0 inside a handful of
segmental-duplication families, every count from those genes is a different quantity from
the one the model will be told it is — **before** a negative binomial is fitted to it.

The alignment step 2 produced already holds the answer, so the cost is minutes.
[plan.md §11.4](../../plan.md#114-step-3-revised) names this stage 0; this is it.

## The rule, fixed before the run

Written into `tools/measure_it2_mapq.py` as constants before the BAM was opened, so it
cannot be chosen afterwards. A gene is **unreachable** when either

| Condition | Threshold | Source |
|---|---|---|
| sparse bait | surviving-k-mer density below **half the median** | [plan §11.7](../../plan.md#117-4b-gates-revised), the rule that replaced `off-target < 5 %` |
| aligner refused | more than **50 %** of its reads carry `MAPQ 0` | this entry, pre-registered |

An unreachable gene is **flagged, never dropped**. Step 3 still designs and counts its
probes; the flag is what stops an absence there being read as a finding. Decoys are
measured identically — H020 is refuted, so nothing in step 3 may assume a target gene's
result outweighs a decoy's before the filter.

## Inputs

| Source | What was read | Version / receipt |
|---|---|---|
| derived | `build/it2/step-2/calls/baited.bam` — the alignment both step-2 callers read | entry 087, `baited.align.provenance.json` |
| derived | `build/it2/step-2/baited-regions.bed` — 3,020 baited intervals over 792 genes | entry 088, `run_it2_step2_calling.py` |
| derived | `results.it2_bait_density` — per-gene surviving-k-mer density and tier | entry 087 |
| clinical | indirectly: the 792 genes are step 1's target set plus its matched decoys, and step 1 read the child's eight HPO terms and nothing else | [084](../../step-1/methodology/084-the-blind-target-set.md), `Challenge_Clinical_Phenotype_1.md` |

No iteration-1 candidate table was opened. MAPQ is a property of the **instrument**,
measured identically for a target and a decoy, and the gene list came from symptoms.

## Commands

```
uv run python tools/measure_it2_mapq.py
```

One `samtools view -F 0x904` pass (unmapped, secondary and supplementary records excluded —
a secondary alignment is the same read placed twice and would inflate exactly the
repetitive regions this measurement exists to find), piped through `cut -f3,4,5`, then
tallied per interval by binary-searching each interval's bounds into the contig's sorted
alignment starts. Intervals sharing a gene label are gathered before the statistics are
computed, so a gene's median is over its reads rather than reconstructed from per-interval
medians. Output carries a gene, a tier, four counts and two flags — **no coordinate**.

## Observed

```json
{"reads_total": 15594481, "regions": 792, "regions_with_reads": 792,
 "off_target_reads": 791059, "off_target_mapq0_fraction": 0.083006,
 "off_target_median_mapq": 60.0, "median_region_mapq0_fraction": 4.4e-05,
 "mapq0_ceiling": 0.5, "above_ceiling": 1,
 "median_bait_density": 0.887717, "density_floor": 0.443859,
 "sparse_bait": 21, "mapq_refused": 1, "both": 1, "unreachable": 21}
```

**The feared pile-up is not there.** Three numbers say so:

| | |
|---|---|
| median per-gene MAPQ-0 fraction | **0.000044** — four reads in a hundred thousand |
| genes above the 50 % ceiling | **1** of 792 — `TBC1D3C`, a decoy with 15 reads in total |
| off-target reads' median MAPQ | **60.0**, the aligner's maximum |

The last is the load-bearing one. 791,059 reads (5.07 % of 15.59 M) landed outside every
baited interval, and the aligner placed them **confidently elsewhere**. That is what an
off-target read is supposed to look like: the bait pulled in a read that belongs to another
locus, and the aligner sent it there. Their MAPQ-0 fraction is 8.3 % — higher than any
baited gene's, and still a minority.

So the 8.79 % of bait lost to repeats cost **bait coverage**, not read placement. The two
failures step 2 saw in the same genes ([092](../../step-2/methodology/092-depth-per-exon-and-the-phasing-drawn.md):
"the two instruments fail in the same place for the same reason") are the uniqueness filter
removing k-mers and the depth that follows from having fewer of them — not the aligner
giving up.

### What the gate excludes

**21 genes of 792, and not one of them is `core` or `mechanism-term`:** 5 `net`, 16 `decoy`.

| Gene | Tier | Bait density | MAPQ-0 |
|---|---|---|---|
| `GTF2IRD2` | net | 0.048 | 0.0825 |
| `ANAPC1` | net | 0.246 | 0.0210 |
| `GTF2I` | net | 0.427 | 0.0067 |
| `HBA2` | net | 0.441 | 0.0620 |
| `PMS2` | net | 0.436 | 0.0040 |
| 16 decoys incl. `PWWP4` (0.045), `TBC1D3C` (0.009) | decoy | ≤ 0.422 | ≤ 0.8667 |

Two predictions from step 2's handover held: [step-3 README §4](../README.md) named
`PWWP4` and `GTF2IRD2` as the two lead genes to expect retiring, and both are excluded here
before a single k-mer was counted.

**The MAPQ rule adds exactly one gene** the density rule had not already caught
(`TBC1D3C`, 15 reads, 13 of them at MAPQ 0). The reachability gate is, in practice, the
bait-density gate — which is a result about the *design*, not a reason to drop the MAPQ
half: it is the measurement that turns "the density rule is probably enough" into a
statement with a number behind it, and it is the half that would fire on a different case.

### The lead gene, and the two tiers step 3 reasons from

| Gene | Tier | Reads | MAPQ-0 | Median MAPQ | Bait density |
|---|---|---|---|---|---|
| `BUB1B` | core | 56,953 | **0.00072** | 60.0 | 0.850 |
| `TMEM185A` | mechanism-term | 13,405 | 0.0106 | 60.0 | 0.449 |
| `CLCNKA` | core | 39,133 | 0.0071 | 60.0 | 0.799 |
| `TERT` | mechanism-term | 50,362 | 0.0071 | 60.0 | 0.874 |

`TMEM185A` at 0.0106 is the **worst** MAPQ-0 fraction in either of the two tiers step 3
draws conclusions from. Every core and mechanism-term gene is reachable.

## Assumptions, limitations and quality checks

* **Reads are tallied by alignment start.** A read whose leftmost mapped base falls just
  before an interval is not counted for that interval, so a gene's tally is short by at
  most one read length at its left edge. Not corrected, because the quantity reported is a
  *fraction* and both numerator and denominator lose the same reads.
* **Overlapping intervals count a read twice.** Two genes whose ±50 kb padding overlaps
  both claim the reads in the overlap. That is the honest answer for a per-gene profile and
  avoids inventing an ownership rule the data does not contain; it makes the per-gene read
  counts sum to more than 15.59 M, which is why the off-target figure is computed from a
  *mask* rather than by subtraction.
* **MAPQ is the aligner's opinion, not ground truth.** `minimap2 -ax sr` computes it from
  its own best-versus-second-best alignment scores. A region absent from GRCh38 entirely
  produces a confident wrong placement, not a MAPQ 0, and nothing here would see it.
* **This does not validate the counts, it bounds a failure mode.** A low MAPQ-0 fraction
  says the aligner was confident; it does not say a k-mer count from that gene is correct.
  The instrument-agreement checks in 094 and 095 are what test that.
* **Decoys were measured identically** and appear in the same table with the same flags.
* **No coordinate leaves `build/`.** `mapq.tsv` carries gene, tier, counts and flags;
  `tools/check_coordinates.py` passes.

## What this hands to the next entry

* A reachability flag per gene, to be loaded as `results.it2_mapq_profile`, and the rule
  that produced it — the replacement for the retired `off-target < 5 %` gate.
* The finding that **alignment ambiguity is not a confounder here**, which means step 3's
  disagreements with step 2 may be read as instrument disagreements rather than as
  paralogue contamination. That is a precondition for H027 meaning anything.
* 771 reachable genes, including every core and mechanism-term gene and `BUB1B` at a
  MAPQ-0 fraction of 0.00072, on which the six claims may be evaluated.
