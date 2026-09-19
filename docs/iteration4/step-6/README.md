# Step 6 — The merged report

**Standing:** **run 2026-09-19**; `P4-8` (H064) **refuted**. Marked **done** in
`src/mva/science/step_maps/iteration4.py` — the claim is settled, and the revision it is owed
belongs to a later lane, not to an unfinished test. Iteration 4, `step-6`.

**Goal** (from `steps.py`):

> Do the models agree, and what does the merged report conclude under each of the three merge methods?

**Plan:** [`../plan.md`](../plan.md) §5, *Step 6*. Only `fusion` is run; `fusion+synthesis` and
`judge` need an LLM and are opt-A / opt-B.

## What happened

| Claim | Prediction | Verdict |
|---|---|---|
| H064 (`P4-8`) | the catalogue-free RRF consensus ranks the confirmed pair **1** | **refuted** — **20,639 of 52,012** ([130](methodology/130-a-consensus-of-lanes-that-declined-to-vote.md)) |

| run | lanes | confirmed pair's RRF rank | of pairs | fused score |
|---|---|---|---|---|
| catalogue-free | alphamissense, esm1b, spliceai | **20,639** | 52,012 | 0.000083 |
| all lanes | + revel | 21,497 | 52,219 | 0.000083 |

**The cause is abstention, not disagreement.** The fused score is exactly `1/(60 + 11,980)` —
SpliceAI's reciprocal rank, alone. AlphaMissense, ESM1b and REVEL have no rank for the pair:
each is missense-only, the pair is half `stop_gained`, and a pair with an unscored half is
excluded rather than scored zero. All 90 disagreement rows are the same benign shape (a
splice-window allele a missense model finds unremarkable), so the table the refutation clause
points at names the wrong thing.

**The catalogue ablation is not load-bearing here.** Excluding REVEL moves the rank by 858 of
~52,000 and leaves the fused score identical. §2 adds a twist: REVEL agrees with AlphaMissense
at ρ = +0.186 and with ESM1b at +0.168 — *lower* than the two catalogue-free missense lanes
agree with each other (+0.580). The ClinVar-trained lane is the least typical missense lane in
this zoo.

**The agreement matrix has two blocks**: three missense lanes at +0.168…+0.580, and SpliceAI
agreeing with none of them (+0.021…+0.043). The zoo holds one opinion about protein damage
sampled three times, and one about splicing.

**The RRF DOI is verified.** Crossref returned the exact title, three authors, SIGIR 2009 and
pages 758-759 for `10.1145/1571941.1572114`; the citation now states the DOI and the date it was
checked (`6c054bf`).

**Predicted, not rationalised.** Plan §10 R9 named this failure mode before the iteration began;
entries [114](../step-1/methodology/114-one-record-per-allele-and-what-it-can-be-spelled-as.md),
[119](../step-2/methodology/119-four-lanes-fetched-licensed-and-joined.md) and
[129](../step-5/methodology/129-what-each-lane-says-about-a-pair-it-can-only-half-see.md) tracked
it from consequence classes to coverage to an absent rank.

## Outputs

| Artifact | Where |
|---|---|
| the merged report, narrative hand-written | [`../report.md`](../report.md) |
| every number it prints | `build/it4/merged.json` (gitignored) |
| agreement heat map, confirmed-rank bars | [`../../../figures/it4/`](../../../figures/it4/) |

## Limitations

Stated by entry 130, beside the result rather than under it.

- **RRF over a thin lane is not weighted by what the lane saw.** ESM1b ranked 3,673 pairs and
  SpliceAI 50,696, yet each would cast a full first-place vote.
- **`n_pairs` differs between the two ablation rows** (52,012 vs 52,219), because excluding a
  lane removes the pairs only that lane ranked. The two rows are therefore not ranked over an
  identical set.
- **Sixteen genes are absent from the pair set** (entry 128).
- **Section 5 of the merged report is hand-written.**
- **No claim here is about the pair being causal.** The zoo ranks; causality is the register's
  business, and the answer key's.

## Reproduce

```bash
uv run mva-zoo run --config src/mva/zoo/zoo.example.toml
curl -sS https://api.crossref.org/works/10.1145/1571941.1572114
```

## Methodology

[`methodology/130`](methodology/130-a-consensus-of-lanes-that-declined-to-vote.md) — the DOI
check, the consensus, the matrix, the disagreement table and the verdict.
