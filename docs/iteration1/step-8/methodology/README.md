# Methodology log — step 8

**Standing:** open — first entry 078 (2026-09-06). No test has run under this step. Entries appear here numbered
from **069**, continuing the global sequence that
[`../../step-0/methodology/`](../../../step-0/methodology/) started and
[`../../step-3/methodology/`](../../step-3/methodology/) last extended. Entry numbers are
global and monotonic across every step folder. Last checked 2026-09-04.

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
| [078](078-track2-data-layer.md) | From the mechanism card to a first public-API snapshot. **273 targets (27 seed + 246 Reactome pathway members), 3,766 candidate rows from Open Targets/ChEMBL/DGIdb, 336 distinct approved drugs, 747 trial rows, 157 literature rows; zero molecules for BUB1B itself — H011 supported 0.80. Case-agnostic tooling `mva-drugs`, 122 tests, every table with a provenance manifest.** |
