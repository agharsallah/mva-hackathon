# 151 — Do the Track 2 leads survive PRISM, a screen nobody curated for this case?

**Step:** iteration 4, [step 9](../README.md), experiment E4. **Date:** 2026-09-24. **Claims:**
H087 (`P4-22`), H088 (`P4-23`), H089 (`P4-24`). **Sources:** **one only — the genomic /
public-screen source.** This experiment reads no clinical (HPO) term. The clinical dataset
enters it indirectly and at one remove: HP:0002859 (rhabdomyosarcoma) is why the tumour-context
lineage of the contrast is rhabdomyosarcoma, a choice made in iteration 2 and inherited here.
No patient sequence, position or allele is used, and none can appear in any output.

## Question

The Track 2 report argues eleven drugs from curated literature and a knowledge graph. Both are
sources somebody wrote *about* this biology. Does any of it survive a large, mechanically
produced cell-line screen that was built for no case in particular — and, where it does not,
is that a negative result or merely no data?

## Hypothesis and prediction

Filed in the register before this entry:

| id | claim | prediction | refuted if |
|---|---|---|---|
| H087 `P4-22` | statins are RMS-selective in PRISM | RMS lines more sensitive than non-RMS to ≥ 1 approved statin, one-sided rank test p < 0.05, lineage-aware; most statins point the same way | no statin reaches p < 0.2, **or** most statins point the other way |
| H088 `P4-23` | chloroquine and the D2 stress drugs are more potent in high-aneuploidy lines | chloroquine p < 0.05 one-sided; most D2 drugs point the same way | chloroquine shows no trend at p < 0.2, **or** high-aneuploidy lines are *less* sensitive |
| H089 `P4-24` | the D5 drugs get an honestly reported contrast whichever way it points | a reported effect size, CI and p for dasatinib and an mTOR inhibitor in both contrasts | neither drug is in PRISM, and the entry says the screen cannot speak to D5 |

**Analysis plan, fixed before the first contrast ran** — written into the module docstring of
[`tools/screen_replication.py`](../../../../tools/screen_replication.py) at the top of the run,
which is the timestamped copy:

| choice | fixed value | why |
|---|---|---|
| primary metric | PRISM Repurposing **24Q2 extended primary**, log fold change of barcode abundance, 5 d at 2.5 µM; lower = more sensitive | the largest compound × line matrix with an approved-drug annotation |
| sensitivity metric | PRISM **20Q2 secondary** dose-response **AUC** | a different release *and* a different readout; if the conclusion flips, say so |
| in-group, contrast A | DepMap 24Q4 `Model.csv` `OncotreeCode` ∈ {RMS, ERMS, ARMS, PLRMS, SCRMS, SRMS} | the child's tumour context, by the screen's own annotation |
| in-group, contrast B | DepMap 24Q4 `OmicsSignatures.csv` `Aneuploidy` (arm-level event count), **strict median split** over screened lines carrying a score, lines exactly at the median dropped | it is an integer count with heavy ties; a `>=` split would put ~80 tied lines on one side |
| test | Mann-Whitney U, **one-sided** "the in-group is more sensitive" | the hypotheses are directional; a two-sided test would hide a refutation |
| effect size | Cliff's delta, computed from the same U so sign and p can never disagree; 95 % percentile bootstrap CI, 2,000 resamples, seed 20260924 | rank effect size, no distributional assumption |
| multiplicity | Benjamini-Hochberg **within each primary contrast**, family = the representative row of every candidate | declared before the run; sensitivity contrasts and controls are outside it and carry raw p only |
| minimum group | 3 lines on each side, else the row is `too-few-lines`, never a null result | a rank test on 2 observations is arithmetic, not evidence |
| candidate list | derived: `shortlist.tsv` rows with verdict `argue` (11) ∪ every PRISM compound annotated `HMGCR INHIBITOR` (the statin class, for "most statins") ∪ the D5 drugs named in `model_interventions.tsv` (dasatinib, quercetin, sirolimus, everolimus, temsirolimus) | never typed; the class comes from the screen's own MOA field |
| drug → screen join | normalised name **and** the release-independent BRD core id (`BRD:BRD-K09416995-001-39-9` → `BRD-K09416995`) | PRISM writes `VALPROIC-ACID`; batch suffixes differ between releases |
| duplicate compounds | every copy reported; the copy measured on most in-group lines is the `representative` and is the one in the BH family | reporting every copy is honest; correcting over copies would inflate the family |
| negative control | 200 seeded compounds marked `Launched` in 20Q2 whose MOA mentions none of HMGCR, proteasome, autophagy, lysosome, NAD, AMPK, mTOR, HDAC, Aurora, spindle, tubulin, kinesin, PLK, HSP90, antimalarial | a one-sided 0.05 test should fire on ~5 % of them; far more means the contrast, not the drug, makes the signal |
| positive control | RAF/MEK inhibitors (dabrafenib, vemurafenib, PLX-4720, selumetinib) vs skin/melanoma lines, same code path | BRAF V600E is mutated in about half of melanoma lines and two of these are licensed on that genotype; a lineage contrast that misses it is broken |
| literature direction check | every Mps1 and Aurora inhibitor, aneuploidy contrast. Cohen-Sharir 2021 (PMID 33505028) reports aneuploid lines are *less* sensitive to short-term SAC inhibition | not a positive control — `research/papers.md` records that no drug-level aneuploidy-selectivity result exists to replicate |
| confounders | (i) each line's median response over all compounds, RMS vs rest; (ii) RMS lines' aneuploidy scores vs the rest; (iii) within-line rank-normalised repeat of contrast A | (i) generic fragility, (ii) are the two contrasts independent, (iii) removes the line-level offset |

## What would refute it

As registered, plus one methodological stop: **if the positive control fails** (RAF inhibitors
not selective for melanoma lines) the pipeline is broken and no candidate row may be read.

## Inputs

Seven public files, all **CC BY 4.0**, fetched 2026-09-24 from the figshare mirrors verified in
[`research/data-sources.md` §1](../research/data-sources.md) (depmap.org itself answers scripts
with a Cloudflare challenge). Each carries its own `<name>.provenance.json` in
`build/it4/track2-e4/raw/` with URL, fetch date, bytes, sha256, licence and release label.

| file | release | bytes | sha256 (first 16) |
|---|---|---|---|
| `PRISM_24Q2_Extended_Primary_Data_Matrix.csv` | PRISM Repurposing 24Q2 | 72,456,953 | `3b6554cfc6c765af` |
| `PRISM_24Q2_Extended_Primary_Compound_List.csv` | PRISM Repurposing 24Q2 | 719,567 | `7e78f5901c1a97d2` |
| `PRISM_24Q2_Cell_Line_Meta_Data.csv` | PRISM Repurposing 24Q2 | 157,294 | `13a85da9e45656c4` |
| `Model_24Q4.csv` | DepMap 24Q4 | 645,696 | `b7a0c1385e6cef30` |
| `OmicsSignatures_24Q4.csv` | DepMap 24Q4 | 131,912 | `2eb6d83065db5b59` |
| `PRISM_20Q2_secondary_dose_response_curve_parameters.csv` | PRISM Repurposing 20Q2 secondary | 290,170,269 | `2ac69a21f1d681fe` |
| `PRISM_20Q2_secondary_treatment_info.csv` | PRISM Repurposing 20Q2 secondary | 4,284,816 | `f0ec000acda7c1a0` |

Repository inputs (digests in the output manifest): `ressources/track2/shortlist.tsv`,
`ressources/track2/model_interventions.tsv` (E2, entry 150).

Code: `src/mva/drugs/screen_replication{,_prism,_report,_plan,_run}.py`,
`tools/screen_replication.py`, `tools/render_step9_e4.py`. scipy 1.18.1, numpy 2.5.2,
polars 1.44.1 (exact versions in the output manifest's `software` block).

## Commands

```bash
uv run python tools/screen_replication.py fetch     # ~365 MB, one manifest per file
uv run python tools/screen_replication.py run       # 97 s, laptop CPU, no GPU
uv run python tools/render_step9_e4.py
uv run pytest -q tests/test_screen_replication.py
```

Outputs: [`ressources/track2/prism_replication.tsv`](../../../../ressources/track2/prism_replication.tsv)
(182 rows) + `.provenance.json`; `build/it4/track2-e4/{controls.json,coverage.tsv,background-*.parquet}`;
`figures/it4/step9-e4-{effects,background,coverage}.svg`.

## Observed output

### 0. The pipeline works, and it is calibrated

| control | result | reading |
|---|---|---|
| positive: dabrafenib, melanoma lines | δ = **+0.670** [0.496, 0.814], n 39/492, p = 1.6 × 10⁻¹² | the contrast finds a real lineage dependency |
| positive: vemurafenib / PLX-4720 / selumetinib | δ +0.595 / +0.539 / +0.575, p 4.4 × 10⁻¹¹ / 2.1 × 10⁻⁹ / 1.8 × 10⁻¹⁰ | all four, same direction |
| negative band, RMS contrast | 76 of 200 control drugs were testable; **5.3 %** reach raw p < 0.05; central 95 % of δ spans **−0.73 to +0.67** | exactly the nominal rate — and the band is enormous, because most control drugs have only 2–3 RMS lines |
| negative band, aneuploidy contrast | 200 of 200 testable; **3.0 %** at p < 0.05; δ band −0.155 to +0.096 | conservative; the aneuploidy contrast is well powered and tight |

### 1. Coverage is the binding constraint, and it is a result

All **24 of 24** candidates are present in the 24Q2 primary matrix; **none is absent**. But
PRISM's primary matrix is three sub-screens with different line panels:

| sub-screen | compounds | mean lines per compound | mean **RMS** lines per compound |
|---|---|---|---|
| REP.PRIMARY | 5,271 | 543.6 | **2.29** |
| REP.1M | 1,277 | 890.2 | 14.0 |
| REP.300 | 241 | 872.1 | 14.0 |

14 RMS lines are in the matrix (TE617T, RD, KYM1, RH30, CW9019, JR, SCMCRM2, SMSCTR, RH28,
RHJT, TTC442, RH36, RH4, RMSYM — every one paediatric, ages 0–17). **10 of the 24 candidates
sit only in REP.PRIMARY and are measured on 2 RMS lines, below the 3-line floor**: lovastatin,
pravastatin, mevastatin, nicotinamide, valproic acid, vorinostat, hydroxychloroquine,
everolimus, temsirolimus, procaine. Five are measured on all 14: atorvastatin, rosuvastatin,
pitavastatin, and the two non-statin HMGCR-MOA compounds meglutol and alpha-asarone. Eleven
candidates are absent from the 20Q2 secondary release (including chloroquine, metformin,
nicotinamide, valproic acid, rosuvastatin).

**Lovastatin — the report's rank-1 lead — cannot be tested in the RMS contrast at all.**

### 2. H087, statins vs rhabdomyosarcoma

Primary contrast (24Q2 LFC), representative rows, BH family = 24 candidates:

| statin | n RMS / other | median LFC in / out | Cliff's δ [95 % CI] | p raw | p BH |
|---|---|---|---|---|---|
| simvastatin | 3 / 528 | −1.246 / −0.041 | **+0.681** [+0.417, +0.875] | **0.0189** | 0.132 |
| rosuvastatin | 14 / 858 | −0.176 / −0.025 | **+0.274** [−0.070, +0.557] | **0.0394** | 0.184 |
| atorvastatin | 14 / 858 | −0.179 / −0.001 | +0.192 [−0.096, +0.484] | 0.109 | 0.382 |
| pitavastatin | 14 / 853 | −2.548 / −1.610 | +0.112 [−0.257, +0.453] | 0.236 | 0.472 |
| fluvastatin | 3 / 528 | −1.413 / −2.051 | −0.253 [−0.347, −0.155] | 0.766 | 0.945 |
| lovastatin, pravastatin, mevastatin | 2 / — | — | — | untestable | — |

**4 of the 5 testable statins point the predicted way**; two reach raw one-sided p < 0.05;
**none survives Benjamini-Hochberg** (lowest q = 0.132). Among all 3,070 compounds the contrast
could test, simvastatin sits at the **97th percentile** of δ and rosuvastatin at the 82nd.

Sensitivity analyses (raw p, outside the family):

| analysis | simvastatin | rosuvastatin | atorvastatin |
|---|---|---|---|
| RMS vs **other soft-tissue lines** (14 vs 11) — the lineage-matched control | δ +0.733, p 0.071 | δ **+0.584** [+0.169, +0.922], p **0.0074** | δ +0.247, p 0.156 |
| within-line **rank-normalised** (removes generic fragility) | δ +0.638, p **0.0285** | δ +0.177, p 0.128 | δ +0.154, p 0.162 |
| 20Q2 secondary **AUC** | 1 RMS line — untestable | not in 20Q2 | 2 RMS lines — untestable |

The two survivors trade places between the two robustness checks: rosuvastatin's signal
strengthens when the comparison is other sarcomas and weakens when the line-level offset is
removed; simvastatin does the reverse. The confounder measurement explains why: **the RMS lines
are generically a little more fragile** — median-of-line-medians LFC −0.145 versus −0.080 for
the other 884 lines.

The secondary release cannot arbitrate: the statins have 0–2 RMS lines there.

### 3. H088, chloroquine and D2 against aneuploidy

Primary contrast (median split at Aneuploidy = 20; 350 high vs 338 low of 729 scored lines):

| drug | δ [95 % CI] | p raw | p BH | direction |
|---|---|---|---|---|
| chloroquine | +0.027 [−0.088, +0.142] | **0.315** | 0.782 | more sensitive |
| bortezomib | +0.056 [−0.057, +0.166] | 0.164 | 0.782 | more sensitive |
| metformin | +0.033 [−0.083, +0.144] | 0.283 | 0.782 | more sensitive |
| hydroxychloroquine | −0.022 [−0.137, +0.094] | 0.648 | 0.790 | less sensitive |

3 of 4 D2 drugs point the predicted way, but **chloroquine does not reach p < 0.2**, which is
the registered refutation clause. The tertile split (274 vs 243) gives chloroquine δ +0.022,
p 0.372; the 20Q2 AUC release has no chloroquine at all, and bortezomib there points the other
way (δ −0.016, p 0.618). In the RMS contrast chloroquine is the strongest candidate on the
board (δ +0.702, p 0.0154, 98th percentile of all compounds) — but on 3 lines, inside a control
band that spans ±0.7, so it is not evidence.

**The literature direction check is the strong result here.** Of 34 Mps1 and Aurora inhibitors,
**33 (97 %)** show high-aneuploidy lines as *less* sensitive; median δ = **−0.139**; not one
reaches p < 0.05 in the "more sensitive" direction. That independently reproduces
Cohen-Sharir 2021's reported direction in a screen and a contrast we built ourselves.

### 4. H089, the D5 drugs

| drug | contrast | n | δ [95 % CI] | p raw | p BH |
|---|---|---|---|---|---|
| dasatinib | aneuploidy, 24Q2 LFC | 238 / 176 | **+0.135** [+0.020, +0.248] | **0.0096** | 0.231 |
| dasatinib | aneuploidy tertile | 189 / 111 | +0.166 [+0.035, +0.303] | 0.0080 | — |
| dasatinib | aneuploidy, 20Q2 AUC | 269 / 241 | +0.053 [−0.051, +0.157] | 0.150 | — |
| dasatinib | RMS, 24Q2 LFC | 3 / 541 | −0.388 [−0.730, +0.006] | 0.870 | 0.945 |
| sirolimus | aneuploidy, 24Q2 LFC | 238 / 176 | +0.038 [−0.072, +0.157] | 0.252 | 0.782 |
| sirolimus | aneuploidy, 20Q2 AUC | 190 / 135 | +0.107 [−0.020, +0.237] | 0.050 | — |
| temsirolimus | aneuploidy, 20Q2 AUC | 270 / 252 | +0.080 [−0.019, +0.184] | 0.057 | — |
| everolimus | aneuploidy, 24Q2 LFC | 240 / 178 | −0.024 [−0.135, +0.088] | 0.662 | 0.790 |
| quercetin | aneuploidy, 24Q2 LFC | 239 / 180 | −0.026 [−0.134, +0.077] | 0.678 | 0.790 |

Dasatinib is the **99.4th percentile** of all 6,790 compounds on the aneuploidy contrast — the
only candidate anywhere on this board that clears its own negative-control band (δ +0.135 vs a
band ceiling of +0.096). It does not survive BH (q = 0.231) and it shrinks by more than half in
the other release. The three rapalogs agree in sign in the AUC release (sirolimus p 0.050,
temsirolimus p 0.057) and are flat in the LFC release; everolimus disagrees with both.

### 5. Confounders, stated plainly

- **n is small.** 14 RMS lines; a one-sided rank test with 14 in-group observations has a hard
  floor near p = 0.07 on any effect it can resolve without every rank cooperating, and the
  bootstrap CIs are correspondingly wide (typically ±0.35).
- **The RMS lines are generically more fragile** (median LFC −0.145 vs −0.080). The
  rank-normalised contrast is the correction; it halves rosuvastatin's effect.
- **The two contrasts are close to independent.** RMS lines' median aneuploidy score is 21
  (n = 11 scored) against 20 for the rest of the screen, so a drug that wins one contrast is
  not winning the other by construction.
- **No growth-rate or per-line screen-quality column exists in the 24Q2 extended primary
  release**, so growth rate could not be adjusted for; the line-median statistic above is the
  available proxy and it is reported rather than corrected away.
- **The candidate set is wider than "statins".** PRISM annotates meglutol, alpha-asarone and
  procaine as `HMGCR INHIBITOR`; they were tested and BH-corrected with the rest (making the
  family, and therefore the correction, more conservative), but they are not statins and are
  not counted in "most statins point the same way".

## Verdict

**H087 (`P4-22`) — supported, weakly; the prediction is met on raw p and fails on the corrected
p.** Neither refutation clause fires: two statins reach p < 0.05 raw (simvastatin 0.019,
rosuvastatin 0.039) and 4 of 5 testable statins point the predicted way. But no statin survives
Benjamini-Hochberg over the 24 candidates (best q = 0.132), the strongest single result
(simvastatin) rests on **3 cell lines inside a control band that spans ±0.7**, and lovastatin —
the molecule the report's rank-1 row is built on — has no testable data. The lineage-matched
contrast (RMS vs other soft tissue) is the one that gets closest to a real result:
rosuvastatin δ +0.584, p 0.0074, on all 14 lines.

**H088 (`P4-23`) — refuted as registered.** The first refutation clause fires exactly:
chloroquine shows no trend at p < 0.2 (p = 0.315, δ +0.027). The second does not — high
aneuploidy is *not* less sensitive, and 3 of 4 D2 drugs still point the predicted way — so this
is "the screen gives D2 no support", not "the screen contradicts D2". The tertile split and the
20Q2 AUC release both agree with the refutation, so it is not an artefact of the split.

**H089 (`P4-24`) — supported.** The refutation condition required both D5 drugs to be absent
from PRISM; both are present and both are reported with an effect size, a CI and a p in both
contrasts. The content is genuinely mixed and is reported as such: dasatinib is the single
best-placed candidate on the aneuploidy contrast (99.4th percentile, δ +0.135, p 0.0096) and
the worst-placed on the RMS contrast (δ −0.388); the rapalogs are marginal in one release and
flat in the other.

## Limitations

- **Cancer cell lines are not the child.** Every line here carries thousands of somatic
  mutations and a fixed karyotype; MVA is a constitutional, mosaic, *ongoing* missegregation
  state. Aneuploidy score is a proxy for a static burden, not for chromosomal instability, and
  Cohen-Sharir's own caveat applies: short-term drug exposure and long-term dependency differ.
- **Coverage, not biology, decides most of these rows.** 10 of 24 candidates and 50 of 182 rows
  are `too-few-lines`. That is reported as *untestable*, never as a null.
- **One-sided tests** cannot detect an effect in the opposite direction as significant, by
  design; the sign and the effect size are reported for every row so the reader can see it.
- **PRISM measures growth inhibition at one dose (24Q2) or a fitted curve (20Q2).** D3 ("raise
  BubR1") is a dosage hypothesis about a hypomorphic protein and has no growth-inhibition
  readout at all — the nicotinamide, niacin, valproate and vorinostat rows in this entry test
  something the direction never claimed, and their nulls mean nothing for D3.
- **The aneuploidy score and the RMS lineage come from DepMap 24Q4, the response from PRISM
  24Q2/20Q2.** The model-id namespace is shared, but the omics and the screen were not run on
  the same passage of the same vial.
- **The bootstrap CI is a percentile interval** with approximate coverage at n = 3; it is
  reported to show width, not to be inverted into a test.

## Conclusion

The independent screen does not confirm the Track 2 shortlist, and it does not refute it
either — it changes what each row is allowed to claim.

1. **D4 (statins) keeps its rank but loses its molecule.** The class-level direction replicates
   weakly (4 of 5 testable statins, two at raw p < 0.05, none after correction, rosuvastatin
   p 0.0074 against other sarcomas). Lovastatin, the molecule the report argues, is untestable
   here — so the report must say "the class direction is weakly reproduced in PRISM; lovastatin
   itself is not in the RMS panel", not "PRISM supports lovastatin".
2. **D2 loses its screen support.** Chloroquine's aneuploidy selectivity does not reproduce
   (p 0.315) in either release or either split. D2 was already the direction with no measured
   target population in this child (step 8); it now also has no support in the largest public
   drug × aneuploidy matrix. It stays in the report as a published-biology hypothesis, ranked
   below D3 and D4, with this negative result stated.
3. **D5 gains the only candidate that clears its own noise band.** Dasatinib is 99.4th
   percentile on the aneuploidy contrast. That is a hypothesis-grade signal, not a result:
   q = 0.231, and it halves in the other release.
4. **The do-not table gains an independent leg.** 33 of 34 Mps1/Aurora inhibitors are *less*
   effective in high-aneuploidy lines, reproducing Cohen-Sharir 2021 from raw data. The report's
   "do not weaken the checkpoint further" row now cites a replication, not only a citation.
5. **The method transfers.** `mva.drugs.screen_replication*` takes a drug list plus a line
   annotation column; swapping the Oncotree codes and the annotation runs the same experiment
   for any lineage, any genotype group, any screen with a compound × line matrix.
