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
