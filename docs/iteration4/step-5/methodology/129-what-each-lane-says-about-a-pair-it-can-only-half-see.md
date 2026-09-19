# 129 — What each lane says about a pair it can only half see

**Written:** 2026-09-19. **Step:** `step-5` (iteration 4). **Run:** R5 of the wave-2 chain.
**Hypotheses tested:** H063 (plan label `P4-6`).

Reads the tables [128](../../step-4/methodology/128-one-command-eight-stages-and-three-things-a-fixture-could-not-catch.md)
wrote. Produces the four per-model reports, their figures, and the one number `P4-6` is about.

## Question

Does every catalogue-free lane place the confirmed `BUB1B` pair in the top decile of the
callset's biallelic pairs — and where each lane cannot, what does it say instead?

## Hypothesis and prediction

*Written before the figures were rendered and before any percentile was read.* Filed as H063.

| | |
|---|---|
| **Statement** | `P4-6`: every catalogue-free lane places the confirmed BUB1B pair in the top decile of the callset's biallelic pairs. |
| **Prediction** | For each of `alphamissense`, `esm1b` and `spliceai`, the confirmed pair's percentile in `results.it4_model_ranks` is at most **10.00 %**. |

## What would refute it

*Written before the run, quoted from [`plan.md` §5](../../plan.md) with the plan's own
"no opinion" carve-out made explicit.*

> Any catalogue-free lane places the confirmed pair **below the median** (percentile above
> 50 %) — reported as that lane's blind spot. **A lane with no opinion on the pair is neither
> support nor refutation.**

## Inputs

| input | rows | role |
|---|---|---|
| `results.it4_model_ranks` | 402 | the per-lane rankings, run `it4-dcda40a4df2c` |
| `results.it4_model_reports` | 4 | the stored section JSON every report renders from |
| `warehouse.allele_scores` | 58,480 | the distributions in section 3 |
| `warehouse.hpo_gene_scores` | term set `with-parental` | section 5 |

## Commands

```bash
uv run mva-zoo run --config src/mva/zoo/zoo.example.toml   # renders docs/iteration4/reports/
uv run python tools/render_it4_figures.py                  # 12 files -> figures/it4/
```

## Observed

### The confirmed pair, per catalogue-free lane

| lane | pairs ranked | confirmed pair's rank | percentile | in the top decile? |
|---|---|---|---|---|
| `alphamissense` | 10,333 | **no opinion** | — | neither |
| `esm1b` | 3,673 | **no opinion** | — | neither |
| `spliceai` | 50,696 | 11,980 of 50,696 | **23.63 %** | **no** — and not below the median either |
| *(`revel`, catalogue-adjacent, outside the claim)* | 10,456 | no opinion | — | — |

### The same pair, allele by allele — where the lanes are not silent at all

| lane | missense half `93e077ae83ac2642` | percentile among the lane's scored alleles | `stop_gained` half `addc19de8fa29228` |
|---|---|---|---|
| `alphamissense` | 0.9229 | **0.47 %** | not scored |
| `esm1b` | 11.537 | **2.52 %** | not scored |
| `revel` (adjacent) | 0.472 | **2.59 %** | not scored |
| `spliceai` | 0.00 | 24.53 % | **0.03** (9.74 %) |

**This is the finding of step 5.** Three lanes of different provenance — a structure-aware
missense model, a protein language model and a ClinVar-trained ensemble — independently put the
missense half of the confirmed pair in the **top 0.5–2.6 %** of everything they scored. None of
them can score a nonsense allele, so none of them can turn that into a statement about the
*pair*, and the pair score `(min, max)` has no `min` to take. The lane that *can* see both
halves sees them through the wrong instrument: SpliceAI's two numbers, 0.03 and 0.00, are far
below its own lowest published cut-off of 0.2, which is the correct reading for a nonsense and
a missense change that act through protein rather than splicing.

### Coverage and distribution, per lane (sections 2 and 3)

| lane | scored / 39,286 | missense | median score | p90 |
|---|---|---|---|---|
| `alphamissense` | 10,601 (27.0 %) | 67.9 % | — | — |
| `esm1b` | 4,562 (11.6 %) | 29.2 % | range −13.619 … 17.936 | — |
| `revel` | 10,783 (27.4 %) | realised | — | — |
| `spliceai` | 32,534 (82.8 %) | 84.3 % | **0** | **0.03** |

SpliceAI's median is 0 and its p90 is 0.03 — the same number as the confirmed `stop_gained`
allele's score. The pair does not sit low in SpliceAI's ranking because the lane judged it
benign; it sits where nine tenths of the callset sits, because the lane has no signal for this
class of change.

### Section 5 — what the clinical terms say

Every report carries the same sentence, now that the phenotype reader is wired
([128](../../step-4/methodology/128-one-command-eight-stages-and-three-things-a-fixture-could-not-catch.md)):

> Against the child's 8 HPO terms, `BUB1B` ranks **#14 of 5,267** genes considered (phenotype
> score **0.36093**, term set `with-parental`). `<lane>` scores the molecular change only and
> never sees the phenotype.

The clinical half of the evidence is therefore **independent** of every number above, and it
points at the gene all four lanes are silent or lukewarm about.

### Section 6, and the figures

Four interpretations, ≤ 200 words each (195 / 173 / 159 / 186), written by hand and signed
`hand-written 2026-09-19`, every sentence naming the section and row it rests on. A re-render
now **keeps** them: `report.write_markdown` reads the prose back from under the section-6
marker, the same rule `merge_render` already followed for the merged narrative. Verified by
re-running the DAG after writing them.

Twelve figures in `figures/it4/` from `tools/render_it4_figures.py`: one score histogram per
lane with the confirmed pair's two alleles marked, the agreement heat map, and the
confirmed-rank bar chart. The report's link to its histogram was root-relative and resolved to
`docs/iteration4/reports/figures/…`; it is now relative to the report.

## Evidence recorded

| evidence | direction | claim |
|---|---|---|
| SpliceAI, the only catalogue-free lane with an opinion, places the pair at the 23.63rd percentile — outside the top decile, above the median | neutral | H063 |
| AlphaMissense and ESM1b have no opinion: each scored one half of the pair, and an unscored pair is excluded | neutral | H063 |
| all three missense lanes put the pair's missense half in the top 0.47–2.59 % of their own scored alleles | supports | H063 |

## Verdict

**H063 (`P4-6`) — `testing`: not supported, and not refuted by its own terms.** Confidence 0.20.

- Two of the three catalogue-free lanes have **no opinion** on the pair, which the claim's own
  refutation clause says is neither support nor refutation. That is not a technicality: each
  scored the missense half and could not score the nonsense half, and `rank.py` excludes a pair
  with an unscored half rather than scoring it zero.
- The one lane that does rank it, SpliceAI, puts it at **23.63 %** — outside the top decile the
  claim predicted, and comfortably above the median that would refute it.

**The claim was aimed at the wrong unit.** Every missense lane places the pair's missense
*allele* in its top 2.6 %, and AlphaMissense in its top 0.47 %; if `P4-6` had been written about
alleles rather than pairs it would be supported three times over. Written about pairs, it cannot
be settled by a roster in which three of four lanes are missense-only and the confirmed pair is
half nonsense — which is exactly the lane gap
[114](../../step-1/methodology/114-one-record-per-allele-and-what-it-can-be-spelled-as.md)
predicted from consequence classes on day one and
[119](../../step-2/methodology/119-four-lanes-fetched-licensed-and-joined.md) confirmed by
coverage. The revision this claim is owed is a lane that scores a nonsense allele — GPN-MSA,
whose promotion has been recorded as due since entry 114.

## Limitations

- **Percentiles are within a lane's own ranked set**, whose size differs by an order of
  magnitude (3,673 to 50,696 pairs). A percentile from ESM1b and one from SpliceAI are not the
  same measurement, and the tables print `n` beside every one.
- **SpliceAI's distribution is degenerate for this purpose**: median 0, p90 0.03. Percentiles in
  the flat part of such a distribution are unstable — a score of 0.00 versus 0.01 moves an
  allele many percentiles.
- **Section 6 is hand-written**, so it is not reproducible from the run. It is signed and dated
  and marked as the only such section; the opt-A `narrate` module would make it reproducible.
- **Sixteen genes are absent from the pair set** (entry 128), so "of 50,696 pairs" means the
  pairs outside those genes.

## Next test

Step 6 (R6): the merged report — agreement matrix, RRF with and without the catalogue-adjacent
lane, the disagreement table — and `P4-8`, whether the fused consensus puts the pair first.
