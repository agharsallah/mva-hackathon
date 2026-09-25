# Methodology log — iteration 4, step 10

Append-only. Entries are numbered globally; each carries `## Hypothesis and prediction`,
`## What would refute it` (written before the run) and `## Verdict` (after).

| entry | tests | result |
|---|---|---|
| [154](154-screen-wide-prism-sweep.md) — S1, the screen-wide PRISM sweep | H093 (`P4-28`) | H093 **refuted** 0.10: no Launched drug reaches q < 0.10 in either contrast (best 0.122 rhabdomyosarcoma, 0.287 aneuploidy); the positive-control sweep passes |
| [155](155-convergence-and-checks.md) — S2, convergence, checks, the candidate table | H094 (`P4-29`), H095 (`P4-30`) | H094 **refuted** 0.15: one shared drug (dasatinib), null p95 1.0, p 0.263. H095 **supported, weak** 0.40: dasatinib passes K1–K3; pre-known lead; K3 self-referential for G3 drugs |
