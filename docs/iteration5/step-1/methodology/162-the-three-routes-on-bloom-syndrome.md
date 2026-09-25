# 162 — The three routes on Bloom syndrome: does the chain transfer by configuration alone?

**Step:** iteration 5, [step 1](../README.md), transfer check. **Date:** 2026-09-25.
**Claims:** none — exploratory, positive controls instead
([note](../../notes/exploratory-no-hypotheses.md)).
**Status:** the *declaration* sections below were written **before any transfer run started**
(2026-09-25T17:19:01Z, `build/it5/transfer/started.txt`). Results were appended after.

## Question

Track 2 is judged 15 % on scalability. Iteration 5 built three routes (R1 readthrough + allele
dosage, entry 158; R2 proliferation-corrected proteomics, entry 159; R3 quote-verified
literature mining, entry 160) and each claims to be *case-agnostic: parameterised by a card*.

The claim is cheap to make and easy to test: **run all three on a second disease and count what
had to be written.** Iteration 4 already did one transfer — its chain on Bloom syndrome (BLM)
needed a 378-line purpose-built driver (`tools/transfer_it4.py`, entry 156). The question here
is whether iteration 5's routes beat that, and by how much.

Second case: **Bloom syndrome / `BLM`** — the same disease iteration 4 used, so the two transfer
costs are comparable. Bloom syndrome is a good stress test for all three routes at once:

| route | why BLM is a real test, not a replay |
|---|---|
| R1 | Bloom syndrome is caused mostly by **premature-termination alleles** (German 2007, PMID 17407155: 54 of 64 registry mutations terminate translation early), and Toledano 2024 (PMID 39174735) **measured** several BLM PTCs — so the model's prediction can be checked against a real measurement, which the BUB1B case could not do. |
| R2 | `BLM` is in the Tirosh S-phase set: the proliferation-correction problem is *worse* for BLM than for BUB1B. Its own score set contains it. |
| R3 | Bloom patients are reported to be chemotherapy-sensitive, so the patient-exposure half of the route has real material — the same safety question, a different disease. |

## Declaration — R3 positive control (written before the first query ran)

Same discipline as entry 160: the corpus queries are built from the gene symbol, its aliases,
topic words and the disease phrase only. **No PMID, author or title is typed into any query.**
The control PMIDs below were resolved by a *separate* title lookup against Europe PMC (recorded
in `build/it5/transfer/r3/control_lookup.json`) purely so they could be named here in advance;
they are read only by the verify stage, to score retrieval and extraction after the fact.

**Part 1 — retrieval.** The topic/disease queries must return all three, unprompted:

| PMID | paper | why it must come back |
|---|---|---|
| 7585968 | Ellis 1995, *Cell* — "The Bloom's syndrome gene product is homologous to RecQ helicases" | the gene's identification; any `BLM` corpus that misses it is broken |
| 4140506 | Chaganti 1974, *PNAS* — "A manyfold increase in sister chromatid exchanges in Bloom's syndrome lymphocytes" | the diagnostic hallmark of the disease, and pre-dates the gene symbol, so only the **disease-phrase** query can find it |
| 17407155 | German 2007, *Hum Mutat* — Bloom's Syndrome Registry mutations | the allele spectrum this transfer's R1 allele is taken from |

**Part 2 — extraction.** The quote-verified table must hold at least one kept row per control
PMID stating that paper's known finding:

| PMID | required `effect_on` | required `direction` |
|---|---|---|
| 4140506 | `sce` | `increase` (loss of BLM raises sister-chromatid exchange) |
| 7585968 | `function` | `decrease` (chain-terminating mutations destroy the helicase) |
| 17407155 | `function` | `decrease` (the registry's alleles terminate translation early) |

Recall is reported n/3 for each part. Below 3/3 the transferred route is reported as
uninterpretable — exactly as entry 160 would be.

## Declaration — R2 positive control

The R2 control (HSP90 inhibition → HSPA1A induction in Mitchell 2023; bortezomib → HSPA1A and
nutlin → MDM2 in the ProTargetMiner deep sets) is a property of the **dataset**, not of the
target gene. It is therefore **reused unchanged and re-reported, not re-derived**: the same
`proteome_control.tsv` verdicts gate the BLM readout. Changing the target does not change
whether HSP70 rose under an HSP90 inhibitor. This is stated rather than silently assumed.

What *is* target-specific and must be re-derived for BLM: the proliferation fit itself (slope,
R², the correlation of BLM with the G2/M score) and every hit.

## Declaration — R1 external check

R1's own control (held-out benchmark panel, entry 158) is dataset-level and is re-run unchanged.
BLM adds an **external check the BUB1B case could not run**: Toledano 2024 measured BLM PTCs
directly. So for the modelled allele the run:

1. removes that PTC context **entirely** from the fit (`ReadthroughModel.without`),
2. predicts it from the remaining contexts only,
3. compares the prediction with the measurement that was held out.

A prediction is only meaningful if it lands near the measurement; the comparison is reported
whether it succeeds or fails.

<!-- results appended below after the runs -->

---

# Results (appended after the runs, 2026-09-25)

## Inputs

| input | identity | role |
|---|---|---|
| Toledano 2024, Supp. Table 3 | PMID 39174735, the file already cached for entry 158 | R1: 5,837 measured pathogenic PTCs × 8 compounds. Contains five `BLM` PTCs, one of which is the modelled allele |
| Ensembl REST + UniProt `P54132` | queried 2026-09-25 | R1: the `BLM` transcript model (ENST00000355112, 22 exons, 4,254 nt CDS, 1,417 aa) and its domain annotation |
| German 2007 | PMID 17407155 | R1/R3: the allele class (54 of 64 registry mutations terminate translation early) |
| Mitchell 2023 + ProTargetMiner (3 lines) + CCLE protein + Mathieson half-lives | the files already cached under `build/it5/r2/raw/` for entry 159 | R2: **no new download**. Only the target gene changed |
| Europe PMC | queried 2026-09-25 | R3: 8 queries → 3,022 papers → 3,675 cached texts (776 open-access full texts) |
| the child's 8 HPO terms | `ressources/hackathon-rules/Challenge_Clinical_Phenotype_1.md` | **not read by any transfer run.** The transfer case has no project patient; the `hpo_overlap` column says so in every row |

## Commands

```bash
# R1 — the case card is a flag; the allele comes from the card, not a callset
BLM=(--gene BLM --card mva.drugs.readthrough_case_blm --accession P54132 \
     --build build/it5/transfer/r1 --tables ressources/track2/it5/transfer/r1 \
     --measurements build/it5/r1/toledano_ptc.tsv)
uv run python tools/it5_readthrough.py facts   $BLM
uv run python tools/it5_readthrough.py predict $BLM
uv run python tools/it5_readthrough.py holdout $BLM     # the external check
uv run python tools/it5_readthrough.py dosage  $BLM

# R2 — no card at all: four flags
uv run python tools/it5_proteome.py run --target BLM --branch stop_allele \
  --out ressources/track2/it5/transfer/r2 --build build/it5/transfer/r2 \
  --genomic-source "none: BLM is the transfer case's gene, read from the published literature"
uv run python tools/it5_proteome.py candidates --out ressources/track2/it5/transfer/r2 \
  --build build/it5/transfer/r2

# R3 — a new card, the same driver
R3=(--card it5_litmine_params_blm --build build/it5/transfer/r3 \
    --out ressources/track2/it5/transfer/r3)
uv run python tools/it5_litmine.py corpus $R3
uv run python tools/it5_litmine.py screen $R3
uv run python build/it5/transfer/r3/extract_rows.py    # the reader's rows
uv run python tools/it5_litmine.py verify $R3
uv run python tools/it5_litmine.py translate $R3

# the measurement, and the figure
uv run python tools/it5_transfer_summary.py
uv run python tools/render_it5_s1.py
uv run python tools/check_module_size.py && uv run lint-imports && uv run python tools/check_coordinates.py

# the first case, re-run unchanged, to prove nothing moved
uv run python tools/it5_readthrough.py predict && uv run python tools/it5_readthrough.py dosage
uv run python tools/it5_proteome.py run && uv run python tools/it5_proteome.py candidates
uv run python tools/it5_litmine.py verify && uv run python tools/it5_litmine.py translate
uv run pytest -q tests/test_drugs_case_cards.py     # 8 passed
```

## Output — what the transfer cost

`ressources/track2/it5/transfer/transfer_summary.tsv` (and `transfer_diffstat.tsv` per file),
figure [`figures/it5/s1-transfer.svg`](../../../../figures/it5/s1-transfer.svg). Line counts
are measured with `git diff --numstat` against `HEAD`, not typed.

| route | new card | config lines | shared files changed | code +/− | portability **+ refactor** | new capability | moved code | wall clock |
|---|---|---|---|---|---|---|---|---|
| R1 readthrough + dosage | 2 files | 311 | 4 | +330 / −135 | 196 | 134 | 119 | 6.1 s |
| R2 proteomics | **none** | **0** | 1 | +47 / −59 | 47 | 0 | 54 | 12.5 s |
| R3 literature mining | 1 file | 276 | 4 | +114 / −41 | 114 | 0 | 0 | 738 s (702 s network) |
| **total** | 3 files | **587** | 9 | **+491 / −235** | **357** | 134 | 173 | ~12.6 min |

**Two numbers for the same thing, and why.** The parameterisation itself was
**112 / 45 / 114 = 271 lines** — that is what `tools/it5_transfer_summary.py` reported when it
was first run, before anything else was touched. Afterwards the repo's own 400-line
module-size gate rejected three drivers that the change had grown, so code was lifted into
`readthrough_facts.py`, `readthrough_external.py`, `proteome_baseline.py`,
`readthrough_dataset.py` and `it5_transfer_plan.py`. That churn (moved code, and the driver
diff that moving it produces) is why the final column reads 357. **271 is the portability cost;
357 is the whole diff.** The table's `moved_lines` and `new_capability_lines_added` columns
separate what can be separated mechanically; the rest is stated here rather than hidden.

**The yardstick.** Iteration 4's transfer of its chain to the same disease needed a **378-line
purpose-built driver** (`tools/transfer_it4.py`, entry 156) *plus* a relabelling pass with 24
substitution rules. Iteration 5's three routes needed **587 lines of case card** — configuration
a reader can argue with, in files that contain no logic — and **271 lines of shared-code
parameterisation**, every one of which turned a constant into a parameter and is now paid once
for every future case.
R2 needed no card at all: `--target BLM` and three path flags.

**What the code changes actually were** (each a constant that had been hiding in the machinery):

| file | what was hard-coded | what it is now |
|---|---|---|
| `src/mva/drugs/litmine_verify.py` | the `effect_on` vocabulary (`bubr1_level`, `acetylation`, …) | `intervention_enums(card.EFFECT_ON)` |
| `src/mva/drugs/litmine_translate.py` | the rubric's directness scale, keyed on `bubr1_level` | a `directness` parameter, defaulting to the first case |
| `tools/it5_litmine.py` | the card imported by name; `BUILD`/`OUT` constants | `--card`, `--build`, `--out` |
| `tools/it5_proteome.py` | `TARGET = "BUB1B"`, the branch string, both directories | `--target`, `--branch`, `--out`, `--build` |
| `tools/it5_readthrough.py` | the card module; the allele read from the patient callset; both directories | `--card`, the card's `ALLELE`, `--build`, `--tables` |
| `src/mva/drugs/readthrough_manifests.py` | the manifest prose (`readthrough_notes`, BubR1 wording) | a `case_notes` parameter |

New modules created by the change, each named in `tools/it5_transfer_plan.py` so the accounting
can be checked: `src/mva/drugs/readthrough_external.py` (the new capability, 97 lines),
`src/mva/drugs/readthrough_facts.py` and `src/mva/drugs/proteome_baseline.py` (existing code
moved out under the 400-line module gate, 173 lines), and `tools/it5_transfer_plan.py` +
`tools/it5_transfer_summary.py` + `tools/render_it5_s1.py` (the measurement itself, which is not
charged to any route).

**The first case did not move.** All nine of iteration 5's committed first-case tables (R1's
three, R2's three, R3's three) were re-run after the parameterisation and match the sha256 in
their own manifests — `first_case_outputs_identical = yes` for every route. Two examples, checked
by hand: `readthrough.tsv` `9483f717…`, `proteome_hits.tsv` `09b032f0…`, both unchanged.

## Positive control — per route

| route | control | result |
|---|---|---|
| R1 | the held-out benchmark panel, unchanged (it is a property of the *dataset*, not the gene) | **passed**: 3 of 8 compounds pass the panel; the untreated column fails, as designed |
| R1 extra | **external check** — the measured `BLM` PTC held out of the fit entirely, then predicted | **ran**: Spearman 0.70 across 9 compounds (p = 0.036), mean absolute error 0.41 pp — *and* up to 4× over-prediction for the two strongest compounds (see below) |
| R2 | the dataset-level gating control (HSP90 inhibition → HSPA1A; bortezomib → HSPA1A, nutlin → MDM2) | **reused unchanged and verified**: `proteome_control.tsv` for the BLM run is `diff`-identical to the BUB1B one. The primary dataset (Mitchell) is interpretable; 2 of 4 datasets pass |
| R3 | retrieval and extraction of three declared Bloom-syndrome papers | retrieval **3/3 passed**; extraction **0/3 FAILED** → the transferred R3 is **uninterpretable** |

### R1's external check, in full

`ressources/track2/it5/transfer/r1/readthrough_external_check.tsv`. The context `BLM_Q548X` was
removed from the model entirely (`ReadthroughModel.without`), then predicted from the other
~5,830 contexts.

| compound | predicted | measured | error |
|---|---|---|---|
| Gentamicin | 0.209 | 0.184 | +0.025 |
| FUr | 0.335 | 0.288 | +0.047 |
| Untreated (negative control) | 0.172 | 0.179 | −0.007 |
| CC90009 | 0.389 | 0.200 | +0.189 |
| G418 | 0.648 | 0.360 | +0.288 |
| DAP | 0.869 | 1.467 | **−0.598** |
| Clitocine | 1.773 | 1.113 | +0.660 |
| SRI | 1.190 | 0.298 | **+0.892** |
| SJ6986 | 1.223 | 0.281 | **+0.942** |

*All values are percent of the no-PTC reporter control.* The model orders the compounds roughly
right (ρ = 0.70) and its untreated baseline is almost exact, but it is **wrong by up to 4× on
the two compounds it ranks highest** — it predicts SJ6986 and SRI at ~1.2 % where this stop
actually gives ~0.28 %. That is the first time any of iteration 5's readthrough numbers has been
checked against a measurement of the same allele, and the answer is: good enough to rank, not
good enough to size an effect. Entry 158's conclusion for the child's stop allele is if anything
strengthened — the predicted readthrough was already far too small to matter, and the model's
error runs in the optimistic direction.

### R3's control failed, and why

Declared in advance: three famous Bloom-syndrome papers must be retrieved *and* must yield a
verified row stating their known finding.

- **Retrieval 3/3.** All three came back from the topic and disease queries, with no PMID,
  author or title anywhere in a query. The two 1970s papers were found only by the
  disease-phrase query, as expected — they pre-date the gene symbol.
- **Extraction 0/3.** None of the three papers contributed a single sentence to the reading
  pack: they were dropped by the **lexical screen**, which requires the subject, an effect *and*
  an intervention cue in one sentence.
- **The diagnosis is the declaration, not the code.** Chaganti 1974 and German 2007 report a
  *genotype–phenotype observation* ("people with this disease have 13× the sister-chromatid
  exchange"; "54 of 64 registry alleles terminate translation early"). Ellis 1995 is a
  gene-identification paper. **None of them is an intervention**, and R3 mines interventions.
  The control I wrote before the run asked the route for something it is built not to produce.
- **Consequence, applied.** `positive_control.passed = false` is written into the manifest and
  into `positive_control_passed` on all five candidate rows, automatically. The BLM candidate
  table is reported as **uninterpretable** and nothing in it is a lead. This is the same
  discipline entry 153 applied to itself.
- **What a corrected control would be** — stated as *post-hoc*, therefore not a validation:
  the BLM-cDNA complementation result (wild-type `BLM` restores the high-SCE phenotype of
  Bloom-syndrome cells, PMIDs 10521302, 11472631, 12034743) and the discovery of ML216 as a BLM
  helicase inhibitor (PMID 23352139). Both *were* recovered by this run — they are rows 1–7 of
  the verified table — so a control named after the fact would have passed. That is exactly why
  it does not count.

## Output — what the three transferred routes produced

**R1.** The modelled allele `BLM` c.1642C>T (p.Gln548*) stops translation in exon 6, 2,432 nt
upstream of the last exon–exon junction, so the message is **NMD-competent** by the 50–55 nt
rule; the truncation loses 61.4 % of the protein and **all three** annotated domains (helicase
ATP-binding, helicase C-terminal, HRDC). The dosage ladder for the homozygote:

| scenario | % of wild-type diploid BLM | nearest published genotype |
|---|---|---|
| wild type | 100.00 | wild type |
| heterozygous carrier | 50.00 | carrier — healthy, normal SCE (PMID 4140506) |
| Bloom syndrome, homozygous p.Gln548* | 0.00 | biallelic PTC — the syndrome |
| + SRI (best controlled prediction) | 0.06 | still the syndrome rung |
| + best agent + complete NMD blockade (not a dose) | 0.58 | still the syndrome rung |
| + a perfect readthrough agent (arithmetic ceiling) | 1.17 | still the syndrome rung |

The conclusion transfers with the method: **readthrough cannot reach the target**. For the
child's compound heterozygote the ceiling was small beside a missense allele that still makes
protein; for a homozygous stop there is nothing else, and the ceiling is 1.17 % against a 50 %
yardstick.

**R2.** `BLM` behaves like a cell-cycle protein, as expected (CCLE correlation with the G2/M
score r = 0.579, 99.0th percentile of 12,050 proteins), but **less strongly than `BUB1B`**
(r = 0.704, 99.7th percentile); the Mitchell regression on the proliferation score explains
R² = 0.69 of `BLM`'s movement against 0.85 for `BUB1B`. After correction, 21 perturbations are
hits, and five have an approved drug:

| drug | robust z | rank | log2 FC | breadth | note |
|---|---|---|---|---|---|
| talazoparib | 12.58 | 1 / 875 | +0.76 | 0.046 | PARP inhibitor; not broad, ≥ 25 % raise |
| vorinostat | 9.71 | 8 | +0.23 | 0.229 | HDAC inhibitor; broad |
| amsacrine | 9.69 | 9 | +0.43 | 0.112 | topoisomerase II poison; broad |
| mycophenolic acid | 6.83 | 12 | +0.45 | 0.198 | broad |
| bortezomib | 3.22 | 1 / 9 | +0.33 | — | deep sets, control-capped |

Talazoparib topping a `BLM` list is mechanistically coherent (PARP inhibition → replication
stress → more BLM), and it is **exactly the wrong drug for a Bloom-syndrome patient**: the
branch is `stop_allele`, and raising a protein that a premature stop prevents the cell from
making raises nothing. The two routes agree, from different data, that the amount-raising branch
is closed for a PTC genotype — the same shape as entry 158's conclusion for the child.
No new data was downloaded: the four cached matrices were re-read for the new target.

**R3 (uninterpretable — control failed).** 3,022 papers, 3,675 cached texts, 4,537 screened
intervention sentences in 1,116 papers, 522 exposure sentences in 202 of 1,320 disease papers.
The model wrote 14 intervention rows and 8 exposure rows; **all 22 passed the quote gate, 0
rejected**. Translation gave 5 candidate rows, every one carrying
`positive_control_passed = false`.

The **patient-exposure table** — the same-disease safety test — is the part worth reading, and
it says the same thing four independent times:

| report | what was given | what happened |
|---|---|---|
| PMID 1633647 | induction chemotherapy for B-cell lymphoma | tumour eradicated; "the bone marrow suppression was severe and persistent" |
| PMID 27966805 | standard chemotherapy, 11-year-old with B-cell lymphoma | "minimal therapeutic response and significant dose-limiting toxicity"; a rituximab-based regimen then succeeded |
| PMID 26774895 | chemotherapy for Burkitt lymphoma | "life-threatening side effects … may require modifications in standard treatment such as dose reduction, which can compromise the tumor prognosis" |
| PMID 21590238 | **half-dose** ALL regimen, no radiation, in a BS sibling | complete remission at 20 months, "free of treatment complications"; the paper also warns of "excessive chemosensitivity" |
| PMID 23443610 | proton beam therapy | "almost complete response for a radiosensitive patient with a deficiency of DNA repair" |

That is the identical shape the BUB1B/MVA exposure table found (entry 160): the disease's own
case reports say *reduce the dose or change the modality*, and they say it more consistently than
any model system does. One contrast is worth recording: growth hormone **worked** in a Bloom
case (PMID 426391, "good therapeutic results with the exogenous human growth hormone
administration"), where four independent MVA reports say it does not. Same clinical question,
opposite answer, both read by the same code from the same source.

## Conclusion

1. **All three routes transferred.** Three cards (587 lines) and 271 lines of shared-code
   parameterisation (357 counting the module-split churn the repo's own size gate forced),
   against iteration 4's 378-line one-off driver plus a relabelling pass —
   and unlike that driver, every line here is paid once and works for the *next* case too.
   R2 transferred with **no configuration file at all**.
2. **Code change was needed, and it is counted honestly.** "Configuration only" is **false**
   for all three routes as they stood: each had exactly one class of constant hiding in a shared
   module (the effect vocabulary, the target gene, the case card's name). Each is now a
   parameter, and the tests in `tests/test_drugs_case_cards.py` fail if one creeps back.
3. **Nothing about the child's case moved.** Nine committed tables, all byte-identical — checked
   twice: once after the parameterisation, and again after the module-size refactor.
4. **The transfer found a real bug in the first case's own conclusion-support, not just in the
   code**: R1's readthrough predictions are checkable, and when checked they are 4× optimistic
   for the best compounds. No first-case conclusion flips — the route already said readthrough
   is not the lever — but any future use of those numbers must carry this error bar.
5. **A control can fail because the control was wrong.** R3's extraction control failed 0/3
   because two of the three papers I declared are observations, not interventions. The route is
   reported as uninterpretable for BLM candidates, and the failure is left standing rather than
   replaced with a control chosen after seeing the answer.

## Limits

- **Line counts are a proxy for effort, not effort.** 134 of R1's 330 added lines are the new
  external-check stage, a capability the first case never had rather than a portability cost,
  and 173 lines across R1 and R2 are existing code moved to satisfy the 400-line module gate.
  Both splits are declared judgements (`new_capability_files`, `moved_files` in
  `tools/it5_transfer_plan.py`), not measurements, and the remaining
  `portability_and_refactor_lines` still contains the driver churn that moving code produces.
- **One case-shaped leak survives, and is not fixed here.** `readthrough_tables.write_dosage`
  hard-codes the allele labels `stop` and `missense` as column names. For the BLM homozygote
  both alleles are labelled `stop`, so `stop_allele_output_pct` reports *one* allele
  (0.029 where the total is 0.058) and `missense_allele_output_pct` is 0 throughout; the
  **totals are correct**, the per-allele columns are not. Fixing it would rename a column in the
  first case's committed table and break the byte-identity check this entry rests on, so it is
  recorded as a known defect for the next iteration instead.
- **`BLM` is an ambiguous symbol** — it is also the usual abbreviation for bleomycin. The
  corpus is visibly contaminated (a `BLM`-treated rat, filter-supported bilayer lipid membranes).
  Nothing in the query prevents that; the screen and the quote gate are what keep a wrong-sense
  sentence out of a row, and a reader is still the last filter. Precision was not measured.
- **The R3 reading is one model's reading of a screened subset.** 4,537 screened sentences were
  not all read; 14 intervention rows is a sample chosen for coverage of the effect vocabulary,
  not a census. A verified quote proves the sentence exists, not that the row reads it correctly.
- **R2's controls are dataset-level and were reused, not re-derived.** That is correct — whether
  HSP70 rose under an HSP90 inhibitor does not depend on which gene is being ranked — but it
  means R2's transfer carries **no gene-specific validation at all** for `BLM`.
- **R1's dosage thresholds for Bloom syndrome have two rungs** (healthy carrier at 50 %,
  syndrome at 0 %) because the disease has no published graded hypomorph series. Every treated
  scenario lands between rungs with nothing published in between. That is a limit of the
  disease's literature, not of the model.
- **Wall clock is not comparable across routes**: R1 and R2 ran entirely from warm caches; R3's
  702 s is network politeness (0.34 s between live full-text calls). The model's reading time —
  the real cost of R3 — is agent time and is not in the table.

## Both datasets

- **Genomic.** No patient genomic data was read by any transfer run. R1's allele is a published
  `BLM` variant taken from the literature (PMIDs 39174735, 17407155) and recorded in
  `ressources/track2/it5/transfer/r1/blm_allele_note.md`; the driver read it from the case card,
  not from `build/it4/records.parquet`. R2 read only a gene symbol. R3 read only public papers.
  `tools/check_coordinates.py` is clean.
- **Clinical.** The child's 8 HPO terms were deliberately **not** used: the transfer case has no
  project patient, and every exposure row says so in its `hpo_overlap` column
  (`not applicable (transfer case: no project patient, no HPO term read)`). Where the first case
  cross-references the terms — R3's exposure table asks "does this drug collide with *this*
  child's phenotype" — the transfer run answers the disease-level question only. The one place
  the two cases are compared clinically is the growth-hormone contrast above, and it compares
  two *published literatures*, not two patients.
