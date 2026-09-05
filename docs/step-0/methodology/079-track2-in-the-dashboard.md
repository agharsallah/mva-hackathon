# 079 — Track 2 in the ledger and the dashboard: lineage, catalog, the report in progress

**A step-0 platform entry (cross-step), naming step 8.** No hypothesis. **Written:** 2026-09-06
from the runs quoted below. Follows [077](077-submissions-in-the-dashboard.md) for Track 2.

## Question

Can a reader see, on one page, what Track 2 knows so far — the mechanism, the evidence tables,
where each byte came from, which Track 1 iteration it rests on, and what still waits — and can
every Track 2 table be traced in the same `data_lineage` ledger as everything else?

## Method

| Piece | Where | Tested by |
|---|---|---|
| Lineage edges for the five `ressources/track2/*.tsv`: `target_schema = track2`; per table one `card` edge (mechanism.json v2 + digest), one `api` edge per host (rolled-up digest of that host's replies; a retrieval window, never an invented version), one `submission` edge to `track1/iteration-1` (the iteration whose H003–H009 the card cites), and a `table` edge to `track2.targets` for the derived tables; idempotent | `src/mva/warehouse/track2_lineage.py`, `tools/record_track2_lineage.py` | `tests/test_warehouse_track2_lineage.py` (9) |
| `GET /api/track2`: card, catalog (every column of every table described in plain English, with the manifest facts), all five tables, summary, lineage (walked, `available:false` fallback), step-8 register, linked iterations (matched by shared hypothesis ids), strategy phases | `src/mva/viz/track2*.py` | `tests/test_viz_track2.py` (14) |
| `/track2` page (*Decide*): strategy timeline (yellow = waiting on the oracle; final suggestion only after all Track 1 iterations merge), linked iterations → `/submissions?it=…`, beginner guide, mechanism card in Q15 order, directions, target set, filterable candidates with two bar charts, trials and literature, register, catalog, lineage graph | `app/src/pages/Track2.tsx`, `app/src/pages/track2/*`; fixture = the captured payload | `app/src/test/track2-page.test.tsx` (10) |
| Strategy written down: [`step-8/README.md`](../../iteration1/step-8/README.md) *Strategy* section | docs | — |

## Commands

```bash
uv run python tools/record_track2_lineage.py          # twice, to prove idempotency
uv run mva-warehouse pg-query "SELECT target_table, source_kind, source_ref FROM pg.warehouse.data_lineage WHERE target_schema='track2'"
tools/check-python.sh ; (cd app && pnpm check)
```

## Observed

```
run 1: track2: 21 edge(s) appended, 0 already present
run 2: track2: 0 edge(s) appended, 21 already present
```

21 rows: 5 `card`, 5 `submission` (→ `track1/iteration-1`), 3 `table` (→ `track2.targets`),
8 `api` (api.fda.gov, api.platform.opentargets.org, dgidb.org, www.ebi.ac.uk,
eutils.ncbi.nlm.nih.gov, reactome.org ×2, clinicaltrials.gov). `GET /api/track2`: targets 273,
candidates 3,766 (1,067 approved), trials 747, literature 157, pathways 10, catalog 5 tables,
register H010/H011, one linked iteration (`track1/iteration-1`, 7 shared claims), 6 strategy
phases, lineage available with 29 edges (21 recorded + 8 walked back) and 10 sources. Page
rendered live with 0 console errors. Gates: Python 1,898 tests green; app 535 tests green.

## Limitations

- The strategy phases are a static list in code; they change by edit, not by measurement.
- The app fixture is 1.85 MB (lazy chunk, offline only); trim if the bundle budget ever bites.
- Nothing on the page ranks a drug — by design, until the oracle has answered.
