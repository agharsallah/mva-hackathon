# Model cards — iteration 4's zoo roster

**Standing:** generated 2026-09-18 (iteration 4, wave 1, agent *registry*) from
[`src/mva/zoo/models.toml`](../../../src/mva/zoo/models.toml). Declarations only: **no model has
run yet**, so no card carries a coverage block or a measured digest. Re-verify after wave 2.

## What is here

| file | what it is |
|---|---|
| `<key>.json` | one **model card** per model — name, exact version, tier, where its numbers come from, licence, whether it is catalogue-adjacent, and the free-text notes (coverage expectation, failure modes, what is still to verify) |
| `licences.md` | the licence manifest — one row per model, and what this public repository ships for it |

A card is a *declaration*, not a result. After a run, `mva.zoo.registry.card_with_coverage()`
adds the measured `coverage` block (scored / total, and the same split per consequence class);
that enriched card is what the step-5 report and the dashboard render.

## Regenerate

```bash
uv run python -c "from mva.zoo import registry as r; r.write_cards(r.load(), 'docs/iteration4/cards')"
```

Never edit a file in this folder. The roster is `src/mva/zoo/models.toml` plus the fragments in
[`src/mva/zoo/models.d/`](../../../src/mva/zoo/models.d/); a measured `sha256` arrives as a
fragment printed by `tools/fetch_zoo_tables.py`, never as a hand-typed value.

## Reading a card

- **tier** — 1 = look the answer up in a precomputed table, 2 = run the model locally on CPU,
  3 = run it on a remote GPU. Cost and latency follow the tier, not the model's fame.
- **source** / **adapter** — `warehouse-column` (already annotated in the warehouse, no
  download), `table` (a public precomputed file), `vep-rest` (Ensembl's REST service),
  `local-process`, `modal`. One adapter module speaks each source.
- **catalogue_adjacent** — `true` means the model was trained on a variant catalogue
  (ClinVar/HGMD-derived labels), so it may have *seen* the answer. The merged ranking in step 6
  is printed twice, with and without these lanes.
- **non_commercial** — the terms forbid commercial use. Hackathon use is non-commercial, so this
  never blocks a run; it blocks shipping the file, which is why no score table is committed.
- **enabled** — `true` for the four MVP lanes only (AlphaMissense, SpliceAI, ESM1b, REVEL). The
  rest are declared, licensed and ready, but do not run in the MVP.

## Roster at a glance (2026-09-18)

19 models declared · 4 enabled · 5 downloadable (`source = "table"`) · 3 catalogue-adjacent
(REVEL enabled, CADD and ClinPred off) · 8 under non-commercial terms.
