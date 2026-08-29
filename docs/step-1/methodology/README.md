# Methodology log — step 1

**Standing:** open, empty. No test has run under this step. Entries appear here numbered
from **018**, continuing the global sequence that
[`../../step-0/methodology/`](../../step-0/methodology/) started. Last checked 2026-08-29.

One entry per test actually executed. **Nothing here is estimated or assumed** — every
number is copied from a run whose output was seen.

**No patient variant coordinates appear here**, per
[no patient data in the repository](../../notes/no-patient-data-in-the-repository.md).
Entries record counts, distributions and classifications; positions stay in
`~/ubuntu/work/`.

Entries are **append-only**: a superseded finding is corrected by a new entry that says so,
never by editing the old one. This index may be corrected; the numbered entries may not.

---

## What changed at step 1

A step-0 entry answers *what did we build, and what did we measure*. It ends in
**Conclusions**, and that was the right shape for machinery.

From here on an entry is **a test bound to a hypothesis under a research goal**, so it
carries three sections the step-0 entries do not — and two of them are written *before* the
run, which is the whole point:

```markdown
# 0NN — <question>

**Step:** step-1   **Hypotheses tested:** H003, H004

## Question
What is being asked, and why now.

## Hypothesis and prediction        <- BEFORE the run
H003: <the claim>. If true, <what must be observed>.

## What would refute it             <- BEFORE the run
<the observation that would kill the claim>

## Inputs
Files, versions, parameters. Cite the `data_lineage` rows where the inputs are warehouse
tables.

## Commands
Exactly what was run, copy-pasteable.

## Observed
The output, as it came out. No interpretation here.

## Evidence recorded
The `evidence_id` rows this run produced, and which way each cut:

    uv run mva-science evidence-add --hypothesis H003 --direction supports \
        --strength 0.7 --claim '<one sentence>' --source-ref methodology/018

## Verdict
Per hypothesis: the status, the confidence, and the reason. Quote the arithmetic from
`mva-science verdict`, and say plainly where the committed number departs from it.

## Next test
What this makes worth doing next, and what it rules out.
```

Writing the refutation condition before the run is what stops a result from being
reinterpreted afterwards to fit. The register enforces it: a claim with no `refuted_by` is
rejected at construction.

The loop this serves is [`../../method.md`](../../method.md). The claims themselves are in
[`../hypotheses/`](../hypotheses/).

## Environment

Unless an entry states otherwise, the environment is the one recorded in
[`../../step-0/methodology/README.md`](../../step-0/methodology/README.md). Reproduce it
with `tools/setup-env.sh`, then `source tools/activate.sh`.

## Entries

None yet.
