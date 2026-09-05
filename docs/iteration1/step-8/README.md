# Step 8 — Track 2, drug repurposing

**Standing:** open for desk research, nothing executed. **Zero code exists for this step.**
Verdicts wait on step 6. Method: [`../method.md`](../../method.md).
Last checked 2026-09-04.

---

## The goal

> **Which market-approved drugs act on the mechanism the confirmed alleles imply, and how
> strong is the evidence for each?**

## Why it matters

- Track 2 is a separate scored deliverable, not a footnote to Track 1.
- It is the only part of the work that reaches the child: a repurposed drug is one already
  approved and therefore available.
- The mechanism argument is the product. A drug named without a cited path from the allele
  to its target is worth nothing.
- **Timing:** desk research opens in **week 2**, in parallel with steps 1–7. Ranking and
  verdicts wait until step 6 confirms the pair — a mechanism argued from an unconfirmed
  allele is a guess dressed as rigour.

## Already done

Nothing.

## Remaining

- **Mechanism characterisation, structured along methods-form Q14:** loss- versus
  gain-of-function, the pathway, and the downstream consequence. Here: spindle-assembly
  checkpoint weakening → chromosome missegregation → aneuploidy → proteotoxic stress and
  tumorigenesis.
- Directions named in the brief, none yet investigated: agents that reinforce the
  checkpoint; aneuploidy-selective stressors exploiting proteotoxic and metabolic stress;
  proteostasis strategies if the allele is a hypomorph (partly working, not dead); a
  cancer-prevention framing for the child's actual malignancy.
- **Sources**, per the form: **DrugBank, ChEMBL, ClinicalTrials.gov, OMIM, PubMed**.
  **Market-approved drugs only.** LLM-assisted search is explicitly legitimate.
- Every candidate registered as a hypothesis with its refutation condition before it is argued.

## Deliverables

| | |
|---|---|
| Report | the written submission, structured along methods-form Q14 |
| Code | a public repository, code only — no data slices |
| Video | 3 minutes |
| Submission | one submitter for the team |

## Exit criterion

A ranked candidate list where every drug carries a cited mechanistic link to the confirmed
alleles, and each verdict is registered.

## Report artifact

The drug × mechanism evidence table, and a pathway diagram from the allele to each
intervention point.

## Tooling this step may need

A case-agnostic drug-source fetcher — one adapter per source — and the evidence-table
renderer. Recorded in this step's methodology.

## The record

| | |
|---|---|
| Hypotheses | none recorded yet — [`hypotheses/`](hypotheses/), written by `mva-science export` |
| Tests | none run under this step — entries land in [`methodology/`](methodology/), numbered from 069 |
| Rendered | `figures/science-report.html` |
