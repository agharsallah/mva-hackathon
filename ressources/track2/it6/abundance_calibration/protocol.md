# External abundance calibration — frozen protocol

**Frozen:** 2026-10-22, before downloading any ProteinGym substitution score file or running
ThermoMPNN on any calibration protein. Committed on its own; its git commit timestamp and
SHA-256 recorded in `manifest.json` are the freeze record.

Plan: `docs/notes/abundance-calibration-experiment-plan.md`.

## Question

Across independent proteins with deep mutational scanning (DMS) measurements of cellular protein
abundance (`coarse_selection_type == "Expression"` in ProteinGym v1), does ThermoMPNN predicted
folding free-energy change ($\Delta\Delta G$, kcal/mol, positive = destabilising) discriminate
low-abundance from wild-type-like single-residue substitutions within buried, high-confidence
residues (`RSA < 0.20`, `AlphaFold pLDDT >= 90`)? And what is the leave-one-protein-out (LOPO)
and random-intercept calibrated probability $P(\text{low abundance} \mid \Delta\Delta G = +1.55\text{ kcal/mol})$
at the child's buried pseudokinase substitution value?

## Predictor and structural features (fixed)

- **Primary predictor:** ThermoMPNN (`src/mva/zoo/modal_apps/thermompnn.py`, commit
  `370f76ec62bd`, `thermoMPNN_default.pt` + ProteinMPNN `v_48_020`, weights digest
  `d7169ce604cfa1197869131aeb016db59759b0ee670ccbf93deef5f0a08f01dd:fdacf4e2d2c49274bd482bcec5193f04d5bf61464648f347db3aae4b7981eea5`)
  evaluated on public AlphaFold DB v6/v4 monomer structures (`https://alphafold.ebi.ac.uk/api/prediction/<acc>`).
  Sign convention: positive $\Delta\Delta G$ = destabilising.
- **Structural context:** per-residue relative solvent accessibility (`RSA`) computed by
  `mva.drugs.variant_atlas_sources.residues_from_pdb` (Shrake–Rupley, probe 1.4 Å, 100 dots,
  Bondi radii, divided by Tien et al. 2013 max ASA) and `pLDDT` from the AlphaFold CA B-factor.
- **Primary stratum:** buried, high-confidence core residues (`RSA < 0.20` and `pLDDT >= 90.0`),
  matching the child's substitution stratum (`report.md` §3.3).
- **Secondary stratum:** all scored single-residue substitutions across the protein (`all_residues`).

## Label source and metadata-only candidate list

- **Source:** ProteinGym v1 (`OATML-Markslab/ProteinGym_v1`, MIT licence), metadata file
  `reference_files/DMS_substitutions.csv` (SHA-256 `ac65645dc39fb92fff06bf876926ffe23dc7eb20da72bc0bb41fd2ccb0ee3f54`,
  217 assays).
- **Selection rule (applied to metadata only, before reading any score file):**
  `coarse_selection_type == "Expression"` (18 assays), then require:
  1. An exact sequence match between ProteinGym `target_seq`, UniProt canonical sequence, and
     the AlphaFold DB structure sequence (`5` assays excluded for isoform/construct mismatch:
     `GLPA_HUMAN_Elazar_2016`, `KCNE1_HUMAN_Muhammad_2023_expression`,
     `OXDA_RHOTO_Vanella_2023_expression`, `RASK_HUMAN_Weng_2022_abundance`,
     `S22A1_HUMAN_Yee_2023_abundance`).
  2. Not in ThermoMPNN's Megascale or FireProt training/validation splits
     (`dataset_splits/megascale_clusters.tsv` and `dataset_splits/fireprot_clusters.tsv` at commit
     `370f76ec62bd`; `0` of the remaining 13 overlap).
  3. At least 50 single-mutant labelled substitutions inside the primary buried stratum
     (`RSA < 0.20` and `pLDDT >= 90.0`) with both classes (`DMS_score_bin == 0` and `1`) present.
- **Candidate assays entering the stratum-size check (13 assays):**
  1. `CP2C9_HUMAN_Amorosi_2021_abundance` (`P11712`, length 490, VAMP-seq protein abundance)
  2. `ERBB2_HUMAN_Elazar_2016` (`P04626`, length 1255, membrane-protein insertion)
  3. `HXK4_HUMAN_Gersing_2023_abundance` (`P35557`, length 465, DHFR-PCA cellular abundance)
  4. `KCNJ2_MOUSE_Coyote-Maestas_2022_surface` (`P35561`, length 428, surface trafficking)
  5. `LYAM1_HUMAN_Elazar_2016` (`P14151`, length 372, membrane-protein insertion)
  6. `NUD15_HUMAN_Suiter_2020` (`Q9NV35`, length 164, VAMP-seq protein abundance)
  7. `OPSD_HUMAN_Wan_2019` (`P08100`, length 348, expression)
  8. `PRKN_HUMAN_Clausen_2023` (`O60260`, length 465, cellular protein stability/abundance)
  9. `PTEN_HUMAN_Matreyek_2021` (`P60484`, length 403, VAMP-seq protein abundance)
  10. `Q53Z42_HUMAN_McShan_2019_expression` (`Q53Z42`, length 365, surface expression)
  11. `SPIKE_SARS2_Starr_2020_expression` (`P0DTC2`, length 1273, yeast surface expression)
  12. `TPMT_HUMAN_Matreyek_2018` (`P51580`, length 245, VAMP-seq protein abundance)
  13. `VKOR1_HUMAN_Chiasson_2020_abundance` (`Q9BQB6`, length 163, VAMP-seq eGFP abundance)
- **Label definition:** single-amino-acid substitutions only (`:` not in `mutant`); positive class
  `y = 1` is `DMS_score_bin == 0` (low abundance / destabilised expression, using ProteinGym's
  own per-assay binarisation cutoff); negative class `y = 0` is `DMS_score_bin == 1`. No cutoff
  is chosen or tuned.
- **Pre-flight gate:** at least 5 assays must survive with $\ge 50$ buried high-confidence
  single-mutant variants and both classes present.

## Primary endpoint and calibration model

1. **Per-protein discrimination:** raw AUROC of ThermoMPNN $\Delta\Delta G$ for `y = 1` (low
   abundance) within the buried stratum (`RSA < 0.20`, `pLDDT >= 90.0`), with 2,000-draw
   stratified bootstrap 95% CI (`seed = 0`).
2. **Across-protein summary (primary):** median AUROC across all surviving proteins, with a
   2,000-draw protein-level cluster bootstrap 95% CI (`seed = 0`). Also report the sub-group of
   canonical intracellular VAMP-seq / abundance-sort assays (`CP2C9`, `HXK4`, `NUD15`, `PRKN`,
   `PTEN`, `TPMT`, `VKOR1`) alongside the full surviving Expression set so assay-type heterogeneity
   is transparent.
3. **Leave-one-protein-out (LOPO) calibration at $\Delta\Delta G = +1.55\text{ kcal/mol}$:**
   fit a two-parameter logistic regression $\text{logit}\,P(y=1 \mid \Delta\Delta G) = \beta_0 + \beta_1\,\Delta\Delta G$
   (protein-equally-weighted across the training proteins in the buried stratum) and evaluate
   $P(y=1 \mid \Delta\Delta G = +1.55)$ on each held-out protein fold; report the median and full
   range across LOPO folds, plus the out-of-fold Brier score and calibration slope.
4. **Random-intercept across-protein prediction interval:** fit protein-specific intercepts
   $\alpha_k$ with a common slope $\beta_1$ in the buried stratum, estimate the between-protein
   intercept variance $\hat{\tau}^2$, and compute the 95% predictive interval for a new protein at
   $\Delta\Delta G = +1.55\text{ kcal/mol}$ via parametric cluster bootstrap (`2,000` draws, `seed = 0`).
5. **Transfer check on `BUB1B` (`n = 8` primary MVA alleles):** evaluate the frozen cross-protein
   logistic curve on the 8 published `BUB1B` alleles (`ressources/track2/bub1b_published_alleles.tsv`)
   with zero refitting.
6. **Decision-model consequence:** run the unified decision model (`mva.drugs.unified_synthesis`)
   at $P(\text{unstable})$ set to the calibrated point estimate and its 95% interval bounds, and
   record whether the optimal pre-blot action or EVSI blot-first conclusion flips.

## Inclusion gate (applied before editing pitch material)

- **Gate A (Informative):** $\ge 5$ surviving proteins, median buried-stratum AUROC $\ge 0.70$,
  protein-bootstrap 95% CI lower bound $> 0.55$, and random-intercept 95% interval for
  $P(\text{low} \mid +1.55)$ excludes $0.50$.
- **Gate B (Predictor works, patient in uncertain band):** AUROC criteria of Gate A met, but the
  95% predictive interval for a new protein at $+1.55\text{ kcal/mol}$ includes $0.50$.
- **Gate C (Null / weak):** median AUROC $< 0.70$ or CI lower bound $\le 0.55$.

## Privacy and budget

- Only public UniProt accessions and AlphaFold DB structures are sent to Modal (`thermompnn`).
  The child's substitution never leaves the laptop.
- Spend ceiling: USD 5.00 on Modal T4. Every app is stopped immediately after scoring.
