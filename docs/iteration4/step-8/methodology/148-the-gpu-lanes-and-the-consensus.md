# 148 — Three GPU lanes see the pair, and the consensus ranks it lower

**Step:** iteration 4, [step 8](../README.md). **Date:** 2026-09-24. **Claims:** H077 (`P4-4`),
H078 (`P4-13`), H079 (`P4-14`), H082 (`P4-17`). Lane entries: 144 NT-v2, 145 ESM-C, 146 Evo 2,
147 Boltz-2; contract 143.

## Question

With NT-v2, Evo 2 and ESM-C in the score cache, where does the confirmed BUB1B pair rank in each
lane and in the catalogue-free consensus (RRF, reciprocal rank fusion) — and what did the GPU
tier cost?

## Hypothesis and prediction

All filed before any GPU run (commit `e88a901`):

| id | claim | prediction |
|---|---|---|
| H077 `P4-4` | the GPU tier runs for ≤ $30 | ledger and billing report ≤ $30, no lane stopped by its share |
| H078 `P4-13` | NT-v2 ranks the pair in its top decile | both alleles scored and pair percentile ≤ 10 |
| H079 `P4-14` | Evo 2 ranks the pair in its top decile | both alleles scored and pair percentile ≤ 10 |
| H082 `P4-17` | the GPU lanes move the consensus from 20,639 into the top 1,000 | catalogue-free RRF rank ≤ 1,000 |

## What would refute it

H077: billing > $50, or ≥ 2 lanes stopped by the cap. H078/H079: a lane abstains on either
allele, or the pair sits above the median. H082: the rank is still worse than 10,000.

## Inputs

| input | value |
|---|---|
| score cache | `warehouse.allele_scores`, nine lanes, 204,153 scores; GPU lanes at venue `modal:L4` (ntv2, esmc), `modal:H100` (evo2) |
| pairs | `results.coding_alleles` het calls → 63,347 pairs; 16 genes over the 60-call cap skipped (as entry 128) |
| run config | [`../zoo.step8.toml`](../zoo.step8.toml) = `src/mva/zoo/zoo.example.toml` + `ntv2`, `evo2`, `esmc`; reports to `step-8/` |
| ablation configs | the same file with `models` set to the six laptop lanes (AlphaMissense, ESM1b, SpliceAI, REVEL, GPN-MSA, ESM2) plus one GPU lane each; outputs in `build/it4/ablation/` |
| merge | RRF, k = 60 (Cormack 2009, DOI verified in entry 130); catalogue-free drops REVEL |

## Commands

```sh
uv run --group zoo-ml mva-zoo run --config docs/iteration4/step-8/zoo.step8.toml          # 2 min 50 s
build/it4/ablation/run.sh     # six, six+evo2, six+ntv2, six+esmc, then the nine again
uv run --group zoo-ml mva-zoo run --config docs/iteration4/step-8/zoo.step8.toml --force  # manifest venues
uv run python tools/render_step8_ablation.py
uv run --group zoo-ml python tools/modal_trace.py summary
modal billing report --for "this week" --json
```

## Observed output

Run `it4-81ec74fb9f9a` ([manifest](../../runs/it4-81ec74fb9f9a.json)): 8 stages, $0 on the
laptop; `rank_per_model` 149 s is most of it.

**Each lane's own ranking of the confirmed pair** (percentile: lower = nearer the top):

| lane | pair rank | percentile | missense half | stop-gained half |
|---|---:|---:|---:|---:|
| GPN-MSA (tier 1) | 508 / 54,865 | **0.93** | 1.38 | 4.09 |
| Evo 2 | 10,362 / 63,347 | 16.36 | 32.07 | 5.61 |
| SpliceAI | 11,980 / 50,696 | 23.63 | 24.53 | 9.74 |
| NT-v2 | 15,157 / 63,347 | 23.93 | 47.75 | 16.52 |
| AlphaMissense, ESM1b, ESM2, ESM-C | no opinion (missense-only; the pair's other half is `stop_gained`) | — | 0.47 · 2.52 · 4.84 · 49.49 | — |

**Leave-one-in on the consensus** (catalogue-free RRF):

![leave-one-in](../../../../figures/it4/step8-consensus-ablation.svg)

> **Legend** — neutral machinery (the six-lane baseline; a lane that ranks the pair); broken /
> dangerous / lost points (worse than the baseline); good / safe / the goal (the top decile,
> dashed; GPN-MSA's 0.9); context, not the subject; hatched = no opinion (the lane cannot score
> both alleles).

| lanes | rank | pairs | percentile |
|---|---:|---:|---:|
| six laptop lanes | 2,734 | 59,474 | 4.60 |
| six + Evo 2 | 3,176 | 63,269 | 5.02 |
| six + NT-v2 | 3,290 | 63,269 | 5.20 |
| six + ESM-C | 3,456 | 59,474 | 5.81 |
| all nine | **4,318** | 63,269 | 6.82 |
| (entry 130, four MVP lanes) | 20,639 | 52,012 | — |

The six-lane figure reproduces run `it4-5e25dd45eee2`'s recorded 2,734 exactly.

**Agreement** (Spearman ρ, from the merged report's matrix): Evo 2 vs GPN-MSA 0.53 (n 35,917),
Evo 2 vs ESM2 0.47 (n 15,592), NT-v2 vs Evo 2 0.01 (n 39,286), NT-v2 vs GPN-MSA 0.01. NT-v2's
cosine score barely correlates with anything: entry 144 measured it about 300× larger on
indels, so it ranks "how much sequence changed" more than "how damaging".

**Money:**

| source | total |
|---|---:|
| ledger (GPU seconds × published rate) | **$11.33** — Evo 2 7.05, NT-v2 2.96, Boltz-2 1.23, ESM-C 0.08 |
| `modal billing report`, week of 2026-09-23 | **$14.57** — Evo 2 9.28, NT-v2 3.71, Boltz-2 1.39, ESM-C 0.20, gateway 0.002 |

The bill is 1.29× the ledger. The guard padded each estimate by 1.3×, so the padding held.
No lane hit its share. 33 Modal commands are traced in [`../modal-runs.md`](../modal-runs.md).
Every `mva-zoo-*` app is stopped (`modal app list`, 2026-09-24).

## Verdict

- **H077 supported** (0.83): $14.57 billed, under $30; no lane stopped.
- **H078 testing** (0.40), undecided by its own terms: both alleles scored, but the pair sits at
  the 23.93rd percentile, between the top-decile prediction and the refuting median.
- **H079 testing** (0.40), undecided by its own terms: both scored; the stop-gained allele is in
  Evo 2's top 5.6 %, the pair at the 16.36th percentile.
- **H082 testing** (0.20), undecided by its own terms: 4,318 is neither ≤ 1,000 nor > 10,000.
  But the mechanism it assumed is contradicted: **each GPU lane alone makes the six-lane
  consensus worse**. The claim's 20,639 baseline was also stale: GPN-MSA had already moved it
  to 2,734.

The confidences are the register's transparent heuristic for triage, not calibrated posteriors.

## Why adding lanes pushes the pair down

RRF sums `1/(60 + rank)` over the lanes that rank a pair. A missense-only lane cannot rank a
missense + stop-gained pair, so it adds nothing to this pair. It does add votes to every
missense + missense pair, and those pairs climb past it. ESM-C is pure abstention: +722 places.
Evo 2 and NT-v2 do vote for the pair. But they vote at the 16th and 24th percentiles, with
0.01 correlation to each other. That lifts many more pairs than this one. Equal-weight RRF
rewards **how many lanes can see a pair**, not how damaging it is. This is entry 130's
abstention effect, now measured one lane at a time.

## Limitations

- One case, one confirmed pair: "worse" is a single rank moving, not a performance estimate.
- The GPU lanes' recipes are single choices, each justified in its entry: NT-v2 cosine
  distance, Evo 2 mean per-base likelihood delta, ESM-C masked marginal on 129 residues. A
  different recipe (NT-v2's `aux.llr`, a full-length ESM-C context) could rank differently. None
  was tried after seeing this result, on purpose.
- The fusion is fixed (`k = 60`, equal weights), as pre-registered in entry 130. A class-aware
  fusion would be a new method and needs a new claim filed first.
- The ledger misses cold start and idle time; the billing report is authoritative. Modal's
  daily report may still add late rows for 2026-09-23.

## Conclusion

The GPU tier works and was cheap: 3 lanes × up to 39,286 alleles plus a Boltz-2 study for
**$14.57**, behind one contract, one gateway and a traced audit trail. It does not rescue the
consensus. The best single catalogue-free opinion on the pair is still GPN-MSA (0.93rd
percentile). Adding the GPU lanes to equal-weight RRF ranks the pair lower. The next move is a
fusion that accounts for which lanes *can* see a pair. It must be filed as a new claim before
it is run.
