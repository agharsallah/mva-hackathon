# 155 — Do iteration 4's four independent drug generators agree beyond chance, and what survives the checks?

**Step:** iteration 4, [step 10](../README.md), experiment S2. **Date:** 2026-09-25.
**Claims:** H094 (`P4-29`), H095 (`P4-30`). **Sources: both.**

- **Genome.** The BUB1B gene drives the walk (G1), the PRISM contrasts (G3) and the LINCS signature (G4). K2's genome half reads the child's callset through PharmCAT phenotypes (entry 152, reused and not re-run). It writes actionability words only.
- **Clinical.** The 8 HPO terms chose the phenotype-twin mice behind G2 (entry 150). K2's phenotype half matches drug labels against the child's own terms.
- **No position, allele or patient sequence appears in any output.**

## Question

Each of four generators (independent sources that *propose* drugs by a rule fixed in advance) produced a list:

- **G1 walk:** PrimeKG knowledge-graph walk.
- **G2 twin:** the phenotype twin's published mouse interventions.
- **G3 prism:** PRISM cell-line screen sweep.
- **G4 lincs:** LINCS expression-signature reversal.

Two questions:

1. Do the lists name the same approved drugs more often than lists of the same sizes drawn at random from the same drug pools would?
2. Does any drug they share pass all three iteration-4 checks: direction, the child's own safety, and a contrary screen?

## Hypothesis and prediction

Registered before this entry (`uv run mva-science show H094`, `... H095`):

> **P4-29 (H094):** iteration 4's independent drug generators converge on the same approved drugs
> more often than chance. **Prediction.** Four generator lists, each fixed by a rule before the
> join […]. Drugs are joined on one normalised name. The count of approved drugs named by 2 or
> more generators exceeds the 95th percentile of a 10,000-draw null that replaces each list with
> an equal-sized random draw from that generator's own approved universe (one-sided p < 0.05).
> Retrospective note, stated before the join: entry 151 already placed dasatinib at the 99.4th
> percentile […] and entry 150 already names it as the twin's approved analogue, so the report
> gives the count with and without dasatinib.

> **P4-30 (H095):** at least one converging approved drug survives every iteration-4 check for
> this child. **Prediction.** At least one drug named by 2 or more generators (P4-29) passes all
> three checks: (a) not in an iteration-4 do-not class (checkpoint-kinase inhibitors, Mps1/TTK and
> Aurora […]; spindle poisons carried as a caution, not an exclusion); (b) not flagged by both
> safety sources for this child when entry 152's method is re-run on the iteration-4 candidate
> set; (c) where PRISM measures it, its effect does not point against the direction it is
> proposed for (Cliff's delta below 0 with one-sided p < 0.05 in the opposite direction).

**Choices the claims leave open.** These were fixed in code (`src/mva/drugs/convergence*.py`, `checks*.py`) and proven on a G1+G2 dry run (`build/it4/track2-s2/dry/`) **before G3 and G4 existed**.

The two sensitivity scenarios were declared in the same command as the primary run. The three generator lists (G2, G3, G4) had been read before that command. No convergence count had been computed on them.

| choice | fixed value | why |
|---|---|---|
| **universe** | every drug a generator *could* have proposed; the null draws from it | README rule |
| G1 list | first **50** distinct join keys with an openFDA label, in walk-score order | README rule. `ranking-walk.tsv` (entry 142) stopped at 100 labelled drugs out of 745 reached, so it cannot give a universe |
| G1 universe | **every** drug the walk reached, re-walked with entry 142's code and parameters unchanged, each base name checked against openFDA | the first 100 labelled drugs came out identical to entry 142 in name and score (manifest field `reproduces_entry_142`) |
| G2 list | rows whose `supports_direction` **starts with** `supports`. A drug is approved when the row's own `analogue_status` calls it approved (`approved_analogues`) | README rule, read literally. `hypothesis only` (the rapalog row) does not vote |
| G2 universe | approved analogues named by any row, ∪ the G1, G3 and G4 universes | README rule |
| join key | `mva.drugs.names.base_name` (the salt-stripped upper-case name). G3 folded PRISM's hyphens to spaces first (its manifest) | README rule |
| null | each list redrawn to its own size without replacement from its own universe, 10,000 draws, numpy `default_rng`, **seed 20260925**; p = (1 + #null ≥ observed) / (1 + draws) | H094. The +1 keeps p above 0 |
| exclusion | dasatinib removed from every list **and** every universe | H094's retrospective note |
| K1 | **fail** when the Drug Repurposing Hub MOA (Broad's curated mechanism-of-action label, as shipped in PRISM 24Q2's compound list, falling back to 20Q2 treatment info) contains `MONOPOLAR SPINDLE 1 KINASE INHIBITOR`, `AURORA KINASE INHIBITOR`, `TTK INHIBITOR` or `MPS1 INHIBITOR`. **Caution** for a tubulin or microtubule MOA (spindle poison), for no Hub annotation, or for annotated targets that include TTK/AURKA/AURKB/AURKC without the MOA naming the class | entry 151 defined the class by exactly these MOA strings |
| K2 | `tools/patient_safety.py labels`, `faers` and `table`, unchanged. Entry 152's aliases and `--extra-gene` pairs are kept, and its `pgx_summary.json` is copied and not re-run. **Fail only if both sources flag**; one source flagging is a caution | entry 152 |
| K2 query name | the join key or a generator's label, whichever OnSIDES v3.1.1 lists as an RxNorm ingredient (RxNorm = the US drug-name vocabulary). Otherwise the first generator's label | `PYRIDOXAL` (the join key) is not an ingredient name; `pyridoxal phosphate` is |
| K2 FAERS pairs | each **converging** drug × the 16 MedDRA preferred terms with `used_for_flag = yes` in `hpo_to_adverse_terms.tsv`. Informational: FAERS (the FDA adverse-event report database) is never part of the flag | chosen by rule, not by hand |
| K3 | from `prism_sweep.tsv`, `representative == true` rows only. The direction maps to the contrast it is proposed on: **D2 → aneuploidy, D4 → rms**; D3, D5 and `none` → not applicable. **Fail** when δ < 0 and the one-sided p in the opposite direction < 0.05 | H095 (c) |
| survivor | named by ≥ 2 generators, **and** no K1/K2/K3 `fail`. A caution travels with the drug and never removes it | H095 |
| sensitivity | (i) without G4, because E3's registered positive control failed and H092 is uninterpretable (entry 153). The G2 universe is rebuilt from G1 and G3 only. (ii) without G4 and without dasatinib. (iii)–(iv) G2's universe = its own 4 approved analogues only, with and without G4 | (i)–(ii) requested by the coordinator. (iii)–(iv) test the README's parenthesis that the widest twin universe "makes the null harder to beat" |

## What would refute it

As registered:

- **H094** is refuted if no drug is named by ≥ 2 generators, or if the observed count is **at or below** the null's 95th percentile.
- **H095** is refuted if every converging drug fails at least one check, or if no drug converges.

Only the primary four-generator test feeds H094's verdict. Sensitivity runs are reported and never used as verdict inputs.

## Inputs

| input | release / version | sha256 (first 16) | rows | licence |
|---|---|---|---|---|
| `ressources/track2/it4/generators/walk.tsv` / `.universe.tsv` (G1, this entry) | PrimeKG 2.1 (`build/primekg/kg.parquet` `7a0df2feece6aeac`), openFDA label API (cached; roll-up digest in the manifest) | `30463e73c775904c` / `0b93d93e83c84a35` | 50 / 738 | CC0-1.0; openFDA public |
| `.../twin.tsv` / `.universe.tsv` (G2, this entry) | `ressources/track2/model_interventions.tsv` `df0a98864f99c2f1` (entry 150) | `e86418b6a4d206a2` / `6eed04aee37cdcb2` | 2 / 1,498 | literature table, PMIDs cited |
| `.../prism.tsv` / `.universe.tsv` (G3) | entry 154 | `f45750b805225350` / `293171e171d08375` | 8 / 613 | CC BY 4.0 |
| `.../lincs.tsv` / `.universe.tsv` (G4) | entry 153 | `6e5088044f7336e5` / `ccae3933bdf3af1d` | 3 / 1,157 | per entry 153 |
| `ressources/track2/it4/prism_sweep.tsv` (K3) | entry 154 | `7749f9f129bd52eb` | 1,266 | CC BY 4.0 |
| `PRISM_24Q2_Extended_Primary_Compound_List.csv`, `PRISM_20Q2_secondary_treatment_info.csv` (K1) | PRISM 24Q2 / 20Q2 | `7e78f5901c1a97d2` / `f0ec000acda7c1a0` | 6,790 / 15,014 | CC BY 4.0 |
| `build/it4/track2-e56/pgx_summary.json` (K2 genome) | PharmCAT 3.4.0, entry 152 | `581c9c4ca8aae9e2` | 171 drug→gene pairs | — (patient-derived, gitignored) |
| OnSIDES `csv/` (K2 phenotype) | v3.1.1 | per entry 152 | — | CC BY 4.0 |
| `ressources/track2/hpo_to_adverse_terms.tsv` | entry 152 | `3313fd4506cd9ff8` | 19 | — |

Code:

- `src/mva/drugs/convergence{,_tables,_generators,_build,_candidates,_run}.py` and `checks{,_safety,_sources}.py`.
- `tools/converge.py`, `tools/render_step10_s2.py`, `tests/test_convergence.py` (22 tests).
- The code version at build time is in each manifest (`77ea199` for the run).

## Commands

```bash
uv run python tools/converge.py walk                        # G1: re-walk, label all 745, top 50 (1 min 17 s)
G=ressources/track2/it4/generators; B=build/it4/track2-s2/universes
uv run python tools/converge.py twin --other-universe $G/walk.universe.tsv \
  --other-universe $G/prism.universe.tsv --other-universe $G/lincs.universe.tsv   # G2
uv run python tools/converge.py twin --out-dir $B/twin-no-lincs \
  --other-universe $G/walk.universe.tsv --other-universe $G/prism.universe.tsv     # for (i)-(ii)
uv run python tools/converge.py twin --out-dir $B/twin-own                          # for (iii)-(iv)
uv run python tools/converge.py run --generator walk --generator twin --generator prism \
  --generator lincs --exclude DASATINIB \
  --sweep ressources/track2/it4/prism_sweep.tsv --sweep-p-opposite p_opposite --sweep-only representative \
  --contrast D2=aneuploidy --contrast D4=rms \
  --scenario "without lincs (G4 positive control failed);gens=walk,twin,prism;swap=twin:$B/twin-no-lincs/twin.universe.tsv" \
  --scenario "without lincs and DASATINIB;gens=walk,twin,prism;exclude=DASATINIB;swap=twin:$B/twin-no-lincs/twin.universe.tsv" \
  --scenario "twin universe = its own analogues only;gens=walk,twin,prism,lincs;swap=twin:$B/twin-own/twin.universe.tsv;role=sensitivity: universe rule (not a verdict input)" \
  --scenario "twin own universe, without lincs;gens=walk,twin,prism;swap=twin:$B/twin-own/twin.universe.tsv;role=sensitivity: universe rule (not a verdict input)"
uv run python tools/render_step10_s2.py
uv run pytest -q tests/test_convergence.py tests/test_patient_safety.py
```

- The run takes 27 s wall, of which K2 is most (OnSIDES in DuckDB plus 16 FAERS queries).
- Cost: $0. No GPU. No patient data leaves the laptop.
- Log: `build/it4/track2-s2/run.log`. Summary: `build/it4/track2-s2/convergence.json`.

## Observed output

### 1. The generators

| generator | listed (approved) | universe (approved) | approval proxy | direction hints |
|---|---|---|---|---|
| G1 walk | 50 | 188 of 738 reached join keys; 1 openFDA query refused (a systematic chemical name, counted not approved) | openFDA label; 15 of the 50 are labels with no application number (supplements, combination products) | none |
| G2 twin | 2: dasatinib (2 supporting rows, D5), niacin (1 row, D3); 9 rows do not vote | 1,498 | the row's `analogue_status` | D5, D3 |
| G3 prism | 8 | 613 | PRISM Launched | D2 ×4, D4 ×4 |
| G4 lincs | 3: phenytoin, albendazole, tofacitinib | 1,157 | ChEMBL max phase 4 | none |

Shared drugs by pair:

- twin ∩ prism = **1**, which is dasatinib.
- Every other pair (walk–twin, walk–prism, walk–lincs, twin–lincs, prism–lincs) shares **0**.

![S2 UpSet](../../../../figures/it4/step10-s2-upset.svg)

> **Legend** — green bar = a combination of ≥ 2 generators (a converging drug), labelled with its
> drug; blue bar = one generator alone; dark dot = the generator is in the combination, grey dot
> = it is not; (n) = drugs the generator lists.

### 2. Convergence against the null (seed 20260925, 10,000 draws each)

| test | role | observed | converging | null mean | null p95 | draws ≥ observed | p |
|---|---|---|---|---|---|---|---|
| all four generators | **primary (verdict input)** | **1** | dasatinib | 0.30 | **1.0** | 2,632 | **0.263** |
| without dasatinib | registered sensitivity | 0 | — | 0.25 | 1.0 | 10,000 | 1 |
| without G4 | sensitivity | 1 | dasatinib | 0.29 | 1.0 | 2,608 | 0.261 |
| without G4 and dasatinib | sensitivity | 0 | — | 0.20 | 1.0 | 10,000 | 1 |
| G2 universe = its 4 own analogues | sensitivity (universe rule) | 1 | dasatinib | 0.38 | 1.0 | 3,289 | 0.329 |
| G2 own universe, without G4 | sensitivity (universe rule) | 1 | dasatinib | 0.29 | 1.0 | 2,577 | 0.258 |

- Primary null histogram (count: draws): 0: 7,368 · 1: 2,275 · 2: 337 · 3: 18 · 4: 2.
- One agreement is what chance gives about a quarter of the time. It needs ≥ 2 to clear the 95th percentile.
- **The README's parenthesis is backwards.** Narrowing G2's universe to its own 4 analogues *raises* the null mean (0.30 → 0.38) and p (0.263 → 0.329). The widest twin universe therefore makes the null **easier** to beat, not harder. That does not change any verdict here.

![S2 null](../../../../figures/it4/step10-s2-null.svg)

> **Legend** — blue bars = the null distribution; yellow bars = null counts above its 95th
> percentile (the pre-registered bar the observed count had to reach); solid line = the observed
> count, green when it clears the bar, red when it does not; only the first panel is a verdict
> input.

### 3. The checks, over all 62 drugs named by any generator

| check | pass | caution | fail |
|---|---|---|---|
| K1 direction | 32 | 30 (27 no Hub MOA, 3 spindle poisons: albendazole, cabazitaxel, vincristine) | **0** (no Mps1/TTK or Aurora inhibitor in any list) |
| K2 safety | 51 (21 of them only because OnSIDES holds no label; 22 of 62 drugs have none) | 10 (4 genome, 6 phenotype) | **1** — vincristine (walk #13): CYP3A5 poor metaboliser, CEP72 extra gene, and its one label names `Muscle atrophy`, the child's own term. Same result as entry 152 |
| K3 contrary screen | 62 (54 not applicable: no D2/D4 hint; 8 measured, all G3-listed drugs incl. dasatinib) | — | **0** |

K2's phenotype base rate on this set:

- 12 of 40 labelled candidates (0.30, CI 0.18–0.45) carry a mapped effect.
- In the breadth-matched comparison set, 45 of 200 (0.225, CI 0.17–0.29) do.
- The intervals overlap. Entry 152's shortlist (0.60) did not overlap its comparison set.

### 4. The survivor: dasatinib

| check | result | numbers |
|---|---|---|
| convergence | twin #1 (D5, PMIDs 18516091, 22048312) and prism #8 (D2, aneuploidy contrast) | — |
| K1 | pass | Hub MOA: BCR-ABL, ephrin, KIT, PDGFR, SRC, tyrosine-kinase inhibitor; not a checkpoint kinase or spindle drug |
| K2 | pass: *unflagged by these two sources (not evidence of safety)* | genome: no pharmacogene tied to dasatinib (no CPIC guideline). Phenotype: 5 of 34 labels name `Rhabdomyolysis` or `Weight decreased` (rate 0.15, below the comparison 0.225; no exact term) |
| FAERS paediatric (informational) | `GROWTH RETARDATION` 15 reports, `MALNUTRITION` 2, `NEPHROLITHIASIS` 1, `RHABDOMYOLYSIS` 1; the other 12 terms 0 | report counts, never rates |
| K3 | pass | aneuploidy δ +0.135 (CI 0.024–0.243), 238 vs 176 lines, one-sided p 0.0096, p opposite 0.990 |
| context, not a check | its RMS contrast is δ −0.388 on 3 lines, p opposite 0.131 | D4 is not its direction. Even if mapped, it would not fail K3 (0.131 ≥ 0.05) |

![S2 checks](../../../../figures/it4/step10-s2-checks.svg)

> **Legend** — generator columns: blue = the generator names the drug (#rank within it); K
> columns: green = pass, yellow = caution (kept, reason in the table), red = fail, grey = not
> run; survivor: green = converges and fails no check, red = does not. Rows: the converging drug,
> then each generator's top 10 (22 of 62 drugs; all 62 below and in `candidates.tsv`).

### 5. Per-candidate table: every drug in any generator list

K1 caution words:

- **no Hub MOA:** the Repurposing Hub does not annotate the drug.
- **spindle poison:** a tubulin or microtubule MOA.

K2 words:

- **genome / phenotype / both sources:** which source flagged.
- **no OnSIDES label:** unflagged only because OnSIDES is silent.

K3 `n/a` means no direction hint maps to a PRISM contrast.

| drug | generators (rank) | direction hint | K1 direction | K2 safety | K3 screen | survivor |
|---|---|---|---|---|---|---|
| Dasatinib | twin #1, prism #8 | D2, D5 | pass | pass | pass (aneuploidy δ +0.135) | **yes** |
| Acyclovir | walk #45 | none | pass | pass | n/a | no |
| Adenosine | walk #26 | none | pass | pass | n/a | no |
| Albendazole | lincs #2 | none | caution: spindle poison | caution (phenotype) | n/a | no |
| Aldesleukin | walk #36 | none | caution: no Hub MOA | pass | n/a | no |
| Basiliximab | walk #37 | none | caution: no Hub MOA | pass | n/a | no |
| Belinostat | walk #15 | none | pass | caution (genome) | n/a | no |
| Bleomycin | walk #40 | none | caution: no Hub MOA | pass | n/a | no |
| Brentuximab Vedotin | walk #8 | none | caution: no Hub MOA | caution (phenotype) | n/a | no |
| Cabazitaxel | walk #47 | none | caution: spindle poison | pass (no OnSIDES label) | n/a | no |
| Caffeine | walk #49 | none | pass | pass | n/a | no |
| Calcium | walk #39 | none | caution: no Hub MOA | pass (no OnSIDES label) | n/a | no |
| Cannabidiol | walk #6 | none | caution: no Hub MOA | caution (phenotype) | n/a | no |
| Carbamazepine | walk #29 | none | pass | caution (genome) | n/a | no |
| Cefpirome | prism #2 | D2 | pass | pass (no OnSIDES label) | pass (aneuploidy δ +0.188) | no |
| Citrulline | walk #43 | none | caution: no Hub MOA | pass (no OnSIDES label) | n/a | no |
| Cladribine | walk #32 | none | pass | pass | n/a | no |
| Copper | walk #5 | none | caution: no Hub MOA | pass | n/a | no |
| Cyclosporine | walk #9 | none | pass | pass | n/a | no |
| Delivert | prism #6 | D2 | pass | pass (no OnSIDES label) | pass (aneuploidy δ +0.142) | no |
| Denileukin Diftitox | walk #38 | none | caution: no Hub MOA | pass (no OnSIDES label) | n/a | no |
| Doxorubicin | walk #30 | none | pass | pass | n/a | no |
| Dronedarone | walk #22 | none | pass | pass | n/a | no |
| Fentiazac | prism #4 | D2 | pass | pass (no OnSIDES label) | pass (aneuploidy δ +0.143) | no |
| Fomepizole | prism #1 | D4 | pass | pass (no OnSIDES label) | pass (rms δ +0.925) | no |
| Fostamatinib | walk #1 | none | pass | pass | n/a | no |
| Glycine | walk #19 | none | caution: no Hub MOA | pass | n/a | no |
| Inositol Hexanicotinate | prism #5 | D4 | caution: no Hub MOA | pass (no OnSIDES label) | pass (rms δ +0.877) | no |
| Isoleucine | walk #27 | none | caution: no Hub MOA | pass | n/a | no |
| L-Glutamine | walk #7 | none | caution: no Hub MOA | pass (no OnSIDES label) | n/a | no |
| Lenalidomide | walk #25 | none | pass | caution (phenotype) | n/a | no |
| Levothyroxine | walk #16 | none | pass | pass | n/a | no |
| Liothyronine | walk #17 | none | pass | pass | n/a | no |
| Magnesium | walk #41 | none | caution: no Hub MOA | pass (no OnSIDES label) | n/a | no |
| Magnesium Carbonate | walk #42 | none | caution: no Hub MOA | pass | n/a | no |
| Mecasermin | walk #23 | none | caution: no Hub MOA | pass | n/a | no |
| Micafungin | walk #21 | none | pass | pass | n/a | no |
| NADH | walk #3 | none | caution: no Hub MOA | pass (no OnSIDES label) | n/a | no |
| Niacin | twin #2 | D3 | pass | pass | n/a | no |
| Perindopril | walk #33 | none | pass | pass | n/a | no |
| Phenytoin | lincs #1 | none | pass | caution (genome) | n/a | no |
| Pizotifen | prism #3 | D4 | pass | pass (no OnSIDES label) | pass (rms δ +0.915) | no |
| Podofilox | walk #48 | none | caution: no Hub MOA | pass | n/a | no |
| Pyridoxal | walk #4 | none | caution: no Hub MOA | pass (no OnSIDES label) | n/a | no |
| Pyruvic Acid | walk #46 | none | caution: no Hub MOA | pass (no OnSIDES label) | n/a | no |
| Quercetin | walk #20 | none | pass | pass (no OnSIDES label) | n/a | no |
| Romidepsin | walk #34 | none | pass | pass | n/a | no |
| Sacituzumab Govitecan | walk #50 | none | caution: no Hub MOA | caution (genome) | n/a | no |
| Serine | walk #28 | none | caution: no Hub MOA | pass | n/a | no |
| Sorafenib | walk #31 | none | pass | caution (phenotype) | n/a | no |
| Taurine | walk #24 | none | pass | pass | n/a | no |
| Tenecteplase | walk #44 | none | caution: no Hub MOA | pass | n/a | no |
| Terazosin | prism #7 | D4 | pass | pass | pass (rms δ +0.871) | no |
| Theophylline | walk #2 | none | pass | caution (phenotype) | n/a | no |
| Thyroid, Porcine | walk #18 | none | caution: no Hub MOA | pass (no OnSIDES label) | n/a | no |
| Tofacitinib | lincs #3 | none | pass | pass (no OnSIDES label) | n/a | no |
| Vincristine | walk #13 | none | caution: spindle poison | **fail** (both sources) | n/a | no |
| Vitamin A | walk #14 | none | caution: no Hub MOA | pass | n/a | no |
| Voclosporin | walk #10 | none | pass | pass | n/a | no |
| Vorinostat | walk #35 | none | pass | pass (no OnSIDES label) | n/a | no |
| Zinc | walk #11 | none | caution: no Hub MOA | pass (no OnSIDES label) | n/a | no |
| Zinc Sulfate, Unspecified Form | walk #12 | none | caution: no Hub MOA | pass (no OnSIDES label) | n/a | no |

## Verdict

**H094 (`P4-29`) — refuted as registered.**

- Evidence: one drug (dasatinib) is named by ≥ 2 generators. The null's 95th percentile is 1.0 and p = 0.263.
- Registered refutation met: "the observed count is at or below the null's 95th percentile".
- Without dasatinib (the registered retrospective check), no drug converges (p = 1).
- Every sensitivity agrees: without G4, without G4 and dasatinib, and G2's narrowest universe, with and without G4. Their p values run 0.258–1.
- The four generators behave as independent sources that do not agree.
- Proposed: **refuted**, confidence **0.15**. The weighing is a transparent heuristic, not a calibrated posterior.

**H095 (`P4-30`) — supported as registered, weakly.**

- Evidence: dasatinib is named by 2 generators and passes (a), (b) and (c).
  - (a) Its MOA is in no do-not class.
  - (b) Only one source even looked: dasatinib has no pharmacogene. OnSIDES labels do not flag it by rate or exact term.
  - (c) PRISM measures it the proposed way on aneuploidy: δ +0.135, p opposite 0.990.
- The prediction is met literally, but three limits weaken it:
  1. It "converges" only by count. H094 shows that count is what chance gives, so "converging" here means named twice, not agreement beyond chance.
  2. Both generators that name it were known to favour it before the join (H094's retrospective note). This is a retrospective observation, not a new prediction.
  3. K3 cannot fail a G3-listed drug on its own contrast, because G3 listed it for a positive δ on that contrast. For dasatinib, K3 re-reads G3's evidence.
- K2 "unflagged" means two sources are silent, not that dasatinib is safe for this child. Paediatric FAERS pairs it with `GROWTH RETARDATION` in 15 reports; the child's own terms include short stature and failure to thrive.
- Proposed: **supported (weak)**, confidence **0.40**. It stays below 0.5 because its evidence is retrospective and self-referential for K3.

## Limitations

- **Approval proxies differ** by generator: an openFDA label (G1; 15 of 50 are supplement or combination labels with no application number), the row's own words (G2), PRISM Launched (G3), ChEMBL phase 4 (G4). A drug approved by one proxy may be absent from another universe.
- **G4's positive control failed** (entry 153). Its 3 drugs match no other list, so dropping G4 changes nothing: p 0.261 without it.
- **G2 is 2 drugs from a hand-curated, abstract-level table** (entry 150). The `supports` rule is that table's own word, and the rapalogs (`hypothesis only`) do not vote.
- **The twin-universe rule** was chosen as "harder to beat", but the run shows it is easier (p 0.263 vs 0.329 with the narrow universe). The step README's rule stands as registered; the correction goes in its S2 paragraph.
- **K1 is annotation-bound.** 27 of 62 drugs have no Repurposing Hub MOA and are cautions, not passes. A missing annotation cannot place a drug in a do-not class.
- **K2's genome half** still sees 1.6 % of PharmCAT positions (entry 152). 22 of 62 drugs have no OnSIDES label, so for them K2 is silence, not a pass.
- **K3 is informative only for drugs from other generators carrying D2/D4 hints.** None exist in this run: all 8 measured drugs are G3's own.
- **Monte-Carlo error** on p = 0.263 with 10,000 draws is about ±0.004 (binomial standard error). The seed is fixed at 20260925; no other seed was run.

## Conclusion

- Iteration 4's four independent generators **do not agree beyond chance** (H094 refuted, p 0.263). Their only shared drug, dasatinib, was known before the join.
- **Dasatinib passes every iteration-4 check** (H095 met literally, weakly).
- It is the one drug iteration 4 can put forward on its own evidence, as a **hypothesis for the D5 (senolytic) and D2 (aneuploidy-stress) directions**:
  - the phenotype twin's senescent-cell papers;
  - a 99.5th-percentile aneuploidy rank with no corrected significance (entry 154);
  - no flag from either safety source.
- The report must say it was a **pre-known lead that survived**, not a discovery.
- Outputs:
  - `ressources/track2/it4/candidates.tsv`: 62 rows, every drug, its generators, ranks, hints, K1–K3, survivor.
  - `ressources/track2/it4/candidate_safety.tsv`: 62 rows, the entry-152 two-source table.
  - Both carry provenance manifests.
