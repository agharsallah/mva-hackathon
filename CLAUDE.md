# Project Instructions

## Python
- Use `uv` for all Python work: `uv run`, `uv add`, `uv sync`. Do not use `pip`, `python -m venv`, or bare `python`.

## Code structure
- No script or module longer than 400 lines. When a file approaches that limit, split it into
  domain-driven modules (one bounded concern per module) instead of growing the file.
- Favor reusability: extract shared logic into reusable functions/modules rather than duplicating it.

## Results integrity
- Never invent or assume a result. Every number, finding, or conclusion must come from an actual
  executed run whose output is visible. If something was not run, say so explicitly.

## Methodology tracking
- Track the methodology and how each result was reached in the `methodology/` folder.
- After any analysis or pipeline run, record in `methodology/` the question, inputs (files, versions,
  parameters), the exact commands run, the observed output, and the conclusion drawn — enough for
  someone else to reproduce it.

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
