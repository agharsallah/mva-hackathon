# Iteration 4 — the todo board

**Standing:** opened 2026-09-18 from [`plan.md`](plan.md) §7b. Living checklist: ticked as work
lands, with the commit or entry that did it. Nothing here is a result. Labels follow the plan:
**MVP** / opt-A / opt-B. Waves follow §7b.

Corrections to the plan found while opening (2026-09-18):

- Next free methodology number is **110**, not 098 — entries 098–109 were filed by iteration 2.
- AlphaMissense and SpliceAI are **already in the warehouse** (`warehouse.it2_insilico_annotations`,
  VEP plugins, iteration 2 entry 098). Two MVP lanes need no download; they need a warehouse-column
  adapter.
- CADD is not served by VEP REST (HTTP 500, entry 098) → O5 defaults to **REVEL**, tested at run.
- No table holds `hgvs_p`/`hgvs_c`; `VepRecord` drops them. Step 1's HGVS needs a VEP re-request.

## Wave 0 — contracts (main thread)

- [x] Plan written and revised (`plan.md`, 2026-09-13 → 09-18)
- [x] `steps.py`: `ITERATION4`, seven steps, registered in `STEPS_BY_ITERATION`
- [x] O4: `mva-science hypothesis-add --iteration` (platform entry 110)
- [x] `src/mva/zoo/` package: `types.py` (AlleleRecord, ScoreRow, Coverage, Adapter, DDL), README
- [x] import-linter layer for `mva.zoo`; `mva-zoo` script entry
- [x] `fixtures/it4/` synthetic records, per-lane score tables, pairs (+ generator script)
- [x] `docs/iteration4/README.md`, step folders 1–7 with README stubs
- [x] this board

## Wave 1 — build against fixtures (Opus agents, disjoint files)

- [ ] agent *record* — `mva.zoo.record` + tests; HGVS columns on `VepRecord` (MVP)
- [ ] agent *registry* — `models.toml` + `models.d/`, `registry.py`, cards, licence manifest, fetch script (MVP)
- [ ] agent *cache+adapters* — `cache.py`, adapters (warehouse column, DuckDB lookup, VEP REST), `cli.py` (MVP)
- [ ] agent *rank+report+merge* — `rank.py`, `merge.py`, `report.py`, `workflow.py`, figure script (MVP)
- [ ] agent *track2* — `mva.drugs.graph_walk`, PrimeKG fetch, decoy, build **and** run (MVP R2)

## Wave 2 — the R1 chain (main thread, strict order, files claims)

- [ ] run step 1 records (VEP HGVS re-request) → file `P4-1a`, entry 111+
- [ ] run step 2 fetch + coverage → `P4-2a`, `P4-3`; settle O5 (REVEL?)
- [ ] run step 3 score → `P4-4a`
- [ ] run step 4 rank + manifest; O7 (does the pair fall in an MVP lane?)
- [ ] run step 5 render (hand-written §6)
- [ ] run step 6 merge → `P4-6`, `P4-8`; `docs/iteration4/report.md` (R1)
- [ ] step 7 claims `P4-11`, `P4-12` filed from the track2 agent's run

## Wave 3 — dashboard + docs

- [ ] `/steps/step-<n>` pages for iteration 4, zoo cards page, agreement matrix, lineage view; fixtures re-blessed
- [ ] step READMEs filled, dictionary batch merged from `terms.draft.md`, `docs/README.md` index rows

## Optional (after R1 closes) — plan §7 A1–A7, B1–B5

- [ ] A1 ESM2 lane · A2 more tier-1 tables · A3 HTTP routes · A4 resume + kill test · A5 narrate · A6 synthesis + submission folder · A7 read-only pairing
- [ ] B1 Modal + NT-v2 · B2 ESM-C/Boltz-2 · B3 EVE/ΔΔG · B4 TxGNN · B5 judge
