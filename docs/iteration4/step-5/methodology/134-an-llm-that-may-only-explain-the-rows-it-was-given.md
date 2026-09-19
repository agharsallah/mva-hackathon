# 134 — An LLM that may only explain the rows it was given

**Written:** 2026-09-20. **Step:** `step-5` (iteration 4). **Run:** A5 of wave 4 (opt-A).
**Hypotheses tested:** H069 (plan label `P4-7`).

Reads the four report JSONs [129](129-what-each-lane-says-about-a-pair-it-can-only-half-see.md)
produced and writes section 6 of each with an LLM. Sections 1-5 and 7 are untouched: the
numbers are the same numbers, only the prose changes, which is the whole point of the test.

## Question

Can an LLM write the one written section of a model report **without being trusted** — that
is, can every sentence it produces be mechanically traced back to a row of the report it was
given, and can the tracing catch it when it reaches instead for what it already knows?

## Hypothesis and prediction

*Written before the first call. Filed as H069 before the run
(`mva-science hypothesis-add --iteration iteration4 --step step-5`).*

| | |
|---|---|
| **Statement** | `P4-7` (scoped to mode `claude-code`): the LLM-written interpretation of every per-model report cites its numbers — each sentence ends in a row id from that report's own sections 2-5 — so the uncited-sentence rate stays at or under 10 %, and no gene or disease the rows never named appears in the prose. |
| **Prediction** | `mva-zoo narrate --mode claude-code` over all four MVP lanes. For each lane `mva.zoo.narrate_check` reports `uncited_sentences / sentences <= 0.10`, `new_names == ()`, and at most 200 words. |

**Scope, stated before the run.** The plan's `P4-7` says *both* modes. Only `claude-code` is
tested here: `NEBIUS_API_KEY` is not present on this machine, so the `nebius` mode is built,
unit-tested against a fake transport, and **not run**. The claim is filed for one mode and
owes a second revision when a key exists.

## What would refute it

*Written before the run.*

> Any of the four lanes returns an interpretation whose uncited-sentence rate exceeds **10 %**,
> or whose prose names a gene or a disease that appears in **none** of that lane's citable
> rows. Either observation is recorded per lane, never averaged across lanes.

A second, softer failure is recorded but does not refute: a reply over the 200-word budget.
The budget is a house style rule, not a claim about whether the model invents.

## What the model is and is not shown

The prompt is **the fixed rules plus the lane's rows, and nothing else**. There is no system
prompt, no repository context, no question. The call runs `claude -p --output-format json`
with `--restricted` (no command- or code-running tools) and `--strict-mcp-config` (no MCP
server on this machine), from an **empty working directory** so Claude Code's own `CLAUDE.md`
discovery finds nothing — otherwise this project's instructions would silently join every
prompt and the stored prompt would not be the whole input.

The model **does** see the gene symbol: `pair.gene` and `hpo.rank` carry `BUB1B`, because a
report that never names its gene is not a report. What it never sees is the *question* —
nothing asks which gene, which pair or which variant is the answer, and the rules forbid
ranking anything. The check below is what makes that instruction verifiable rather than
hopeful: the model knows the MVA → `BUB1B` association from training text (plan §11, risk
R3), so a gene or disease name the rows never gave it is the fingerprint of recall.

`claude -p` has **no temperature flag** (checked against Claude Code 2.1.278 `--help`). The
config's `[llm] temperature = 0` is therefore recorded for this mode and applied only by
`nebius`. This mode is not bit-reproducible and the report says so.

## Inputs

| input | rows | role |
|---|---|---|
| `build/it4/reports/{alphamissense,esm1b,revel,spliceai}.json` | 4 | the stored section JSON, run `it4-dcda40a4df2c` |
| `docs/iteration4/reports/*.md` | 4 | the hand-written section 6 of each, read back and kept |
| Claude Code CLI | 2.1.278 | the `claude-code` mode's transport |
| `src/mva/zoo/zoo.example.toml` | `[llm]` | mode, model, temperature, `max_words = 200` |

## Commands

```bash
uv run mva-zoo narrate --config src/mva/zoo/zoo.example.toml --mode claude-code --dry-run
uv run mva-zoo narrate --config src/mva/zoo/zoo.example.toml --mode claude-code
```

## Observed

Four lanes, four calls, one model (`claude-opus-5[1m]`, read back from the reply's
`modelUsage` block — the CLI's own default; no `--model` was pinned).

### The claim's numbers

| lane | sentences | cited | uncited | uncited rate | words | ids that resolve to no row | gene/disease the rows never gave |
|---|---|---|---|---|---|---|---|
| `alphamissense` | 9 | 9 | 0 | **0.00** | 199 | none | none |
| `esm1b` | 13 | 13 | 0 | **0.00** | **213** | none | none |
| `revel` | 10 | 10 | 0 | **0.00** | 200 | none | none |
| `spliceai` | 9 | 9 | 0 | **0.00** | 197 | none | none |

41 sentences, 41 citations that resolve, **0 uncited**, **0 invented ids**, **0 new names**.
The bar was 10 %; the observed rate is 0 %.

The table is reproducible from the stored rows alone — the checker is pure string work over
`reply` and the report's own rows:

```bash
uv run python - <<'EOF'
import json, pathlib
from mva.zoo.narrate_check import check_narrative
from mva.zoo.narrate_rows import citable_rows
for p in sorted(pathlib.Path("build/it4/reports").glob("*.json")):
    d = json.loads(p.read_text()); rows = citable_rows(d)
    block = d["sections"]["interpretation"]
    for v in [block, *block.get("alternatives", [])]:
        print(d["model"], v["llm_mode"], check_narrative(v["text"], rows, max_words=200).summary())
EOF
```

### Cost and time

| lane | seconds | USD |
|---|---|---|
| `alphamissense` | 28.4 | 0.117 |
| `esm1b` | 27.4 | 0.122 |
| `revel` | 31.1 | 0.130 |
| `spliceai` | 40.8 | 0.165 |
| **total** | **127.7** | **0.534** |

For comparison, the whole deterministic chain (R6) runs at zero marginal cost. Prose is the
most expensive thing in this pipeline per byte produced, and it produces no result.

### The hand-written sections, measured by the same checker

| lane | sentences | cited | uncited rate | words | tokens the "new name" rule caught |
|---|---|---|---|---|---|
| `alphamissense` | 8 | 0 | 1.00 | 195 | `MVP` |
| `esm1b` | 7 | 0 | 1.00 | 173 | — |
| `revel` | 7 | 0 | 1.00 | 159 | `REVEL` |
| `spliceai` | 7 | 0 | 1.00 | 186 | `SNV` |

**This is not a finding about the human.** The hand-written sections cite at *section*
granularity — "(§3, marks)", "(§4)" — and the checker only understands *row* ids. The two
conventions are different, and the checker was written for one of them. What the row shows is
that the machine convention is the checkable one: a section reference cannot be resolved
mechanically, a row id can. The three flagged tokens are all false positives of the
gene-symbol shape rule (`MVP`, `SNV`, and `REVEL` — the lane's own name, which reaches the
rows only in lower case). `check_narrative(extra_safe=...)` exists for exactly this and was
not used here, so the false positives are visible rather than suppressed.

### What the generated prose actually does

Every lane's section 6 says the same three things in its own numbers: how much of the record
set the lane could score, that its silence on a class is an absence of opinion rather than a
verdict of harmless, and that a pair with one unscored half leaves the ranking rather than
scoring zero. None of the four asserts a cause, ranks anything, or reaches for `BUB1B`'s
known association — which is the behaviour the rules asked for and the checker verified.

## Verdict

**H069 (`P4-7`, scoped to `claude-code`) — supported.** Every one of 41 sentences across four
lanes ends in a citation that resolves to a row of that lane's own report; none names a gene
or disease outside the rows. The refutation condition (any lane over 10 % uncited, or any new
name) was met by no lane.

**The soft failure, recorded as pre-declared:** `esm1b` came back at **213 words** against a
stated budget of 200. `narrate_check` flags it (`over_length`); it does not refute, because
the claim is about invention, not length. The prompt states the budget and the model missed
it by 6.5 % on one of four calls.

## Limitations

- **One mode.** `nebius` was **not run: no key** on this machine. It is built and unit-tested
  against a fake transport; the claim is filed for `claude-code` alone and owes a revision.
- **Not reproducible.** `claude -p` has no temperature flag, so the same prompt can return
  different prose. The *prompt* is reproducible and stored; the reply is a record, not a
  function. `nebius` at `temperature = 0` is the mode that would close this.
- **The checker is shape-based, not a gene list.** It flags any `[A-Z][A-Z0-9]{1,9}` token the
  rows never gave, which catches `MVP` and `SNV` as readily as `CEP57`. That is the safe
  direction to err, and the false positives are listed above rather than hidden.
- **A citation is not a justification.** The checker proves a sentence *points at* a row. It
  does not prove the sentence is a correct reading of it. A human still reads section 6.
- **Provenance wrinkle in this run.** The eight rows this run stored carry
  `run_id = it4-2962e3117b5c` — the config digest *at narrate time*, which changed when the
  `[llm]` keys were added to `zoo.example.toml`. They explain the reports of run
  `it4-dcda40a4df2c`. The defaulting was corrected straight after (a narrative's `run_id` is
  now the run of the report it explains, so `it4_narratives.run_id` joins
  `it4_model_reports.run_id`); the mapping for *these* eight rows is the one stated in this
  sentence. The narrate call's own digest stays on the lineage edge's `source_version`.

## Outputs

| artifact | where |
|---|---|
| four reports, section 6 in two versions each | [`../../reports/`](../../reports/) |
| the narratives, prompt and reply included | `results.it4_narratives` (8 rows) + one `warehouse.data_lineage` edge |
| the run log | `build/it4/a5-narrate-claude-code.log` (not tracked) |
