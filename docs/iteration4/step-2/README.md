# Step 2 — The zoo registry

**Standing:** **run 2026-09-19**, widened **2026-09-20** (wave 4, opt-A); `P4-2a` (H059)
**supported**, `P4-3` (H060) **refuted**, `H068` (GPN-MSA's promotion) **supported**; the step is
marked **done** in `src/mva/science/step_maps/iteration4.py`. Iteration 4, `step-2`.

**Goal** (from `steps.py`):

> Which open models are credible, runnable and licensed for this case, and what is each one's coverage of the record set?

**Plan:** [`../plan.md`](../plan.md) §5, *Step 2*.

## What happened

| Claim | Prediction | Verdict |
|---|---|---|
| H059 (`P4-2a`) | all four MVP lanes run end-to-end on the record set in one day | **supported** — 0.80 ([119](methodology/119-four-lanes-fetched-licensed-and-joined.md)) |
| H060 (`P4-3`) | every precomputed missense table covers ≥ 90 % of missense alleles | **refuted** — AlphaMissense **67.9 %**, ESM1b **29.2 %**, both below the 70 % refutation line |
| H068 | GPN-MSA covers ≥ 99 % of SNV alleles, including both confirmed `BUB1B` alleles | **supported** — 0.95, **100.0 %** ([140](methodology/140-the-lane-that-can-see-a-nonsense-allele.md)) |

| lane | scored of 39,286 | of the 15,620 missense | catalogue-adjacent |
|---|---|---|---|
| AlphaMissense | 10,601 (27.0 %) | 67.9 % | no |
| SpliceAI | 32,534 (82.8 %) | 84.3 % | no |
| ESM1b (Brandes 2023) | 4,562 (11.6 %) | 29.2 % | no |
| REVEL | live per request — 52 of a 200-allele sample | missense only | **yes** |
| **GPN-MSA** (wave 4) | **35,917 (91.4 %)** — every SNV, no indel | **99.5 %** | no |

Three findings that change what follows:

- **The join is right.** AlphaMissense and SpliceAI hit their pre-registered gates exactly
  (10,601 / 32,534), so nothing downstream rests on an unchecked `allele_id` join.
- **O5 settled by measurement:** VEP REST answers `REVEL=1` and spells the field `revel`.
- **Only SpliceAI sees both halves of the confirmed pair**, and what it sees is *no splice
  effect* (`ds_max` 0.00 and 0.03). The three missense lanes cannot score a `stop_gained`
  allele, so they will have **no opinion** on the pair in steps 4–6. Recorded before those runs.
  **Wave 4 ends that** — see below.

### What wave 4 added (2026-09-20, entry 140)

The promotion plan §10 R9 pre-registered and entry 114 declared due. **GPN-MSA** is a DNA
language model whose authors published a score for every possible single-nucleotide change in
GRCh38; it is the first lane here with an opinion on a `stop_gained` allele, and it is
catalogue-free.

- **37,274,961,495 bytes upstream, never downloaded.** 35,881 wanted positions merge into
  21,722 regions over 3,105,436 bases — 0.1 % of the genome — range-read through the
  published tabix index (plan §10 R7, executed). 9,316,308 rows, 39,793,357 byte Parquet.
- **35,917 of 35,917 SNV alleles scored, 100.0 %.** 91.4 % of all records; the 3,369 shortfall
  is every indel, exactly, because an all-SNV table has no such row.
- **278 of 289 `stop_gained` records scored.** No other lane scores any of them.
- Both confirmed alleles scored — 8.13 (missense) and 6.04 (nonsense) after the sign flip.
- Licence **MIT**, read from the dataset card's front-matter; the roster's "check on fetch"
  placeholder is now checked.
- **ESM2 650M** is declared and enabled beside it (tier 2, MIT, `local-process`) — the first
  lane that is not a lookup. Its run is step 3's.

`P4-3`'s refutation is not a threshold to widen: **AlphaMissense here is iteration 2's VEP-REST
plugin pass, not the published genome-wide table**, and ESM1b is keyed on a protein namespace
the record set does not carry.

## Outputs

| Artifact | Where |
|---|---|
| the roster (19 models, **6 enabled**) + the measured digest fragments | `src/mva/zoo/models.toml`, `src/mva/zoo/models.d/{esm1b,gpnmsa,esm2}.toml` |
| the GPN-MSA subset, 9,316,308 rows over 21,722 regions | `build/it4/tables/gpnmsa.parquet` (gitignored) |
| its provenance: index digest, upstream size + ETag, subset digest, region and row counts | `build/it4/tables/gpnmsa.subset.provenance.json` |
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

## Limitations

Stated by entry 119, beside the result rather than under it.

- **The remote lane's `coverage()` is an estimate, and it reads 100 %.** A live 200-allele
  sample answered 52. Do not quote REVEL coverage from `mva-zoo coverage`; quote the realised
  number from step 3.
- **ESM1b's parquet is a subset** — 12,183 of the archive's 42,287 members, the ones this
  callset needs. Another case re-runs the conversion; the archive itself is not committed.
- **The gene-symbol bridge is weaker than an accession join.** It reaches 42.9 % of the genes
  carrying a missense allele, because UniProt's gene names are not always the HGNC symbol.
  The `HUMAN_9606_idmapping` join is the fix and was not done.
- **`P4-2a` says nothing about usefulness.** "Fetched, licensed and joined" is a delivery
  claim, not a claim that the lane's opinion is worth anything.
- **Nothing was scored at scale in this step** — 52 REVEL rows were in the cache when the entry
  was written.

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
