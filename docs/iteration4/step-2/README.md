# Step 2 — The zoo registry

**Standing:** **run 2026-09-19**; `P4-2a` (H059) **supported**, `P4-3` (H060) **refuted**; the
step is marked **done** in `src/mva/science/step_maps/iteration4.py`. Iteration 4, `step-2`.

**Goal** (from `steps.py`):

> Which open models are credible, runnable and licensed for this case, and what is each one's coverage of the record set?

**Plan:** [`../plan.md`](../plan.md) §5, *Step 2*.

## What happened

| Claim | Prediction | Verdict |
|---|---|---|
| H059 (`P4-2a`) | all four MVP lanes run end-to-end on the record set in one day | **supported** — 0.80 ([119](methodology/119-four-lanes-fetched-licensed-and-joined.md)) |
| H060 (`P4-3`) | every precomputed missense table covers ≥ 90 % of missense alleles | **refuted** — AlphaMissense **67.9 %**, ESM1b **29.2 %**, both below the 70 % refutation line |

| lane | scored of 39,286 | of the 15,620 missense | catalogue-adjacent |
|---|---|---|---|
| AlphaMissense | 10,601 (27.0 %) | 67.9 % | no |
| SpliceAI | 32,534 (82.8 %) | 84.3 % | no |
| ESM1b (Brandes 2023) | 4,562 (11.6 %) | 29.2 % | no |
| REVEL | live per request — 52 of a 200-allele sample | missense only | **yes** |

Three findings that change what follows:

- **The join is right.** AlphaMissense and SpliceAI hit their pre-registered gates exactly
  (10,601 / 32,534), so nothing downstream rests on an unchecked `allele_id` join.
- **O5 settled by measurement:** VEP REST answers `REVEL=1` and spells the field `revel`.
- **Only SpliceAI sees both halves of the confirmed pair**, and what it sees is *no splice
  effect* (`ds_max` 0.00 and 0.03). The three missense lanes cannot score a `stop_gained`
  allele, so they will have **no opinion** on the pair in steps 4–6. Recorded before those runs.

`P4-3`'s refutation is not a threshold to widen: **AlphaMissense here is iteration 2's VEP-REST
plugin pass, not the published genome-wide table**, and ESM1b is keyed on a protein namespace
the record set does not carry.

## Outputs

| Artifact | Where |
|---|---|
| the roster (19 models, 4 enabled) + the measured digest fragment | `src/mva/zoo/models.toml`, `src/mva/zoo/models.d/esm1b.toml` |
| one card per model + the licence manifest | [`../cards/`](../cards/) |
| the ESM1b score table, 169,457,840 rows, 12,183 of 42,287 members | `build/it4/tables/esm1b.parquet` (gitignored) |
| its provenance: archive digest, licence, row count, output digest | `build/it4/tables/esm1b.provenance.json` |
| the publisher's accession → gene map, and the accession subset asked for | `build/it4/tables/esm1b.genes.csv`, `esm1b.accessions.txt` |
| 52 REVEL rows (the live sample) | `warehouse.allele_scores` |

## Tools this step needed

| Tool | Why |
|---|---|
| `tools/fetch_zoo_tables.py` + `--accessions` | download, digest, convert; the plan's tier-1 rule — a subset for this case's records only |
| `mva.zoo.tables` **(new)** | reshape a matrix archive into one long table; Python + pyarrow, because one `UNPIVOT` over a glob never finishes |
| `mva.zoo.adapters.protein_table` **(new)** | a lane keyed by protein accession + `R550Q`, reached from `gene` + `hgvs_p` through the publisher's own map |
| `mva.zoo.registry` | validation at load time; `ADAPTER_FOR_SOURCE` now admits two adapters for a downloaded table |

## Reproduce

```bash
uv run python tools/fetch_zoo_tables.py --fetch esm1b --execute \
    --accessions build/it4/tables/esm1b.accessions.txt
uv run mva-zoo coverage --model alphamissense
uv run mva-zoo coverage --model spliceai
uv run mva-zoo coverage --model esm1b
uv run mva-zoo score --model revel --limit 200
```

## Methodology

[`methodology/119`](methodology/119-four-lanes-fetched-licensed-and-joined.md) — the fetch, the
five fixes it needed, the coverage numbers, O5, and both verdicts.
