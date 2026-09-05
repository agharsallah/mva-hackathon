# {track_title} — iteration {next} ({today})

**Standing:** draft — opened {today}, nothing built. Iteration {n} is frozen at
[`../iteration-{n}/`](../iteration-{n}/README.md).

## Why this iteration exists

Reply to submission {n}: **{reply}**. Decode-table row it matched (copy from
[`../iteration-{n}/decode-table.md`](../iteration-{n}/decode-table.md)) and what that row
says the next submission should hold:

- (fill in)

## What to upload

| Deliverable | File | Notes |
|---|---|---|
| Predictions CSV | `build/submission/{track}_submission_v{next}.csv` — gitignored | sha256 (fill in after the build); rebuild: see *Regenerate* |
| Report | `<user>_{track}_report.pdf` rendered from [`report.md`](report.md) | |
| Methods form | `<user>_{track}_methods_form.xlsx` from [`methods-form.json`](methods-form.json) | model number {next} |

## Which steps contributed

| Step | Contribution | Methodology |
|---|---|---|
| (fill in) | | |

## Regenerate this folder

```bash
uv run python tools/resolve_submission_spec.py --selectors {folder}/spec.selectors.json --out build/submission/spec.json
uv run python tools/design_submission.py --spec build/submission/spec.json --out build/submission/{track}_submission_v{next}.csv --decode-md {folder}/decode-table.md
uv run python tools/render_track1_figures.py
uv run python tools/md_to_html.py {folder}/report.md build/{track}-report.html --repo-url https://github.com/agharsallah/mva-hackathon/blob/main
node tools/md_to_pdf.mjs build/{track}-report.html {folder}/<user>_{track}_report.pdf
uv run python tools/fill_methods_form.py --sheet "Track 1 methods" --answers {folder}/methods-form.json --out {folder}/<user>_{track}_methods_form.xlsx
uv run python tools/check_iteration.py {folder}
```

## After the upload

1. `uv run mva-warehouse probe-log --by <member> --type F --payload-file build/submission/{track}_submission_v{next}.csv --response '<reply>' --rationale 'iteration {next}'`
2. `uv run mva-science probe-link <probe_id> --hypothesis <H…> --direction <supports|refutes> --claim '<what the reply said>'`
3. `uv run python tools/new_iteration.py --track {track} --reply '<reply>'`
