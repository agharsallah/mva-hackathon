# Step 6 — The merged report

**Standing:** **run 2026-09-19**, extended **2026-09-20**; `P4-8` (H064) **refuted**, H072
(the synthesis's citation check) **supported**. Marked **done** in
`src/mva/science/step_maps/iteration4.py` — `P4-8` is settled, and the revision it is owed
belongs to a later lane, not to an unfinished test. Iteration 4, `step-6`.

**Goal** (from `steps.py`):

> Do the models agree, and what does the merged report conclude under each of the three merge methods?

**Plan:** [`../plan.md`](../plan.md) §5, *Step 6*. `fusion` is the configured method;
**`fusion+synthesis` ran in wave 4** (opt-A, A6) and its narrative sits above the hand-written
one in the merged report. `judge` needs an LLM ranking task and is opt-B, not built.

## What happened

| Claim | Prediction | Verdict |
|---|---|---|
| H064 (`P4-8`) | the catalogue-free RRF consensus ranks the confirmed pair **1** | **refuted** — **20,639 of 52,012** ([130](methodology/130-a-consensus-of-lanes-that-declined-to-vote.md)) |
| H072 | the synthesised narrative cites every sentence to a merged row | **supported at 0.80** — **7 of 7**, 0 invented ids, 0 new names ([137](methodology/137-a-synthesis-that-must-cite-the-lane-it-builds-on.md)) |

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

**Section 5 now carries two versions.** `mva-zoo narrate --merged --mode claude-code`
(`claude-opus-5[1m]`, one call, 20.1 s, **$0.116**) wrote a synthesis from **18 rows** — one
`lane.<model>.rank` per lane, six `rho.<a>.<b>` cells, `rrf.free.rank` and `rrf.all.rank`,
`disagree.n`, `method`, and one `interp.<model>` row carrying what each lane's own section 6
says. **7 of 7 sentences cite a row that was sent**, none cites an id that was not, and no
lane, gene or disease outside the rows appears. The hand-written narrative stays beneath it
with its own badge.

The synthesis reaches entry 130's conclusion from the rows alone, and says it in one line:
**"the consensus here is one opinion plus three abstentions"** — it cannot show agreement,
cannot read silence as harmlessness, and does not establish that anything causes anything. Two
independent writers, the same rows, the same reading.

An accident inside the first hour made the case for storing prompt and reply rather than only
the rendered page: the first render used the per-model slot's marker, the next re-render did
not recognise it and dropped the synthesis — which was then restored from
`results.it4_narratives` with no second call and no second $0.116. Both halves are fixed
(entry 137).

**Predicted, not rationalised.** Plan §10 R9 named this failure mode before the iteration began;
entries [114](../step-1/methodology/114-one-record-per-allele-and-what-it-can-be-spelled-as.md),
[119](../step-2/methodology/119-four-lanes-fetched-licensed-and-joined.md) and
[129](../step-5/methodology/129-what-each-lane-says-about-a-pair-it-can-only-half-see.md) tracked
it from consequence classes to coverage to an absent rank.

## Outputs

| Artifact | Where |
|---|---|
| the merged report, §5 synthesised **and** hand-written | [`../report.md`](../report.md) |
| the synthesis, prompt and reply included | `results.it4_narratives` (model `merged`) |
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
- **`[merge] method` is still `fusion`.** The synthesis is produced by `mva-zoo narrate
  --merged`, not by the run's own render stage, so the run manifest records `fusion`. Wiring
  the config key to it is a change to the workflow's render stage, which another agent owns
  this wave (the exact request is in `build/it4/agents/g3-narrate.md`).
- **A `mva-zoo run` deletes the synthesised §5** until that change lands, because its render
  stage restores only the hand-written narrative. Recovery is one command with no LLM call:
  `uv run mva-zoo narrate --merged --mode none`.
- **The synthesis is not reproducible.** `claude -p` has no temperature flag; the prompt is a
  function of the run, the reply is a record of one call. `nebius` at `temperature = 0` would
  close this and **was not run: no `NEBIUS_API_KEY` on this machine**.
- **No claim here is about the pair being causal.** The zoo ranks; causality is the register's
  business, and the answer key's.

## Reproduce

```bash
uv run mva-zoo run --config src/mva/zoo/zoo.example.toml
curl -sS https://api.crossref.org/works/10.1145/1571941.1572114
uv run mva-zoo narrate --config src/mva/zoo/zoo.example.toml --merged --mode claude-code --dry-run
uv run mva-zoo narrate --config src/mva/zoo/zoo.example.toml --merged --mode claude-code
```

## Methodology

[`methodology/130`](methodology/130-a-consensus-of-lanes-that-declined-to-vote.md) — the DOI
check, the consensus, the matrix, the disagreement table and the verdict.
[`methodology/137`](methodology/137-a-synthesis-that-must-cite-the-lane-it-builds-on.md) — the
18 rows, the synthesis, its citation check, the marker incident and H072's verdict.
