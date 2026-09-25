# 154 — Is any launched drug selective for both high-aneuploidy and rhabdomyosarcoma lines, screen-wide?

**Step:** iteration 4, [step 10](../README.md), experiment S1 (generator G3). **Date:** 2026-09-25.
**Claim:** H093 (`P4-28`). **Sources:** **one — the public-screen source.** No clinical (HPO) term
is read. The clinical dataset enters at one remove: HP:0002859 (rhabdomyosarcoma) is why the
lineage contrast is rhabdomyosarcoma (RMS). No patient sequence, position or allele is used.

## Question

Entry 151 tested 24 drugs *named in advance*. A named list can only confirm or deny itself. The
unbiased question: over **every** launched drug PRISM (a pooled cancer-cell-line drug screen)
measured well enough, does any one hit both the child's tumour context (RMS lines) and his
chromosome-number state (high-aneuploidy lines) harder than the rest, **after** paying for
testing all of them? The same run is iteration 4's generator G3: its top-ranked drugs go to the
step-10 convergence test (entry 155).

## Hypothesis and prediction

Registered before this entry (`uv run mva-science show H093`):

> **P4-28:** screen-wide, at least one launched drug is selective for both high-aneuploidy and
> rhabdomyosarcoma cell lines in PRISM.
> **Prediction.** Over every Launched compound in PRISM Repurposing 24Q2 measurable on at least 3
> rhabdomyosarcoma lines and at least 20 lines in each aneuploidy arm, with entry 151's tests
> unchanged (24Q2 LFC, one-sided Mann-Whitney U, strict median aneuploidy split), at least one
> drug has Benjamini-Hochberg q < 0.10 in the aneuploidy contrast and q < 0.10 in the
> rhabdomyosarcoma contrast, BH taken across all eligible Launched compounds in each contrast.

**Choices the claim leaves open, fixed before the first p value** — written into the docstring of
[`tools/screen_sweep.py`](../../../../tools/screen_sweep.py) before the run. Coverage counts (how
many compounds, how many lines) were looked at first; no contrast result was.

| choice | fixed value | why |
|---|---|---|
| metric | PRISM 24Q2 extended primary, **LFC** (log fold change of barcode abundance, 5 d, 2.5 µM); lower = more sensitive | entry 151's primary metric; the claim names 24Q2 |
| **Launched** | the compound's core BRD id (release-independent Broad compound id) is `Launched` in the 20Q2 **primary or secondary** treatment-info file | the 24Q2 list has no phase column. Both 20Q2 files copy the Drug Repurposing Hub's clinical phase. Entry 151 used only the secondary file (597 Launched rows) for its control universe; the primary file (2,175 Launched rows) is the wider copy of the same label |
| groups | RMS = `Model.csv` 24Q4 `OncotreeCode` ∈ {RMS, ERMS, ARMS, PLRMS, SCRMS, SRMS} vs every other line; aneuploidy = `OmicsSignatures.csv` 24Q4 `Aneuploidy`, strict median split, ties dropped | entry 151's builders, unchanged |
| eligibility | a copy has ≥ 3 RMS lines **and** ≥ 20 lines in each aneuploidy arm (RMS comparison arm ≥ 3); a drug is eligible if any copy is | the claim's numbers |
| test | one-sided Mann-Whitney U "in-group more sensitive"; Cliff's delta (δ, rank effect size) from the same U; 95 % percentile bootstrap CI, 2,000 resamples; seed 20260924 + the copy's index in the sorted eligible list | entry 151's `contrast_item`, unchanged |
| one drug, one test | copies grouped by join key and by shared core BRD id; entry 151's `representative` rule (the copy measured on most in-group lines) picks one copy per contrast | duplicates must not inflate the family |
| multiplicity | BH over every eligible drug's representative, within each contrast | the claim |
| rank, percentile | rank by one-sided p, ties by larger δ; percentile = share of the family with δ ≤ the drug's δ (entry 151's convention) | two views of one drug's place |
| G3 list | union of the top **0.5 %** (`ceil`) of the family on each contrast; `direction_hint` D4 (RMS hit), D2 (aneuploidy hit), `D4|D2` (both); `approval_evidence` `PRISM Launched`; universe = every eligible drug | step-10 generator rule, fixed 2026-09-25 |
| controls (context) | negative band re-drawn from the eligible set (200 seeded, entry 151's MOA exclusion list); family calibration; the positive control as a **sweep** (skin lines vs rest over every Launched compound, BH over the family); the RMS lines' generic fragility; which RMS lines the compounds were measured on; within-line rank-normalised repeat of the RMS contrast | the noise floor a reader needs before any hit |
| retrospective | entry 151 put dasatinib at the 99.4th percentile of all 6,790 compounds on the aneuploidy contrast. Reported here; **no rule reads it** | it is not a prediction |

## What would refute it

As registered: **no eligible Launched compound reaches q < 0.10 in both contrasts.** Stop rule:
if the positive-control sweep finds no RAF inhibitor at q < 0.10, the pipeline is broken and no
row may be read.

## Inputs

| file | release | sha256 (first 16) | licence |
|---|---|---|---|
| `PRISM_24Q2_Extended_Primary_Data_Matrix.csv` | PRISM Repurposing 24Q2 | `3b6554cfc6c765af` | CC BY 4.0 |
| `PRISM_24Q2_Extended_Primary_Compound_List.csv` | PRISM Repurposing 24Q2 | `7e78f5901c1a97d2` | CC BY 4.0 |
| `Model_24Q4.csv` | DepMap 24Q4 | `b7a0c1385e6cef30` | CC BY 4.0 |
| `OmicsSignatures_24Q4.csv` | DepMap 24Q4 | `2eb6d83065db5b59` | CC BY 4.0 |
| `PRISM_20Q2_secondary_treatment_info.csv` | PRISM Repurposing 20Q2 secondary | `f0ec000acda7c1a0` | CC BY 4.0 |
| `PRISM_20Q2_primary_treatment_info.csv` (**new**, figshare files/36794583, `prism-repurposing-20q2-primary-screen-replicate-collapsed-treatment-info.csv`, 1,312,286 bytes; md5 matched figshare's `1e69e342…`) | PRISM Repurposing 20Q2 primary (article 20564034) | `f92e58eb04b0db5c` | CC BY 4.0 |

The first five are entry 151's downloads under `build/it4/track2-e4/raw/`. The run digests each
and **refuses** on any mismatch with `ressources/track2/prism_replication.provenance.json`; all
matched. The new file lives in `build/it4/track2-s1/raw/` with its own manifest.

Code: `src/mva/drugs/screen_sweep{,_plan,_prism,_controls,_report,_run}.py`,
`tools/screen_sweep.py`, `tools/render_step10_s1.py`. Reused unchanged:
`mva.drugs.screen_replication` (`contrast_item`, `with_adjusted`, `median_split`,
`run_contrast`), `_prism` (readers, `lineage_group`), `_report` (`representative`,
`negative_control_band`, `confounder_summary`, `write_provenance`). One backward-compatible
addition: `screen_replication_plan.fetch_files` (the body of `fetch_sources`, callable with any
file list). scipy 1.18.1, numpy 2.5.2, polars 1.44.1.

## Commands

```bash
uv run python tools/screen_sweep.py fetch       # the one new file + its manifest
uv run python tools/screen_sweep.py run         # 3 min 47 s wall, 9 worker processes
uv run python tools/render_step10_s1.py
uv run pytest -q tests/test_screen_sweep.py tests/test_screen_replication.py
```

Outputs: [`ressources/track2/it4/prism_sweep.tsv`](../../../../ressources/track2/it4/prism_sweep.tsv)
(1,266 rows = 633 copies × 2 contrasts, sha256 `7749f9f129bd52eb…`) + `.provenance.json`;
[`generators/prism.tsv`](../../../../ressources/track2/it4/generators/prism.tsv) (8 rows) +
`prism.universe.tsv` (613) + `prism.provenance.json`; `build/it4/track2-s1/{controls.json,
positive-control-sweep.tsv}`; `figures/it4/step10-s1-{volcano,percentiles,funnel}.svg`.

**Reproducibility, checked.** The sweep ran three times: twice with the first join key (outputs
byte-identical — the parallel run is deterministic) and once after the join-key change below.
Every copy's δ, CI, p and q is identical across all three.

**Entry 151 re-run** (the brief's regression check on `screen_replication*`): into a scratch
directory, `tools/screen_replication.py run` reproduced every primary 24Q2 row and
`coverage.tsv` byte-identically. **21 rows differ, only in `ci_low` / `ci_high`, all in the two
20Q2 AUC sensitivity contrasts.** Cause, measured: `load_secondary_auc` builds its matrix with a
polars `group_by` + `pivot` whose line order changes between runs (two loads gave different
line orders), and the bootstrap resamples by position. This is pre-existing in entry 151's code,
independent of this entry's one change (the fetcher, which `run` never calls). Not fixed here:
it would change committed entry-151 numbers; flagged to the coordinator.

## Observed output

### 0. The machinery can clear BH screen-wide — the positive control

Skin/melanoma lines (53) vs the rest (845), every Launched compound with ≥ 3 lines each side,
BH over **2,032** drugs:

| rank | drug | MOA | δ | p | q |
|---|---|---|---|---|---|
| 1 | dabrafenib | RAF inhibitor | +0.670 | 1.6 × 10⁻¹² | 3.2 × 10⁻⁹ |
| 2 | vemurafenib | RAF inhibitor | +0.595 | 4.4 × 10⁻¹¹ | 4.5 × 10⁻⁸ |
| 5 | cobimetinib | MEK inhibitor | +0.457 | 3.2 × 10⁻⁷ | 1.3 × 10⁻⁴ |
| 6 | trametinib | MEK inhibitor | +0.449 | 4.9 × 10⁻⁷ | 1.7 × 10⁻⁴ |

**20 drugs reach q < 0.10**; the two RAF inhibitors are ranks 1 and 2. The stop rule does not
fire.

### 1. The funnel

| stage | count |
|---|---|
| compound rows in PRISM 24Q2 | 6,790 |
| core BRD ids Launched in either 20Q2 file | 2,075 |
| 24Q2 copies whose core is Launched | 2,189 (REP.PRIMARY 2,175, REP.1M 14) |
| **eligible copies** (≥ 3 RMS, ≥ 20 per aneuploidy arm) | **633** (REP.PRIMARY 619, REP.1M 14) |
| **eligible drugs** = BH family per contrast | **613** |
| 24Q2 compounds absent from both 20Q2 files (cannot be called Launched) | 1,489 (REP.1M 1,250, REP.300 239) |
| cores whose phase differs between or within the two files | 11 (e.g. 5 `Launched` vs `NA`, 2 `Launched` vs `Preclinical`); union rule applied |

**The RMS contrast is really a 3-line contrast.** 619 of the 633 eligible copies were measured
on exactly the same three RMS lines — **TE617T, RD, RH30**. Only the 14 REP.1M copies carry all
14 RMS lines.

### 2. H093 — the two families

| | RMS contrast | aneuploidy contrast |
|---|---|---|
| in-group / comparison lines | 14 / 884 (3 measured on most copies) | 350 / 338 (median split at 20 over 729 scored lines) |
| family size | 613 | 613 |
| p needed at rank 1 for q < 0.10 (0.10 / 613) | 1.6 × 10⁻⁴ | 1.6 × 10⁻⁴ |
| smallest p | 2.8 × 10⁻⁴ (fomepizole) | 4.7 × 10⁻⁴ (cefpirome) |
| **smallest q** | **0.122** | **0.287** |
| drugs with q < 0.10 | **0** | **0** |
| share of the family at raw p < 0.05 (null ≈ 5 %) | **9.6 %** | 4.1 % |
| same, RMS contrast rank-normalised within line | 4.4 % | — |
| negative band (200 seeded eligible controls): raw p < 0.05 | 9.0 % | 4.5 % |
| negative band: central 95 % of δ | −0.800 to +0.727 | −0.104 to +0.100 |

**No drug reaches q < 0.10 in either contrast, so none reaches it in both.** Two drugs reach raw
one-sided p < 0.05 in both (indomethacin: RMS p 0.046, aneuploidy p 0.048; mebicar: 0.012,
0.033), which is about what independence predicts (613 × 0.096 × 0.041 ≈ 2.4).

The RMS contrast fires at **twice the nominal rate** (9.6 %), and so does its negative band
(9.0 %). Rank-normalising within each line brings it back to **4.4 %**. The three RMS lines are
generically easy to kill: median-of-line-medians LFC **−0.145** vs **−0.080** for the other 884
lines. Much of the RMS contrast's apparent selectivity is line fragility, not drug selectivity.

The two contrasts pick different drugs: over 613 drugs the Spearman correlation of their δ
percentiles is **ρ = −0.112** (p 0.0057) — slightly *anti*-aligned, not aligned.

### 3. G3 — the list handed to the convergence test

`top_k = ceil(0.005 × 613) = 4` per contrast; the union is 8 drugs, none shared:

| G3 rank | drug | MOA / target (PRISM) | hint | RMS δ, p, q, rank | aneuploidy δ, p, q, rank | RMS rank-normalised p | contrary (δ < 0, p_opposite < 0.05) |
|---|---|---|---|---|---|---|---|
| 1 | fomepizole | alcohol dehydrogenase inhibitor / ADH1A-C | D4 | +0.925, 2.8e-4, 0.122, 1 | +0.045, 0.21, 1.00, 110 | 0.010 | no |
| 2 | cefpirome | bacterial cell-wall synthesis inhibitor | D2 | −0.655, 0.98, 1.00, 576 | +0.188, 4.7e-4, 0.287, 1 | 0.97 | **RMS, p_opp 0.024** |
| 3 | pizotifen | serotonin receptor antagonist / HTR1A, 2A, 2C | D4 | +0.915, 4.0e-4, 0.122, 2 | −0.014, 0.59, 1.00, 332 | 0.0086 | no |
| 4 | fentiazac | cyclooxygenase inhibitor / PTGS1-2 | D2 | −0.641, 0.97, 1.00, 573 | +0.143, 0.0061, 1.00, 2 | 0.96 | **RMS, p_opp 0.027** |
| 5 | inositol hexanicotinate | not annotated | D4 | +0.877, 0.0012, 0.177, 3 | −0.011, 0.58, 1.00, 320 | 0.0083 | no |
| 6 | delivert | angiotensin receptor agonist / AGTR1-2 | D2 | +0.227, 0.26, 0.84, 187 | +0.142, 0.0067, 1.00, 3 | 0.20 | no |
| 7 | terazosin | α1-adrenergic antagonist / ADRA1A-D | D4 | +0.871, 0.0013, 0.177, 4 | +0.008, 0.45, 1.00, 247 | 0.029 | no |
| 8 | dasatinib | BCR-ABL / SRC-family kinase inhibitor | D2 | −0.388, 0.87, 1.00, 517 | +0.135, 0.0096, 1.00, 4 | 0.86 | no (RMS p_opp 0.131) |

Every G3 drug is REP.PRIMARY, so every RMS number above rests on the same three lines. The four
RMS picks keep raw p < 0.03 after rank normalisation; that is outside the family and is no
correction.

Across the whole family, 53 drugs (RMS) and 40 drugs (aneuploidy) show δ < 0 with
`p_opposite` < 0.05 — the input K3 (contrary screen) reads in entry 155.

### 4. Retrospective: dasatinib

| | this entry (613 eligible Launched drugs) | entry 151 (6,790 compounds, no correction) |
|---|---|---|
| aneuploidy δ [95 % CI] | +0.135 [+0.024, +0.243], n 238 / 176 | +0.135 [+0.020, +0.248] |
| p / q | 0.0096 / **0.9997** | 0.0096 / 0.231 (family of 24) |
| rank / percentile | **4 of 613** / 99.5th | — / 99.4th |
| RMS δ, p | −0.388, 0.870 (3 lines) | −0.388, 0.870 |

The p value is the same measurement (same copy, same lines). Its **q moves from 0.231 to 1.0**
because the family grows from 24 chosen drugs to 613. Dasatinib clears the aneuploidy negative
band (ceiling +0.100) and sits at rank 4, **exactly the G3 cut**: `ceil(0.005 × 613) = 4`. With
`floor` rounding (3) it would not be listed. The rounding was fixed in code
(`screen_sweep.top_k`) before any run; dasatinib's inclusion is therefore a consequence of the
rule, not a choice — but it sits on the boundary, and the convergence count in entry 155 is to be
reported with and without it (step-10 README).

### 5. Join key — an interface change after the first run

The first run keyed drugs by "hyphen → space between two letters". The step-10 convergence join
asked for its shared rule, `base_name(name.replace("-", " "))`. The key now is: drop a trailing
racemate marker `-(+/-)`, then that rule (so `LEVOBUNOLOL-(+/-)` → `LEVOBUNOLOL`, `PLX-4720` →
`PLX 4720`). Re-run in full: family size stays 613, every statistic is identical, the G3 list is
the same 8 drugs.

## Verdict

**H093 (`P4-28`) — refuted as registered.** The refutation condition fires exactly: no eligible
Launched compound reaches q < 0.10 in both contrasts — none reaches it in *either* (best q 0.122
RMS, 0.287 aneuploidy). The positive-control sweep, through the same code, recovers the RAF
inhibitors at q ≈ 10⁻⁹, so this is a real null of the screen at this power, not a broken
pipeline. It is a weak null in the RMS arm: that contrast is three cell lines for 619 of 633
copies, fires at twice the nominal rate from line fragility, and its best drug misses the BH
threshold by a factor of 1.7 in p.

## Limitations

- **Launched is PRISM's 2020 label.** 1,489 compounds of the newer REP.1M / REP.300 sub-screens —
  the ones measured on all 14 RMS lines — have no phase in either 20Q2 file and are excluded
  unclassified, not as "not approved". A ChEMBL max-phase join would recover some; it was not run
  (G3's approval rule is PRISM Launched).
- **Three RMS lines** carry the RMS contrast for 98 % of eligible copies (TE617T, RD, RH30).
  A one-sided rank test on 3 lines can reach small p only when all three are the most sensitive,
  and generic fragility of those three lines inflates the raw hit rate to 9.6 %.
- **One dose, one release.** 24Q2 LFC at 2.5 µM for 5 days; no dose-response check in this entry.
- **Cancer lines are not the child** (entry 151's limitation applies unchanged): aneuploidy score
  is a static count, MVA an ongoing mosaic missegregation state.
- **BH over 613 drugs is the registered family**; a smaller mechanistically chosen family would
  pass more drugs and is exactly the post-hoc freedom the claim was written to remove.
- **The bootstrap CI** is a percentile interval with approximate coverage at n = 3.

## Conclusion

1. **PRISM names no launched drug selective for both contexts.** The screen-wide answer to
   "which drug hits RMS *and* aneuploid lines" is none, at a power where it does find BRAF
   inhibitors for melanoma.
2. **The two contrasts are independent sources that disagree** (ρ −0.112): the drugs that lead one
   are average or contrary in the other; two of the four aneuploidy leads (cefpirome, fentiazac)
   point significantly the *wrong* way in RMS.
3. **G3 hands 8 drugs to the convergence test as a weak generator**: none has q < 0.10; its RMS
   picks rest on three lines. G3's value is the *universe* (613 drugs measured both ways) and the
   contrary-direction evidence (K3), more than its list.
4. **Dasatinib's entry-151 signal survives as a rank (4 of 613), not as a result (q 1.0)**, and
   it enters G3 on the rounding boundary.
5. **The method transfers.** `mva.drugs.screen_sweep*` takes any response matrix, any two line
   groups and any approval label; the positive-control sweep is the reusable check that a
   screen-wide null is a null.
