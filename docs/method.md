# The method — how a question becomes a scored answer

**Standing:** the scientific method for this project. It owns the loop, the five stations,
and the rules the register enforces. What is *currently* believed lives in the step folders
and in `figures/science-report.html`; this page owns the *shape*, not the content.
Last checked 2026-08-29.

---

## Why this page exists

The repository already answers *where did this byte come from*: the object store is
hash-verified, the ingest is lossless, and `data_lineage` records which bytes produced
which table. That is **provenance**, and it is necessary.

It is not sufficient. A report is made of a different question — *what do we believe, how
strongly, and on what basis* — and nothing in a lineage edge answers it. Before this
framework, findings were recorded as prose ending in **Conclusions**: no claim stated
before the test, no statement of what would refute it, no verdict, no confidence, and no
link from a finding to a submission row. A report written from that has to be transcribed
by hand, and a transcription cannot be checked against anything.

So the record is **machine-readable**, and the report and the submission rows are generated
from it.

---

## The loop

```mermaid
flowchart LR
  subgraph STEP["one research step = one goal"]
    direction LR
    H["<b>Hypothesis</b><br/>a falsifiable claim<br/>+ prediction<br/>+ what would refute it"]:::machine
    T["<b>Test</b><br/>an executed run,<br/>recorded as a<br/>methodology entry"]:::machine
    E["<b>Evidence</b><br/>one observation,<br/>tagged and sourced"]:::machine
    V{"<b>Verdict</b><br/>the evidence weighed<br/>into a confidence"}:::decide
    H --> T --> E --> V
  end
  G[/"<b>Goal</b><br/>the question the<br/>step exists to answer"/]:::raw --> H
  V -->|supported| S["<b>Submission row</b><br/>notes carry the<br/>hypothesis id"]:::good
  S --> O(["the oracle replies"]):::decide
  O -.->|"logged as a probe<br/><b>and</b> as new evidence"| E
  V -->|"refuted or open"| N["deepen the cheapest<br/>unfinished path"]:::machine
  classDef raw fill:#e0d4f7,stroke:#7a5cab,color:#333333
  classDef machine fill:#cfe8ff,stroke:#3d7ebd,color:#333333
  classDef decide fill:#ffe9b3,stroke:#c98f1e,color:#333333
  classDef good fill:#8fd18f,stroke:#3f8f47,color:#333333
```

> **Legend** — **purple = the raw input** (the step's goal, the only thing not derived from
> something else); **blue = neutral machinery** (the stations that transform a claim into an
> observation); **yellow = a decision point** (the verdict, and the oracle reply that may
> change it); **green = the goal** (a scored submission row). Solid arrows are the forward
> path; the dotted arrow is the feedback edge — **an oracle reply re-enters as evidence**,
> so a probe does not merely score, it moves a belief.

---

## The five stations

| Station | What it is | Where it lives |
|---|---|---|
| **Goal** | One question a step exists to answer. Declared in code, reviewable in a diff. | `src/mva/science/steps.py` |
| **Hypothesis** | A falsifiable claim, its prediction, and the observation that would kill it. | `warehouse.hypotheses`, append-only revisions |
| **Test** | An executed run. The methodology entry *is* the test — the reproducible receipt. | `docs/step-<n>/methodology/` |
| **Evidence** | One observation, tagged supports/refutes/neutral, weighted, and carrying its source. | `warehouse.evidence`, append-only |
| **Verdict** | The evidence weighed into a status and a confidence, with a stated reason. | a new revision of the hypothesis |

Then the crossing: a **supported** claim becomes a submission row whose `notes` column
carries its hypothesis id, so a row the scorer sees can be traced back to the claim behind
it. The reply is recorded twice — in `warehouse.probe_ledger` as *what happened*, and in
`warehouse.evidence` as *what it means*.

---

## Steps, and why everything hangs off one

A step declares **one research goal**. Every hypothesis names a step, so the record reads
by question rather than by date.

```
uv run mva-science steps
```

| Step | Kind | Goal |
|---|---|---|
| `step-0` | platform | Can the delivered bytes be trusted, stored without loss, and queried in SQL? |
| `step-1` | research | Does every variant have exactly one spelling, so an exact-match scorer can be trusted with an indel? |
| `step-2` | research | Which variants are rare and damaging enough for an ultra-rare recessive disease, and in which gene? |
| `step-3` | research | Does an unbiased phenotype-driven ranking agree with the panel-first list? |
| `step-4` | research | Is one allele hiding in a call the quality filters discarded? |
| `step-5` | research | Is the missing allele one the caller could not emit at all? |
| `step-6` | research | Which pair does the scorer confirm, and what does each reply tell us next? |

**Step 0 is different, and the difference is the point.** It is *machinery*. "PostgreSQL is
the right database" is a decision with alternatives, judged by whether it works — not a
claim about the patient that evidence can refute. So step 0 takes no hypotheses; its
reasoning lives in [`step-0/notes/`](step-0/notes/) as decisions, and its
[`methodology/001–016`](step-0/methodology/) are platform records. The register refuses a
hypothesis filed under it.

From step 1 on, every methodology entry is a **test bound to a hypothesis under a goal**.

---

## What the register refuses

Enforced in constructors, not asked for in a template — a template is advice, a constructor
is a gate.

| Refused | Why it is worth the friction |
|---|---|
| A hypothesis with no `refuted_by` | A claim nothing could disprove is not a hypothesis. Writing the refutation sentence *before* the run is what stops a result being reinterpreted afterwards to fit. |
| An observation with no `source_ref` | An unverifiable observation is not evidence. The source is a methodology entry, a table, a PMID, a ClinVar id, or a probe reply. |
| A confidence with no stated reason | A number nobody can check is exactly what this register exists to prevent. |
| A genomic position in an exported file | `mva-science export` scans and refuses. Name the gene and the consequence, never the position — see [no patient data](notes/no-patient-data-in-the-repository.md). |
| An edit to anything recorded | Both tables are append-only. A changed belief is a **new revision**, so the record of the belief moving survives. |

---

## The weighing, and its limits

`mva-science verdict H001` accumulates evidence in log-odds and prints every term:

```
prior 0.50  (log-odds +0.000)
  +1.400  supports 0.70 — BUB1B is depleted of loss-of-function variants.   -> 0.802
  -0.600  refutes 0.30 — the second allele is absent from the delivered VCF. -> 0.690
suggested confidence 0.69 (1 supporting, 1 refuting, 0 neutral)
```

**This is a transparent heuristic for triage, not a calibrated posterior.** Strengths are
human judgments, and rows drawn from the same underlying data are not independent the way
the sum treats them. It exists so a suggested confidence can be *argued with*.

It writes nothing. Committing takes `--commit` plus `--reasoning`, and where the committed
number differs from the suggestion by 0.15 or more, both are shown side by side — the gap
is a judgment someone made, and it should be visible rather than reconstructed.

---

## The entry template, step 1 onward

The existing `001–016` keep their shape: they are append-only and were written before this
framework existed, and retro-fitting them would mean inventing hypotheses nobody stated.
New entries add three sections the old ones lack.

```markdown
# 0NN — <question>

**Step:** step-1   **Hypotheses tested:** H003, H004

## Question
## Hypothesis and prediction     <- stated BEFORE the run
## What would refute it          <- stated BEFORE the run
## Inputs                        (with lineage refs)
## Commands
## Observed
## Evidence recorded             <- the evidence_id rows this run produced
## Verdict                       <- per hypothesis, with confidence and reasoning
## Next test
```

Entry numbers stay **global and monotonic** across step folders.

---

## Working it

```bash
uv run mva-science steps                      # the goals
uv run mva-science hypothesis-add --step step-1 \
    --statement '…' --prediction '…' --refuted-by '…' --gene BUB1B
uv run mva-science evidence-add --hypothesis H001 --direction supports \
    --strength 0.7 --claim '…' --source-ref methodology/003
uv run mva-science verdict H001               # arithmetic only, writes nothing
uv run mva-science verdict H001 --commit --status supported --reasoning '…'
uv run mva-science check                       # the publish gate
uv run mva-science export                      # the committed mirror
uv run mva-science report                      # figures/science-report.html
```

The report also renders with no database at all, from the committed mirror:

```bash
uv run mva-science report --from docs/science-register.json
```

That is deliberate — a reviewer with a clone and no credentials sees the same page the
team sees.

---

## Where it all lives

| | Path |
|---|---|
| The step map, in code | [`src/mva/science/steps.py`](../src/mva/science/steps.py) |
| The register and the ledger | `warehouse.hypotheses`, `warehouse.evidence` — see [`step-0/infrastructure.md`](step-0/infrastructure.md) |
| The committed mirror | `docs/step-<n>/hypotheses/`, `docs/science-register.json` |
| The rendered record | `figures/science-report.html` |
| The shared renderer both reports use | [`src/mva/render/`](../src/mva/render/) |
