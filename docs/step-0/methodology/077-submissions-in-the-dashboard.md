# 077 — Every submission in the dashboard, with its lineage and both inputs

**A step-0 platform entry (cross-step), so it carries no hypothesis.** Names step 6 (the
submission) and the dictionary. **Written:** 2026-09-05, from the runs quoted below. Follows
the standing directive recorded the same day in [`CLAUDE.md`](../../../CLAUDE.md) (*Two data
sources, one lineage* · *The dashboard is the single source of truth*).

## Question

Can a reader open the app and see, for every submission iteration, what was uploaded (or
built), why each row is there, which steps and register claims it rests on, where its data
came from — the raw callset **and** the clinical terms — and what it has cost? And can the
dictionary say, for every term, where it came from and when it entered the project?

## Method

| Piece | Where | Tested by |
|---|---|---|
| `GET /api/submissions` — one record per `submissions/*/iteration-*` folder (state, deliverables, decode table, coordinate-free selectors, methods form, contributions with methodology links, referenced claims, figures, report, **lineage**, **audit**); `…/{track}/{n}/report`; `…/{track}/{n}/figure/{slug}` | `src/mva/viz/submissions.py`, `submissions_reader.py`, `submissions_markdown.py`, `submissions_lineage.py`, `submissions_audit.py`; one registration line in `routes_warehouse.py` | `tests/test_viz_submissions.py` (30) |
| Lineage per submission: walk `warehouse.data_lineage` from the selector tables to the roots; add the clinical document (sha256 on disk) and the selectors file; degrade to `available: false` with the reason when the database is unreachable, keeping the roots knowable from disk | `submissions_lineage.py` | same |
| The iteration's own edges: `tools/resolve_submission_spec.py --record-lineage` appends `target_schema = submissions`, one edge per selector table, one for `spec.selectors.json` (sha256), one for the clinical dataset (sha256, "8 HPO terms"); idempotent | `src/mva/warehouse/submission_lineage.py` | `tests/test_warehouse_submission_lineage.py` (7) |
| The `/submissions` page (group *Decide*): iteration picker (cumulative, URL state), header with state and CSV digest, **two inputs** panel (the 8 HPO terms beside the callset object), decode table coloured by the repo convention, selectors with the "why no coordinate" callout, contributions with GitHub links and claim badges, lineage graph (inline SVG, purple roots → blue tables → green iteration folder) with the sources grouped by kind, audit trail (probe ledger, register), deliverables, figures, methods form, report | `app/src/pages/Submissions.tsx`, `app/src/pages/submissions/*`, `app/src/api/types/submissions.ts`, fixture `app/src/fixtures/data/submissions.json` (**captured** from the live API with the database reachable) | `app/src/test/submissions-page.test.tsx` (6) + the module, a11y, fixture-hash and patient-data gates |
| Dictionary metadata: an optional `*Context:*` line (`source:`, `related:`, `see:`, `first seen`) parsed into fields; `first seen` derived for **every** entry from one `git log -p` walk of `docs/dictionary.md` (~35 ms); rendered as a footer on `/learn` | `app/tools/gen-dictionary.mjs` (split into `dictionary-blocks.mjs`, `dictionary-context.mjs`), `app/src/lib/dictionary/index.ts`, `app/src/pages/learn/Blocks.tsx` | `app/src/test/dictionary-metadata.test.ts` (8) |
| New entries: clinical dataset, submission iteration, selector (submission), folder gate, frozen iteration, scorer cross-check, coordinate gate, methodology entry, audit trail; context added to 13 central entries; `decode table` rewritten | `docs/dictionary.md` | `pnpm dictionary:check` |

## Commands

```bash
uv run python tools/resolve_submission_spec.py --selectors submissions/track1/iteration-1/spec.selectors.json \
    --out build/submission/spec.json --check build/submission/spec.json --record-lineage
uv run mva-warehouse pg-query "SELECT source_kind, source_ref FROM pg.warehouse.data_lineage WHERE target_schema='submissions'"
uv run mva-viz-api &  (cd app && pnpm dev &)          # then GET /api/submissions?refresh=true, screenshot /submissions
tools/check-python.sh
cd app && pnpm dictionary && pnpm check
```

## Observed

Lineage edges appended for iteration 1, then the rerun:

```
track1/iteration-1: 4 edge(s) appended, 0 already present
track1/iteration-1: 0 edge(s) appended, 4 already present
```

| source_kind | source_ref |
|---|---|
| table | results.coding_candidates |
| table | results.panel_candidates |
| file | submissions/track1/iteration-1/spec.selectors.json (sha256 `20d09995…`) |
| clinical | ressources/hackathon-rules/Challenge_Clinical_Phenotype_1.md (sha256 `7d410bb0…`, "8 HPO terms") |

`GET /api/submissions?refresh=true` with the database reachable: state `ready`; claims
H001–H009 referenced; lineage `available: true`, **12 edges** reached from 4 tables, 9 sources —
raw `s3://mva/source/WGS_EX2312012_HGWCNDSX7.vcf.gz` (version + sha256 from the ledger),
clinical, the selectors file, 4 tables, 2 reference inputs (HPO release, VEP REST release 116);
decode table 7 rows; 9 contributions; 3 figures served as `image/png`; probes 0 (nothing
uploaded); register 9 rows. Every 7+-digit number in the payload is an HPO id, a ClinVar
accession or a digest substring — no position.

The page rendered from the live API (headless Chromium, 1440 px wide, full height 7,858 px,
**0 console errors**): the lineage graph shows 15 nodes, 12 edges, 2 levels, the clinical
document and the callset object as roots side by side; the audit trail reads "no upload yet
— 0 of 6 spent". `/learn` shows `first seen` under every entry (dates from git: 2026-08-27
for the probe vocabulary, 2026-09-05 for today's terms).

Gates: `tools/check-python.sh` green — **1,730 tests** (1,687 before this entry);
`cd app && pnpm check` green — typecheck, eslint, prettier, theme, `dictionary:check`
(**454 entries, 22 context lines**), **511 tests** in 37 files.

## Limitations, stated

- `docs/science-register.json` exports each claim's current state and a revision *count*,
  not the revision history; the audit trail therefore shows one row per claim with its
  revision number and no timestamp. Exporting the history is a register change, not a
  dashboard one.
- Lineage edges for a submission are appended when `--record-lineage` runs; the API also
  walks the older edges, so an iteration whose tool run predates the flag still shows its
  table roots.
- The fixture is a capture, not the live API: when a new iteration is added the fixture must
  be re-captured (`fixtureHashes.json` re-blessed) or the offline page shows only iteration 1.

## Conclusion

The dashboard now carries every submission iteration with its two inputs, its lineage to
the byte-verified callset object and the clinical document, and its audit trail; the
dictionary says for every term when it entered the project and, for the new and central
ones, where from. Adding iteration 2 is: run the tools, re-capture the fixture.
