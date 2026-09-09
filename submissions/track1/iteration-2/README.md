# Track1 — iteration 2 (2026-09-09)

**Standing:** draft — opened 2026-09-09, nothing built. Iteration 1 is frozen at
[`../iteration-1/`](../iteration-1/README.md).

## Why this iteration exists

Reply to submission 1: **full match at rank 1: stop+missense (100 rank points, F-max 1.0, threshold 0.9963)**. Decode-table row it matched (copy from
[`../iteration-1/decode-table.md`](../iteration-1/decode-table.md)) and what that row
says the next submission should hold:

- Row 1 of the decode table: `full match rank 1 · F-max 1.000 · at epcr 0.9963 · prior mass 0.78 · survivors: stop+missense`. The answer key **is** the BUB1B stop_gained + BUB1B missense pair (H009 → `supported`, revision 3; probe 1 in the ledger; [083](../../../docs/iteration1/step-6/methodology/083-oracle-reply-submission-1.md)).
- The automated score for the pair is at its maximum (100 / 100, F-max 1.0); the other 7 keys are eliminated. Iteration 2 is therefore **not a replay of iteration 1's steps 1–8**.
- Iteration 2 gets **its own plan, methodology and steps**: the plan is defined first, then cut into steps declared in `src/mva/science/steps.py` for this iteration, each with its own `docs/iteration2/step-<n>/` folder and methodology log. The output is again a submission built by the same tooling (selectors → derivation → CSV → rehearsal).
- Until the plan is written this folder is a draft; the step table in [`docs/iteration2/README.md`](../../../docs/iteration2/README.md) is filled from `steps.py` once the steps exist.

## What to upload

| Deliverable | File | Notes |
|---|---|---|
| Predictions CSV | `build/submission/track1_submission_v2.csv` — gitignored | sha256 (fill in after the build); rebuild: see *Regenerate* |
| Report | `<user>_track1_report.pdf` rendered from [`report.md`](report.md) | |
| Methods form | `<user>_track1_methods_form.xlsx` from [`methods-form.json`](methods-form.json) | model number 2 |

## Which steps contributed

| Step | Contribution | Methodology |
|---|---|---|
| iteration 1, step 6 | reply decoded, H009 supported, budget 1 of 6 | [083](../../../docs/iteration1/step-6/methodology/083-oracle-reply-submission-1.md) |
| iteration 2 steps | to be declared with the plan | — |

## Regenerate this folder

```bash
uv run python tools/resolve_submission_spec.py --selectors submissions/track1/iteration-2/spec.selectors.json --out build/submission/spec.json
uv run python tools/design_submission.py --spec build/submission/spec.json --out build/submission/track1_submission_v2.csv --decode-md submissions/track1/iteration-2/decode-table.md
uv run python tools/render_track1_figures.py
uv run python tools/md_to_html.py submissions/track1/iteration-2/report.md build/track1-report.html --repo-url https://github.com/agharsallah/mva-hackathon/blob/main
node tools/md_to_pdf.mjs build/track1-report.html submissions/track1/iteration-2/<user>_track1_report.pdf
uv run python tools/fill_methods_form.py --sheet "Track 1 methods" --answers submissions/track1/iteration-2/methods-form.json --out submissions/track1/iteration-2/<user>_track1_methods_form.xlsx
uv run python tools/check_iteration.py submissions/track1/iteration-2
```

## After the upload

1. `uv run mva-warehouse probe-log --by <member> --type F --payload-file build/submission/track1_submission_v2.csv --response '<reply>' --rationale 'iteration 2'`
2. `uv run mva-science probe-link <probe_id> --hypothesis <H…> --direction <supports|refutes> --claim '<what the reply said>'`
3. `uv run python tools/new_iteration.py --track track1 --reply '<reply>'`
