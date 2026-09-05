# Step 7 — Knowledge and literature

**Standing:** open, nothing executed. No hypothesis is filed and no test has run under this
step. Desk and API work with no shared bottleneck — it runs beside steps 1–5.
Method: [`../method.md`](../../method.md). Last checked 2026-09-04.

---

## The goal

> **Does public knowledge - published MVA cases, ClinVar, protein-model scores - name an
> allele or a pair the data-driven steps missed, or independently corroborate the one they
> found?**

## Why it matters

- The data-driven steps all read the same VCF. They can agree and still be wrong together.
- Published knowledge is a genuinely independent source: a matching published
  compound-heterozygous case *is* the answer key.
- Protein-model scores (zero-shot predictions of whether an amino-acid change breaks the
  protein) rank missense candidates the population filters cannot separate.
- Nothing here needs the callset normalized, so it costs no critical-path time.

## Already done

Nothing. The ClinVar presence join is counted under step 2.

## Remaining

- **Reported-allele catalogue** — literature mining plus ClinVar for every published
  MVA / spindle-assembly-checkpoint allele, joined against the callset.
- **Protein-model scores** — zero-shot scores on missense candidates, plus domain mapping;
  a kinase-domain hit outranks a linker hit.
- **LLM evidence tournament** — pairwise judged matches between candidate pairs, every
  judgment carrying a citation or discarded, fused with the mechanical rank.
- **Case-report hunt** — the MVA literature searched against the child's phenotype vector.
- **Trap-first conditional partner search** — for each strong single allele, search
  *conditionally* for its partner instead of ranking pairs symmetrically.
- **Spike-in harness** — inject known MVA pairs into public benchmark callsets and reads,
  and measure whether each method recovers them. The only honest pre-oracle calibration.

## Exit criterion

Verdicts on two claims: that no published allele beats the current candidate, and that the
spike-in recovery rate is **measured** rather than assumed.

## Report artifact

The tournament bracket with cited judgments, the catalogue-overlap table, and the spike-in
recovery table per method — the portfolio's honesty proof.

## Tooling this step may need

A case-agnostic allele-catalogue fetcher and joiner, the audited tournament re-ranker, a
conditional-partner mode in `pipeline/ranking.py`, and the spike-in harness. Recorded in
this step's methodology.

## The record

| | |
|---|---|
| Hypotheses | none recorded yet — [`hypotheses/`](hypotheses/), written by `mva-science export` |
| Tests | none run under this step — entries land in [`methodology/`](methodology/), numbered from 069 |
| Rendered | `figures/science-report.html` |
