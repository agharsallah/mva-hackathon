# ESM-2 model-generation check — frozen protocol

**Frozen:** 2026-10-22, before any ESM-2 score for BUB1B was computed. This file is committed
on its own; its git commit time and the SHA-256 recorded in `manifest.json` are the freeze
record. It is *prospectively specified for this run*, not a pre-registration that predates the
project's earlier use of the same labels (entry 149 already used them for ThermoMPNN and ESM1b).

Plan: `docs/notes/esm2-submission-experiment-plan.md`. Sources: `docs/notes/esm2-orthogonal-benchmark-sources.md`.

## Model and score

- Checkpoint: `facebook/esm2_t33_650M_UR50D`, Hugging Face revision
  `08e4846e537177426273712802403f7ba8261b6c` (MIT licence), loaded with `transformers`, float32,
  `eval()`, `torch.inference_mode()`, no dropout. One model; no size tuning.
- Score: masked marginal, `s = log P(alt | window, site masked) − log P(wt | same)`.
  Damage ranking uses `−s` (higher = more damaging). The direction is fixed now.
- Tokens: `<cls>` precedes residue 1 of the window, so window residue *i* (0-based) is token *i+1*.

## Input and context rule

- Sequence: UniProt O60566 canonical (1,050 aa), fetched from UniProt and required to equal the
  `wt` column of `ressources/track2/bub1b_atlas.parquet` at every position, else abort.
- ESM-2 was trained on crops of at most 1,024 tokens (1,022 residues). No 1,050-residue pass.
- **Primary window** for 1-based site *p*: 1,022 residues starting at
  `start = clamp(p − 1 − 511, 0, 1050 − 1022)` (0-based), i.e. site-centred, terminal-clamped.
- **Sensitivity windows:** N = residues 1–1022, C = residues 29–1050. Every site inside a
  window is scored under it. Reported: score/rank change for the labelled alleles and for the
  pseudokinase domain (UniProt "Protein kinase", 766–1050). Not used for any headline.
- Only the public sequence crosses to Modal. The patient's substitution is never sent or marked.

## Primary endpoint

- References: the eight `primary=yes` rows of `ressources/track2/bub1b_published_alleles.tsv`
  (5 abundance-lowering, 3 stable), no relabelling or exclusion.
- Outcome: raw-score AUROC of `−s`, abundance-lowering = positive.
- The class-size floor of entry 149 (≥ 4 per class) is **not met** (3 stable): no result here
  can overturn the H083 verdict, even AUROC 1.0.
- Exact one-sided label-permutation tail: all C(8,5) = 56 assignments, fraction with AUROC ≥
  observed (ties counted as ≥).
- Interval: stratified bootstrap, 2,000 draws, seed 0 (`variant_atlas_model.bootstrap_auroc`).
- Comparators reported beside it, unchanged: ThermoMPNN ΔΔG and −ESM1b LLR from the atlas.
  Paired AUROC difference (ESM-2 minus each) with the same stratified bootstrap — descriptive.

## Secondary (cannot rescue a failed primary)

- Extended set (primary + C945Y).
- Window sensitivity (above).
- Patient placement, local only, output under `build/`: continuous percentile of `−s` among
  all 19,950 substitutions and within the pseudokinase domain. "High damage" = top 20 %
  (percentile ≥ 80), descriptive.

## Not allowed

Ensembling, probability cutoffs, model-size tuning, swapping score strategy, converting
scores to a prior, multiplying evidence, averaging with kcal/mol.

## Inclusion gate (applied before editing any pitch material)

| Observed | Report | Pitch |
| --- | --- | --- |
| AUROC ≥ 14/15 and exact p ≤ 0.05, window-stable, patient ≥ 80th pct | qualified exploratory result, all three models | backup only (no new external labels exist) |
| discriminates, patient < 80th | explain contradiction | at most "computation did not resolve mechanism" |
| patient damaging, references do not discriminate | unvalidated sequence-damage evidence | no positive headline |
| weak / null / unstable | transparent negative result in report | omit, or one negative sentence if it clarifies |
| driven by window choice or one control | fragile, backup | backup only |
| numbering error, nonfinite, failed smoke, incomplete job | excluded, failure recorded | not added |

## Budget

Spend ceiling USD 5 (Modal, one L4, timeout 30 min, max 1 container). A 16-site pilot is
timed first; the full scan runs only if the extrapolated GPU time is under 25 minutes.
