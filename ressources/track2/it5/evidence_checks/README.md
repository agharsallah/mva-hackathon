# Bounded evidence checks — 2026-10-22

**Conclusion: no validated expansion.** Neither the stability classifier nor the
two drug-protein signals is promoted beyond exploratory evidence. These checks
are deliberately bounded, not a systematic review or proof of absence.

## Reproduction

From repository root:

```sh
uv run python ressources/track2/it5/evidence_checks/check_cached_evidence.py
```

Requires the existing cached public supplements under `build/it5/r2/raw` and
`openpyxl`. The script asserts expected counts, reads the original protein
measurements, scans all cached Mitchell workbook cells for candidate names,
and writes the tables and input SHA256 manifest in `summary.json`.
No patient data is used or sent externally; no GPU work was performed.
This is a one-off audit script colocated with its evidence, not a maintained
production entry point. Its layout/search assumptions are explicit in
`summary.json`; drug-target inhibition or association is never counted as
demonstrated BUB1B abundance rescue.

## Point 4: abundance/stability labels

The existing published-allele input has **8 primary labels: 5 abundance-lowering,
3 stable**, plus **1 extended-only stable** and **2 ambiguous excluded**.
Primary raw ΔΔG AUROC remains **0.60**, bootstrap 95% interval **0.133–1.0**.
The registered ≥0.8 hypothesis failed and the negative class has fewer than
four labels. This is not a validated probability estimator or measured prior.
Pathogenicity annotations are not protein-abundance ground truth.

The bounded review checked the existing input and cached primary papers:

| Source | Finding / exclusion |
|---|---|
| [Suijkerbuijk 2010, PMID 20516114](https://pmc.ncbi.nlm.nih.gov/articles/PMC2887387/) | Existing eight primary allele-level labels; no additional independent label recovered. Cellular and ectopic abundance differ for Y155C, so preserve the input's assay context. |
| [Sieben, PMID 31738183](https://pmc.ncbi.nlm.nih.gov/articles/PMC6934189/) | Mouse L1002P models the already labeled human L1012P, not an independent human substitution. X753 truncation and hypomorphic expression are not new missense labels. |
| [PMC9616775](https://pmc.ncbi.nlm.nih.gov/articles/PMC9616775/), [PMC7455400](https://pmc.ncbi.nlm.nih.gov/articles/PMC7455400/) | No new assay-resolved missense abundance/stability label established in this bounded check. A disease/sequence association alone is insufficient. |
| [Hahn 2016, PMID 27239782](https://pubmed.ncbi.nlm.nih.gov/27239782/) | C945Y already counted as extended-only stable; not new MVA validation. Existing input/abstract evidence only; no newly obtained full text. |
| [PMC13349884](https://pmc.ncbi.nlm.nih.gov/articles/PMC13349884/) | W722R/A739S remain ambiguous: qualitative carrier protein trend with lower mRNA does not isolate allele-specific protein stability. |

**New validated independent BUB1B labels: 0. New validated comparable-domain
labels: 0.** No defensible cross-protein abundance-calibration panel was
established within the time bound; no cross-protein pooling or refit was done.
The zero is an audit result, not a claim that no such experiments exist.

## Point 5: dose/time/replicate neighbours and independent proteomics

| Source | Reproducible count | Interpretation |
|---|---|---|
| [Mitchell 2023 / Gygi, DOI 10.1038/s41587-022-01539-0](https://doi.org/10.1038/s41587-022-01539-0), MOESM3 | 875 compound columns; one gliclazide and one migalastat summary column | Both HCT116, **10 µM, 24 h**; raw BUB1B log2FC **+0.22 / +0.20**, or **1.165 / 1.149-fold**. Not +1.47/+1.44 raw log2FC. These are protein-group measurements, not missense-specific functional rescue. |
| Same source, MOESM4–8 | Exactly two workbook-row candidate-name matches, both the compound metadata in MOESM4 (`10uM`) | No extra candidate dose/time/replicate condition recovered. Follow-up experiments do include other compounds' dose/time/replicates, which cannot be reassigned to these candidates. The single summary column is not a claim about the original experiment's biological replicate count; candidate-level replicates are not resolved here. |
| [Saei 2019, DOI 10.1038/s41467-019-13582-8](https://doi.org/10.1038/s41467-019-13582-8), MOESM7–9 | BUB1B measured in **81 columns = 9 drugs × 3 replicates × 3 cell lines** (A549/MCF-7/RKO) | Independent BUB1B perturbation proteomics exists, but neither candidate is in these panels. The 81 are not 81 independent drugs or candidate replications. Ratios/log2FC are exported in `independent_BUB1B_conditions.tsv`. |
| [decryptE 2024, DOI 10.1038/s41587-024-02218-y](https://doi.org/10.1038/s41587-024-02218-y), PMID 38714896, Table S1 | **144 compounds**, **0 candidate matches**, including listed aliases | New primary-source check. Main text describes Jurkat, 18 h, five doses; neither candidate is present. This compound inventory is not a BUB1B protein measurement and does not establish BUB1B coverage or replication. |

Canonical proliferation-adjusted residuals are **0.1953 / 0.1866** and robust z
scores **3.591 / 3.416** (ranks **20 / 23**), from existing `proteome_hits.tsv`;
these are not dose responses, p-values, independent replication, or measured
evidence-strength probabilities. Existing CCLE baseline associations and
Mathieson half-life tables do not provide candidate replication; the prior
audit reports no BUB1B half-life row.

### New external primary-source extraction

`decryptE_compounds.tsv` contains the exact values from the complete
`Table S1 - Cpd info` worksheet. `decryptE_compounds.provenance.json`
records the original supplementary URL, SHA256, size, worksheet and method.
The 90 MB workbook was removed after extraction to keep this deliverable
compact. To repeat acquisition, download that public URL to this evidence
directory and use `openpyxl.load_workbook(..., read_only=True, data_only=True)`,
then write that named worksheet's `iter_rows(values_only=True)` to TSV.
Only this small compound inventory was extracted; no protein-level decryptE
data was claimed or inferred.

**Actionable next step:** obtain candidate-specific biological replicates and
dose/time measurements in a BUB1B-relevant model, with cell-cycle controls and
functional SAC/alignment readouts. No current evidence warrants claiming a
validated stability prior, pharmacological stabilization, or candidate rescue.

## Critical units/provenance discrepancy: exact upstream surfaces

`canonical_units_audit.tsv` reads `proteome_hits.tsv` directly and verifies its
raw values against the original MOESM3 CSV. Column meanings and values:

| Canonical column | Gliclazide | Migalastat | Units / meaning |
|---|---:|---:|---|
| `raw_log2fc` | 0.22 | 0.20 | log2 protein fold change vs vehicle |
| `proliferation_score` | 0.04 | 0.03 | median gene-set log2FC |
| `residual` | 0.1953 | 0.1866 | OLS-adjusted log2FC response |
| `robust_z` | 3.591 | 3.416 | dimensionless robust standardized residual |
| `rank` | 20 | 23 | corrected ranking, not raw-effect rank |
| `sensitivity_z` | 3.149 | 3.239 | dimensionless, SAC-excluded score sensitivity |
| `sensitivity_rank` | 19 | 17 | corresponding sensitivity ranking |

The implementation `src/mva/drugs/proteome_tables.py::hit_rows` maps
`raw_log2fc` to `r.raw`, `residual` to `r.residual`, and `robust_z` to `r.z`;
it does not reinterpret a standardized score as a log2FC.
`src/mva/drugs/proteome.py::robust_z` computes
`(residual - median(residual)) / (1.4826 * MAD(residual))` across finite
responses. This is **not empirical-Bayes shrinkage**.

The earlier **1.47/1.44 are hard-coded narrative claims, not demonstrated
EB-standardized z scores** in this pipeline. They cannot be rescued by simply
relabeling their units. The inspected upstream surfaces still carrying the
claims at audit time are:

- `src/mva/drugs/unified_clinical.py::_build_pkpd`, around lines 348–349 and
  364–365: `structural_or_target_mechanism` strings claim +1.44/+1.47 log2FC,
  2.7/2.8-fold and a separate Gygi-10k / PMID 38942016 attribution.
- `src/mva/drugs/pitch_deck.py`, around lines 174–175 and 187–190: hard-coded
  slide/narration strings repeat those units and explicitly assert
  empirical-Bayes shrinkage and an 8,793-compound scan without a linked
  calculation in the inspected canonical proteome pipeline.
- Generated `ressources/track2/it5/unified/paediatric_pkpd_dosing.tsv`
  `structural_or_target_mechanism`, and the corresponding entries in
  `unified_summary.json`, inherit the clinical source strings.

The correct measured source identified here is **Mitchell 2023, 875
compound columns, PMID 36593396**, not independently verified evidence for
the separate 8,793-compound claim. This audit does not prove such another
dataset cannot exist; it establishes that the asserted numbers/EB provenance
are unsupported by these canonical inputs and computations.

Final-submission owners were notified immediately. Output normalizers in
`tools/sync_track2_submission.py` and `tools/render_track2_pitch_slides.py`
correct the final submission wording, but do not repair the upstream clinical
and pitch source strings or historical generated unified tables. Those
surfaces are explicitly outside this evidence agent's edit ownership.
