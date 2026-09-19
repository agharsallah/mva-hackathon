# 128 — One command, eight stages, and three things a fixture could not catch

**Written:** 2026-09-19. **Step:** `step-4` (iteration 4). **Run:** R4 of the wave-2 chain.
**Hypotheses:** **none.**

This entry declares no hypothesis, on the two conditions
[`method.md`](../../../method.md) sets for a machinery entry inside a research step:

1. **Why.** It builds and measures an *instrument* — the checkpointed DAG that turns a score
   cache into per-lane rankings, reports and a manifest. "`mva-zoo run` writes
   `results.it4_model_ranks`" is true or false regardless of what this child's genome says;
   evidence cannot refute it, only a rerun can. Plan §5 step 4 files no MVP claim for the same
   reason; the opt-A claim `P4-5` (resume) is not scheduled.
2. **Which hypotheses it serves.** `P4-6` (every catalogue-free lane places the confirmed pair
   in the top decile) and `P4-8` (RRF consensus places it first) are filed and tested in R5 and
   R6 respectively. Both read the tables this run writes. The numbers those claims will be
   judged on are produced here; **they are not interpreted here.**

Precedent: iteration 2 entries [085](../../../iteration2/step-2/methodology/085-the-bait-and-where-it-runs.md),
[086](../../../iteration2/step-2/methodology/086-can-the-off-target-gate-be-reached.md) and
[089](../../../iteration2/step-2/methodology/089-the-instruments-and-the-gate-that-was-skipped.md).

## Question

Does one command run the whole zoo end to end on the real callset — normalize → registry check
→ fan-out → collect → rank-per-model → report-per-model → merge → render — writing each stage's
table with a lineage edge, and what does it cost in wall-clock and dollars?

## Inputs

| input | rows | role |
|---|---|---|
| `src/mva/zoo/zoo.example.toml` | — | the config; its sha256 **is** the run id (`it4-dcda40a4df2c`) |
| `results.it4_allele_records` | 39,286 | the record set ([114](../../step-1/methodology/114-one-record-per-allele-and-what-it-can-be-spelled-as.md)) |
| `warehouse.allele_scores` | 58,480 over 4 lanes | the cache ([122](../../step-3/methodology/122-every-lane-scored-once-and-only-once.md)) |
| `results.coding_alleles` | het rows | the biallelic pairs, via `mva.pipeline.compound_het` |
| `warehouse.hpo_gene_scores` | 5,261 rows, term set `with-parental` | section 5 of every report — the clinical half |

## Commands

```bash
uv run mva-zoo run --config src/mva/zoo/zoo.example.toml
```

## Observed

### The run

| stage | seconds | rows | note |
|---|---|---|---|
| normalize | 4.78 | 39,286 | records |
| registry_check | 0.01 | 4 | lanes |
| fan_out | 6.61 | 58,480 | scores over 4 lanes (all cached — nothing re-scored) |
| collect | 0.10 | 4 | coverages |
| rank_per_model | 1.49 | 0 | **63,347 pairs**; 0 rows because this `run_id` already wrote them |
| report_per_model | 0.43 | 4 | reports |
| merge | 1.44 | 4 | RRF rank (catalogue-free): **20,639** |
| render | 0.00 | 1 | `docs/iteration4/report.md` |
| **total** | **≈ 15 s** | | **$0** |

The first invocation that got this far wrote **402 rank rows**; the repeat above wrote 0 because
`run_id` is the config digest and every warehouse writer skips a `run_id` it has already
written. That is the idempotence the stage design promises, observed rather than asserted.

### Pairs, and the confirmed one

```
pairs: 63,347
confirmed_note: BUB1B has one pair; flagged confirmed
confirmed flagged: 1
```

**`PairBuild.skipped_genes` is not empty.** Sixteen genes exceeded `MAX_CALLS_PER_GENE = 60`
heterozygous calls and were skipped whole:

> AHNAK2, CARMIL1, CELF2, GRM8, HLA-DRB1, LRP1B, LTBP1, MUC16, MUC3A, MUC6, OR8U1, PDE3A,
> PDZD2, RYR3, SUGCT, ZNF717

Every one is a known high-diversity or repeat-rich locus — three mucins, an HLA class II gene,
two very large receptors (LRP1B, RYR3) and a nuclear pore-adjacent giant (AHNAK2). The cap
exists because pairing *n* het calls is O(n²), and 60 calls is already 1,770 pairs. `BUB1B` is
not among them, so the confirmed pair is unaffected — but **the list is a stated blind spot**,
not an empty set, and any claim about "every biallelic pair in the callset" is really about
every pair outside these sixteen genes.

The confirmed pair is flagged **exactly once**: `BUB1B` yields one pair in the callset, so the
consequence rule (a truncating allele plus a missense one) was not needed to disambiguate.

### Per-lane ranking of the confirmed pair

| lane | pairs ranked | pairs unscored | confirmed rank | percentile |
|---|---|---|---|---|
| `alphamissense` | 10,333 | 53,014 | **—** | — |
| `esm1b` | 3,673 | 59,674 | **—** | — |
| `revel` (adjacent) | 10,456 | 52,891 | **—** | — |
| `spliceai` | 50,696 | 12,651 | **11,980** | 23.63 % |

Three lanes have **no opinion**: each scored at most one half of the pair, and an unscored pair
is excluded rather than scored zero. This is what entries 119 and 122 predicted, now as a
ranking rather than as a coverage table.

### Three faults the fixtures could not have caught

Each was found by running against the real warehouse, and each is committed separately, before
this entry.

**1. The result schema and the lineage schema were one argument** (`91a7156`).
`rank.write_ranks` and `report.write_reports` took a single `schema` and used it both for the
table they write (`results`) and for the lineage edge (`warehouse`). The DAG died after
`collect` with `Table with name data_lineage does not exist`. The tests passed because their
in-memory warehouse emulated only `pg.results`, so an edge written into the result schema looked
right. They now create both schemas.

**2. The DAG could not find the cache it had written** (`58c0ae5`). `Deps.warehouse().score`
read `allele_scores` out of `config.schema` as well. This one **did not error**: it reported
`0 scores over 4 lanes`, ranked nothing, and produced a merged report whose RRF rank was `None`.
A silent wrong answer is the expensive kind, and it is the reason this entry exists as a
record rather than as a line in the next one. `Config` now carries `warehouse_schema`.

**3. Section 5 never quoted the phenotype** (`58c0ae5`). `Deps.hpo_row` was declared with a
`lambda: None` default and `Deps.warehouse` never supplied a reader, so every report printed
*"The child's 8 HPO terms produced no `BUB1B` row"* — for a gene the table ranks **#14 of 5,267
genes considered, phenotype score 0.36093** under term set `with-parental`. The repository's
standing two-sources rule says every result states what the clinical terms say about it; this
one was silently saying nothing. Fixed, and pinned by a test.

### Outputs

| artifact | where |
|---|---|
| per-lane ranks, 402 rows | `results.it4_model_ranks` |
| the seven-section report JSON, 4 rows | `results.it4_model_reports` |
| one lineage edge per table per run | `warehouse.data_lineage` |
| the run manifest (config digest, versions, venues, per-stage seconds, dollars) | `build/it4/runs/it4-dcda40a4df2c.json` |
| its coordinate-free copy | [`../../runs/it4-dcda40a4df2c.json`](../../runs/it4-dcda40a4df2c.json) |
| four per-model reports + the merged report | `docs/iteration4/reports/`, `docs/iteration4/report.md` |

The manifest answers the methods form's Q17 with measured numbers: eight stages, ≈ 15 s warm
(113 s on the first full pass), **$0**, four models at four named versions, every venue
`laptop`.

## Limitations

- **Sixteen genes are not in the pair set** (above). Stated wherever the pair count is quoted.
- **The manifest's per-stage seconds are for a warm run.** `fan_out` reads a full cache; a cold
  run's cost is entry 122's 6,320 s, and the two must not be added.
- **Resume is nominal.** `--from <stage>` skips stages; there is no kill-mid-fan-out test, so
  `P4-5` is not claimed (plan §5 step 4, opt-A).
- **`read_only_percentiles` is unused.** The 1,199 read-only alleles are scored but not paired
  and no stage yet builds their percentile table (plan §5 step 1, opt-A).
- **Two earlier manifests were deleted before committing** — the run that died on the schema
  bug and the run that ranked nothing. They are artefacts of a bug, not results; this entry is
  their record.

## Next test

Step 5 (R5): the per-model reports and their figures, section 6 written by hand, and `P4-6` —
does every catalogue-free lane place the confirmed pair in the top decile? Three of the four
have no opinion, which the claim's own wording says is neither support nor refutation; the
entry will say so in those words.
