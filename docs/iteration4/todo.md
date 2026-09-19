# Iteration 4 — the board: the whole plan, end to end

**Standing:** rewritten 2026-09-18 to cover **every** item of [`plan.md`](plan.md) — MVP, opt-A and
opt-B — after the user asked for the full system, not the minimum. Ticked as work lands, with the
commit or entry that did it. Nothing here is a result. Labels: **MVP** / **A** (opt-A) / **B**
(opt-B), waves per plan §7b; *build* = code vs `fixtures/it4/` (agents, parallel), *run* = real data
(main thread, strict chain, files claims).

**Target system.** One `AlleleRecord` in; N models behind one `Adapter` protocol across three
hosting tiers (warehouse/table lookup on the laptop, CPU process on the laptop, GPU function on
Modal); every score in one append-only cache with lineage; one resumable DAG from one command or
one HTTP call; one report template per model with an LLM-written interpretation in two switchable
modes; three merge methods behind one config key; Track 2 by graph walk **and** GNN over PrimeKG
with a decoy control; every page on the dashboard. Change the inputs, not the code (plan §9).

Corrections to the plan found while opening (2026-09-18): next methodology number is **111**
(110 = the `--iteration` platform fix); AlphaMissense and SpliceAI already sit in
`warehouse.it2_insilico_annotations`; CADD is not served by VEP REST (entry 098) → O5 = REVEL;
no table holds HGVS, so step 1 re-asks VEP.

---

## Wave 0 — contracts (main thread) — **done**, `f493364` + `2447e3e` + `b9429ad`

- [x] `steps.py`: `ITERATION4`, seven steps, `STEPS_BY_ITERATION`
- [x] O4: `mva-science hypothesis-add --iteration` (entry 110)
- [x] `src/mva/zoo/types.py`: `AlleleRecord` (+`uniprot`), `ScoreRow`, `Coverage`, `RemoteJob`, `Adapter`, DDLs, `allele_id`
- [x] import-linter layer, `mva-zoo` script, `fixtures/it4/` + generator, folder skeleton

## Wave 1 — build the MVP chain against fixtures — **done**

- [x] step 1 `record` / `record_hgvs` / `record_write`; HGVS + UniProt on `VepRecord` — `41f093b`
- [x] step 2 `registry`, `models.toml` (19 cards, 4 enabled), `models.d/`, cards, licence manifest, `fetch_zoo_tables.py` — `9bfdfa6`
- [x] step 3 `cache`, adapters `warehouse_column` / `duckdb_lookup` / `vep_rest`, `mva-zoo` CLI — `91742ad`
- [x] steps 4–6 `pairs`/`rank`, `report*`, `merge*`, `workflow*`, `render_it4_figures.py` — `0e5e87a`
- [ ] step 7 *track2* build: `mva.drugs.graph_walk`, PrimeKG fetch + digest, approved-drug filter, decoy card (O6), `ranking-walk.tsv` + provenance — **deferred**: Track 2 session active in `src/mva/drugs/**`; start when it lands, or land it as `src/mva/zoo/track2/` if the collision persists

## Wave 2 — run the MVP chain on real data (main thread, strict order, each run files its entry + claims)

- [x] R1 step 1 (`05d7326`) — **entry 114**, `P4-1a` = **H058 supported** (0.99953 of 38,087 coding alleles
  spelled; 39,286 records; 1 h 45 m; VEP release 116/GRCh38). Two REST fixes were needed:
  `uniprot=1` is **500 on POST** (so `uniprot` is null everywhere — ESM1b's join key is step 2's
  problem) and `QUERY_PARAMS` times out at 200 alleles (lean payload instead).
  **O7 answered: the lane gap hits the pair** — `BUB1B` has exactly one `missense_variant` and
  one `stop_gained`, and three of the four MVP lanes are missense-only, so **GPN-MSA's
  promotion into the MVP is due** (plan §10 R9; opt-A, not built here)
- [x] R2 step 2 (`cf492c5`) — **entry 119**, `P4-2a` = **H059 supported** (all four lanes ran; AlphaMissense
  10,601 and SpliceAI 32,534 hit their join gates exactly), `P4-3` = **H060 refuted**
  (AlphaMissense **67.9 %** and ESM1b **29.2 %** of the 15,620 missense alleles, both under the
  70 % refutation line). **O5 settled**: VEP REST spells the field `revel`. Five measured fixes:
  the REVEL lane sent the whole annotation payload and timed out; the ESM1b converter excluded
  the wrong index column, used a bound parameter as a COPY target, matched the *directory* with
  its accession regex, and could not finish one `UNPIVOT` over a glob — reshaping now lives in
  `src/mva/zoo/tables.py` (**169,457,840 rows in 95 s**). ESM1b needed a new lane,
  `adapters/protein_table.py`. **Only SpliceAI sees both halves of the confirmed pair**, at
  `ds_max` 0.00 and 0.03 — recorded before R5/R6 run
- [ ] R3 step 3: `mva-zoo score` × 4 lanes (catalogue-free), re-run one for the no-op proof, `--mode aware` pass for the ablation. File **P4-4a** (≤ 1 h laptop, $0)
- [ ] R4 step 4: `mva-zoo run` → `results.it4_model_ranks`, manifest `build/it4/runs/<id>.json` + coordinate-free copy; check `skipped_genes` empty, confirmed-pair flagging unique
- [ ] R5 step 5: per-model reports `docs/iteration4/reports/<key>.md`, §6 hand-written and signed, histograms in `figures/it4/`
- [ ] R6 step 6: agreement matrix, RRF with/without adjacent, disagreement table, `docs/iteration4/report.md` (method `fusion`). File **P4-6**, **P4-8** (MVP lanes)
- [ ] R7 step 7 run: walk over MONDO:0009759 and the decoy card; overlap figure; Q14 section. File **P4-11**, **P4-12**
- [ ] step READMEs 1–7 "What happened" filled from the entries; `docs/README.md` index rows

## Wave 3 — dashboard + docs for the MVP (2 agents)

- [ ] API: `GET /api/zoo/models` (cards + coverage), `GET /api/zoo/scores?allele_id=`, `GET /api/zoo/ranks`, `GET /api/zoo/merge` (matrix, RRF, disagreements), `GET /api/zoo/runs` (manifests) under `src/mva/viz/api_zoo*.py`
- [ ] app: `/steps/step-<n>` pages for iteration 4 (one per step, from the live API), zoo cards page, agreement-matrix view, per-model report view, run-manifest view, lineage view per table; fixtures re-captured and hashes re-blessed
- [ ] dictionary: merge the six `docs/iteration4/step-<n>/terms.draft.md` into `docs/dictionary.md` in dependency order; `/learn` regenerated
- [ ] `docs/iteration4/README.md` step table with statuses; `docs/README.md` iteration-4 rows; `src/mva/README.md` gains the `zoo` row and graph edge

## Wave 4 — opt-A: widen the zoo, automate the prose, open the HTTP API (parallel groups after R6)

**G1 — more lanes (rerun the chain from R3 after)**
- [ ] A1 step 1 `protein_window` (wild-type + mutant amino-acid window from UniProt/Ensembl sequence + `hgvs_p`); file **P4-1** (protein half)
- [ ] A1 step 2 ESM2 650M card (MIT, tier 2) + step 3 `adapters/local_process.py` (`transformers` on CPU, masked-marginal log-likelihood ratio, batched, checkpointed); `zoo-ml` dependency group (`transformers`, `torch`)
- [ ] A2 tier-1 lanes GPN-MSA (HF `songlab/gpn-msa-hg38-scores`, tabix subset for the ~40k alleles only — R7), PrimateAI-3D (human accepts terms, drops file), Pangolin (tier 2 local, second splice opinion); `duckdb_lookup` gains a coordinate-keyed reader **inside** `build/it4/`
- [ ] A7 read-only allele pairing with same-gene VCF alleles (step 4 substep); `read_only_percentiles` gets its stage + table
- [ ] re-file **P4-3**, **P4-6**, **P4-8** as new revisions per added lane; **P4-2** (≥ 8 lanes) filed when the count allows

**G2 — API + resume**
- [ ] A3 read-only routes (wave 3) → batch job routes: `POST /api/zoo/score {model, allele_ids, mode} → {job_id}`, `GET /api/zoo/jobs/{id}/wait`, on the existing `/api/jobs` worker pattern (`viz/serve.py`); token-gated like the rest
- [ ] A4 step 4 `--from <stage>` real resume: skip-if-checkpoint-exists per stage, kill-mid-fan-out test; file **P4-5**

**G3 — narrate (serial inside)**
- [ ] A5 `mva.zoo.narrate`: prompt = section JSON + "cite every sentence by row id", temperature 0; mode `claude-code` (`claude -p`, model id recorded from the reply) first
- [ ] A5 mode `nebius` via LiteLLM (`NEBIUS_API_KEY`, model id from config — **O1**), same prompt, same JSON
- [ ] A5 `results.it4_narratives` (prompt, reply, mode, model id, run_id); citation checker; file **P4-7**
- [ ] both modes on every model, side by side in §6 (B)

**G4 — after G3**
- [ ] A6 merge `fusion+synthesis`: LLM synthesises the merged narrative from per-model interpretations + matrix, cited; default method
- [ ] A6 `submissions/track1/iteration-4/` rehearsed: CSV via `tools/design_submission.py`, methods form row "model 4" (automated yes, public models only, runtime + cost from the manifest), decode table, README with sha256; `tools/check_iteration.py` green; **upload default: no** (O3)
- [ ] `submissions/track2/iteration-<n>/` scaffolded by `tools/new_iteration.py` when R2 is upload-worthy

## Wave 5 — opt-B: GPU tiers on Modal, the judge, the GNN

- [ ] B1 step 1 `dna_window_ref/alt` (8,192 bp from the pinned reference, only in `build/it4/`); file **P4-1** (DNA half)
- [ ] B1 Modal project: account, `$50` hard cap in config, one volume per model (weights), `docs/notes/data-deletion-checklist.md` lists every volume (O9: check `docs/README.md` for an owner first)
- [ ] B1 step 3 `adapters/modal.py`: `submit()` sends windows + `allele_id` only; result parquet pulled into the cache; GPU type, seconds, dollars into the manifest (per-stage cost attribution)
- [ ] B1 NT-v2 500M lane (plain `transformers`, any GPU) — the first tier-3 DNA-LM
- [ ] B1 Evo 2 1B lane (A100 first, H100 if the authors' stack demands it; cut before NT-v2 — R1)
- [ ] B2 ESM-C 600M lane (record `github.com/evolutionaryscale/esm` tag + weights digest); ESM2 vs ESM-C agreement figure
- [ ] B2 Boltz-2: wild-type vs mutant BubR1 structure, confidence delta + visual (one protein, not a scorer); verify the bioRxiv DOI by Crossref before citing
- [ ] B3 EVE (coverage footnote), RaSP / ThermoMPNN ΔΔG on the AlphaFold model → hypomorph vs null → drug direction D1–D4 into the Q14 section
- [ ] B4 TxGNN on Modal (Python 3.8 / DGL 0.5.2 image, one-day timebox; fallback = walk alone, recorded) → `ranking-txgnn.tsv`; file **P4-10**
- [ ] B5 merge `judge`: LLM ranks the models by evidential value, printed beside RRF, flagged non-reproducible; file **P4-9**
- [ ] **P4-4** (full zoo ≤ $30, ≤ 8 h laptop) filed from the manifests; cut order §7 applied and recorded if refuted
- [ ] re-run the chain with every lane; final revisions of **P4-3**, **P4-6**, **P4-8**; dashboard pages updated (cards, matrix, cost view)

## Quality gates that hold throughout (plan §8)

- [ ] every `allele_scores` row carries model, version, digest, licence, venue, run_id (test exists — keep it green as lanes are added)
- [ ] every card says catalogue-adjacent yes/no; merge prints both ranks
- [ ] every LLM sentence resolves to a row id; failure rate printed (A5)
- [ ] dollars and seconds per model per run in the manifest (B1)
- [ ] licence manifest one line per model; fetch scripts + digests only, never score files
- [ ] `tools/check-python.sh` green before every push; `check_coordinates.py` on every commit
- [ ] every figure names its script and source table

## Open items (plan §12) — status

| # | item | status |
|---|---|---|
| O1 | Nebius model id | open until A5 |
| O2 | dependency groups `zoo` / `zoo-ml` | `zoo` needs nothing beyond base (duckdb is a base dep); `zoo-ml` added with A1 |
| O3 | upload as model 4 | prepare + rehearse, **no upload** unless the user decides |
| O4 | `--iteration` flag | **settled**, entry 110 |
| O5 | REVEL or CADD | **settled, entry 119**: REVEL, and the reply spells the field `revel` |
| — | `uniprot=1` on VEP REST | **new, entry 114**: 500 on POST, 200 on GET → `AlleleRecord.uniprot` is null; ESM1b needs an `ENSP` → UniProt mapping in R2 or the lane is substituted |
| O6 | decoy gene for step 7 | chosen in step 7's first entry |
| O7 | confirmed pair in an MVP lane's class? | **answered, entry 114**: `BUB1B` = one `missense_variant` + one `stop_gained`; three MVP lanes are missense-only and the fourth is splice, so **GPN-MSA's promotion is due** (opt-A, unbuilt) |
| O8 | `ITERATION` constant | stays `iteration2`; iteration 4 steps carry their own |
| O9 | deletion-checklist owner | B1 |
