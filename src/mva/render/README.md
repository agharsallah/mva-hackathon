# mva.render

One report shell and one colour palette, shared by every report in the repository.

**Standing:** 2026-09-01 — written from source at commit `c652265`.

## What it is

- A small library with no knowledge of its subject: it renders whatever `Section`/`Exhibit`
  objects a caller hands it into a self-contained HTML page.
- Three modules: `theme.py` (colours, Plotly styling), `figure.py` (the figure + caption +
  legend unit), `report.py` (assembling sections into one page).
- Originally lived inside `mva.explore`. Extracted into its own package (`docs/step-0/methodology/017-the-research-record.md`)
  when `mva.science` needed the same look without depending on the callset-profile package.

## Why it exists

Two different reports — the data-profile explorer (`mva.explore`) and the research record
(`mva.science`) — need the same visual language so a reader moving between them "does not
have to relearn what a colour means" (`src/mva/render/theme.py:7`). Centralizing the palette,
the figure-plus-caption rule, and the page shell in one package is what makes that guarantee
mechanical rather than a convention people can forget.

## Module map

| Module | Responsibility | Key exports |
|---|---|---|
| `theme.py` | The one place a colour is chosen; registers the shared Plotly template | `Hue`, `GOOD`, `BAD`, `DECISION`, `MACHINE`, `RAW`, `MUTED`, `SEQUENCE`, `install_template`, `legend_line` |
| `figure.py` | A figure bundled with its caption and legend; can't emit a chart without its explanation | `Exhibit`, `Section`, `sized`, `inline` |
| `report.py` | Sections → one navigable HTML file (sidebar, scrollspy, keyword filter) | `render`, `export_exhibits`, `STYLE`, `SCRIPT`, `DEFAULT_BLURB` |
| `report.css` | The report's stylesheet, inlined into every page at import time | — (read by `report.py`) |
| `__init__.py` | Re-exports the public surface of the three modules above | see API surface |

## Theme contract

Defined in `theme.py` as `Hue(fill, line, label)` dataclasses — `fill` is the pastel for areas/bars, `line` is the saturated outline/text colour:

| Constant | fill | line | label (legend text) |
|---|---|---|---|
| `GOOD` | `#8fd18f` | `#3f8f47` | good / safe / the goal |
| `BAD` | `#ff9999` | `#c0392b` | broken / dangerous / lost points |
| `DECISION` | `#ffe9b3` | `#c98f1e` | a decision point |
| `MACHINE` | `#cfe8ff` | `#3d7ebd` | neutral machinery |
| `RAW` | `#e0d4f7` | `#7a5cab` | the raw input |
| `MUTED` | `#e6e6e6` | `#888888` | context, not the subject |

Other tokens: `SEQUENCE` (10-colour sweep for series with no semantics — lanes, contigs,
genes), `INK`/`SUBTLE_INK`/`GRID`/`PAPER` (text/grid/background), `FONT`/`MONO` (font
stacks), `TEMPLATE_NAME = "mva"` (the registered Plotly template name).

Matches CLAUDE.md's convention exactly: green=good, red=broken, yellow=decision,
blue=machinery, purple=raw input. No mismatch found — `GOOD`/`BAD`/`DECISION`/`MACHINE`/`RAW`
map one-to-one onto that rule; `MUTED` is an addition on top (grey, for de-emphasized
context) not covered by the CLAUDE.md list.

## API surface

- `Hue(fill: str, line: str, label: str)` — one semantic colour role, frozen dataclass.
- `install_template() -> None` — registers the `"mva"` Plotly template and makes it default. Idempotent; called at import time of both `mva.explore` and (via re-export) anything importing `mva.render.theme`.
- `legend_line(*hues: Hue, extra: str = "") -> str` — builds the `**Legend** — ...` sentence from the same `Hue` objects a figure was coloured with.
- `Exhibit(slug, title, caption, legend, figure=None, html="", height=420, notes=[])` — one figure + its words.
  - `.to_div(embed_runtime: bool = False) -> str` — HTML fragment; `embed_runtime=True` must be set on exactly one exhibit per page (the first one carrying a real Plotly figure).
  - `.write_html(directory) -> Path` — standalone interactive page (`{slug}.html`).
  - `.write_image(directory, scale=2) -> Path | None` — static PNG via the optional `kaleido` engine; returns `None` (does not raise) if unavailable.
- `Section(slug, title, blurb, exhibits: list[Exhibit] = [])` — a named group of exhibits.
- `sized(figure: go.Figure, height: int, title: str = "") -> go.Figure` — sets exhibit height (and optionally title) on a Plotly figure in one call.
- `inline(text: str) -> str` — escapes then renders `**bold**` and `` `code` `` markup for captions/legends/notes.
- `render(sections: list[Section], title: str, subject: str, blurb: str = DEFAULT_BLURB) -> str` — the full HTML page as a string.
- `export_exhibits(sections, directory, images: bool = False) -> list[Path]` — writes each exhibit as its own file (one subfolder per section slug).
- `STYLE`, `SCRIPT` — the inlined CSS/JS the page embeds. `DEFAULT_BLURB` — fallback orienting sentence when a caller doesn't supply one.

Worked example:

```python
from mva.render import Exhibit, Section, render, GOOD, legend_line
import plotly.graph_objects as go

fig = go.Figure(go.Bar(x=["A", "B"], y=[3, 7], marker_color=GOOD.fill))
exhibit = Exhibit(
    slug="demo", title="Demo counts",
    caption="Counts per category.",
    legend=legend_line(GOOD),
    figure=fig,
)
section = Section("s1", "Demo section", "One exhibit for illustration.", [exhibit])
html = render([section], title="Demo report", subject="worked example")
```

## Relationship to `src/mva/explore/`

Verified from source, not inferred:

- `src/mva/explore/theme.py` and `src/mva/explore/figure.py` are **pure re-export shims**:
  each is a docstring plus `from ..render.theme import ...` / `from ..render.figure import ...`
  and an `__all__` list — no logic of their own. Both docstrings say outright: "The real
  definitions moved to `mva.render.*`... New code should import from `mva.render`."
- `src/mva/explore/report.py` is **not** a shim — it imports the subject-agnostic `render`,
  `STYLE`, `SCRIPT`, `export_exhibits` from `mva.render.report`, then adds what's genuinely
  callset-specific: `build_report`/`write_report` (wires `views.build_sections(profile)` into
  the shared `render`) and the `PROFILE_BLURB`/`LOCUS_BLURB` orienting sentences.
- History: `mva.render` did not exist first. Per `docs/step-0/methodology/017-the-research-record.md`,
  `figure.py`/`theme.py`/`report.css`/`render()` were already subject-agnostic inside
  `mva.explore` and were extracted to `src/mva/render/` once `mva.science` (the research
  record) needed the identical rendering without a dependency on the profile-loading package.
  The methodology entry states the extraction "changed no existing output byte."
- Net effect: `mva.render` is the generic layer; `mva.explore` is a consumer that keeps its
  old import paths alive via shims for backward compatibility, plus its own callset-specific
  report wiring. Neither is "legacy" — both are live, but `mva.explore.theme`/`.figure` exist
  only so `from mva.explore.figure import Exhibit` keeps working.

## Where it is used

- `src/mva/explore/theme.py`, `src/mva/explore/figure.py` — re-export shims (see above).
- `src/mva/explore/report.py` — imports `render`, `STYLE`, `SCRIPT`, `export_exhibits` from `mva.render.report`, and `Exhibit`/`Section` from `mva.render.figure`.
- `src/mva/science/hypothesis.py`, `src/mva/science/evidence.py` — import `Hue` and colour constants (`BAD`, `DECISION`, `GOOD`, `MACHINE`, `MUTED`) directly from `mva.render.theme`.
- `src/mva/science/report.py` — imports `Section` from `mva.render.figure` and `render` from `mva.render.report`.
- `src/mva/science/views/{board,ledger,loop,methods,submission,__init__}.py` — each imports `Exhibit`/`Section` from `mva.render.figure` and the colour constants + `legend_line` from `mva.render.theme` it needs for that view.
- No usage found in `src/mva/viz/`, `src/mva/warehouse/`, or `tools/`.
- Tests exercise it only indirectly, through `mva.explore` (`tests/test_explore_report.py`, `tests/test_explore_views.py`, `tests/test_explore_checks.py`, `tests/test_explore_profile.py`, `tests/test_cli_parsers.py`); no `tests/test_render_*.py` exists.

## Key facts / gotchas

- Plotting library: Plotly (`plotly>=7.0.0` in `pyproject.toml`). Static image export needs the
  optional `kaleido` engine, which is **not** in `pyproject.toml` — `Exhibit.write_image`
  catches any exception and returns `None` rather than raising when it's missing.
- Output is a single self-contained HTML file: everything is inlined (CSS from `report.css`,
  JS from `report.SCRIPT`) except the Plotly runtime itself, fetched from a CDN — only one
  exhibit per page may set `embed_runtime=True` (tracked by the private `_RuntimeFlag` helper
  in `report.py`), otherwise later charts render blank with no error.
- Light theme only, deliberately — `report.css`'s opening comment says a dark shell around
  white Plotly canvases "would read as a rendering bug rather than a theme." Print (`@media
  print`) rules are included so the same page works as a PDF.
- Font stack: Inter with system fallbacks (`FONT` in `theme.py`); monospace stack for code/hover
  labels (`MONO`). DPI/scale: `write_image` defaults to `scale=2`, `width=1100`, using the
  exhibit's own `height` (default 420).
- `install_template()` is idempotent and registers the `"mva"` Plotly template as the process
  default — calling it twice (e.g. once from `mva.explore.__init__` and again elsewhere) is safe.
- Side effects: `Exhibit.write_html`/`write_image` and `export_exhibits` create directories
  (`mkdir(parents=True, exist_ok=True)`) and write files; `render()` itself is pure (returns a
  string, writes nothing) — `mva.explore.write_report` is what writes it to disk.
- `inline()` escapes HTML first, then applies `**bold**`/`` `code` `` markup — an unpaired
  delimiter (odd count) is left as a literal character rather than partially transformed.

## Related

- [`src/mva/explore/`](../explore/) — the callset-profile report; consumer + re-export shims (see relationship section above).
- [`src/mva/science/`](../science/) — the research-record report; direct consumer of `mva.render`.
- [`docs/step-0/methodology/017-the-research-record.md`](../../../docs/step-0/methodology/017-the-research-record.md) — the extraction of `mva.render` out of `mva.explore`.
- [`docs/step-0/exploration.md`](../../../docs/step-0/exploration.md) — the exploration toolkit `mva.explore` is documented in.
- [`docs/README.md`](../../../docs/README.md) — doc index; lists `src/mva/render/` as "the shared renderer both reports use."
- [CLAUDE.md](../../../CLAUDE.md) — "Visualizations" section; owns the colour convention this package encodes.
