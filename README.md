# SEPIQ 2026 — antibody–antigen interface prediction

**Standing:** 2026-10-05 — this branch was stripped of its previous case and repointed at
the SEPIQ challenge on this date. **No analysis has been run. The dataset is not
downloaded.** Everything here is machinery.

Predict where a **VHH** (a single-chain antibody, ~120 amino acids) touches **HER2** (a
human cell-surface receptor and a major cancer drug target), from sequence alone.

| | **Track A · SEPIQ** | **Track B · CAPRI** |
|---|---|---|
| Question | which *residues* form the interface? | what does the *complex* look like in 3D? |
| Output | per-residue probabilities, or a binary contact map | predicted atomic coordinates |
| Metric | **PR AUC** | **DockQ**, L-RMSD, i-RMSDbb, fnat |

The full challenge statement — both tracks, the dataset schema, what is organiser-stated
fact versus our inference, and the open questions — is
**[`docs/challenge.md`](docs/challenge.md)**. Read it first.

## Data perimeter

Two published CSVs (625 MB total) plus three prediction templates, from the organisers'
AVIDa-hHER2 release. They live in `data/raw/` and are **gitignored**: re-downloadable
from the organisers, so the tree carries the recipe, not the bytes. Derived tables go to
`data/parquet/`, each with a committed provenance manifest in `data/manifests/` recording
how it was made. Layout and the reasoning: [`data/README.md`](data/README.md).

Queried in-process with Polars and DuckDB. **There is no database server to set up.**

## Quickstart

```sh
# Python — uv only, never pip or bare python
uv sync
tools/check-python.sh          # the five static gates; --fix to format first

# The HTTP API (serves the dashboard; wires no routes yet)
uv run sepiq-api                 # 127.0.0.1:8900

# The dashboard — pnpm only, never npm
cd app && pnpm install && pnpm run dev
```

Hooks and the commit convention: `sh tools/setup-git.sh`, then
[`CONTRIBUTING.md`](CONTRIBUTING.md).

## What is in here

```
docs/        challenge statement, toolset, dictionary, decision notes  → docs/README.md
src/sepiq/     io · render · zoo · viz                                   → src/sepiq/README.md
app/         the React dashboard (shell + 3D structure viewer)
tools/       the gates, the report renderers, the Modal tracer         → docs/toolset.md
data/        raw (ignored) · parquet (ignored) · manifests (committed) → data/README.md
```

Start at **[`docs/README.md`](docs/README.md)** — the one documentation index. This page
is the front door and does not duplicate it.

## How this repo is meant to be read

Two things are being built at once: a solution to this challenge, and a toolset that
transfers to the next one. That is why `io`, `render`, `zoo` and `viz` carry no challenge
vocabulary, and why the enforced package layering
([`src/sepiq/README.md`](src/sepiq/README.md)) matters more than it would in a one-off.

Three rules shape everything written here:

- **Never invent a result.** Every number comes from an executed run whose output is
  visible. If something was not run, the page says so. There are no results yet, and the
  docs say that on every page.
- **Explain for a software engineer, not a biologist.** Domain terms get the plain-English
  meaning *and* the real technical word, every time. The teaching reference is
  [`docs/dictionary.md`](docs/dictionary.md), served at `/learn` in the app.
- **Show, don't only tell.** Every pipeline, funnel and result set gets a diagram, under
  one colour convention: green = the goal, red = lost points, yellow = a decision point,
  blue = machinery, purple = the raw input.
