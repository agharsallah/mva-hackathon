# External abundance calibration: the one remaining experiment and its submission decision

**Status:** proposed, not run. Written 2026-10-22 after the ESM-2 check
([plan](esm2-submission-experiment-plan.md), [result in report §3.2.1](../../submissions/track2/iteration-6/report.md))
came back below its gate. This is the **single** remaining experiment for final Track 2
iteration 6. No result, runtime or cost below is observed. Nothing in the submission may
describe it as done until its artifacts and checks exist.

## 1. Why ESM-2 could not have helped, and what that tells us to do instead

The ESM-2 check did run cleanly. ESM-2 scored AUROC 0.67 (10/15, exact tail 16/56), ThermoMPNN
0.60 and ESM1b 0.53. The top reference was the stable Y155C allele, and the child sat at the
77th percentile. The diagnosis is **not** "wrong model". Three structural problems remain, and
another model or a larger checkpoint would hit all of them again:

| Bottleneck | Evidence | Consequence |
| --- | --- | --- |
| **Too few labels.** 5 abundance-lowering vs 3 stable, the floor is 4 per class | protocol, entry 149 | No predictor can pass on this set. Even AUROC 1.0 has tail 1/56 and cannot overturn H083 |
| **Wrong target.** Sequence scores flag *function*, not *abundance* | Y155C ranks top under ESM-2 | Swapping in a better sequence model is the same mistake |
| **Labels reused.** All 8 were already used for ThermoMPNN and ESM1b | entry 149 | A third model on them is model shopping |

The binding constraint is therefore **the labels, not the predictor**. The one experiment that
changes this calibrates our *already frozen* predictors on **large, independent, experimentally
measured protein-abundance data from other proteins**. It then asks one quantitative question:

> Given what ThermoMPNN says about the child's substitution (ΔΔG +1.55 kcal/mol, buried core,
> pLDDT ≥ 90), how often does a substitution like that **actually** lower cellular protein
> abundance when someone measured it?

That is the quantity behind the 55% / 45% unstable-versus-inactive split on slide 2. That split
is currently a stated prior (H084), not a calibrated one. This experiment can either support it,
move it, or show that computation cannot inform it. All three outcomes are reportable.

**Rejected alternatives (one chance, so they are not run):**

- ESM-2 3B/15B, ESM-C, or ensembles: model shopping on the same 8 labels, with the same
  function-versus-abundance confusion.
- Rosetta/FoldX ΔΔG, or MD on the mutant: another stability predictor, still unvalidated for abundance.
- Mega-scale stability (Tsuboyama 2023) as labels: **ThermoMPNN was trained on it**, so it leaks.
  It also measures in vitro folding stability, not cellular abundance.
- Literature search for new BUB1B labels: worthwhile, but not an experiment. If one turns up, it
  enters only as a secondary sanity check (§5).

## 2. Scientific question and what it cannot answer

**Primary question:** across independent proteins with VAMP-seq-style *cellular abundance*
measurements, does ThermoMPNN ΔΔG separate abundance-lowering from WT-like substitutions
**among buried, high-confidence residues**? If it does, what is the calibrated probability of
low abundance at ΔΔG = +1.55 kcal/mol?

**Cannot answer:**

- Whether *BubR1* in particular behaves like the calibration proteins. Transport across
  proteins is an assumption. It is quantified by between-protein spread, not removed.
- Whether HSP90/proteasome dependence in BubR1 (PMID 20516114) differs from that of the
  calibration proteins.
- Whether a stabilised protein would be functional, or whether NMN/SIRT2 shielding works.
  The cycloheximide-chase blot remains the discriminator in every outcome.

## 3. Freeze the protocol before any new score or label is read

Commit `ressources/track2/it6/abundance_calibration/protocol.md` on its own, before downloading
labels or scoring anything. The commit time and its SHA-256 in `manifest.json` are the freeze
record. Mirror the ESM-2 protocol's format. It fixes:

- **Predictor (primary):** ThermoMPNN, the same Modal app (`src/mva/zoo/modal_apps/thermompnn.py`),
  the same pinned commit and weights digest, and AlphaFold DB models, exactly as for the BUB1B atlas.
  Sign: positive = destabilising. No retraining, no other predictor in the primary analysis.
- **Predictor (secondary, descriptive only):** ESM-2 650M masked marginal, the same checkpoint,
  revision and window rule as the frozen ESM-2 protocol. It is included **only** to test the
  function-versus-abundance explanation of the Y155C result. It cannot become the headline.
- **Label source:** ProteinGym v1.x substitution DMS assays with `coarse_selection_type =
  Expression`, which are VAMP-seq and abundance-sort assays. Pin the release version and file
  digest. Label = the assay's own `DMS_score_bin` (0 = low abundance). That cutoff is set per
  assay by ProteinGym, so we choose no threshold. List the included assays in the protocol
  **by reading only the reference metadata file**, not the score files.
- **Exclusions, fixed now:** assays on proteins in ThermoMPNN's training or validation set
  (check the ThermoMPNN repo's split files), proteins without an AlphaFold DB model, multi-mutant rows,
  and any assay with fewer than 50 labelled variants in the buried stratum.
- **Structural stratum (primary):** residues with RSA < 0.20 (Shrake–Rupley, as in the atlas)
  and AlphaFold pLDDT ≥ 90. This is the child's own context, the same definition as report §3.3.
  The all-residue analysis is secondary.
- **Primary endpoint:** for each protein, the AUROC of ΔΔG for low abundance in the buried
  stratum. Summary = the **median across proteins**, with a protein-level bootstrap interval
  (2,000 draws, seed 0). Variant-level pooling is reported but is not primary, because large
  assays would dominate it.
- **Calibration (the number we want):** a **leave-one-protein-out** logistic fit of low
  abundance on ΔΔG within the stratum. It has one slope and an intercept, no splines and no
  other features. Report P(low abundance | ΔΔG = +1.55) as the median and the range of the
  per-held-out-protein fits, plus a random-intercept (protein) logistic estimate with its 95%
  interval. The random intercept is the honest "new protein" uncertainty.
- **Transfer check on BUB1B (cannot tune anything):** apply the frozen calibration to the 8
  primary BUB1B alleles and report each predicted probability beside its label. This is
  descriptive only, with n = 8.
- **Decision-model consequence:** re-run the existing R4 decision model
  (`tools/it5_r4_decision.py`, `decision_config.with_prior`) with the missense prior set to
  the calibrated point estimate and to both interval ends. Report **whether the recommended
  first action (blot before treat) changes**. Utility weights are untouched.
- **Not allowed:** choosing assays after seeing scores, changing the RSA/pLDDT cut, adding
  covariates, swapping ThermoMPNN for ESM-2 if ESM-2 looks better, or multiplying the result
  with any other evidence.

## 4. Data, privacy and GPU execution

**Public only on Modal.** ProteinGym assays and AlphaFold models are public (check the
ProteinGym and per-assay licences and record them in provenance). The child's allele never
leaves the laptop: its ΔΔG (+1.55) is already in the local atlas, and its placement on the
calibration curve happens locally under `build/`.

**Pre-flight (laptop, CPU, ~20 min):**

1. Download ProteinGym reference metadata and substitution zip into a fresh directory under
   `build/abundance_calibration/raw/`. Treat it as untrusted data and read it with `python -I`.
2. Resolve each assay's UniProt ID → AlphaFold DB model. Verify that the assay's WT sequence equals
   the AlphaFold sequence at every scored position and fail on any offset (the same rule as the ESM-2 run).
3. Compute RSA (Shrake–Rupley) and pLDDT per residue locally. Count labelled variants per stratum
   and apply the frozen exclusions. **Gate: at least 5 proteins survive with ≥ 50 buried labelled
   variants each.** If not, stop and record "insufficient independent labels" as the result.

**GPU (Modal, one experiment):**

1. `tools/modal_trace.py run thermompnn smoke` (p53 2OCJ) reproduces the stored smoke
   output within tolerance before anything else runs.
2. Run `thermompnn atlas --uniprot <ID>` for each surviving protein, sequentially, on one L4,
   max 1 container, 30-minute timeout. One structure per protein yields every single-residue swap,
   so cost scales with protein count, not variant count. Plan for roughly 5–15 proteins.
3. Optionally, for the secondary ESM-2 comparison, reuse `src/mva/zoo/modal_apps/esm2.py` with
   the frozen window rule on the same proteins. Run it only if the ThermoMPNN step finished under
   budget.
4. Record wall time, GPU seconds, billed cost and app IDs. Run `tools/modal_trace.py stop` for
   each app and confirm nothing is left running. List any volumes created, for deletion.

**Budget:** spend ceiling **USD 10**. Pilot one protein first, extrapolate, and stop if the
estimate exceeds the ceiling or the remaining time. For reference, the BUB1B ESM-2 run cost
$0.14 and the step-8 GPU lanes cost $14.57. These are not estimates for this run.

**Time envelope (planning estimate, not measured):** about 30 min for protocol and pre-flight,
30–60 min for Modal, 45 min for evaluation and tests, and 45–60 min for integration into the
report, deck and PDFs. If less than ~1 h remains after the evaluation, take the "no time" row in §6.

## 5. Evaluation

Add `src/mva/drugs/abundance_calibration.py`, with a thin CLI in `tools/abundance_calibration.py`
and a test file. Reuse `variant_atlas_model.bootstrap_auroc` and the exact-tail helpers from
`esm2_check.py`. Outputs go to `ressources/track2/it6/abundance_calibration/`: `protocol.md`,
`manifest.json`, `scores.parquet` with `.provenance.json`, and `evaluation.json`. The figure goes
to `figures/it6/`.

Report, all pre-specified:

- A per-protein table with protein, assay, PMID, n buried, n low, AUROC and interval. Show
  every protein, including those where the predictor fails.
- The median AUROC across proteins with its protein-bootstrap interval, plus the all-residue secondary.
- The calibration curve (held-out fits as thin lines, random-intercept fit with band) and
  a marker at ΔΔG = +1.55 showing **P(low abundance)** with its interval.
- Secondary: ESM-2 AUROC on the same stratum. If ESM-2 does worse than ThermoMPNN on
  abundance, that is direct evidence for the function-versus-abundance reading of Y155C. This is
  descriptive and adds no new claim.
- BUB1B transfer table: the 8 alleles' calibrated probabilities against their labels.
- Decision-model rerun: the first action under the point estimate and interval ends.

Unit tests: label parsing, sequence-offset failure, stratum filter, LOPO fit on a synthetic
fixture with a known slope, and a check that no `build/` path or patient field enters the Modal input.

## 6. Inclusion gate, applied before touching the pitch

The blot stays the proposed discriminator in every row. Utility weights never change.

| Observed outcome | Report | Pitch (slide 2, replace, don't add) |
| --- | --- | --- |
| **A. Informative.** Median buried-stratum AUROC ≥ 0.70, its interval lower bound > 0.55, ≥ 5 proteins, and the random-intercept interval for P(low \| +1.55) **excludes 0.5** | New §3.2.2 with table, figure and decision rerun. The 55/45 split is shown beside the calibrated value, explicitly labelled as cross-protein and not BubR1-measured | Replace the "AUROC 0.60 on 8 alleles" fragment with the calibrated number (template below). Max two numbers |
| **B. Predictor works, patient ambiguous.** AUROC gate met, but the interval for P(low \| +1.55) includes 0.5 | §3.2.2. State that the predictor sees abundance, but the child's ΔΔG sits in the uncertain zone | One sentence: "Calibrated on N proteins, the child's change sits right in the uncertain zone, so the cell test decides." This strengthens "test once before you treat" |
| **C. Predictor doesn't work.** Median AUROC < 0.70 or interval reaching 0.55 | Transparent negative in §3.2.2 and the ledger. The 55/45 stays a stated prior | Omit, or keep the current fragment unchanged |
| **D. Decision flips** under the point estimate (blot-first no longer optimal) | Report prominently, with the tornado | Discuss before editing. It changes the story, so it needs a deliberate, rehearsed rewrite or the backup slide only |
| **E. Invalid.** Offset errors, < 5 proteins, failed smoke, leaked training proteins, incomplete job | Record the failure only | Do not add |
| **F. No time** to regenerate report, deck, PDFs and XLSX and re-check them | Preserve the current submission and add an optional "proposed" note | Do not add |

These thresholds are editorial inclusion gates fixed now. They are not biological validation.

**Pitch wording, technical (row A only, fill observed values):**

> "Is it unstable? We stopped guessing: calibrated on [N] proteins where cellular abundance was
> actually measured, a buried change like the child's lowers abundance [P]% of the time, [lo–hi]
> across proteins. Blot first still wins."

**Plain-language (row A):**

> "We checked our protein-stability computer against thousands of real lab measurements in
> other proteins. Changes like this child's usually make the protein disappear, but only the cell
> test tells us for sure."

Never say "validated in BubR1", "measured the child's protein", "proved unstable", or
"two independent confirmations". Rehearse slide 2 inside its 0:22–0:46 slot.

## 7. Integration, if the gate allows

- `report.md`: new §3.2.2 "External abundance calibration (frozen protocol)" after §3.2.1. Add rows to
  the compute table, the hypothesis ledger (file a new H-number with its prediction **at freeze
  time**) and the uncertainty/VOI limitations.
- `pitch-script.md` (both cuts), `pitch-slides.html` (slide 2 click 2, preserving deck interactions),
  then regenerate `pitch-slides.pdf`, `agharsallah_track2_report.pdf`, `methods-form.json`/`.xlsx`
  via the existing render and sync tools, and update the iteration-6 README links.
- The app's Provenance page and the dataset provenance envelope for the new data (lineage rule).
- Before submitting: grep the spoken script, HTML, report and generated files for stale numbers
  (old AUROC fragment, "nearly threefold") and run the submission readiness gate.
- Commit by explicit path, one semantic commit per lint-clean unit: protocol first and alone,
  then code and tests, then data and lineage, then submission. Parallel sessions may own other files.

## 8. Acceptance checklist

1. Protocol committed alone, before any label or score is read. Assay list frozen from metadata only.
2. ThermoMPNN smoke reproduces, all sequence offsets pass, no training-set protein included.
3. ≥ 5 proteins in the buried stratum, every protein reported, held-out calibration and decision rerun done.
4. No patient data on Modal. Apps stopped, cost recorded and under the ceiling.
5. Gate row chosen from §6 **before** editing pitch files and recorded in `evaluation.json`.
6. Report, deck, PDFs and XLSX regenerated together, stale-number grep clean, pitch rehearsed at time.

## 9. What to expect, honestly

This is the only option left that changes the *evidence* rather than the *model*. It replaces
"we pre-registered, and our predictor scored 0.60 on 8 alleles" with a calibration on hundreds
to thousands of measured variants. Published VAMP-seq work suggests that structure-based ΔΔG
predicts abundance loss moderately well for buried residues, so row A or B is plausible. Row C
is still possible and still reportable. Even the best outcome is a cross-protein estimate, not a
BubR1 measurement: it sharpens *why* the blot comes first rather than replacing it.

## Sources to verify before execution

- ProteinGym (Notin et al. 2023, NeurIPS): <https://proteingym.org>, reference file and DMS
  substitution archive. Confirm the `coarse_selection_type` and `DMS_score_bin` definitions.
- VAMP-seq: Matreyek et al. 2018 (*Nat Genet*, PTEN/TPMT), plus the per-assay papers listed in the
  ProteinGym reference file.
- ThermoMPNN (Dieckhaus et al. 2024, PNAS, PMID 38285937) and its training/validation split files
  for the leakage exclusion.
- Existing work: [ESM-2 plan](esm2-submission-experiment-plan.md),
  [ESM-2 sources](esm2-orthogonal-benchmark-sources.md),
  [`esm2_check/protocol.md`](../../ressources/track2/it6/esm2_check/protocol.md),
  entry 149, and report §3.2.1 and §3.3.
