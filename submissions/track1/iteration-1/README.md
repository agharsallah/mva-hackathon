# Track 1 — iteration 1 (2026-09-05)

**Standing:** built and rehearsed 2026-09-05; **not uploaded** (0 of 6 submissions spent).
One folder = one upload-ready iteration. Everything the organisers receive, plus the
material a judge needs to check it, is here or linked from here.

## What to upload (the challenge asks for three things)

| Deliverable | File | Notes |
|---|---|---|
| Predictions CSV | `build/submission/track1_submission_v1.csv` — **gitignored, outside the repository** | sha256 `fbc9e750dea5ebee1da0465e47e6cb20fe53e51e9961a7320fff0750ada92e6a`; 8 rows; holds real coordinates, so it is never committed. Rebuild: `uv run python tools/design_submission.py --spec build/submission/spec.json --out build/submission/track1_submission_v1.csv` — the rebuild re-grades the file with our replica **and** the organisers' `evaluation.py` and stops if they disagree |
| Report (PDF or Markdown) | [`agharsallah_track1_report.pdf`](agharsallah_track1_report.pdf) — rendered from [`report.md`](report.md) | filename carries the username as the form asks; rename if the registered team name differs |
| Methods description form | [`agharsallah_track1_methods_form.xlsx`](agharsallah_track1_methods_form.xlsx) — the organisers' template with column B filled from [`methods-form.json`](methods-form.json) | `uv run python tools/fill_methods_form.py --sheet "Track 1 methods" --answers methods-form.json --out …` |
| GitHub URL | `https://github.com/agharsallah/mva-hackathon` | entered in the submit form |

## How to read this iteration

1. [`report.md`](report.md) — the report: clinical picture → data → funnel → the two alleles → the submission as a measurement → limitations → methods form. Every number links to its owner in [`ideation/data-findings.md`](../../../ideation/data-findings.md) and to the methodology entry that produced it.
2. [`decode-table.md`](decode-table.md) — what every possible scorer reply would mean (labels only, no coordinates).
2b. [`spec.selectors.json`](spec.selectors.json) — **why every row is there, without saying where**: each allele is a selector over a warehouse result table (gene, consequence, ClinVar flag, gnomAD presence) that must match exactly one row; rows, epcr values, priors and the notes the organisers receive are copied through verbatim. `tools/resolve_submission_spec.py` turns it into the gitignored spec on any machine with database access, and `--check` proved it resolves to the same seven coordinates the uploaded-to-be CSV was built from.
3. Figures: [`figures/track1/`](../../../figures/track1/) (funnel, gene scatter, decode table; regenerate with `tools/render_track1_figures.py`) and the interactive page [`figures/track1-report.html`](../../../figures/track1-report.html).
4. The research record: [`docs/science-register.json`](../../../docs/science-register.json) → [`figures/science-report.html`](../../../figures/science-report.html); hypotheses H001–H009.

## Which steps contributed, and where their evidence lives

| Step | Contribution | Methodology |
|---|---|---|
| 0 platform | lossless VCF layer, lineage, register, scorer replica, probe builder | [`docs/step-0/`](../../../docs/step-0/README.md) |
| 1 normalize | both alleles SNVs, spelling invariant; genome-wide norm changed 0 bi-allelic records | [073](../../../docs/iteration1/step-1/methodology/073-normalization-of-the-candidates.md) |
| 2 annotate | panel → 2 alleles (031, 051); coding layer + genome-wide scan → BUB1B the only qualifying gene | [069](../../../docs/iteration1/step-2/methodology/069-layer-2-coding-scan.md), [070](../../../docs/iteration1/step-2/methodology/070-genome-wide-annotation-and-verdict.md) |
| 3 phenotype | BUB1B 6/5,267 by symptoms; first among 65 biallelic genes | [067](../../../docs/iteration1/step-3/methodology/067-phenotype-ranking-without-java.md), [071](../../../docs/iteration1/step-3/methodology/071-phenotype-callset-join.md) |
| 4 suppressed calls | nothing hides behind a filter, panel or genome-wide | [049](../../../docs/step-0/methodology/049-suppressed-calls.md), [072](../../../docs/iteration1/step-4/methodology/072-genome-wide-suppressed-calls.md) |
| 5 reads | not needed; triggered only by the "partner unseen" reply | [`docs/iteration1/step-5/`](../../../docs/iteration1/step-5/README.md) |
| 6 oracle | submission designed, rehearsed, decode table; upload pending | [074](../../../docs/iteration1/step-6/methodology/074-submission-v1-design.md) |
| 7 literature | PMIDs 15475955, 20516114, 31184400 as evidence rows on H009 | in [074](../../../docs/iteration1/step-6/methodology/074-submission-v1-design.md) |
| 0 platform fix | coordinate gate, one redaction, scorer cross-check | [075](../../../docs/step-0/methodology/075-coordinate-gate-and-redaction.md) |

## Integrity checks (all run 2026-09-05, all green)

| Check | Command | Result |
|---|---|---|
| Selectors resolve to the coordinates the CSV was built from | `uv run python tools/resolve_submission_spec.py --selectors submissions/track1/iteration-1/spec.selectors.json --out build/submission/spec.json --check build/submission/spec.json` | `identical`, 7 of 7 alleles |
| Folder complete and consistent | `uv run python tools/check_iteration.py submissions/track1/iteration-1` | ready — ok |
| CSV re-graded with the organisers' published scorer, every answer key | `uv run python tools/design_submission.py --spec build/submission/spec.json --out build/submission/track1_submission_v1.csv` | 8 of 8 keys agree with the replica; sha256 unchanged |
| Template conformance | same command | header byte-identical to the organisers' template, `PROBAND01`, `chr` prefix, epcr strictly descending, ≤ 10 rows |
| No patient coordinate in the tree | `uv run python tools/check_coordinates.py` | clean (part of `tools/check-python.sh`) |
| Register publishable | `uv run mva-science check` | 9 hypotheses, 29 evidence rows, no coordinates |
| Python gates | `tools/check-python.sh` | green, 1,687 tests |
| Relative links in `docs/`, `submissions/`, `ideation/` | ad-hoc link walk | no broken link in any file written this iteration |

## After the upload

1. `uv run mva-warehouse probe-log --by <member> --type F --payload-file build/submission/track1_submission_v1.csv --response '<reply>' --rationale 'iteration 1, see submissions/track1/iteration-1'`
2. `uv run mva-science probe-link <probe_id> --hypothesis H009 --direction <supports|refutes> --claim '<what the reply said>'`
3. Find the reply's row in [`decode-table.md`](decode-table.md); it names the next iteration.
4. Start `submissions/track1/iteration-2/` — never edit this folder.

## Regenerate this folder

```bash
uv run python tools/resolve_submission_spec.py --selectors submissions/track1/iteration-1/spec.selectors.json --out build/submission/spec.json
uv run python tools/render_track1_figures.py
uv run python tools/design_submission.py --spec build/submission/spec.json \
    --out build/submission/track1_submission_v1.csv --decode-md submissions/track1/iteration-1/decode-table.md
uv run python tools/md_to_html.py submissions/track1/iteration-1/report.md build/track1-report.html \
    --repo-url https://github.com/agharsallah/mva-hackathon/blob/main
node tools/md_to_pdf.mjs build/track1-report.html submissions/track1/iteration-1/agharsallah_track1_report.pdf
uv run python tools/fill_methods_form.py --sheet "Track 1 methods" \
    --answers submissions/track1/iteration-1/methods-form.json \
    --out submissions/track1/iteration-1/agharsallah_track1_methods_form.xlsx
```
