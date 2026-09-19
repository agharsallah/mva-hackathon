# Iteration 4 — the model zoo

**Standing:** opened 2026-09-18; the **R1 critical path ran 2026-09-18/19** — steps 1 to 6, one
entry and one verdict each; re-checked 2026-09-19 (wave 3: dashboard, API, reusability, docs).
Iteration 2 stays the current iteration (`ITERATION = "iteration2"`); iteration 4 runs beside
it. Track 2 (step 7) has not run — [`step-7/`](step-7/README.md) says why and what it needs.

**The one-line result.** The zoo works and the roster does not: four open models scored 58,480
alleles with full lineage for $0, three of them independently placed the confirmed pair's
*missense* allele in the top 0.5–2.6 % of everything they scored — and **none of them can score
a nonsense allele**, so the merged consensus ranks the *pair* 20,639th of 52,012. The failure
was pre-registered (plan §10 R9) and tracked across four entries before it was measured.

**Plan:** [`plan.md`](plan.md) — every credible open variant-effect model run under one
contract (record → adapter → cache → rank → template → merge), with lineage, and a merged
report no single model produces. **Board:** [`todo.md`](todo.md) — what is done, what is next,
by wave. Iteration 3 was a draft, absorbed here as step 1; it is not declared.

## Steps

Read them on the dashboard at `/steps?iteration=iteration4`, which carries each step's goal,
its claims with their verdicts, and its methodology entries in full. Each step also has its own
page below: what happened, what it produced, what it does not support, and how to reproduce it.

| step | goal (one question) | folder | status | claim → verdict |
|---|---|---|---|---|
| 1 | one normalized allele record every model class can read | [`step-1/`](step-1/README.md) | **done** | `P4-1a` H058 **supported** 0.95 — 0.99953 of 38,087 coding alleles spelled |
| 2 | which open models are credible, runnable, licensed; their coverage | [`step-2/`](step-2/README.md) | **done** | `P4-2a` H059 **supported** 0.80 · `P4-3` H060 **refuted** — AlphaMissense 67.9 %, ESM1b 29.2 % of missense |
| 3 | one batch inference API, one cache with provenance | [`step-3/`](step-3/README.md) | **open** | `P4-4a` H062 **testing** — 1 h 45 m at $0: over the hour predicted, under the 4 h that refutes |
| 4 | a checkpointed DAG from one command, costed | [`step-4/`](step-4/README.md) | **done** | machinery — no hypothesis (see [`method.md`](../method.md)) |
| 5 | one report template per model | [`step-5/`](step-5/README.md) | **open** | `P4-6` H063 **testing** — 2 of 3 lanes have no opinion; SpliceAI 23.63 % |
| 6 | do the models agree; the merged report | [`step-6/`](step-6/README.md) | **done** | `P4-8` H064 **refuted** — RRF rank 20,639 of 52,012, not 1 |
| 7 | Track 2: graph walk vs GNN over PrimeKG, against a decoy | [`step-7/`](step-7/README.md) | **planned** | none filed — deferred to the session that owns `src/mva/drugs/**` |

Two steps are **open** rather than done: each has a claim that its own pre-registered clauses
leave undecided, and the revision both are owed is the same one — a lane that scores a nonsense
allele (GPN-MSA, plan §10 R9).

## Results in one paragraph

Six runs, six entries, one finding. The instrument works: 39,286 alleles normalized with one
spelling each (entry [114](step-1/methodology/114-one-record-per-allele-and-what-it-can-be-spelled-as.md)),
four open models fetched, licensed and joined (entry [119](step-2/methodology/119-four-lanes-fetched-licensed-and-joined.md)),
58,480 scores cached with provenance for "**$0**" (entry [122](step-3/methodology/122-every-lane-scored-once-and-only-once.md)),
the whole chain in one command at "≈ 15 s warm" (entry [128](step-4/methodology/128-one-command-eight-stages-and-three-things-a-fixture-could-not-catch.md)).
The **roster** does not. The confirmed pair is one missense allele plus one nonsense allele,
and every MVP lane is a missense or splice model, so two of the three catalogue-free lanes
recorded *no opinion* on the pair and the third placed it at "23.63 %" (entry
[129](step-5/methodology/129-what-each-lane-says-about-a-pair-it-can-only-half-see.md)); the
RRF consensus landed at "**20,639 of 52,012**", refuting `P4-8` (entry
[130](step-6/methodology/130-a-consensus-of-lanes-that-declined-to-vote.md)). What the zoo did
establish is that three models of different provenance independently rank the pair's *missense*
allele in their top "0.47 %, 2.52 % and 2.59 %". The gap — no lane scores a nonsense allele —
was **pre-registered as risk R9** (plan §10) before any of it ran, and the revision both open
claims are owed is the same one: promote a DNA-level lane (GPN-MSA) and re-run from step 3.

## What to read

| | |
|---|---|
| the merged result | [`report.md`](report.md) — narrative hand-written, every number cited to a table |
| one report per model | [`reports/`](reports/) — seven sections, section 6 hand-written and signed |
| the figures | [`../../figures/it4/`](../../figures/it4/) — 12 files: 4 histograms, the agreement heat map, the confirmed-rank bars |
| what each run cost | [`runs/`](runs/) — the coordinate-free manifests |
| the model cards + licences | [`cards/`](cards/) |
| running the zoo on another illness | [`reusability.md`](reusability.md) — the inputs, the six commands, the honest list of what is still case-specific |
| the board | [`todo.md`](todo.md) — every plan item by wave, ticked with the entry and commit that did it |

Methodology numbering continues globally. Iteration 4's entries are **114**, **119**, **122**,
**128**, **129** and **130** — not a contiguous block, because iteration 2's steps 7 and 8 were
running beside this one and the numbers are handed out in filing order across every step. Step
7 has none.

## Code

`src/mva/zoo/` ([README](../../src/mva/zoo/README.md)); contracts in `types.py`; the case
config in `case_config.py` + [`cases/`](../../src/mva/zoo/cases/README.md); synthetic fixtures
in [`fixtures/it4/`](../../fixtures/it4/README.md). Track 2's engine lives in
`src/mva/drugs/graph_walk.py`. Nothing in the package names this illness: the gene, the docs
folder and the table prefix are one `[case]` block
([note](../notes/zoo-case-config.md), [walkthrough](reusability.md)).
