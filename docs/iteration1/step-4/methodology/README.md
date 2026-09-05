# Methodology log — step 4

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
| [072](072-genome-wide-suppressed-calls.md) | Is a second allele hiding in a filtered call, genome-wide? **BUB1B has no non-PASS coding candidate; 26 rescue-only genes, none with a P/LP or LoF allele or a top-30 rank.** _(H007 supported 0.80; H006 retrospective, supported 0.77.)_ |
