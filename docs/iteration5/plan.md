# Iteration 5 — allele-first Track 2

**Standing:** plan, written 2026-09-25. Nothing here is a result. One step
([`step-1/`](step-1/README.md)); exploratory, no pre-registered claims
([note](notes/exploratory-no-hypotheses.md)). Methodology numbers are assigned at filing time
(re-check on disk — parallel sessions take numbers).

## The question

Start from the child's two `BUB1B` alleles — one `stop_gained`, one missense — and the BubR1
protein, not from the drug databases. Which therapeutic route exists **per allele**, which one
passes its own positive control, and which lab test picks between them?

## Why this shape (what iterations 2 and 4 taught)

| earlier route | outcome | lesson |
|---|---|---|
| PrimeKG walk (G1, entry 142) | hubs on top | graph proximity ≠ mechanism |
| PRISM sweep (G3, entry 154) | nothing past correction | cancer lines ≠ a constitutional hypomorph |
| LINCS reversal (G4, entry 153) | positive control failed | mRNA of a cell-cycle gene reads as arrest |
| convergence (entry 155) | chance level | weak sources do not add up |
| phenotype twin (entry 150) | NAD⁺/SIRT2, senolysis | mechanism-first found the real leads |

## Four routes, one step

| id | route | question | positive control |
|---|---|---|---|
| R1 | allele-specific | can the stop allele be read through (stop codon, context, NMD)? what does the missense branch (unstable vs inactive) allow? | published measured readthrough of known premature stops |
| R2 | protein-level readout | which compounds raise BUB1B **protein** in drug-perturbation proteomics; does a cell-cycle-corrected LINCS signature pass the control entry 153 failed? | a textbook protein induction (e.g. HSP90 inhibition → HSPA1A); SAC-gene similarity after correction |
| R3 | quote-verified literature | every intervention reported to change BubR1 level, acetylation or function, each row backed by a sentence verified in the source text | recovers North 2014 (PMID 24825348) and the senescent-clearance papers (PMIDs 18516091, 22048312) unprompted |
| R4 | decision + value of information | per branch (stop readthrough feasible? missense unstable or inactive?), which candidate is best for this child, and how much would the cycloheximide-chase blot change the choice? | the tree reproduces a hand-worked case |

## Contracts

- Tables: `ressources/track2/it5/`, each with a `.provenance.json` in the existing format.
- Every route emits `ressources/track2/it5/<route>_candidates.tsv` with the columns
  `drug_name, route, branch, evidence_kind, evidence_strength, positive_control_passed,
  source, notes`; `branch` ∈ `stop_allele | missense_unstable | missense_inactive | any`;
  `evidence_strength` ∈ [0, 1] from a rubric stated in the route's entry.
- Figures: `figures/it5/`. Code: `src/mva/drugs/` (case-agnostic, parameterised by a card) and
  one driver per route under `tools/`.
- Inputs from iteration 4 reused as-is: the mechanism card, the phenotype twin (entry 150),
  per-child safety (entries 152, 155), the stability atlas (entry 149).
- No coordinate leaves `build/`.
