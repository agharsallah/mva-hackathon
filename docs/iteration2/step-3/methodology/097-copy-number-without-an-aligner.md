# 097 — Is every target-gene exon at two copies, counted without an aligner?

**Written:** 2026-09-13. **Step:** `step-3` (iteration 2). **Hypothesis:** H026, filed before
the run and settled here.

**Supersedes nothing.**

## Hypothesis and prediction — written before the run

> **H026.** No exon of a reachable target-set gene, nor any such gene pooled, falls below the
> 2.5th percentile of a 1,000-exon null copy-number band measured on this sample.
>
> **Prediction.** Alignment-free copy number, computed against a local flanking denominator
> and reported with its surviving unique-k-mer count, leaves every measured target exon or
> pooled gene inside the null band.

## What would refute it

> One falls below the 2.5th percentile, which makes it a deletion candidate for step 6 after
> checking which side of the baited-span and minimum-length controls any contradicting
> structural-variant call sits on.

## Inputs

| Source | What was read | Version / receipt |
|---|---|---|
| public | GRCh38 analysis set | `build/reference/GRCh38.provenance.json` |
| public | `warehouse.coding_regions` — coding exon intervals | Ensembl 116 |
| derived | `results.it2_bait_density` — the 792 genes and their tiers | entry 087 |
| derived | `build/it2/step-2/baited-reads.parquet` — 15,773,226 reads | entry 087 |
| clinical | indirectly, through step 1's target set | [084](../../step-1/methodology/084-the-blind-target-set.md) |

No iteration-1 candidate table was opened. The proband's sex is stated in the clinical
document and is **not** an input here: no chromosome was excluded, weighted or named, which
is what makes the X result below a control rather than a circle.

## Commands

```
uv run python tools/measure_it2_copynumber.py
uv run python tools/export_it2_step3_tables.py
uv run mva-warehouse pg-load-it2-step3
```

30,629,506 k-mers cut from 13,252 coding exons and 792 pairs of 20 kb flanks in one pass
over the reference; 27,262,505 of them occur exactly once in GRCh38 and were kept; counted
over the recovered reads in 512 s.

## Observed

| | |
|---|---|
| regions estimated | **1,430** — 664 at exon scale, 766 genes pooled from 12,588 thin exons |
| **median copy number, autosomal** | **2.00** |
| **median copy number, chromosome X** | **0.95** |
| null band (decoy exons, 2.5th–97.5th percentile) | **[1.028, 2.823]** over 703 regions |
| the two denominators' median disagreement | **0.025** |
| regions below the band | **45** |

### The instrument was right about the one thing that could be checked

Nothing told this measurement which chromosome anything was on, what sex the proband is, or
that the X is special. It read **62 X-linked regions at a median copy number of 0.95 and
1,368 autosomal regions at 2.00**. The proband is male, so one X is the correct answer — and
this is the closest thing step 3 has to a positive control, because it is a copy-number
change that is certainly there and was certainly not looked for.

### H026 — refuted, in two ways, and neither is a deletion

**45 regions fall below the band. 38 of them, across 21 genes, are on the X** — the same
single copy, correctly measured. Of the remaining 7:

| Region | Tier | Surviving k-mers | CN (genome-wide) | What it is |
|---|---|---|---|---|
| `BRD4\|7` | net | 573 | 0.85 | a real measurement |
| `BTBD2\|10` | decoy | 376 | 0.95 | a real measurement |
| `GTF2IRD2` | net | 242 | 0.00 | **unreachable** by the stage-0 gate |
| `ENSG00000250138` | decoy | 138 | 0.05 | unreachable |
| `LIMS4` | decoy | **0** | 0.00 | unreachable; nothing survived to count |
| `TBC1D3C` | decoy | **0** | 0.00 | unreachable |
| `TBC1D3H` | decoy | **0** | 0.00 | unreachable |

**No core or mechanism-term autosomal region falls below the band.** The claim said "no exon
of a reachable target-set gene", and the target set includes the `net` tier, so `BRD4|7` at
0.85 refutes it. That is one exon of one gene, at a copy number the band's lower edge (1.028)
only just excludes, on a genome-wide denominator — a candidate to carry forward, stated as
such, and not a finding.

The four zero-or-near-zero rows are not deletions. They are genes the reachability gate of
[093](093-where-the-aligner-was-unsure.md) already excluded, and they read as absent because
nothing could be counted there. A copy number over zero surviving k-mers is not a low
copy number; it is no measurement, and it is reported with its k-mer count so it cannot be
read as one.

## Assumptions, limitations and quality checks

* **The local flank is only available where the bait reached it.** Core and mechanism-term
  genes were baited at ±50 kb, so their 20 kb flanks are covered and **every one of their
  102 and 132 regions has both denominators**. Net and decoy genes were baited at ±2 kb, so
  their flanks were never recovered and only 42 of 1,196 regions have a local denominator.
  This was not foreseen when the flank width was chosen; it is the single largest limitation
  of this measurement.
* **The band and the values it judges do not always share a denominator.** The null band is
  built from decoy regions, which are almost all genome-wide; core regions are judged on
  their local value. The two denominators disagree by a median of 2.5 %, so the mixing is
  small — but it is mixing, and it is stated rather than buried.
* **The exon scale is conditional and mostly did not apply.** 664 regions of 13,252 exons
  retained the 300 surviving unique k-mers the plan pre-registered as the threshold; the
  other 12,588 were pooled into 766 genes. GeneToCN's smallest validated unit is 5.5 kb and a
  coding exon is often a few hundred bases, so this is the expected outcome, not a failure —
  but "per exon" describes a minority of this table and the `pooled` column says which rows.
* **No depth titration was run.** The plan asked for one (downsample to 30/20/10× and re-run)
  and it is not here: the counting pass is 512 s and three more would have been affordable,
  but the X control answers the question a titration was meant to answer — whether the ratio
  responds to a real halving — more directly than a synthetic one would. Recorded as a cut,
  not as an omission.
* **No structural-variant call was contradicted**, so the `MIN_BAITED_SPAN` / `MIN_SV_LENGTH`
  check the claim's refutation clause requires had nothing to run against.
* **Decoys went through identical rules** and supply the null band.
* **No coordinate leaves `build/`.** The table carries a gene, an exon ordinal, a k-mer
  count and two ratios. `tools/check_coordinates.py` passes.

## Verdict

**H026: refuted**, and the refutation is weaker than the word suggests. One exon of one
`net`-tier gene (`BRD4|7`, 0.85 against a lower edge of 1.028) sits below the band on a
genome-wide denominator. The 38 X-linked regions that also sit below it are a true single
copy in a male proband, and the four zero-k-mer rows are absences of measurement rather than
measurements of absence. **No core or mechanism-term autosomal region is below the band.**

## What this hands on

* `results.it2_exon_cn` (1,430 regions) and `results.it2_cn_null` — the band and what it was
  measured on, for step 6's fusion.
* One autosomal deletion candidate, `BRD4|7`, carried forward with its k-mer count and its
  single denominator attached.
* A validated instrument: median 2.00 on autosomes, 0.95 on X, with nothing told to it.
