# Track 2 — Iteration 6: Unified Cross-Iteration Synthesis & Calibrated Decision Dossier

**Standing:** ready (assembled 2026-09-27 from executed runs across Step 0, Iteration 1, Iteration 2, Iteration 4, and Iteration 5, unified in Methodology Entry 163). **Not uploaded** — Track 2 accepts a single final submission (deadline ~2026-10-20).

This folder is the **definitive, merged Track 2 submission package** for the MVA Hackathon 2026. Rather than discarding earlier iterations when new tools were introduced, Iteration 6 (`src/mva/drugs/unified_synthesis.py`, Entry 163) formally integrates **all 52 unique drug candidates, 13 primary databases, 6 mechanistic directions (`D1`–`D5` + `A1/A2`), 4 pre-registered discovery generators (`G1`–`G4`), 3 orthogonal mechanistic routes (`R1`–`R3`), a 2-source per-child safety and callability audit (`K1/K2/K3`), and a calibrated Bayesian Value-of-Information (`EVPI / EVPPI / EVSI`) decision framework** into one coherent, falsifiable dossier.

---

## 1. Deliverables in this folder

Per the challenge rules (`ressources/hackathon-rules/Readme.md`), Track 2 requires two uploaded files plus an optional 3-minute video pitch:

| # | Deliverable | File in this folder | Upload filename | Status |
|---|---|---|---|---|
| 1 | **Technical report** (PDF, 8–10 page body + appendices, all 25 Track 2 figures across Iterations 2, 4, and 5 embedded) | [`report.md`](report.md) → [`agharsallah_track2_report.pdf`](agharsallah_track2_report.pdf) | `agharsallah_track2_report.pdf` | Ready |
| 2 | **Methods summary form** (official organiser `.xlsx` template, rows 7–16 filled, row 16 abstract $\le 500$ words) | [`methods-form.json`](methods-form.json) → [`agharsallah_track2_methods_form.xlsx`](agharsallah_track2_methods_form.xlsx) | `agharsallah_track2_methods_form.xlsx` | Ready |
| 3 | **3-minute video pitch script & 7-slide companion deck** (two complete 180-second scripts — **Version A** technical cut + **Version B** plain-English cut — with exact `[👉 SLIDE N]` cues, interactive widescreen [`pitch-slides.html`](pitch-slides.html), and print-ready [`pitch-slides.pdf`](pitch-slides.pdf)) | [`pitch-script.md`](pitch-script.md), [`pitch-slides.html`](pitch-slides.html), [`pitch-slides.pdf`](pitch-slides.pdf) | *(optional video companion)* | Ready |

No predictions CSV is used in Track 2. Zero patient genomic coordinates (`chr:pos`) appear in any file in this folder or anywhere in git (`uv run python tools/check_coordinates.py`).

---

## 2. How Iteration 6 unifies and enhances Iterations 1, 2, 4, and 5

Each prior Track 2 iteration contributed a distinct methodological layer, and each left one specific blind spot that Iteration 6 resolves:

| Iteration | Core contribution preserved in Iteration 6 | Blind spot identified | How Iteration 6 (`entry 163`) resolves it |
|---|---|---|---|
| **Iteration 1** (`entries 069–083`) | Established the Track 1 causal genotype (`BUB1B` compound heterozygote: maternal-like `stop_gained` + paternal-like pseudokinase `missense_variant` in trans, oracle-confirmed at Rank 1 in entry 083) and the initial structural + clinical phenotype baseline. | Baseline heuristic shortlist (`metformin`, `rapamycin`, `nicotinamide`) had no patient-specific VCF pharmacogenomic audit or quantitative screen validation. | Replaces heuristic ranking with quantitative PRISM (`n=919`), Gygi-10k (`n=8,793`), MGI (`n=76,699`), and PharmCAT + OnSIDES per-child safety checks; explicitly tracks how `rapamycin` and `metformin` behave in PRISM (`entry 151`). |
| **Iteration 2** (`entries 096–101, 138–146`) | Framed the **6 therapeutic directions** (`D1`–`D5` + `A1/A2`), built the **5-rung N-of-1 evidence ladder**, discovered the **`Bub1b^{H/H}` NAD+/SIRT2 rescue axis** (`niacin`, `nicotinamide`, `NMN`, `PMID:24825348`), identified **Rung-5 rhabdomyosarcoma trials** (`simvastatin`/`lovastatin` `NCT02390843` + `PMID:41249736`), and ran the first PharmCAT + FAERS safety screen. | Relied on literature curation and PrimeKG random-walk proximity without testing generator convergence against chance or quantifying whether the child's missense is unstable vs catalytically dead. | Preserves the 5-rung ladder, the `D4` rhabdomyosarcoma statin leads (gated on `SLCO1B1`), and the `A1/A2` Do-Not boundaries, while embedding them inside the calibrated 2-state Bayesian decision model. |
| **Iteration 4** (`entries 147–156`) | Read the LoF mechanism from **5 independent instruments** (9 variant models, Boltz-2 fold, all-19,950-substitution ThermoMPNN $\Delta\Delta G$ atlas at 87.3rd pct, 76,699 MGI mouse genotypes matching `Bub1b^{H/H}` at top 0.99%, HPO gene ranking), tested **4 pre-registered generators** (`G1`–`G4`) against a **10,000-draw permutation null** (`dasatinib` sole 2-generator survivor), built the **2-source per-child safety check** (`vincristine` flagged by both genome and HPO label; 1.6% VCF PGx callability), and validated **scalability on Bloom syndrome (`BLM`)**. | Strict generator isolation excluded `NMN`, dropped the `D4` rhabdomyosarcoma trials when PRISM's 3-RMS-line sweep was underpowered, and treated the 87.3rd-percentile $\Delta\Delta G$ prediction without a formal Value-of-Information (VOI) model for the wet-lab follow-up. | Integrates Iteration 4's 5-instrument mechanism proof, permutation null, `dasatinib` (`twin|prism`) lead, `vincristine` dual flag, and Bloom syndrome transfer directly with Iteration 5's proteome scan and VOI engine. |
| **Iteration 5** (`entries 159–162`) | Audited **premature-stop readthrough/NMD context** (`R1_score=0.33`, entry 159), scanned **8,793 Gygi-10k proteome perturbations** (`PMID:38942016`) by empirical-Bayes shrinkage (`gliclazide` +1.47, `migalastat` +1.44 $\log_2\text{FC}$ BubR1, entry 160), formalized the **callability-aware safety contract** (`entry 161`), and proved via **EVPI / EVPPI / EVSI** (`entry 162`) that 100% of actionable uncertainty sits on `missense_class` (`EVPI = 0.1800`) and 0% on `readthrough_feasible`. | Equal route weighting (`w_R2 = 1.0`) let 1-replicate asynchronous HCT116 cell-line proteomics (`gliclazide`/`migalastat`, `u=0.7000`) numerically overshadow multi-animal *in vivo* `Bub1b^{H/H}` mouse survival rescues (`NMN` `u=0.4800`, `niacin/nicotinamide` `u=0.1920`). | **Entry 163 (`src/mva/drugs/unified_synthesis.py`)** sweeps $w_{R2} \in [0.05, 1.00]$ and calibrates `w_R2 = 0.25` (reflecting the failed taxane/veliparib asynchronous HCT116 positive control `H099` and `n=1` replicate design), proving two exact flip thresholds ($w_{R2}^* = 0.6857$ overall to `NMN`; $w_{R2}^* = 0.2743$ FDA-approved to `niacin/nicotinamide`) while showing `EVPI = 0.1800` is 100% invariant and `EVSI(chx_chase_blot)` rises from **59.1% to 69.1% of EVPI**. |

---

## 3. Contributing steps and methodology entries

Every claim, table, and figure in `report.md` traces to an append-only methodology entry:

- **Track 1 oracle confirmation & genomic foundation**:
  - [`docs/step-0/methodology/083-oracle-submission-1-reply.md`](../../../docs/step-0/methodology/083-oracle-submission-1-reply.md) — Oracle confirms `BUB1B` (`stop_gained` + `missense_variant` in trans) at Rank 1 (`1.0` full match).
  - [`docs/iteration4/step-1/methodology/114-callset-re-normalization-and-audit.md`](../../../docs/iteration4/step-1/methodology/114-callset-re-normalization-and-audit.md) & [`docs/iteration4/step-7/methodology/148-gpu-zoo-ntv2-evo2-esmc-boltz2-and-9-model-fusion.md`](../../../docs/iteration4/step-7/methodology/148-gpu-zoo-ntv2-evo2-esmc-boltz2-and-9-model-fusion.md) — 9-model variant-effect characterization.
- **Iteration 2 — Mechanistic directions, 5-rung ladder, PrimeKG walk & PGx baseline**:
  - [`docs/iteration2/step-5/methodology/139-bub1b-pathology-and-therapeutic-directions.md`](../../../docs/iteration2/step-5/methodology/139-bub1b-pathology-and-therapeutic-directions.md) — Directions `D1`–`D5` and Do-Not `A1/A2`.
  - [`docs/iteration2/step-5/methodology/140-patient-context-pharmacogenomics-and-modifier-screen.md`](../../../docs/iteration2/step-5/methodology/140-patient-context-pharmacogenomics-and-modifier-screen.md) — Initial patient modifier and PGx scan.
  - [`docs/iteration2/step-5/methodology/142-primekg-random-walk-and-depmap-prism-aneuploidy-screen.md`](../../../docs/iteration2/step-5/methodology/142-primekg-random-walk-and-depmap-prism-aneuploidy-screen.md) — PrimeKG walk (`H074` supported, 2/20 decoy overlap) + initial DepMap/PRISM analysis.
  - [`docs/iteration2/step-5/methodology/144-evidence-rung-ladder-and-n-of-1-shortlist.md`](../../../docs/iteration2/step-5/methodology/144-evidence-rung-ladder-and-n-of-1-shortlist.md) — 5-rung evidence ladder (`niacin/nicotinamide`, `NMN`, `simvastatin/lovastatin`, `rapamycin`, `metformin`, `ataluren`).
- **Iteration 4 — Five-instrument mechanism, 4-generator permutation null, 2-source safety & second-disease transfer**:
  - [`docs/iteration4/step-6/methodology/147-boltz2-wt-vs-mutant-bubr1-structure-comparison.md`](../../../docs/iteration4/step-6/methodology/147-boltz2-wt-vs-mutant-bubr1-structure-comparison.md) — Boltz-2 WT vs mutant fold (`H081` inconclusive).
  - [`docs/iteration4/step-9/methodology/149-bubr1-thermompnn-stability-atlas-and-allele-class-calibration.md`](../../../docs/iteration4/step-9/methodology/149-bubr1-thermompnn-stability-atlas-and-allele-class-calibration.md) — All-19,950-substitution ThermoMPNN $\Delta\Delta G$ atlas (`H083` calibration AUROC 0.60; `H084` child's missense at 87.3rd pct, `+1.55 kcal/mol`).
  - [`docs/iteration4/step-9/methodology/150-cross-species-phenotype-twin-mgi-genotype-matching.md`](../../../docs/iteration4/step-9/methodology/150-cross-species-phenotype-twin-mgi-genotype-matching.md) — 76,699 MGI mouse genotypes (`H085` supported: `Bub1b^{H/H}` top 0.99%, $p=0.026$).
  - [`docs/iteration4/step-9/methodology/151-prism-aneuploidy-and-senolytic-replication.md`](../../../docs/iteration4/step-9/methodology/151-prism-aneuploidy-and-senolytic-replication.md) — 919-line PRISM audit: 33/34 Mps1/Aurora inhibitors less effective in aneuploid lines (`δ = -0.139`); `dasatinib` at 99.4th pct (`δ = +0.135, p = 0.0096`).
  - [`docs/iteration4/step-9/methodology/152-per-child-two-source-safety-pharmcat-and-onsides.md`](../../../docs/iteration4/step-9/methodology/152-per-child-two-source-safety-pharmcat-and-onsides.md) — PharmCAT v3.1.1 (20/1,223 loci called, 1.6%) + OnSIDES v3.1.0 (`vincristine` dual flag; `RYR1` VUS).
  - [`docs/iteration4/step-9/methodology/153-lincs-bub1b-knockout-signature-reversal.md`](../../../docs/iteration4/step-9/methodology/153-lincs-bub1b-knockout-signature-reversal.md) — LINCS `BUB1B` KO reversal (`H092` failed positive control).
  - [`docs/iteration4/step-10/methodology/154-screen-wide-prism-sweep-aneuploidy-and-rms.md`](../../../docs/iteration4/step-10/methodology/154-screen-wide-prism-sweep-aneuploidy-and-rms.md) — Screen-wide PRISM sweep (`H093` refuted after BH correction; melanoma positive control `dabrafenib` $q = 3.2\times 10^{-9}$).
  - [`docs/iteration4/step-10/methodology/155-four-generator-convergence-and-permutation-null.md`](../../../docs/iteration4/step-10/methodology/155-four-generator-convergence-and-permutation-null.md) — 4-generator convergence (`H094` refuted $p=0.263$; `H095` supported: `dasatinib` survives K1/K2/K3).
  - [`docs/iteration4/step-11/methodology/156-second-disease-transfer-bloom-syndrome.md`](../../../docs/iteration4/step-11/methodology/156-second-disease-transfer-bloom-syndrome.md) — Bloom syndrome (`BLM`) transfer execution ($0, 53 min, Jaccard 0.095).
- **Iteration 5 — Mechanistic routes (`R1`–`R3`), VOI (`EVPI/EVPPI/EVSI`), and Cross-Iteration Calibrated Synthesis (`R5`)**:
  - [`docs/iteration5/step-1/methodology/159-stop-context-readthrough-and-nmd-evaluation.md`](../../../docs/iteration5/step-1/methodology/159-stop-context-readthrough-and-nmd-evaluation.md) — Route R1 sequence-context readthrough & NMD audit (`H097` refuted: `R1_score = 0.33`).
  - [`docs/iteration5/step-1/methodology/160-gygi-10k-bubr1-proteome-perturbation-scan.md`](../../../docs/iteration5/step-1/methodology/160-gygi-10k-bubr1-proteome-perturbation-scan.md) — Route R2 empirical-Bayes shrinkage over 8,793 Gygi-10k compounds (`H098` supported: `gliclazide` +1.47, `migalastat` +1.44 $\log_2\text{FC}$; `H099` control refuted).
  - [`docs/iteration5/step-1/methodology/161-pharmacogene-callability-and-two-source-safety-matrix.md`](../../../docs/iteration5/step-1/methodology/161-pharmacogene-callability-and-two-source-safety-matrix.md) — Unified 29-candidate two-source safety matrix (`H100` supported).
  - [`docs/iteration5/step-1/methodology/162-value-of-information-and-expected-utility-n-of-1-trial-design.md`](../../../docs/iteration5/step-1/methodology/162-value-of-information-and-expected-utility-n-of-1-trial-design.md) — Two-state Bayesian decision model & VOI (`H101`, `H102` supported).
  - [`docs/iteration5/step-1/methodology/163-cross-iteration-synthesis-and-calibrated-decision-analysis.md`](../../../docs/iteration5/step-1/methodology/163-cross-iteration-synthesis-and-calibrated-decision-analysis.md) — **Cross-iteration synthesis (52 drugs) & Route-R2 scale calibration (`w_R2 = 0.25`)**.

---

## 4. Exact regeneration commands

Every table, figure, PDF, and Excel file in this folder is 100% reproducible from tracked scripts:

```bash
# 1. Run the unified cross-iteration synthesis engine (Entry 163)
uv run python tools/it5_unified_synthesis.py

# 2. Render the cross-iteration calibration figure (figures/it5/r5-cross-iteration.svg)
uv run python tools/render_it5_r5.py

# 3. Fill the official Track 2 methods summary form (.xlsx)
uv run python tools/fill_methods_form.py \
  --sheet "Track 2 methods" \
  --answers submissions/track2/iteration-6/methods-form.json \
  --out submissions/track2/iteration-6/agharsallah_track2_methods_form.xlsx

# 4. Render the technical report to HTML and print-ready PDF
uv run python tools/md_to_html.py \
  submissions/track2/iteration-6/report.md \
  build/submission/track2-it6-report.html
node tools/md_to_pdf.mjs \
  build/submission/track2-it6-report.html \
  submissions/track2/iteration-6/agharsallah_track2_report.pdf

# 5. Run all repository quality and coordinate gates
uv run python tools/check_iteration.py
uv run python tools/check_coordinates.py
./tools/check-python.sh
```
