# Step 5 — The report per model

**Standing:** **run 2026-09-19**, extended **2026-09-20**; `P4-6` (H063) tested and **undecided
by its own terms**, `P4-7` (H069) **supported** in one of its two modes. Marked **open** in
`src/mva/science/step_maps/iteration4.py` — `P4-6` is owed a revision once a lane that scores a
nonsense allele is added, `P4-7` once a Nebius key exists. Iteration 4, `step-5`.

**Goal** (from `steps.py`):

> Can one report template describe every model identically — coverage, distribution, the confirmed pair's rank and percentile, limitations — with an LLM writing only the interpretation?

**Plan:** [`../plan.md`](../plan.md) §5, *Step 5*. Section 6 was hand-written in the MVP; wave 4
built the `narrate` module and ran the first of its two LLM modes (opt-A, A5).

## What happened

| Claim | Prediction | Verdict |
|---|---|---|
| H063 (`P4-6`) | every catalogue-free lane puts the confirmed pair in the top decile | **testing** — SpliceAI 23.63 %; AlphaMissense and ESM1b have **no opinion** ([129](methodology/129-what-each-lane-says-about-a-pair-it-can-only-half-see.md)) |
| H069 (`P4-7`) | every LLM-written section 6 cites every sentence to a row, ≤ 10 % uncited | **supported at 0.83**, scope `claude-code` — **41 of 41** sentences cite a resolving row, 0 invented ids, 0 new names ([134](methodology/134-an-llm-that-may-only-explain-the-rows-it-was-given.md)) |
| H070 | — | **superseded**: a duplicate filing of `P4-7`, recorded rather than deleted (the register is append-only) |

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

**Section 6 now carries two versions in every report**, side by side with a badge each, and a
re-render keeps both. The hand-written one (195 / 173 / 159 / 186 words, signed
`hand-written 2026-09-19`) is unchanged; above it sits one written by
`claude-opus-5[1m]` through `mva-zoo narrate --mode claude-code`.

**What the LLM was and was not shown.** The prompt is a fixed rule block plus that lane's own
rows for sections 2-5, each with a stable id (`cov.missense_variant`, `dist.p90`, `pair.rank`,
`hpo.rank`) — no system prompt, no repository context, and **no question**. It is told to
interpret, never to rank, and never to name a gene or disease the rows did not give it. It
*does* see `BUB1B`, through `pair.gene` and `hpo.rank`, because a report that never names its
gene is not a report; what it is denied is the ranking task (plan §11, risk R3).

| lane | sentences | cited | uncited rate | words | new names |
|---|---|---|---|---|---|
| `alphamissense` | 9 | 9 | 0.00 | 199 | none |
| `esm1b` | 13 | 13 | 0.00 | **213** | none |
| `revel` | 10 | 10 | 0.00 | 200 | none |
| `spliceai` | 9 | 9 | 0.00 | 197 | none |

41 sentences, 41 resolving citations, **0 %** uncited against a 10 % bar; `esm1b` overran the
200-word budget, which the checker flags and the claim does not test. Four calls cost
**$0.534** and **128 s** — the most expensive thing in this pipeline per byte, and it produces
no result.

**The same checker run over the hand-written sections reports 100 % uncited** — not a finding
about the human, but about the two conventions: the hand-written prose cites sections
("(§3, marks)"), the checker resolves row ids. The machine convention is the checkable one.

## Outputs

| Artifact | Where |
|---|---|
| four seven-section reports | [`../reports/`](../reports/) |
| 12 figures (4 histograms, agreement heat map, confirmed-rank bars; `.svg` + `.html`) | [`../../../figures/it4/`](../../../figures/it4/) |
| the stored section JSON every report renders from | `results.it4_model_reports` |
| the generated and hand-written section 6, prompt and reply included | `results.it4_narratives` (8 rows) |

## Limitations

Stated by entry 129, beside the result rather than under it.

- **Percentiles are within a lane's own ranked set**, and those sets differ by an order of
  magnitude (3,673 to 50,696 pairs). A percentile is comparable *within* a lane, not across.
- **SpliceAI's distribution is degenerate for this purpose**: median 0, p90 0.03. A percentile
  drawn from it separates almost nothing.
- **Section 6 is still not reproducible**, for a new reason: `claude -p` has no temperature
  flag, so the same stored prompt can return different prose. The prompt is a function of the
  run; the reply is a record of one call. `nebius` at `temperature = 0` is the mode that would
  close this, and it **was not run: no `NEBIUS_API_KEY` on this machine**.
- **`P4-7` is tested in one of its two modes.** The claim is filed and verdicted for
  `claude-code` alone and owes a revision.
- **A citation is not a justification.** The checker proves a sentence points at a row; it does
  not prove the sentence reads the row correctly. A human still reads section 6.
- **The "new name" rule is shape-based**, so it flags `MVP` and `SNV` as readily as a gene
  symbol. Erring that way is deliberate; the false positives are listed in entry 134.
- **Sixteen genes are absent from the pair set** (entry 128), so "of 50,696 pairs" means the
  pairs outside those genes.

## Reproduce

```bash
uv run mva-zoo run --config src/mva/zoo/zoo.example.toml
uv run python tools/render_it4_figures.py
uv run mva-zoo narrate --config src/mva/zoo/zoo.example.toml --mode claude-code --dry-run
uv run mva-zoo narrate --config src/mva/zoo/zoo.example.toml --mode claude-code
```

## Methodology

[`methodology/129`](methodology/129-what-each-lane-says-about-a-pair-it-can-only-half-see.md) —
the per-lane numbers, the allele-level result, and the verdict.
[`methodology/134`](methodology/134-an-llm-that-may-only-explain-the-rows-it-was-given.md) —
the prompt, what the model may and may not see, the citation check, cost, and `P4-7`'s verdict.
