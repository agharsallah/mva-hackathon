# Step 4 — Mine the suppressed calls

**Standing:** exit criterion met for coding calls 2026-09-05 — H006 (panel, retrospective) and H007 (genome-wide coding) supported ([072](methodology/072-genome-wide-suppressed-calls.md)). Earlier standing: closed for the eight-gene panel, untested genome-wide. No hypothesis was
filed. Method: [`../method.md`](../../method.md). Sequencing:
[`../roadmap.md`](../../roadmap.md) §1. Last checked 2026-09-04.

---

## The goal

> **Is one of the two alleles hiding in a call the quality filters discarded, rather than
> absent from the sample?**

## Why it matters

- The caller emits a `FILTER` column. A call marked non-PASS is still a call — it was
  observed, then judged unreliable.
- Filters are tuned for a genome-wide false-positive rate, not for one child's disease
  allele. A true variant in a hard-to-map region is exactly what they suppress.
- This is the cheapest place a missing second allele could be: hours of SQL against a day
  of re-calling, so it runs before any FASTQ work.

## Already done

- The panel's 20 non-PASS records were annotated and screened in step-0 methodology
  [049](../../step-0/methodology/049-suppressed-calls.md): **0 rare protein-altering**.
  TRIP13's cluster is a paralogous-read pileup. Numbers:
  [`../../ideation/data-findings.md`](../../../ideation/data-findings.md) §6.2.
- The derivations that did it — `panel_suppressed`, `panel_filter_census` — live in
  `src/mva/warehouse/analysis_suppressed.py` and are reusable genome-wide.

## Remaining

- File the panel result as a `retrospective` hypothesis.
- The genome-wide pass over non-PASS calls, dominated by `MQ40` and `QD2`.
- A **rescue score** that re-weights each filter reason by local mappability instead of
  trusting the caller's verdict.

## Exit criterion

A verdict on whether any suppressed call is a credible second allele.

## Report artifact

The filter-reason × gene heat map, and the before/after rescue funnel.

## Tooling this step may need

Rescue views as `Derivation` records beside the existing suppressed-call analyses; an app
exhibit for the heat map. Recorded in this step's methodology.

## The record

| | |
|---|---|
| Hypotheses | H006 (retrospective), H007 — [`hypotheses/`](hypotheses/) |
| Tests | [072](methodology/072-genome-wide-suppressed-calls.md) |
| Rendered | `figures/science-report.html` |
