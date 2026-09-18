# Iteration 4 — the model zoo

**Standing:** opened 2026-09-18; steps declared in `src/mva/science/steps.py` (`ITERATION4`),
all `planned`. No step has run; no claim is filed. Iteration 2 stays the current iteration
(`ITERATION = "iteration2"`); iteration 4 runs beside it.

**Plan:** [`plan.md`](plan.md) — every credible open variant-effect model run under one
contract (record → adapter → cache → rank → template → merge), with lineage, and a merged
report no single model produces. **Board:** [`todo.md`](todo.md) — what is done, what is next,
by wave. Iteration 3 was a draft, absorbed here as step 1; it is not declared.

## Steps

| step | goal (one question) | folder | status |
|---|---|---|---|
| 1 | one normalized allele record every model class can read | [`step-1/`](step-1/README.md) | planned |
| 2 | which open models are credible, runnable, licensed; their coverage | [`step-2/`](step-2/README.md) | planned |
| 3 | one batch inference API, one cache with provenance | [`step-3/`](step-3/README.md) | planned |
| 4 | a checkpointed DAG from one command, costed | [`step-4/`](step-4/README.md) | planned |
| 5 | one report template per model | [`step-5/`](step-5/README.md) | planned |
| 6 | do the models agree; the merged report | [`step-6/`](step-6/README.md) | planned |
| 7 | Track 2: graph walk vs GNN over PrimeKG, against a decoy | [`step-7/`](step-7/README.md) | planned |

Methodology numbering continues globally; the first iteration-4 entry is **111**
(110 is the platform fix that let a claim name its iteration —
[`../step-0/methodology/110-a-claim-names-its-iteration.md`](../step-0/methodology/110-a-claim-names-its-iteration.md)).

## Code

`src/mva/zoo/` ([README](../../src/mva/zoo/README.md)); contracts in `types.py`; synthetic
fixtures in [`fixtures/it4/`](../../fixtures/it4/README.md). Track 2's engine lives in
`src/mva/drugs/graph_walk.py`.
