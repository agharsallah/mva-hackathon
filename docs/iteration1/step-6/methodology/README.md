# Methodology log — step 6

**Standing:** open. Entries below, numbered in the global sequence. Last checked 2026-09-09.

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
| [074](074-submission-v1-design.md) | Submission v1: the pair at rank 1, every other row a question. **8 rows rehearsed on the replica: 100 / 1.0 if the pair is right; 7 distinguishable replies over 8 answer keys, 1.455 bits expected gain. Not uploaded — 0 of 6 spent.** _(H009 → testing.)_ |
| [076](076-iteration-tooling.md) | Can iteration 1 be rebuilt from the repository alone, and can iteration 2 be opened without hand-work? **Coordinate-free selectors (`spec.selectors.json`) resolve to the same 7 coordinates the CSV was built from — same sha256, all 8 keys still agree with the organisers' scorer; a folder gate (`check_iteration.py`) and a scaffolder (`new_iteration.py`) join the tooling; the decode-table PNG is sized to its rows.** _(tooling for step 6, no hypothesis.)_ |
| [082](082-derived-submission-rows.md) | Can every non-coordinate field of the submission CSV be derived from the warehouse and the register instead of typed? **Yes: notes quote only result-table columns, epcr is anchored on the register's confidence for H009 and shared by pair score, priors follow the rows; the tool refuses a typed epcr, note, number or a mis-ranked anchor. Same 7 coordinates, 8 of 8 keys agree with the organisers' scorer; sha256 changes; expected gain 0.963 bits under the derived priors.** _(tooling for step 6; H009 unchanged.)_ |
| [083](083-oracle-reply-submission-1.md) | What did the oracle say to submission 1? **Rank points 100.0 / 100, F-max 1.000, F-max epcr threshold 0.9963, full match at rank 1 — decode-table row 1, sole survivor stop+missense. H009 → `supported` (revision 3); probe 1 logged; 1 of 6 spent; iteration 1 frozen, iteration 2 opened as a draft with its own plan and steps to declare.** _(H009 → supported.)_ |
