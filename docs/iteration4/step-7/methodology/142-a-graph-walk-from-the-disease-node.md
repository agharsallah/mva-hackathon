# 142 — A graph walk from the disease node, and a decoy walked the same way

**Written:** 2026-09-23. **Step:** `step-7` (iteration 4). **Hypotheses:** **H074** (`P4-11`,
specificity against a decoy) and **H075** (`P4-12`, agreement with iteration 2's candidate list),
both filed with `mva-science hypothesis-add --iteration iteration4` **before** any walk ran.

## Question

Step 7's goal asks two things: does a **graph walk** and a **GNN** (graph neural network) over one
knowledge graph converge on the same approved drugs, and how does each rank against a **decoy**?
This entry answers the graph-walk half only. TxGNN (the GNN half) is skipped by the user's
decision of 2026-09-23 (`../../todo.md`, *Close-out*), so `P4-10` is never filed.

The two questions this entry can answer:

1. Is the walk **specific**: does it rank different drugs when started from an unrelated
   disease? (`P4-11`)
2. Does the walk **agree** with the literature/API-derived candidate list iteration 2 built
   (`ressources/track2/drug_candidates.tsv`)? (`P4-12`)

## Hypothesis and prediction

- **H074 / `P4-11`.** The walk's top 20 approved drugs share **≤ 5** with the same walk from a
  decoy card's disease node. Decoy: `XDH`, chosen by plan §12 O6's rule; `NTRK3` only if `XDH`
  fails a rule condition.
- **H075 / `P4-12`.** The walk's top 20 contains **≥ 2** drugs that appear in
  `drug_candidates.tsv` (any row, approved or not).

Both comparisons match drug names through `mva.drugs.names.base_name` (salt words folded,
upper-cased). Pre-registered choices, fixed before the run:

- **Top 20** = the first 20 rows of the ranking after the approved-drug filter.
- **Standard-of-care drugs are not removed** from the walk; they are flagged in a column.
- **Ties** break on drug name, so the ranking is deterministic.

## What would refute it

- **H074:** a top-20 overlap **above 10**. 6–10 is recorded as inconclusive.
- **H075:** **0** matches. 1 is recorded as inconclusive. On a refutation the entry lists which
  expected paths the graph lacks.
