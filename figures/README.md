# Figures — generated report artifacts

**Standing:** generated output, not source. Both files are regenerable; nothing here is
hand-edited. Last checked 2026-08-29.

Three self-contained HTML pages, each opening from the filesystem with no server and no
build step. Only Plotly's runtime is fetched from a CDN; every style, behaviour and data
point is inlined. All three come off one renderer, [`src/mva/render/`](../src/mva/render/),
so the palette and the shell are shared.

| File | What it is | Regenerate with |
|---|---|---|
| `explore-report.html` | the full exploration report — twenty exhibits over the committed data profile, each with its caption and legend | `uv run mva-explore report ressources/data-profile` |
| `science-report.html` | the research record — the method, the step goals, the hypothesis board, the evidence ledger, the oracle budget, and the methods form. **Currently renders as empty**, because no hypothesis has been recorded yet; that is the honest state, not a broken page | `uv run mva-science report --from docs/science-register.json` |
| `locus-fixture.html` | the locus browser rendered over the **synthetic** `tests/fixtures/mini.vcf`, so the page can be committed | `uv run mva-explore locus tests/fixtures/mini.vcf --out figures/locus-fixture.html` |

`locus-fixture.html` is deliberately built from the fixture rather than the real callset:
the locus views are the only ones that read patient records, and a page built from the real
VCF must be written outside the repository. `science-report.html` is committed for the same reason it is safe to: the register holds no
genomic positions, and [`mva-science export`](../docs/method.md) refuses to write one. See
[`docs/step-0/exploration.md`](../docs/step-0/exploration.md),
[`docs/method.md`](../docs/method.md), and the
[data-handling perimeter](../README.md#data-handling--read-this-first).
