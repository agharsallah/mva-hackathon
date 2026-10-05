# `render/` — the shared visual language

**Standing:** 2026-10-05 — verified against the source on this branch. This package was
not changed when the repository was repointed at a new challenge: it had no domain
vocabulary to strip.

One palette, one exhibit primitive, one report shell. Every figure and every page in the
repo goes through here, so a reader learns the colour code once.

## Modules

| Module | Holds |
|---|---|
| `theme.py` | The palette and the Plotly template. `GOOD` green, `BAD` red, `DECISION` yellow, `MACHINE` blue, `RAW` purple, `MUTED` grey — registered once as a named template so no figure sets its own colours. |
| `figure.py` | `Exhibit` (a figure plus its caption and legend) and `Section`. HTML-escapes every label it is handed. |
| `report.py` | Assembles sections into one self-contained HTML page with a keyword filter. |
| `report.css` | The page styling, inlined into that output. |

## The colour contract

| Colour | Means | Use it for |
|---|---|---|
| green | good / safe / the goal | the outcome you want, a passing check |
| red | broken / dangerous / lost points | a failure, a disqualifying condition |
| yellow | a decision point | a branch, a threshold, a judgement call |
| blue | neutral machinery | a pipeline stage, a transform, a service |
| purple | the raw input | the data as delivered, before anything touched it |
| grey | muted | context that must be visible but not read first |

This is the same convention the docs and the dictionary use. It holds across Mermaid
diagrams, SVG assets and plotted charts, which is the whole point: the reader should never
have to re-learn what a colour means when moving between a doc and a figure.

**Every diagram carries a `> **Legend**` line** decoding its own colours and symbols. The
convention is repo-wide, not a property of this package, but `Exhibit` is where a figure's
legend is attached to the figure rather than left to the surrounding prose.

## Why it is subject-agnostic

`render` knows about exhibits, sections, captions and colours. It does not know what is
being plotted. That is what let it survive a complete change of domain untouched, and it
is the standard the rest of the repo is held to: a module that would need editing to plot
a different kind of thing is a module with the domain baked in too deep.

## Callers

`mva.viz` may import it. It imports no sibling package itself — enforced by the "leaf
packages import no sibling package" contract in `pyproject.toml`.
