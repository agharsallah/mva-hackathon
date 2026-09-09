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

## Solving phase (opened 2026-09-04)
- Step 0 (the platform) is **closed** at methodology entry 068. Read, in order:
  [`docs/toolset.md`](docs/toolset.md) → [`docs/roadmap.md`](docs/roadmap.md) →
  [`ideation/data-findings.md` §6](ideation/data-findings.md) → the README of the step you work.
  Do not re-explore the platform; the toolset page names the verb, route, page and module.
- A tool a research step needs (app page, API route, module) is recorded in **that step's**
  `methodology/`; only a cross-step platform fix still lands in step-0 and names the step.
- Methodology numbers are global; the next is **084**. Never reuse a number. (079 = Track 2 in the
  ledger and the dashboard; 080 = hosting the dashboard — the same-origin proxy, the API token and
  the password gate; 081 = fewer requests from the hosted dashboard — the persisted query cache,
  its coordinate-free allowlist, and quieter polls; 082 = derived submission rows — epcr, notes
  and priors from the warehouse and the register, never typed; 083 = the oracle's reply to submission 1.)
- Oracle budget is **6** uploads (one registered member). No upload before step 6's gate:
  callset normalized, hypotheses filed, CSV rehearsed on the scorer replica **and** cross-checked
  with the organisers' published `evaluation.py` (`tools/design_submission.py` does both), two
  independent methods agree. Timing is the user's call when step 6 opens.
- A claim whose test already ran in step 0 is filed prefixed `retrospective:` and cites the
  entry; it is never a pre-registered prediction.
- Priority: analysis of the genomic and clinical data and a well-elaborated report outrank
  oracle tactics. Every step produces its report artifact as it runs.

## Submissions — one iteration, one folder
- Every upload-ready iteration lives in `submissions/<track>/iteration-<n>/`: the report
  (`report.md` + the rendered `<user>_<track>_report.pdf`), the filled methods form
  (`methods-form.json` → `<user>_<track>_methods_form.xlsx`), the coordinate-free decode
  table, and a `README.md` that says what to upload, how to read the folder, which steps
  contributed (with links to their methodology entries), and what to do after the reply.
- An iteration's steps **contribute** to it; they do not own deliverables. **Each iteration declares
  its own plan, methodology and steps** (`src/mva/science/steps.py`, per iteration) — iteration 2
  does not replay iteration 1's steps 1–8. Plan first, then steps, then a submission. Their evidence
  stays in `docs/<iteration>/step-<n>/`; the iteration folder links to it. Figures stay in `figures/`.
- The predictions CSV holds real coordinates and is **never committed**: it lives under
  `build/submission/` and the folder README records its sha256 and rebuild command.
- An iteration folder is frozen once uploaded. The reply starts `iteration-<n+1>/` —
  `tools/new_iteration.py` does the freezing and the scaffolding; its README lifecycle page
  is `submissions/README.md`.
- The dashboard's `/submissions` page picks up every iteration folder automatically from
  `GET /api/submissions`; after adding one, re-capture `app/src/fixtures/data/submissions.json`
  from the live API and re-bless its hash (`app/src/test/fixtureHashes.json`). Every iteration
  shown there carries a beginner walkthrough (plain words, each term linked to `/learn`) built
  from its own payload — a new iteration must not need hand-written prose to be understood.
- Tooling, in order: `tools/resolve_submission_spec.py` (committed coordinate-free
  `spec.selectors.json` → gitignored spec), `tools/design_submission.py` (CSV + rehearsal +
  cross-check against the organisers' scorer + decode table), `tools/check_iteration.py` (the
  folder gate: deliverables present and fresh, form complete, selectors consistent, sha256,
  frozen folders untouched), `tools/new_iteration.py` (freeze n, open n+1, bump `ITERATION`),
  `tools/check_coordinates.py` (no coordinate leaves `build/`),
  `tools/render_track1_figures.py`, `tools/md_to_html.py` + `tools/md_to_pdf.mjs` (PDF),
  `tools/fill_methods_form.py` (xlsx). Track 2 follows the same layout.

## Two data sources, one lineage (standing directive, 2026-09-05)
- The case has **two inputs**: the 85 GB raw dataset (VCF + FASTQ, `ideation/data-findings.md`)
  and the **clinical dataset** — the proband's 8 HPO terms
  (`ressources/hackathon-rules/Challenge_Clinical_Phenotype_1.md`). Every analysis, derived
  table, ranking, figure and submission row cross-references both wherever relevant: a
  genomic result states what the clinical terms say about it (and vice versa), and a result
  that uses only one source says so.
- **Complete lineage, always.** Every dataset, table, feature, metric, figure and deliverable
  names its sources and its transformation: raw and clinical inputs, intermediate tables,
  parameters, tool and version. Tables record it in `warehouse.data_lineage` (append-only);
  files carry a provenance manifest or a `Standing:`/`Verified:` line naming the entry that
  produced them; submissions carry `spec.selectors.json` + the README's sha256 and rebuild
  commands. Nothing is produced without its source and generation process documented.
- **Every artifact states assumptions, limitations, validation steps and quality checks**
  next to its result, with the parameters and versions needed to reproduce it.

## The dashboard is the single source of truth
- The React app (`app/`) is cumulative: it shows raw-data findings, the clinical terms, derived
  tables, the research record, **every submission iteration** (deliverables, decode table,
  coordinate-free selectors, which steps and methodology entries contributed, figures), a
  **lineage view per submission**, the processing workflows, and audit trails (probe ledger,
  register revisions). New results and new iterations are added to the app as they are made,
  never only to the docs. What was created, how, and from which source data must be readable
  on the page itself.
- The dictionary is served in the app (`/learn`) from `docs/dictionary.md` through
  `tools/gen-dictionary.mjs`; an update to the dictionary is an update to the dashboard.

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
It runs the eight gates CI runs: ruff format, ruff lint, module size, import layering, mypy,
the coordinate gate (`tools/check_coordinates.py` — no patient position in any tracked file;
synthetic examples go in `tools/coordinate_allowlist.txt` with a reason), the iteration-folder
gate (`tools/check_iteration.py` — every `submissions/*/iteration-*` honours its declared
state), pytest. Why each rule is set where it is — and what to do when one fails — is owned by
[`docs/notes/python-quality-gates.md`](docs/notes/python-quality-gates.md). Two standing rules:
- A gate that is wrong for a change gets fixed, and the reason recorded in that note. Never
  `--no-verify`, never a bare `# noqa` — a suppression states its reason inline.
- mypy's per-package strict list in `pyproject.toml` is a ratchet: packages come off the
  permissive list as they are annotated, never back onto it.

## Documentation rules
- One doc index: `docs/README.md`. The root `README.md` is the front door (what this is, data
  perimeter, quickstart) and links to the index; it never duplicates it.
- Docs are grouped by roadmap step. `docs/step-0/` is the built platform (delivery, object
  store, warehouse, exploration toolkit). Research steps live under
  `docs/<iteration>/step-<n>/` (`iteration1/` today; `mva.science.steps.ITERATION` names the
  current one) — one folder per submission iteration, frozen once that iteration is uploaded. Cross-step pages — `current-state.md`,
  `roadmap.md`, `decisions.md`, `dictionary.md` — stay at `docs/` root. Each step folder carries
  its own `README.md` index, linked from `docs/README.md`.
- Every measured number about the dataset has exactly one owner: `ideation/data-findings.md`.
  Other docs link to it; they never restate the number. Evidence for how a number was measured
  lives in the `methodology/` entry that produced it (`docs/step-0/` or `docs/<iteration>/step-<n>/`).
- One decision, one note: design decisions live in `docs/notes/` when they govern every step, or
  in the step's own `notes/` folder when they belong to one step — one file each, with a
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
  it belongs to — `docs/step-0/methodology/` for the platform,
  `docs/<iteration>/step-<n>/methodology/` after.
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
- Every time a new domain term, concept, methodology, abbreviation, metric, biological entity,
  clinical term or technical artifact comes up in the work, add it: the technical term in bold, a
  one-line plain-English definition, an `*Example:*` line with a concrete value, and a
  `*Context:*` line saying where it is used, where it came from (the methodology entry, paper,
  file or tool that introduced it — its source), the related terms (linked), and the date it was
  first introduced (`first seen YYYY-MM-DD`). Where a figure or exhibit shows the concept, link
  it. Entries written before 2026-09-05 gain these fields as they are touched; the generator
  derives `first seen` from git history for every entry.
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
