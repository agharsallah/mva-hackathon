# 130 — A consensus of lanes that declined to vote

**Written:** 2026-09-19. **Step:** `step-6` (iteration 4). **Run:** R6 of the wave-2 chain,
and the last of it. **Hypotheses tested:** H064 (plan label `P4-8`).

Closes the R1 critical path: record → registry → cache → rank → report → **merge**.

## Question

Do the four lanes agree, and does the merged report's reciprocal rank fusion place the confirmed
`BUB1B` pair first among the callset's biallelic pairs once the catalogue-adjacent lane is
excluded?

## Hypothesis and prediction

*Written before the merged JSON was read.* Filed as H064.

| | |
|---|---|
| **Statement** | `P4-8`: the RRF consensus places the confirmed BUB1B pair first among the callset's biallelic pairs when catalogue-adjacent lanes are excluded. |
| **Prediction** | In `docs/iteration4/report.md` §3, the catalogue-free row's confirmed-pair RRF rank is **1**. |

## What would refute it

*Written before the run, quoted from [`plan.md` §5](../../plan.md).*

> The confirmed pair's catalogue-free RRF rank is **outside the top 5** — the disagreement table
> then names the lanes responsible.

## Inputs

| input | value | role |
|---|---|---|
| `results.it4_model_ranks` | 402 rows, run `it4-dcda40a4df2c` | the four per-lane rankings |
| `warehouse.allele_scores` | 58,480 rows | the agreement matrix and the disagreement table |
| `build/it4/merged.json` | — | every number §1–§4 of the merged report prints |
| RRF | k = 60 | Cormack, Clarke & Buettcher, SIGIR 2009 |

## Commands

```bash
uv run mva-zoo run --config src/mva/zoo/zoo.example.toml    # merge + render
curl -sS https://api.crossref.org/works/10.1145/1571941.1572114
```

## Observed

### The RRF DOI, verified

Plan §11 lists `10.1145/1571941.1572114` as **from memory, verify by Crossref before citing**,
and assigns the check to the first step that cites it. `GET https://api.crossref.org/works/10.1145/1571941.1572114`
returned, on 2026-09-19:

| field | value |
|---|---|
| DOI | `10.1145/1571941.1572114` |
| title | Reciprocal rank fusion outperforms condorcet and individual rank learning methods |
| authors | Cormack Gordon V.; Clarke Charles L A; Buettcher Stefan |
| container | Proceedings of the 32nd international ACM SIGIR conference on Research and development in information retrieval |
| issued | 2009-07-19 |
| pages | 758-759 |
| publisher | ACM |

Every field matches what `mva.zoo.merge.RRF_CITATION` already said. The citation now states the
DOI **and the date it was checked**; the test that pinned the `(DOI to verify)` caveat now pins
the verification (`6c054bf`).

### The consensus

| run | lanes | excluded | k | confirmed pair's rank | of pairs | percentile | fused score |
|---|---|---|---|---|---|---|---|
| **catalogue-free** | alphamissense, esm1b, spliceai | revel | 60 | **20,639** | 52,012 | 39.68 % | 0.000083 |
| all lanes | + revel | — | 60 | 21,497 | 52,219 | 41.17 % | 0.000083 |

### Why: three lanes declined to vote

| lane | pairs ranked | pairs unscored | rank of the confirmed pair |
|---|---|---|---|
| `alphamissense` | 10,333 | 53,014 | — |
| `esm1b` | 3,673 | 59,674 | — |
| `revel` (adjacent) | 10,456 | 52,891 | — |
| `spliceai` | 50,696 | 12,651 | **11,980** |

The fused score **0.000083 is exactly `1 / (60 + 11,980)`** — SpliceAI's reciprocal rank, alone,
with no other term in the sum. Three lanes scored one half of the pair and could not score the
other, and `mva.zoo.rank` excludes a pair with an unscored half rather than scoring it zero. A
fusion over lanes that decline to vote is one lane's opinion divided by four, and that is what
§3 reports.

### The agreement matrix

Spearman ρ, with the shared-allele count:

| ρ (n) | alphamissense | esm1b | revel | spliceai |
|---|---|---|---|---|
| alphamissense | — | +0.580 (3,943) | +0.186 (9,365) | +0.033 (9,532) |
| esm1b | +0.580 (3,943) | — | +0.168 (3,997) | +0.043 (4,051) |
| revel | +0.186 (9,365) | +0.168 (3,997) | — | +0.021 (9,816) |
| spliceai | +0.033 (9,532) | +0.043 (4,051) | +0.021 (9,816) | — |

Two blocks. The three missense lanes agree weakly to moderately (+0.168 … +0.580); SpliceAI
agrees with none of them (+0.021 … +0.043). That is the expected shape — splice disruption and
amino-acid damage are different mechanisms — and it means the zoo holds **one opinion about
protein damage sampled three times, and one about splicing**, which is a thin basis for a
fusion.

**The catalogue-adjacent lane is the least typical missense lane.** REVEL correlates with
AlphaMissense at +0.186 and with ESM1b at +0.168, both *lower* than the two catalogue-free
missense lanes agree with each other (+0.580).

### The disagreement table

Ninety rows in the JSON, twenty printed. **Every one has the same shape**: SpliceAI in the top
1 % against a missense lane in the bottom half. There is no row of the opposite kind, because
SpliceAI's distribution is degenerate (median 0, p90 0.03) and almost nothing is in its bottom
half by a meaningful margin. The table names the lanes the refutation clause asks for, and the
answer is that the disagreements are not what sank the pair — the abstentions are.

### The ablation

The two §3 rows differ by 858 ranks out of ~52,000 and share an identical fused score. Excluding
REVEL moves the consensus by 1.5 percentile points, because REVEL has no rank for this pair
either. **The catalogue leak a reviewer checks first is not load-bearing in this run** — which
is a real, if deflating, answer to the question D4 was asked to settle.

## Evidence recorded

| evidence | direction | claim |
|---|---|---|
| the catalogue-free RRF consensus places the pair at rank 20,639 of 52,012 — far outside the top 5 | refutes | H064 |
| the fused score is exactly 1/(60 + 11,980): only SpliceAI voted, the other three lanes had no rank | refutes | H064 |
| excluding the catalogue-adjacent lane moves the rank by 858 of ~52,000 and leaves the fused score identical | neutral | H064 |

## Verdict

**H064 (`P4-8`) — refuted, confidence 0.02.** The claim predicted rank **1** and pre-registered
"outside the top 5" as refuting. The measurement is **20,639 of 52,012**. There is no reading of
that as a near miss.

**The refutation clause asks the disagreement table to name the lanes responsible, and the
honest answer is that it names the wrong thing.** The disagreements are uniform and benign —
splice-window alleles that missense models find unremarkable. What sank the pair is not
disagreement but **abstention**: AlphaMissense, ESM1b and REVEL are missense-only, the confirmed
pair is half `stop_gained`, and none of the three could rank it at all. The consensus is one
lane's opinion, and that lane is a splice model looking at two changes that do not act through
splicing (`ds_max` 0.03 and 0.00, both far under SpliceAI's own lowest published cut-off of 0.2).

**This was pre-registered as a risk and is being recorded as it was predicted, not
rationalised.** Plan §10 R9 named exactly this failure mode before the iteration began;
[114](../../step-1/methodology/114-one-record-per-allele-and-what-it-can-be-spelled-as.md)
read the pair's two consequence classes off the record set on day one and recorded GPN-MSA's
promotion as due; [119](../../step-2/methodology/119-four-lanes-fetched-licensed-and-joined.md)
confirmed it with coverage; [129](../../step-5/methodology/129-what-each-lane-says-about-a-pair-it-can-only-half-see.md)
measured it as an absent rank. Four entries, one cause, no surprise.

**What the zoo did establish**, and it is not nothing: three models of different provenance —
structure-aware, protein-language, ClinVar-trained — independently place the pair's *missense*
allele in the top 0.47 %, 2.52 % and 2.59 % of everything they scored (entry 129). The
machinery, the cache, the lineage and the ablation all work; the roster is what is wrong.

## Limitations

- **RRF over a thin lane is not weighted by what the lane saw.** ESM1b ranked 3,673 pairs and
  SpliceAI 50,696, yet each would cast a full first-place vote. The plan's `thin-lane effect`
  is real here and is a reason not to read §3 as four independent opinions.
- **`n_pairs` differs between the two ablation rows** (52,012 vs 52,219), so the two ranks are
  not on quite the same scale; both are printed with their denominator.
- **Sixteen genes are absent from the pair set** ([128](../../step-4/methodology/128-one-command-eight-stages-and-three-things-a-fixture-could-not-catch.md)),
  so "of 52,012 pairs" means the pairs outside those genes.
- **Section 5 of the merged report is hand-written**, so it is not reproducible from the run; it
  is signed and dated, and the LLM modes that would make it reproducible are opt-A.
- **No claim here is about the pair being causal.** It is confirmed by the oracle in iteration 1;
  this iteration asks only what open models say about it, and the answer is that these four
  mostly cannot say anything.

## Next test

None in this chain — R6 closes it. The revision `P4-6` and `P4-8` are both owed is a lane that
scores a nonsense allele (GPN-MSA, plan §10 R9, opt-A), after which the chain re-runs from step
3 and both claims are re-filed as new revisions.
