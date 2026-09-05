# Methodology log — step 2

**Standing:** open. Entries below, numbered in the global sequence. Last checked 2026-09-05.

One entry per test actually executed. **Nothing here is estimated or assumed** — every
number is copied from a run whose output was seen.

From step 1 on an entry is **a test bound to a hypothesis**. It carries three sections the
step-0 entries lack: `## Hypothesis and prediction` and `## What would refute it`, both
written *before* the run, and `## Verdict` after it. The template is spelled out in
[`../../step-1/methodology/README.md`](../../step-1/methodology/README.md); the loop it
serves is [`../../method.md`](../../../method.md).

**No patient variant coordinates appear here**, per
[no patient data in the repository](../../../notes/no-patient-data-in-the-repository.md).

Entries are **append-only**: a superseded finding is corrected by a new entry that says so,
never by editing the old one. This index may be corrected; the numbered entries may not.

New tooling this step needs — an app page, an API route, a module — is recorded in *this*
log, not in a step of its own.

## Environment

The environment is the one recorded in
[`../../step-0/methodology/README.md`](../../../step-0/methodology/README.md). Reproduce it with
`tools/setup-env.sh`, then `source tools/activate.sh`.

## Entries

| # | Question |
|---|---|
| [069](069-layer-2-coding-scan.md) | Which alleles can alter a protein, genome-wide? **Coding-interval reference (223,048 intervals, 19,750 genes) + layer 2: 38,437 (gene, allele) rows, 38,087 distinct alleles; BUB1B contributes exactly its two.** Tooling: `build_coding_regions.py`, `analysis_coding.py`, `annotate-coding`, the `{res}` placeholder. _(H004 pre-registered.)_ |
| [070](070-genome-wide-annotation-and-verdict.md) | Does any coding gene outrank the BUB1B pair? **All 38,087 alleles annotated; 65 genes biallelic on PASS calls; exactly one with a ClinVar pathogenic allele and a phenotype rank ≤ 30 — BUB1B.** _(H004 supported 0.93; H003 retrospective, supported 0.93.)_ |
