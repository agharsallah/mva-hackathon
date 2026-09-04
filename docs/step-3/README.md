# Step 3 — Rank by phenotype

**Standing:** open. The ranking is built and has run; the claim it supports is registered
but not yet confirmed against the callset. Method: [`../method.md`](../method.md).
Evidence: [`methodology/067`](methodology/067-phenotype-ranking-without-java.md).
Last checked 2026-09-03.

---

## The goal

> **Does an unbiased genome-wide ranking driven by the child's HPO terms agree with the
> panel-first candidate list?**

## Why it matters

Everything found so far came through an **eight-gene panel chosen by hand** from what is
known about the disease. That prior is circular — the search found MVA genes because it
only looked at MVA genes — and a candidate list cannot be corroborated by the assumption
that produced it.

A phenotype ranking is the independent check. It reads the child's symptoms and public
gene-phenotype curation, and it never sees the panel, the callset, or a variant. So when
it places the same gene near the top of five thousand, that is evidence of a different
kind.

## Why it did not wait for steps 1 and 2

[`roadmap.md`](../roadmap.md) sequences this after normalisation and annotation. That
turned out to be unnecessary: ranking **genes** by symptoms needs no callset at all, so it
runs against nothing but two public files. The dependency was assumed, not real.

## What was done

A reimplementation of Exomiser's hiPHIVE **human-only** phenotype path, in Python, with no
JVM and under 100 MB of reference data. Exomiser's own bundles are H2 MVStore databases
and Java-serialised objects — 31.5 GB unpacked, unreadable from Python — but its phenotype
*inputs* are plain text, and the published optimisation study measures human-only at 82.8%
top-10 against 66.6% for the cross-species default. The components that are hard to
reproduce are the ones the evidence says to leave out.

The package is [`src/mva/phenotype/`](../../src/mva/phenotype/README.md). Nothing in
`mva.pipeline` changed to accommodate it.

## Headline result

BUB1B ranks **6th of 5,267 genes** on the child's own seven features, from a scorer that
never saw the candidate panel — and **26th of 18,882** in Phen2Gene, an unrelated method.
The full table, including where the other seven panel genes landed and why, is in
[`methodology/067`](methodology/067-phenotype-ranking-without-java.md) §5.

Two questions the roadmap had open are now answered with numbers:

- **The parental term `HP:0200067` should be excluded** from the proband's term set. Every
  panel gene rises without it; BUB1B rises 8 places.
- **Constraint-free corroboration exists.** The ranking reconstructs the panel's own
  confidence ordering — established genes in the top 26, the two the panel labels "case
  reports" and "candidate" at 1,010 and 4,485.

## What is still open

The ranking is over **genes**. It says nothing about which alleles are broken, and it must
not be fused into per-variant evidence. The confirmatory test — joining the ranking to the
callset's rare protein-altering alleles — is the next thing to run, and it is the one that
could still refute the corroboration.

## Contents

| Path | Holds |
|---|---|
| [`methodology/`](methodology/) | Executed runs, from entry 067 (filed as 056, renumbered) |
| [`notes/`](notes/) | Decisions belonging to this step |
