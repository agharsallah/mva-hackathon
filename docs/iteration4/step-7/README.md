# Step 7 — Track 2 — two engines, one graph

**Standing:** status **planned** (declared 2026-09-18 in `src/mva/science/steps.py`,
`ITERATION4`); re-checked 2026-09-19 — **nothing has run, no claim is filed, no methodology
entry exists**. Iteration 4, `step-7`.

**Goal** (from `steps.py`):

> Do a graph walk and a GNN over the same knowledge graph converge on the same approved drugs for the mechanism, and how does each rank against a decoy?

**Plan:** [`../plan.md`](../plan.md) §5, *Step 7*. MVP and optional substeps are labelled there.

## What happened

Nothing. R7 is the one run of the iteration-4 chain that did not execute: R1–R6 ran
2026-09-18/19 and closed the critical path at step 6
([130](../step-6/methodology/130-a-consensus-of-lanes-that-declined-to-vote.md)), and the
board records the chain as ending there — see [`../todo.md`](../todo.md), *Where the chain
ended*.

**Why it is deferred.** Track 2's code (`src/mva/drugs/**`) and its inputs
(`ressources/track2/**`) were being worked by a **different, concurrent session** while
iteration 4's waves ran. Two sessions writing the same engine would have produced a merge
conflict rather than a result, so step 7 was left to the session that owns those files. This
is a scheduling decision, not a finding: nothing about the step was tried and abandoned.

## What R7 needs before it can run

| need | state |
|---|---|
| a mechanism to walk from — the gene and the process the Track 1 result implicates | available: iteration 4's result is about `BUB1B` and the spindle-assembly checkpoint |
| the knowledge graph both engines read (nodes: gene, drug, disease, pathway; edges from the Track 2 snapshot) | owned by `src/mva/drugs/**` in the concurrent session |
| the **graph walk** engine and the **GNN** engine over that same graph | `src/mva/drugs/graph_walk.py` exists; the GNN lane does not |
| a **decoy set** — drugs that should *not* rank, so a ranking can be scored rather than admired | not built |
| a hypothesis with a prediction and a refutation condition, filed **before** the run (`mva-science hypothesis-add`) | not filed |
| the next global methodology number | ≥ 133 — numbers are global and monotonic; check `docs/` before writing |

## Outputs

None yet.

## Limitations

Stated in advance, so the first run does not have to discover them:

- **Convergence is not correctness.** Two engines agreeing on the same approved drugs is
  evidence that they read the same graph, not that the drugs work. The decoy set is what makes
  the comparison a test rather than a demonstration.
- **The graph is a snapshot.** Whatever edges the Track 2 snapshot holds on the day it runs
  are the whole world for both engines; a drug absent from the snapshot cannot rank.
- **Track 1's result is weak input here.** Iteration 4 refuted its own consensus claim
  (entry 130); a mechanism taken from it carries that uncertainty into Track 2.

## Methodology

[`methodology/`](methodology/) — empty. The first entry opens it, and it is a *test bound to a
hypothesis*: `## Hypothesis and prediction` and `## What would refute it` written before the
run, `## Verdict` after it ([`../../method.md`](../../method.md)).
