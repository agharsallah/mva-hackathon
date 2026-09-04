# Step 2 — Annotate the callset

**Standing:** open. The eight-gene panel is annotated and reduces to one BUB1B pair; the
genome-wide pass has not run, and no hypothesis is filed. Method:
[`../method.md`](../method.md). Sequencing: [`../roadmap.md`](../roadmap.md) §1.
Last checked 2026-09-04.

---

## The goal

> **Which variants are rare enough and damaging enough to cause an ultra-rare recessive
> disease, and in which gene?**

## Why it matters

- The delivered VCF carries no annotation worth ranking on. Every variant looks alike.
- Two signals separate ~5M calls into candidates: **rarity** (gnomAD population frequency)
  and **consequence** (VEP — does the change break the protein?).
- A recessive disease allele is essentially absent from the population, so rarity alone
  removes most of the callset.
- Nothing downstream can rank without this: step 3's cross-check and step 6's probes both
  need a genome-wide rare protein-altering set.

## Already done

- Ensembl VEP REST over the eight-gene panel — step-0 methodology
  [031](../step-0/methodology/031-vep-rest-panel-annotation.md). Filtering to rare **and**
  protein-altering leaves one BUB1B pair. Counts:
  [`../../ideation/data-findings.md`](../../ideation/data-findings.md) §6.1.
- ClinVar presence measured site-first, an independent path —
  [051](../step-0/methodology/051-clinvar-presence.md).
- This ran inside step 0 because the machinery was being built at the same time. That is
  why the step opens with results and no hypotheses.

## Remaining

- File the panel result as a `retrospective` hypothesis — the test ran before the claim.
- Build **layer 2** (`variants`, `genotypes`, `variant_info`) so the annotation join has
  somewhere to land — [`../step-0/data-layers.md`](../step-0/data-layers.md).
- A genome-wide backend behind the [annotation port](../notes/annotation-as-a-port.md):
  offline VEP cache plus gnomAD. Backend choice open in [`../decisions.md`](../decisions.md).
- Required fields: gene symbol, consequence, gnomAD popmax AF. Valuable: CADD, REVEL,
  AlphaMissense, SpliceAI, ClinVar significance.

## Exit criterion

The genome-wide rare protein-altering set exists, and the claim *no pair outside the panel
beats the BUB1B pair* has a verdict.

## Report artifact

The filtering funnel — every filter with its removal count.

## Tooling this step may need

Layer-2 tables, the VEP-cache annotation backend, an app page for the funnel. Each is
recorded in this step's methodology, not in a step of its own.

## The record

| | |
|---|---|
| Hypotheses | none recorded yet — [`hypotheses/`](hypotheses/), written by `mva-science export` |
| Tests | none run under this step — entries land in [`methodology/`](methodology/), numbered from 069 |
| Rendered | `figures/science-report.html` |
