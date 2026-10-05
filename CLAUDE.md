# Project Instructions

## Goal

- We are competing in the **SEPIQ 2026 Challenge**: predict the antibody–antigen interface
  between VHH nanobodies and HER2. Two tracks — **A (SEPIQ)**, residue-level epitope/paratope
  prediction scored by PR AUC; **B (CAPRI)**, atomic-level complex prediction scored by DockQ,
  L-RMSD, i-RMSDbb and fnat. The challenge statement, the dataset schema and the open questions
  live in [`docs/challenge.md`](docs/challenge.md). Read it before making strategy decisions.
- Be **scientific yet creative**: ground every claim in an executed run with visible output, but
  actively try new methodology rather than only replaying standard pipelines.
- Build **two deliverables at once**: (1) a solution to this challenge, and (2) a reusable
  toolset — generic, well-factored modules that transfer to the next structural-biology or
  sequence-prediction problem. Prefer parameterised, case-agnostic tools over one-off scripts.
- **Strong reporting with lots of visuals.** Every phase produces report-ready material —
  figures, diagrams, tables, worked examples — as it runs, not afterwards.
- Always keep data traceability, lineage, cataloguing and metadata.
- Ignore file timestamps; never make a change only to refresh one.

## What this repo is right now

A **platform, stripped of its previous case**. The MVA genomics work was removed on this branch
(it remains in git history). What survives is machinery, not science:

| Package | What it is |
|---|---|
| [`src/mva/io/`](src/mva/io/README.md) | Parsers for plain-text tool output — header-first TSVs with rollup lines, `##`-sectioned files — plus the TSV/JSON writers. Missing values become `None`, never exceptions. |
| [`src/mva/render/`](src/mva/render/README.md) | The shared visual language: exhibit/section primitives, the report shell, the one palette. Subject-agnostic. |
| [`src/mva/viz/`](src/mva/viz/README.md) | The FastAPI shell: app factory, bearer-token auth, disk cache, the `{data, cached_at, source}` envelope, an upstream proxy, the uvicorn entrypoint. Serves the React app. No routers yet. |
| [`src/mva/zoo/`](src/mva/zoo/README.md) | The model-lane contract: a TOML registry of frozen third-party models, the tier-3 Modal wire contract, the GPU spend ledger. Nothing is trained. The roster is empty. |
| [`app/`](app/) | The React dashboard, stripped to its shell: router, components, theme, the `/learn` dictionary, and `viz3d` — the 3D structure viewer, which Track B needs. |

**No science has been done yet. The dataset is not downloaded.** Say so rather than implying
otherwise.

## Data

- Two inputs, both from the organisers' AVIDa-hHER2 release: `AVIDa-hHER2.csv` (499 MB, one row
  per VHH with per-condition scores, derived labels and cluster assignment) and
  `NGS_read_count_table.csv` (126 MB). Plus three `prediction_template_ONU*.csv` files — the
  actual output contract. Schema and the reading of each column: [`docs/challenge.md`](docs/challenge.md).
- **Lightweight by design.** 625 MB does not need Postgres or an object store. Raw files land in
  `data/raw/` (gitignored), derived tables in `data/parquet/`, queried in-process with Polars or
  DuckDB. There is no database server to set up.
- **Complete lineage, always.** Every derived table carries a provenance manifest in
  `data/manifests/` naming its sources, its parameters, the tool and the version. Nothing is
  produced without its source and generation process recorded.
- **Every artifact states assumptions, limitations, validation steps and quality checks** next to
  its result, with the parameters and versions needed to reproduce it.

## Results integrity

- Never invent or assume a result. Every number, finding or conclusion must come from an actual
  executed run whose output is visible. If something was not run, say so explicitly.
- A literature fact is written as a literature claim with its source, not as a repo fact.
- The split is **by sequence cluster, never by row**. A random row split leaks near-identical
  sequences between train and test and inflates PR AUC. Any reported metric names its split.

## Methodology tracking

- After any analysis or pipeline run, record in `docs/methodology/` the question, the inputs
  (files, versions, parameters), the exact commands, the observed output, and the conclusion —
  enough for someone else to reproduce it.
- `docs/methodology/` is an **append-only** audit log: never edit an entry, only append one that
  supersedes it and says so. Entry numbers are global and monotonic, starting at **001**.
- There is no hypothesis register on this branch. A methodology entry records what was run and
  what came out; it is not a pre-registered prediction.

## Python

- Use `uv` for all Python work: `uv run`, `uv add`, `uv sync`. Never `pip`, `python -m venv`, or
  bare `python`.

## JavaScript

- Use `pnpm`, never `npm`.

## Code structure

- No module longer than 400 lines (600 for a test module). When a file approaches the limit,
  split it into domain-driven modules — one bounded concern each — instead of growing it.
  Enforced: `uv run python tools/check_module_size.py`.
- Favour reusability: extract shared logic rather than duplicating it.
- Respect the layering in [`src/mva/README.md`](src/mva/README.md): `io` and `render` are leaves
  and import no sibling; nothing outside `mva.viz` may import it. Enforced: `uv run lint-imports`.

## Quality gates

- Do not run slow or expensive checks locally. Do not write slow tests. Write only robust tests
  that are meaningful and necessary.
- Before pushing Python, run `tools/check-python.sh` (`--fix` to format and autofix first). It
  runs the five gates CI runs: ruff format, ruff lint, module size, import layering, mypy, pytest.
  Why each rule sits where it does — and what to do when one fails — is owned by
  [`docs/notes/python-quality-gates.md`](docs/notes/python-quality-gates.md).
- A gate that is wrong for a change gets **fixed**, and the reason recorded in that note. Never
  `--no-verify`; never a bare `# noqa` — a suppression states its reason inline.
- mypy's per-package strict list in `pyproject.toml` is a ratchet: packages come off the
  permissive list as they are annotated, never back onto it.

## Documentation rules

- One doc index: `docs/README.md`. The root `README.md` is the front door (what this is, data
  perimeter, quickstart) and links to the index; it never duplicates it.
- Cross-cutting pages — `challenge.md`, `toolset.md`, `dictionary.md` — stay at `docs/` root.
- Every measured number about the dataset has exactly one owner page. Other docs link to it; they
  never restate the number. Evidence for how it was measured lives in the `docs/methodology/`
  entry that produced it.
- One decision, one note, in `docs/notes/` — one file each, with a `**Standing:**` line saying
  whether it still holds. Other docs state the _result_ in one sentence and link the note; they
  never re-argue it.
- Every doc outside `methodology/` carries a `Standing:` or `Verified:` line near the top with the
  date it was last checked against reality. A doc describing system state that has not been
  re-verified must say so.
- Before writing a new doc, check the index for an existing owner of the topic. Extend the owner;
  do not start a parallel document.

## The dashboard is a source of truth, not a copy

- The React app (`app/`) is cumulative: it shows the data findings, the derived tables, the
  research record, the processing workflows and the audit trails. New results are added to the
  app as they are made, never only to the docs. What was created, how, and from which source data
  must be readable on the page itself.
- The dictionary is served at `/learn` from `docs/dictionary.md` through
  `app/tools/gen-dictionary.mjs`; an update to the dictionary is an update to the dashboard.

## Writing style

- Write the minimum text that still lands every main point. Cut filler, restatement and hedging;
  never cut a point, a caveat or a technical term. Compact must not become unclear or incomplete.
- Prefer lists, tables and short sentences over prose. One idea per line.
- Applies everywhere: chat replies, commit messages, docs, methodology entries, code comments.

## Audience: explain for a software engineer, not a structural biologist

- The user's background is software engineering. Assume **no** prior knowledge of biology,
  immunology or structural bioinformatics. Never assume a domain term is understood.
- Explain domain concepts in software-engineering terms where an honest analogy exists (a protein
  sequence as a string over a 20-letter alphabet, a contact map as a boolean matrix, a scoring
  model as a pure function over records). Flag where an analogy breaks instead of stretching it.
- Always give **both**: the plain-language explanation _and_ the correct technical term. The user
  needs to recognise the real word when it appears in a tool flag, a file header or a paper — so
  never silently substitute a simplification for it. Pattern: `technical term (plain-English
  meaning)` on first use, then the technical term. Example: "paratope (the residues on the binder
  that actually touch the target)". Do not strip the jargon out; teach it.

### Dictionary

- The one dictionary is [`docs/dictionary.md`](docs/dictionary.md). Do **not** create a second
  glossary anywhere. Enrich this one.
- It is written for a beginner and ordered so each entry only uses words already defined above it.
  Keep that property when inserting: put a new term after everything it depends on.
- Every time a new domain term, concept, methodology, abbreviation, metric, biological entity or
  technical artifact comes up, add it: the term in bold, a one-line plain-English definition, an
  `*Example:*` line with a concrete value, and a `*Context:*` line saying where it is used, where
  it came from (the methodology entry, paper, file or tool that introduced it), the related terms
  (linked), and `first seen YYYY-MM-DD`. Where a figure shows the concept, link it.
- If a term is there but poorly explained, improve the existing entry — never append a duplicate.
- Diagram assets live in `docs/assets/`, referenced as `assets/<name>.svg`. Each is followed by a
  `> **Legend**` line decoding its colours.
- `CONTEXT.md` is a different thing and stays separate: it is the _naming discipline_ for code and
  write-ups (one chosen word per idea, plus an _Avoid_ list). The dictionary teaches concepts;
  `CONTEXT.md` fixes vocabulary. When a term belongs in both, keep them consistent.

### Visualizations

- Default to showing, not just telling. For any pipeline, data flow, file format, filtering funnel
  or result set, include a visualization.
- Choose the lightest medium that carries the meaning: a Mermaid block inline for structure and
  flow, an SVG in `docs/assets/` for anatomy that needs real shapes, a plotted chart (script in
  `tools/`, output in `figures/`) for actual data, a small worked example with real values for
  record formats.
- Follow one colour convention everywhere: **green = good / safe / the goal**, **red = broken /
  dangerous / lost points**, **yellow = a decision point**, **blue = neutral machinery**,
  **purple = the raw input**. Every diagram gets a `> **Legend**` line beneath it decoding its own
  colours and symbols.
- Every diagram must be reproducible: commit the source (Mermaid text, the SVG, or the plotting
  script), not only a rendered bitmap.
