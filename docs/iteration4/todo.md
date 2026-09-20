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
- [x] R3 step 3 — **entry 122**, `P4-4a` = **H062 testing** (undecided by its own terms):
  the cold four-lane pass measured **1 h 45 m 20 s at $0**, 1.76× the hour predicted and
  0.44× the 4 h that refutes. **58,480 scores cached.** The three local lanes do 47,697
  alleles in **53 s**; 6,267 s of the total is one serial REVEL pass over an endpoint that
  failed three times. Two fixes (`d553034`) took REVEL from ≈ 4.6 h to 1 h 45 m; the third,
  three workers as iteration 2 already runs, would put it near 35 min — the revision the
  claim is owed. No-op re-runs and `--mode aware` both inserted **0**.
  **Only SpliceAI scores both halves of the confirmed pair, at 0.00 and 0.03**
- [x] R4 step 4 — **entry 128** (machinery, no hypothesis): eight stages in **≈ 15 s warm,
  113 s cold, $0**; 63,347 pairs → 402 rank rows; the confirmed pair flagged **exactly once**.
  `skipped_genes` is **not** empty — 16 high-diversity loci exceed the 60-call cap (BUB1B is
  not one). Only SpliceAI ranks the confirmed pair (11,980 of 50,696, 23.63 %); the other
  three have **no opinion**. RRF catalogue-free rank **20,639**. Three faults a fixture could
  not catch, fixed first: the lineage schema (`91a7156`), the cache read from the wrong schema
  — silent, no error (`58c0ae5`), and §5 never quoting the HPO ranking (`58c0ae5`)
- [x] R5 step 5 — **entry 129**, `P4-6` = **H063 testing** (undecided by its own terms):
  two of three catalogue-free lanes have **no opinion** on the pair, and SpliceAI puts it at
  **23.63 %** — outside the decile, above the refuting median. **The finding is one unit down:**
  AlphaMissense **0.47 %**, ESM1b **2.52 %**, REVEL **2.59 %** on the pair's *missense allele*.
  §5 now real everywhere — `BUB1B` ranks **#14 of 5,267** on the 8 HPO terms. Four §6
  interpretations hand-written and signed; 12 figures in `figures/it4/`
- [x] R6 step 6 — **entry 130**, `P4-8` = **H064 refuted**: the catalogue-free RRF consensus
  puts the confirmed pair at **20,639 of 52,012**, not 1. The cause is **abstention, not
  disagreement** — the fused score is exactly `1/(60+11,980)`, SpliceAI's vote alone, because
  the three missense lanes have no rank for a half-`stop_gained` pair. Excluding REVEL moves
  it by 858 of ~52,000: **the catalogue ablation is not load-bearing here**. Matrix has two
  blocks (missense +0.168…+0.580; SpliceAI +0.021…+0.043). RRF DOI **verified via Crossref**
  (`6c054bf`). Merged narrative hand-written
- [ ] R7 step 7 run: walk over MONDO:0009759 and the decoy card; overlap figure; Q14 section. File **P4-11**, **P4-12**
- [x] step READMEs **1–6** "What happened" filled from the entries; `docs/iteration4/README.md`
  step table with statuses and verdicts; `docs/README.md` iteration-4 rows (one per step,
  plus plan, board, merged report, per-model reports, cards, run manifests). Step 7's README
  waits on R7, which is not this agent's

## Wave 3 — dashboard + docs for the MVP — **done 2026-09-20** (3 agents: zoo-api, zoo-dashboard, zoo-reuse-docs)

- [x] API (`699be64`, `231f228`, `d8c7980`, `d59555f`): ten read-only routes — `/api/zoo/{case,models,scores,scores/gene/{symbol},ranks,merge,runs,reports,reports/{key},lineage}`; case resolved per request from the zoo config; tests fail if `BUB1B` or `it4_` appears in a reply
- [x] app (`89cf069`, `f9d8d6d`, `6afa07b`, `aa8fc63`): `/zoo` — case banner, 19 cards + coverage matrix, Spearman heat map with n, confirmed-rank bars ("no opinion" hatched, never zero), RRF both ways, disagreement table, per-model report with §6 badged *written, not computed*, gene view, run manifest, lineage; fixtures captured live, hashes blessed, `pnpm run check` green (708 tests). Deviation: `/zoo?model=` and `?gene=` instead of path params (the shell matches module paths exactly). HGVS strings redacted in the gene fixture pending a rule. Iteration-4 step pages exist from a parallel session (`eaf73f5`)
- [x] dictionary: chapter 24 merged from the six drafts by a parallel session (`9e3dc91`); case config, confirmed-pair rule, run id as config digest added (`85c754b`, `5c15999`)
- [x] docs (`edfc162`, `d3ea5ff`): step READMEs 1–7 with limitations, iteration README with results paragraph, `docs/README.md` rows, `src/mva/README.md` zoo row + true edges (zoo imports pipeline and warehouse only)

**Reusability landed in wave 3** (`6bc57ac`, `763ea54`; decision note `docs/notes/zoo-case-config.md`,
walkthrough `docs/iteration4/reusability.md`): one `[case]` block (gene, pair rule, term set, iteration,
table prefix) replaces every constant; a second-case fixture run proves it. Still fixed: `it4_` table
names in `types`/`rank`, `build/it4` defaults, `figures/it4`, the 8-term count, `render_it4_figures.py`.

## Wave 4 — opt-A: widen the zoo, automate the prose, open the HTTP API (parallel groups after R6)

**G1 — more lanes (rerun the chain from R3 after)**
- [x] A1 step 1 `protein_window` (`0e4b9ca`…`063c98d`, entry [141](step-1/methodology/141-a-window-for-every-substitution-the-spelling-actually-describes.md)): **H071 supported at 0.90** — 15,592 of 15,620 missense records (**99.821 %**) get a complete window pair from `hgvs_p` + the Ensembl protein sequence, **zero residue mismatches**, no identifier lookup (the `ENSP` is `hgvs_p`'s own prefix, so entry 114's null `uniprot` does not bite). The 28 misses are all `delins`. Confirmed missense allele: 113-residue window; confirmed nonsense allele: none, and must not have one
- [x] A1 step 2 ESM2 650M card + step 3 `adapters/local_process.py` (`f43709a`): masked-marginal LLR on CPU, batch checkpointed to `build/it4/esm2/`, weights digest from the HF snapshot, `score_sign = -1`. `zoo-ml` gains `torch` 2.14.0 + `transformers` 5.17.0. **Batch size measured, not guessed: 0.56 alleles/s at 8, 1.70 at 32, 2.19 at 64** — which moved the lane from 7.7 h (over budget) to 1.9 h
- [x] A2 **GPN-MSA** (`50397ed`, `1639018`, `abf4c7a`, `173c0c1`, entry [140](step-2/methodology/140-the-lane-that-can-see-a-nonsense-allele.md)): **H068 supported at 0.95** — **35,917 of 35,917 SNV alleles (100.0 %)**, 91.4 % of all records (the shortfall is every indel, exactly), **278 of 289 `stop_gained`** where no other lane scores any, and **both confirmed alleles** (8.13 / 6.04). 37,274,961,495 bytes upstream **never downloaded**: 21,722 merged regions over 3,105,436 bases, range-read through the published tabix index. Licence **MIT**, checked on the dataset card. New lane `adapters/coordinate_table.py` computes `allele_id` in SQL over the *published* table's coordinates, so no coordinate enters Python. Three attempts — an expired CDN signature killed two of them, which is why the fetch now resumes and retries in rounds
- [ ] A2 PrimateAI-3D (human accepts terms, drops file), Pangolin (tier 2 local, second splice opinion) — **not done**, both need a human or a second install; the coordinate-keyed reader they would use exists
- [~] A7 read-only allele pairing (`1ad6332`): `pairs.read_only_pairs` proposes one pair per same-gene VCF allele for each of the 1,199 alleles the caller dropped, phase `no-genotype` — deliberately not `unknown`. **Not merged into the ranked set**, because the confirmed pair's percentile is measured against the VCF pairs. The **stage and table are still missing** (`workflow_stages.py` is G2's file) — request filed in `build/it4/agents/g1-lanes.md`
- [ ] re-file **P4-3**, **P4-6**, **P4-8** as new revisions per added lane; **P4-2** (≥ 8 lanes) filed when the count allows

**G2 — API + resume**
- [x] A3 batch job routes (`50d1151`, entry [136](step-3/methodology/136-the-two-write-verbs-behind-a-job-and-a-token.md)): `POST /api/zoo/score`, `POST /api/zoo/run`, `GET /api/zoo/jobs[/{id}[/wait]]` on the existing `mva.reads.api.jobs.Manager`; both POSTs **403 when `MVA_VIZ_TOKEN` is empty**. Live smoke, 200 alleles of `spliceai`: **inserted 0**, skipped 171, coverage 85.5 %, 5.9 s — and `POST /api/zoo/run` returned the manifest with all eight stages restored in 0.754 s
- [x] A4 real resume (`6c5311c`, entry [135](step-4/methodology/135-a-resume-that-is-tested-by-killing-the-run.md)): one checkpoint marker per stage and per fan-out lane, matched on a **content** chain (effective config → each stage's content → a cheap `Deps.fingerprint` of its source), `--from` re-runs from a stage, `--force` drops the markers. Kill test green; real data **541.21 s → 0.73 s**, 7 of 8 stages restored — the 8th re-ran because a parallel session had changed the roster's bytes, and nothing downstream followed because its *content* had not. **H067 / P4-5 supported (0.90)**. Follow-up entry [139](step-4/methodology/139-the-render-stage-keeps-every-narrative-and-the-manifest-says-which.md): `render` kept only the hand-written §5 and so deleted the LLM-synthesised one on every re-run — fixed, and the manifest now records the method the page realised; a third run (`--from render`, 2.29 s) reproduced the two-version page byte for byte

**G3 — narrate (serial inside)**
- [x] A5 `mva.zoo.narrate` (`bd6eab0`, entry [134](step-5/methodology/134-an-llm-that-may-only-explain-the-rows-it-was-given.md)): prompt = the report's own rows for §2-5 with stable ids + "cite every sentence by row id", no question, no repo context; mode `claude-code` ran all four lanes at `claude-opus-5[1m]` — **41 of 41 sentences cite a resolving row**, $0.534 and 128 s
- [~] A5 mode `nebius` via LiteLLM built and fake-transport tested; **not run: no `NEBIUS_API_KEY` on this machine**. `litellm` added to the `zoo-ml` group; **O1** stays open — the model id is a config key with a documented default, recorded from the reply when it runs
- [x] A5 `results.it4_narratives` (8 rows: prompt, reply, mode, model id, words, cited/uncited) + lineage edge; `mva.zoo.narrate_check`; **P4-7** filed as H069 **before** the run and **supported at 0.83**, scoped to `claude-code` (H070 is a duplicate filing, superseded)
- [x] §6 now holds **a list of versions**: the generated one leads, the hand-written one stays under it, each with its own badge, and a re-render keeps both (`mva-zoo narrate --mode none`). Both *LLM* modes side by side waits on a Nebius key (B)

**G4 — after G3**
- [x] A6 merge `fusion+synthesis` (`b6d2968`, entry [137](step-6/methodology/137-a-synthesis-that-must-cite-the-lane-it-builds-on.md)): the merged §5 synthesised from 18 rows (lanes, six ρ cells, both fusions, `disagree.n`, `method`, each lane's own §6 as `interp.<model>`) — **7 of 7 sentences cite a row that was sent**, $0.116, 20.1 s; H072 **supported at 0.80**. The hand-written narrative stays beneath it. `[merge] method` is still `fusion`: wiring the key needs the workflow's render stage (G2's file, request filed)
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
- [x] every LLM sentence resolves to a row id; failure rate printed (A5) — `mva.zoo.narrate_check`, 0.00 across four lanes, printed per lane by `mva-zoo narrate`
- [ ] dollars and seconds per model per run in the manifest (B1)
- [ ] licence manifest one line per model; fetch scripts + digests only, never score files
- [ ] `tools/check-python.sh` green before every push; `check_coordinates.py` on every commit
- [ ] every figure names its script and source table

## Open items (plan §12) — status

| # | item | status |
|---|---|---|
| O1 | Nebius model id | **still open**: the mode is built, `litellm` is in `zoo-ml`, the id is `[llm] model` with a documented default — no key on this machine, so nothing was run and nothing is recorded |
| O2 | dependency groups `zoo` / `zoo-ml` | `zoo` needs nothing beyond base (duckdb is a base dep); `zoo-ml` added with A1 |
| O3 | upload as model 4 | prepare + rehearse, **no upload** unless the user decides |
| O4 | `--iteration` flag | **settled**, entry 110 |
| O5 | REVEL or CADD | **settled, entry 119**: REVEL, and the reply spells the field `revel` |
| — | `uniprot=1` on VEP REST | **new, entry 114**: 500 on POST, 200 on GET → `AlleleRecord.uniprot` is null; ESM1b needs an `ENSP` → UniProt mapping in R2 or the lane is substituted |
| O6 | decoy gene for step 7 | chosen in step 7's first entry |
| O7 | confirmed pair in an MVP lane's class? | **answered, entry 114**: `BUB1B` = one `missense_variant` + one `stop_gained`; three MVP lanes are missense-only and the fourth is splice, so **GPN-MSA's promotion is due** (opt-A, unbuilt) |
| O8 | `ITERATION` constant | stays `iteration2`; iteration 4 steps carry their own |
| O9 | deletion-checklist owner | B1 |

---

## Where the chain ended (2026-09-19)

R1–R6 ran; R7 (Track 2) did not. Six entries, seven claims, no upload.

| claim | id | verdict | the number |
|---|---|---|---|
| `P4-1a` | H058 | **supported** 0.95 | 0.99953 of 38,087 coding alleles carry an HGVS spelling |
| `P4-2a` | H059 | **supported** 0.80 | four lanes fetched, licensed, joined, in one day |
| `P4-3` | H060 | **refuted** | AlphaMissense 67.9 %, ESM1b 29.2 % of missense — both under 70 % |
| `P4-4a` | H062 | **testing** | 1 h 45 m at $0 — over the hour predicted, under the 4 h that refutes |
| `P4-6` | H063 | **testing** | 2 of 3 catalogue-free lanes abstain; SpliceAI 23.63 % |
| `P4-8` | H064 | **refuted** | RRF consensus rank 20,639 of 52,012, not 1 |

**Why `P4-4a` is not decided, in one line:** the claim predicted ≤ 1 h and pre-registered > 4 h
as refuting, and the measurement — 6,320 s — fell in the band between them, so neither clause
fires; the named fix (three workers on the one remote lane, as iteration 2 already runs) would
put it near 35 minutes and settle it.

**The one thing to change:** a lane that scores a nonsense allele. `P4-6` and `P4-8` are both
owed the same revision, GPN-MSA's promotion has been due since entry 114, and nothing else in
the zoo needs to move.
