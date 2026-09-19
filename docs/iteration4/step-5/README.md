# Step 5 — The report per model

**Standing:** **run 2026-09-19**; `P4-6` (H063) tested and **undecided by its own terms**. Marked
**open** in `src/mva/science/step_maps/iteration4.py` — the claim is owed a revision once a lane
that scores a nonsense allele is added. Iteration 4, `step-5`.

**Goal** (from `steps.py`):

> Can one report template describe every model identically — coverage, distribution, the confirmed pair's rank and percentile, limitations — with an LLM writing only the interpretation?

**Plan:** [`../plan.md`](../plan.md) §5, *Step 5*. Section 6 is hand-written in the MVP; the
`narrate` module and its two LLM modes are opt-A and are **not** built.

## What happened

| Claim | Prediction | Verdict |
|---|---|---|
| H063 (`P4-6`) | every catalogue-free lane puts the confirmed pair in the top decile | **testing** — SpliceAI 23.63 %; AlphaMissense and ESM1b have **no opinion** ([129](methodology/129-what-each-lane-says-about-a-pair-it-can-only-half-see.md)) |

**The finding is one row below the claim's unit.** Three lanes of different provenance put the
confirmed pair's *missense allele* in the top 0.5–2.6 % of everything they scored:

| lane | missense half | percentile | `stop_gained` half |
|---|---|---|---|
| AlphaMissense | 0.9229 | **0.47 %** | not scored |
| ESM1b | 11.537 | **2.52 %** | not scored |
| REVEL (adjacent) | 0.472 | **2.59 %** | not scored |
| SpliceAI | 0.00 | 24.53 % | **0.03** (9.74 %) |

None of them can score a nonsense allele, so none can turn that into a verdict on the *pair*.
The lane that sees both halves sees them through the wrong instrument: SpliceAI's 0.03 and 0.00
are far under its own lowest published cut-off of 0.2 — correct for changes that act through
protein, not splicing — and its median score is 0 with p90 at 0.03, so the pair sits where most
of the callset sits.

**Section 5 is now real in every report:** against the child's 8 HPO terms, `BUB1B` ranks
**#14 of 5,267** genes (phenotype score 0.36093, term set `with-parental`) — evidence
independent of every model number above, pointing at the gene they are silent or lukewarm about.

**Section 6 is hand-written** in all four reports (195 / 173 / 159 / 186 words), signed
`hand-written 2026-09-19`, every sentence naming the section and row it rests on. A re-render
keeps it: `report.write_markdown` reads the prose back from under the marker.

## Outputs

| Artifact | Where |
|---|---|
| four seven-section reports | [`../reports/`](../reports/) |
| 12 figures (4 histograms, agreement heat map, confirmed-rank bars; `.svg` + `.html`) | [`../../../figures/it4/`](../../../figures/it4/) |
| the stored section JSON every report renders from | `results.it4_model_reports` |

## Reproduce

```bash
uv run mva-zoo run --config src/mva/zoo/zoo.example.toml
uv run python tools/render_it4_figures.py
```

## Methodology

[`methodology/129`](methodology/129-what-each-lane-says-about-a-pair-it-can-only-half-see.md) —
the per-lane numbers, the allele-level result, and the verdict.
