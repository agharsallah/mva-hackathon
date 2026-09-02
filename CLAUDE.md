# Project Instructions

## Goal
- We are competing in the MVA Hackathon 2026: identify the causal compound-heterozygous variant
  pair for one child with Mosaic Variegated Aneuploidy (Track 1) and propose drug repurposing
  candidates (Track 2). The full intelligence brief — challenge rules, scorer mechanics,
  biology priors, oracle protocol, and the master plan — lives in
  [`ideation/hackathon-intel.md`](ideation/hackathon-intel.md). Read it before making strategy
  decisions.
- Be **scientific yet creative**: ground every claim in executed runs and citable evidence, but
  actively try new methodologies (e.g. adaptive oracle probing, novel ranking approaches, new visualization tools) rather
  than only replaying standard pipelines. Innovation is an explicitly judged criterion.
- Build **two deliverables at once**: (1) a solution to this specific case, and (2) a reusable
  tooling set — generic, well-factored modules and pipelines that transfer to other N-of-1 /
  rare-disease problems. Prefer parameterized, case-agnostic tools over one-off scripts.
- The endgame requires **strong reporting with lots of visuals**: every phase should produce
  report-ready material (figures, diagrams, tables, worked examples) as it runs, not as an
  afterthought. Qualitative review of the report and repo is the tiebreaker — treat report
  quality as a first-class output, following the Visualizations rules below.

## Python
- Use `uv` for all Python work: `uv run`, `uv add`, `uv sync`. Do not use `pip`, `python -m venv`, or bare `python`.

## Code structure
- No script or module longer than 400 lines (600 for a test module). When a file approaches
  that limit, split it into domain-driven modules (one bounded concern per module) instead of
  growing the file. Enforced: `uv run python tools/check_module_size.py`.
- Favor reusability: extract shared logic into reusable functions/modules rather than duplicating it.
- Respect the package layering in [`src/mva/README.md`](src/mva/README.md): `io`, `pipeline` and
  `render` are leaves and import no sibling package; nothing outside `mva.viz` may import it.
  Enforced: `uv run lint-imports`.

## Quality gates
Before pushing Python, run `tools/check-python.sh` (add `--fix` to format and autofix first).
It runs the six gates CI runs: ruff format, ruff lint, module size, import layering, mypy,
pytest. Why each rule is set where it is — and what to do when one fails — is owned by
[`docs/notes/python-quality-gates.md`](docs/notes/python-quality-gates.md). Two standing rules:
- A gate that is wrong for a change gets fixed, and the reason recorded in that note. Never
  `--no-verify`, never a bare `# noqa` — a suppression states its reason inline.
- mypy's per-package strict list in `pyproject.toml` is a ratchet: packages come off the
  permissive list as they are annotated, never back onto it.

## Documentation rules
- One doc index: `docs/README.md`. The root `README.md` is the front door (what this is, data
  perimeter, quickstart) and links to the index; it never duplicates it.
- Docs are grouped by roadmap step: `docs/step-<n>/` holds the pages, notes and methodology
  entries for work that belongs to that step. `docs/step-0/` is the built platform (delivery,
  object store, warehouse, exploration toolkit). Cross-step pages — `current-state.md`,
  `roadmap.md`, `decisions.md`, `dictionary.md` — stay at `docs/` root. Each step folder carries
  its own `README.md` index, linked from `docs/README.md`.
- Every measured number about the dataset has exactly one owner: `ideation/data-findings.md`.
  Other docs link to it; they never restate the number. Evidence for how a number was measured
  lives in the `docs/step-<n>/methodology/` entry that produced it.
- One decision, one note: design decisions live in `docs/notes/` when they govern every step, or
  in `docs/step-<n>/notes/` when they belong to one step — one file each, with a
  `**Standing:**` line saying whether it still holds. Other docs state the *result* in one
  sentence and link the note; they never re-argue it.
- Every doc outside `methodology/` and `archive/` carries a `Standing:` or `Verified:` line near
  the top with the date it was last checked against reality. A doc describing system state that
  has not been re-verified must say so.
- `methodology/` is an append-only audit log: never edit an entry, only append a new one that
  supersedes it (and says so). Entry numbers are global and monotonic across step folders.
- `archive/` holds superseded documents for provenance. Never edit them, never cite them as
  current, never delete them.
- Before writing a new doc, check the index for an existing owner of the topic. Extend the owner;
  do not start a parallel document.

## Results integrity
- Never invent or assume a result. Every number, finding, or conclusion must come from an actual
  executed run whose output is visible. If something was not run, say so explicitly.

## Methodology tracking
- Track the methodology and how each result was reached in the `methodology/` folder of the step
  it belongs to — `docs/step-0/methodology/` for the platform, `docs/step-<n>/methodology/` after.
- After any analysis or pipeline run, record in `methodology/` the question, inputs (files, versions,
  parameters), the exact commands run, the observed output, and the conclusion drawn — enough for
  someone else to reproduce it.

## The scientific record
The method is owned by [`docs/method.md`](docs/method.md). Read it before recording a finding.
- Every research step declares **one goal**, declared in `src/mva/science/steps.py`. Step 0 is
  platform machinery and takes no hypotheses; its reasoning is decisions, not claims.
- From step 1 on, a methodology entry **is a test bound to a hypothesis**, and adds three sections
  the step-0 entries lack: `## Hypothesis and prediction` and `## What would refute it`, both
  written *before* the run, and `## Verdict` after it.
- A claim goes in the register before it is tested: `mva-science hypothesis-add` requires a
  prediction and a refutation condition, and refuses a claim without them.
- Every observation is an evidence row naming its source — a methodology entry, a table, a PMID,
  a ClinVar id, or a probe reply. `mva-science evidence-add` refuses an unsourced observation.
- Confidence is never asserted. `mva-science verdict` suggests a number and prints its arithmetic;
  committing it takes `--commit` and a stated reason. The weighing is a transparent heuristic for
  triage, not a calibrated posterior — say so wherever it is quoted.
- Never write a genomic position into a hypothesis, an evidence claim, or any exported file. Name
  the gene and the consequence. `mva-science check` and `export` refuse and are not to be bypassed.
- Both register tables are append-only. A changed belief is a new revision, never an edit.

## Writing style
- Write the minimum text that still lands every main point. Cut filler, restatement, and hedging;
  never cut a point, a caveat, or a technical term. Compact must not become unclear or incomplete.
- Prefer lists, tables, and short sentences over prose. One idea per line.
- Applies everywhere: chat replies, commit messages, docs, `methodology/` entries, code comments.

## Audience: explain for a software engineer, not a bioinformatician
- The user's background is software engineering. Assume **no** prior knowledge of bioinformatics,
  genetics, or clinical genomics. Never assume a domain term is understood.
- Explain domain concepts in software-engineering terms where an honest analogy exists (e.g. a VCF
  as a row-oriented record format, a reference genome as a coordinate system, a pipeline stage as a
  pure function over records). Flag when an analogy breaks down instead of stretching it.
- Always give **both**: the plain-language explanation *and* the correct technical term. The user
  needs to recognise the real word when it appears in a tool flag, a file header, a paper, or a
  conversation with a domain expert — so never silently substitute a simplification for it.
  Pattern: `technical term (plain-English meaning)` on first use, then use the technical term.
  Example: "compound heterozygote (two different broken copies of the same gene, one from each
  parent)". Do not strip the jargon out; teach it.

### Dictionary
- The one dictionary is [`docs/dictionary.md`](docs/dictionary.md). Do **not** create a second
  glossary file anywhere. Enrich this one.
- It is written for a beginner and ordered so each entry only uses words already defined above it.
  Keep that property when inserting: put a new term after everything it depends on.
- Every time a new domain term, gene name, file format, tool, or concept comes up in the work, add it:
  the technical term in bold, a one-line plain-English definition, and an `*Example:*` line with a
  concrete value. Link related terms already in the dictionary.
- If a term is already there but poorly explained, improve the existing entry — never append a
  duplicate.
- Diagram assets for the dictionary live in `docs/assets/` and are referenced relatively as
  `assets/<name>.svg`. Each diagram is followed by a `> **Legend**` line decoding its colours.
- `CONTEXT.md` is a different thing and stays separate: it is the *naming discipline* for code and
  write-ups (one chosen word per idea, plus an _Avoid_ list). The dictionary teaches concepts;
  `CONTEXT.md` fixes vocabulary. When a term belongs in both, keep them consistent.

### Visualizations
- Default to showing, not just telling. For any pipeline, data flow, file format, coordinate scheme,
  filtering funnel, or result set, include a visualization.
- Choose the lightest medium that carries the meaning: a Mermaid block inline for structure and flow,
  an SVG in `docs/assets/` for anatomy that needs real shapes, a plotted chart (script in `tools/`,
  output in `figures/`) for actual data, a small worked example with real values for record formats.
- Follow the dictionary's conventions so the visual language stays consistent across the repo:
  **green = good / safe / the goal**, **red = broken / dangerous / lost points**,
  **yellow = a decision point**, **blue = neutral machinery**, **purple = the raw input**.
  Every diagram gets a `> **Legend**` line beneath it decoding its own colours and symbols.
- Every diagram must be reproducible: commit the source (Mermaid text, the SVG, or the plotting
  script), not only a rendered bitmap.
