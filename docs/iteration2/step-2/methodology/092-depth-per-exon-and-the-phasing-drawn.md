# 092 — How deep is each *exon*, and what does the lead gene's phasing actually look like?

**Written:** 2026-09-12, closing section D of
[`notes/completion-audit.md`](../notes/completion-audit.md). **Step:** `step-2`
(iteration 2). **Hypotheses:** none — like
[089](089-the-instruments-and-the-gate-that-was-skipped.md) this is a measurement and two
exhibits, not a test. It **refines the evidence behind** H016's and H019's already-recorded
verdicts and changes neither.

**Supersedes nothing.** 085–090 stand as written.

## Why this ran

Two report artifacts could not be built from what step 2 had already produced.

1. **`results.it2_exon_depth` is named for exons and does not hold them.** It holds the
   *merged baited intervals* the coverage stage was run over. For 126 of the 128 core and
   mechanism-term genes that is a single interval spanning the whole gene, so the table can
   answer "is this gene deep enough" and cannot answer "is this **exon** deep enough" — and
   the second question is the one every absence inside a gene has to be read against. A
   gene-level mean of 44x can hide an exon at 3x completely.
2. **The phasing result was a count, not a picture.** H019 was settled as "it named the
   gap" on a distribution of block spans. Where the gap actually falls relative to the
   lead gene's exons was never drawn.

## Inputs

| Source | What was read | Version / receipt |
|---|---|---|
| derived | `build/it2/step-2/calls/baited.bam` — the alignment both callers read | entry 087, `baited.align.provenance.json` |
| public | `warehouse.coding_regions` — coding exon intervals | Ensembl 116 |
| derived | `results.it2_bait_density` — the tier of every gene | entry 087 |
| derived | `results.it2_phase_blocks`, `results.it2_read_alleles` | entry 088 |

No clinical term and no candidate table of any earlier iteration was opened. The blind
protocol is untouched: depth and phasing are properties of the *instrument*, measured
identically for a target and a decoy.

## Commands

```
uv run python tools/measure_it2_exon_depth.py        # mosdepth over coding exons
uv run python tools/export_it2_step2_analysis.py     # + the phase_track block
uv run python tools/render_it2_step2_figures.py
uv run python tools/render_it2_phase_block.py
```

`measure_it2_exon_depth.py` pulls the coding exons of every non-decoy gene, writes them as
a BED whose **name field carries `gene|ordinal`**, runs mosdepth at `--mapq 20` — the same
mapping-quality cut the calling stage used, so these depths are comparable with
`results.it2_exon_depth` and not with a raw pileup — and writes
`build/it2/step-2/exon-depth.tsv`, which carries a gene, an exon's ordinal, its length and
its mean depth **and no coordinate**.

## Observed

```
{'regions': 6693, 'median_depth': 44.96, 'min_depth': 0.0, 'max_depth': 106.13,
 'floor': 10.0, 'below_floor': 68}
```

| | |
|---|---|
| coding exons measured (target tiers) | **6,693** |
| median exon depth | **44.96x** — matching the 44.08x the merged intervals reported |
| exons below the 10x floor | **68**, in **10 genes** |
| exons at exactly 0.00x | **36** |
| of those 68, in the two tiers the step draws conclusions from | **4**, in 3 genes (`ABCC6` x2, `TMEM185A`, `MECP2`) |

The thin exons are **not** spread evenly. 61 of the 68 fall in four genes — `NEB` (19),
`GTF2I` (18), `GTF2IRD2` (14) and `ANAPC1` (10) — every one of which has a known paralogue
or pseudogene. That is exactly where the uniqueness filter removed the bait's k-mers
(entry 086) and where the aligner then refuses to place a read uniquely, so the two
instruments fail in the same place for the same reason.

All four are **net**-tier, not core. That is the load-bearing detail: `ANAPC1` sits in the
mitotic-checkpoint mechanism this case is about, and ten of its coding exons carry no
usable depth — but it was screened in by the wide net, so nothing in the step's conclusions
rests on it. The two tiers step 2 does reason from lose **4 exons of 2,046**.

**What this changes.** No verdict. One thing about how an absence is read: "no second allele
in `ANAPC1`" is, for ten of its exons, a statement about the instrument and not about the
child. The gene-level depth column in `results.it2_scored_pairs` averages that away; the new
exhibit does not.

## The phasing exhibit

`BUB1B` is the gene drawn: core tier, the only lead carrying a ClinVar pathogenic
assertion, and the gene the mechanism is named after in the literature.

| | |
|---|---|
| heterozygous sites in the baited window | **113** |
| read-backed phase blocks in the window | **16** |
| phase blocks overlapping the **coding span** | **0** |
| widest unphased stretch inside the gene | **59,554 bp — the entire coding span** |

Not one WhatsHap block reaches the coding exons of `BUB1B`. Every block sits in the ±50 kb
padding on either side. So for this gene the read route cannot say whether any two
heterozygous coding alleles sit on the same copy or on opposite copies; it can only say
that it does not know. That is H019's "it named the gap", now with the gap's size and
position relative to the exons.

## Assumptions, limitations and quality checks

* **Exon ordinals are over a union of transcripts.** `warehouse.coding_regions` merges the
  coding intervals of every transcript of a gene, so exon *n* is the gene's *n*-th coding
  interval and not a named transcript's exon *n*. The grid is therefore correct about
  *where along the gene* and not about a clinical exon number.
* **Decoys were measured but are not drawn.** The decoy null is a per-gene rate; nothing in
  the report reads a decoy at exon resolution, and 396 more rows would make the exhibit a
  texture.
* **Cross-check.** The median of the 6,693 per-exon depths (44.96x) agrees with the median
  of the 3,020 merged intervals already reported (44.08x). Two independent aggregations of
  the same alignment landing within 2 % is the check that the new BED and the old one
  address the same reads.
* **No coordinate leaves `build/`.** The exon table is gene + ordinal + length + depth; the
  phase track is offsets from the baited window's own start. Both pass
  `tools/check_coordinates.py`.
* **The figures are now gated.** `tools/check_figures_fresh.py` fails any rendered artifact
  older than the analysis it is drawn from — the failure mode that left four exhibits on
  the pre-H020-flip numbers for nine hours.

## Conclusion

Per-exon depth exists, and it says the target set contains 68 exons where an absence is a
gap in the data — 61 of them in four paralogue-rich net-tier genes, 4 in the tiers the step
reasons from. `BUB1B`'s coding span carries no
read-backed phasing at all. Neither result changes a verdict; both change what a reader of
step 2 is allowed to conclude from a blank cell.
