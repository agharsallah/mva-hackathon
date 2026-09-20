# Methodology log — iteration 4, step 3

Append-only. Entries are numbered globally (next free number is recorded in
[`../../README.md`](../../README.md)); each entry from a research step carries
`## Hypothesis and prediction`, `## What would refute it` (written before the run) and
`## Verdict` (after).

| entry | date | what it records | hypothesis |
|---|---|---|---|
| [122](122-every-lane-scored-once-and-only-once.md) | 2026-09-19 | the cold four-lane pass: 58,480 rows, 6,320 s, $0; the cache key's no-op | `P4-4a` (H062) — testing |
| [136](136-the-two-write-verbs-behind-a-job-and-a-token.md) | 2026-09-20 | `POST /api/zoo/score` and `POST /api/zoo/run` as background jobs, refused when `MVA_VIZ_TOKEN` is empty; live smoke: 200 alleles, **inserted 0** | none (machinery) |
