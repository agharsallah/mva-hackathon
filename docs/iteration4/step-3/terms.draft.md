# Step 3 — dictionary terms, drafted

**Standing:** drafted 2026-09-18 by the wave-1 agent *cache-adapters*. **Not merged.** The
*docs* agent merges these into [`docs/dictionary.md`](../../dictionary.md) in one pass (plan
§7b), in an order where every term follows the terms it depends on.

Dependency-safe order: **inference tier** (already drafted by step 2 — do not duplicate it) →
**adapter** → **batch job** → **cache key** → **append-only cache** → **feature store** →
**no-op re-run**.

Sources: `src/mva/zoo/adapters/`, `src/mva/zoo/cache.py`, `src/mva/zoo/cli.py`,
`docs/iteration4/plan.md` §5 step 3. Nothing has been run on real data, so no entry quotes a
coverage, a row count or a wall-clock number.

---

**Adapter** — the thin piece of code that makes one model look like every other model to the
rest of the pipeline: hand it allele records, get score rows back. Same idea as a database
driver — the caller writes one piece of code and swaps the driver underneath. One file per
model (`src/mva/zoo/adapters/<lane>.py`); adding a model is adding a file, never editing a
shared one.
*Example:* `warehouse_column.py` answers for AlphaMissense by reading the
`am_pathogenicity` column the warehouse already holds; `vep_rest.py` answers for REVEL by
asking Ensembl. Both satisfy the same three methods — `coverage()`, `score()`, `submit()`.
*Context:* the protocol is `mva.zoo.types.Adapter`, pinned in wave 0; the three MVP lanes are
built in `src/mva/zoo/adapters/`. Related: [inference tier](#), [model card](#),
[batch job](#). Introduced by plan §5 step 3 (first seen 2026-09-18).

---

**Batch job** — one run of one model over many alleles at once, instead of one request per
allele. Batching is what makes a remote model affordable: 40,000 single calls to a rate-limited
server would take days; 200 alleles per call takes minutes.
*Example:* the VEP REST lane sends 200 alleles per HTTP POST — Ensembl's documented ceiling —
and a batch the server refuses is split in half and retried rather than lost whole.
*Context:* batching lives in `mva.pipeline.annotate_vep.batches` and is reused unchanged by
`mva.zoo.adapters.vep_rest`; the cache writes in batches of 5,000 rows for the same reason.
Related: [adapter](#), [inference tier](#). Introduced by plan §5 step 3 (first seen
2026-09-18).

---

**Cache key** — the columns that decide whether a stored result already exists. Ask for
something whose key is already present and you get the stored answer instead of a new
computation.
*Example:* the score cache's key is `(model, version, allele_id)` — three columns. A new
version of the same model on the same allele is a *different* key, so it is stored beside the
old one rather than replacing it.
*Context:* `mva.zoo.cache.KEY_COLUMNS`; the skip is performed as a SQL anti-join, so a repeat
run costs one round trip per batch rather than one per row. Related: [append-only cache](#),
[no-op re-run](#), [allele id](#). Introduced by plan §5 step 3 (first seen 2026-09-18).

---

**Append-only cache** — a store that is only ever added to: no row is updated, no row is
deleted. A correction is a new row (a new model version), never an edit of the old one.
*Example:* `warehouse.allele_scores` — writing the same `(model, version, allele_id)` twice
inserts nothing the second time, and the first row keeps the `run_id` of the run that produced
it.
*Context:* `mva.zoo.cache.write`; the same discipline the repository already applies to
`warehouse.data_lineage` and to the hypothesis register — a record that can be edited is not
evidence. Related: [cache key](#), [lineage](#), [no-op re-run](#). Introduced by plan §5 step
3 (first seen 2026-09-18).

---

**Feature store** — one table of pre-computed inputs that every downstream job reads, instead
of each job recomputing them. Here: every model's verdict on every allele, in one place, so the
ranker, the per-model report and the merge all read the same numbers.
*Example:* `warehouse.allele_scores` holds `allele_id, model, version, digest, score, aux,
venue, licence, run_id, ts`. Step 4's ranking never calls a model — it reads this table.
*Context:* `mva.zoo.cache`, `mva.zoo.types.ALLELE_SCORES_COLUMNS`; this is the idea iteration
3's draft proposed and iteration 4 absorbed as step 3 (plan §5). Related: [append-only
cache](#), [cache key](#), [adapter](#). Introduced by plan §5 step 3 (first seen 2026-09-18).

---

**No-op re-run** — running the same command a second time and having it do nothing, because
everything it would produce is already there. The property that makes a long pipeline safe to
interrupt: after a crash you re-run the whole thing and pay only for what had not finished.
*Example:* `uv run mva-zoo score --model alphamissense` twice in a row prints
`inserted 0, skipped <n> (already cached)` the second time, and the table is unchanged.
*Context:* `mva.zoo.cache.write` returns `Written(inserted, skipped)`; the remote VEP lane gets
the same property from a checkpoint file under `build/it4/vep-<plugin>/` that holds allele ids
and numbers only. The related property for a whole pipeline stage is **idempotence**.
Related: [cache key](#), [append-only cache](#), [idempotent stage](#). Introduced by plan §5
step 3 (first seen 2026-09-18).
