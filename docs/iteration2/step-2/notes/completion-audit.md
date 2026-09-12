# Step 2 — what actually ran, what did not, and what to change

**Standing:** opened and closed 2026-09-12. Every row of table B is done and
`uv run mva-science check --blind iteration2` passes. This note supersedes the
`Standing: complete` line the step README carried earlier that day, which was wrong: four
pre-registered items had not run and the iteration's own blind gate was red.

The step README states results; this note states *state*. Table C is the part worth
re-reading later: the findings that change how **later** steps must report a rate.

## Why this note exists

`tools/check-python.sh` was green while `mva-science check --blind iteration2` was red.
Nothing in the repository connected the two, so a failing integrity gate did not stop a
commit that declared the step complete. Row **B4** fixes that; the rest of the table is
the backlog the missing gate let through.

---

## A — done, verified against an executed run

| | What | Evidence |
|---|---|---|
| A1 | `mva.kmer` engine: 2-bit packing, canonical form, bait cutting, uniqueness pass, membership | `tests/test_kmer.py`; [085](../methodology/085-the-bait-and-where-it-runs.md) |
| A2 | Bait built over targets **and** decoys, gate numbers printed before the pass | `build/it2/step-2/bait-profile.json` |
| A3 | Uniqueness sweep; off-target measured at **8.79 %** against a `< 5 %` gate — **gate failed, recorded as failed** | [086](../methodology/086-can-the-off-target-gate-be-reached.md) |
| A4 | `POST /bait` deployed by the user; full pass over 1,071,835,104 reads | [087](../methodology/087-the-pass-and-what-it-recovered.md) |
| A5 | Recovery: 14,657,560 reads, 7,886,613 complete fragments, zero unpaired | `build/it2/step-2/recovery.json` |
| A6 | H021 witness recall 0.9052 against a `≥ 0.90` gate | `build/it2/step-2/bait-recall.json` |
| A7 | Align / coverage / freebayes / bcftools / delly / dysgu / whatshap, all resumable | `build/it2/step-2/calling-report.json` |
| A8 | Six `results.it2_*` tables loaded with dual lineage rows | `mva-warehouse pg-load-it2-step2` |
| A9 | Five figures + the results page | `figures/track1/iteration2/step-2/` |
| A10 | Four methodology entries, 085–088 | `docs/iteration2/step-2/methodology/` |
| A11 | Step-3 handover | [`../../step-3/README.md`](../../step-3/README.md) |

---

## B — left, in the order it will be done

Ranked by what a wrong answer costs, not by effort.

| | What | Why it is not optional | State |
|---|---|---|---|
| **B1** | **Blind gate is red** — `H017`/`H018` settled with no evidence row; entry 088 names two iteration-1 candidate tables inside a sentence saying they were *not* read | The gate is this iteration's only mechanical proof that the blinding held. A red gate is not a formatting complaint; it is the audit trail refusing to sign | **done** — the platform survey in [089](../methodology/089-the-instruments-and-the-gate-that-was-skipped.md) is the missing evidence row; 088's disclaimer is exempted by exact quotation in `mva.science.blind.NOT_READ_DECLARATIONS` because `methodology/` is append-only and the sentence cannot be rewritten |
| **B2** | **DNA-literal rule in `tools/check_coordinates.py`** | Declared in the plan as owned by this step. The gate stops patient *positions*; nothing stops patient *sequence*. Step 2 is the first step that produces 31-mers | **done** — rule 4, ≥ 25 `[ACGTN]`. It found eleven sequences already committed; ten synthetic, and the eleventh (the store's probe k-mer, in four docs) allowlisted only after a genome pass proved it reference-identical |
| **B3** | **The scoring join can only rediscover what the vendor already reported** | `it2_scored_pairs` joins `warehouse.coding_annotations`, built from the delivered VCF. Read-derived alleles with no annotation row were uncounted — exactly the class a second, independent caller exists to find. Plan stage 11 said to annotate them; it never ran | **done, and it flipped H020** — 1,199 alleles annotated into `warehouse.it2_read_annotations`; targets and decoys come out exactly equal ([090](../methodology/090-the-alleles-the-vendor-never-reported.md)) |
| **B4** | Blind gate is not one of the quality gates | It went red without failing anything. `tools/check-python.sh` must run it | **done** — `tools/check_blind.py` is the filesystem half, runs with no database, and is now a gate CI runs. The register half still needs the warehouse and stays in `mva-science check` |
| **B5** | **Stage 4 scaling test never ran** (10³–10⁷ patterns) | Pre-registered gate with a numeric threshold. Skipping a gate and reporting the step complete is the same error the off-target gate was handled correctly against | **done, and reported as late** — 45.9 min projected against a 60 min gate; a 36,000× larger bait costs 1.05× per read. It cannot license a pass that already happened and [089](../methodology/089-the-instruments-and-the-gate-that-was-skipped.md) says so |
| **B6** | Step README claims `complete`, lists built modules under "still to build", and duplicates the H017/H018 rows | A status line that is wrong is worse than none | **done** — rewritten, with the audit named in its standing line |
| **B7** | Dictionary: 11 of 15 step-2 terms absent | CLAUDE.md makes this mandatory per new term, and `/learn` is the reader's only route into the vocabulary | **done** — dictionary section 18, fifteen terms in dependency order with their own funnel diagram. Adding *reverse complement* gave an existing `/probes` explainer chip a definition to link to, which the link test caught |
| **B8** | `/steps/step-2` deep page + fixture capture + hash re-bless | The dashboard is the declared single source of truth; figures alone render on `/steps`, the deep page does not exist | **done** — `GET /api/steps/step-2` (aggregates only; a test reads the SQL and fails a block that selects a position) and `/steps/step-2`, with fixtures captured and hashes re-blessed |

---

## C — improvements the step surfaced, for the plan's global context

These change how **later** steps must be written. They are findings, not chores.

| | Finding | What it changes |
|---|---|---|
| C1 | **Without a rarity + consequence filter the decoys beat the targets** (57.3 % vs 50.8 %); with it the ordering inverts (1.69 % vs 0.51 %) | Every later step quoting a target-vs-decoy rate must say which version. The discriminating power is in the filter, not the gene list — so step 6 must weight the *filter*, not the symptom-derived list |
| C2 | **H020 is refuted.** With every read-derived allele scored, targets and decoys are exactly equal at 10/396 (p = 0.589); on the pre-registered reachable-gene view the decoys are marginally ahead | The earlier `supported` at 4/396 vs 2/396 was not a judgement call that aged badly — it was computed on an input the plan had said to complete and nobody did. The consequence was pre-registered: **the read route enters the step-6 fusion at reduced weight.** Step 4's genome-wide null is now the only route to a discriminating target set |
| C7 | **`analysis.json` had no producing script.** The figures were correct and irreproducible | A diagram commits its source; an untracked file assembled at a prompt is not one. `tools/export_it2_step2_analysis.py` is now that source, and the H020 caption is computed from the table rather than typed beside it |
| C8 | **The kernel's cost is set by bytes of sequence, not by bait size** — 1.05× per read across 36,000× of bait | `mva.kmer` transfers to any target set at any size without a new cost estimate. It is the step's innovation claim, now with a curve behind it |
| C9 | Twenty genes survive the filter, ten targets and ten decoys; the top of the table by its own sort key is a **decoy** | The read route alone does not rank a causal gene first. Exactly one of the twenty carries a ClinVar pathogenic assertion, and that flag comes from a public catalogue, not from the reads — which is the honest measure of what step 2 achieved on its own |
| C3 | A baited alignment is islands of coverage; read-pair callers read the gaps as megabase events | `MIN_BAITED_SPAN` and `MIN_SV_LENGTH` are permanent properties of any baited SV call, not step-2 fixes. Step 3's copy-number work inherits them |
| C4 | The off-target gate is **unreachable at any available parameter** (8.38 %–10.25 % across padding and k) | The `< 5 %` threshold was set without measuring the surface. A later step that reuses a bait must set its gate from [086](../methodology/086-can-the-off-target-gate-be-reached.md), not from the plan |
| C5 | The target set is an enrichment at recall ≈ 0.36 | Already inherited from step 1; restated because step 2's *absence* results are not exclusions |
| C6 | Contig spelling silently returned zero rows once | `check_contigs()` now refuses a mixed load. Any new table joining the callset must pass through it |
