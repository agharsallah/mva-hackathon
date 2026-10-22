# Iteration 5 · step 1 — allele-first therapy routes

**Standing:** open, verified 2026-09-25 against the filed entries. Goal declared in
`src/mva/science/step_maps/iteration5.py`; routes as in the [plan](../plan.md). Exploratory: no
claims are filed, each route carries a positive control instead
([note](../notes/exploratory-no-hypotheses.md)). Written summary and figure captions:
[`narrative.json`](narrative.json).

**Goal.** Starting from the child's two `BUB1B` alleles (one `stop_gained`, one missense) and
the BubR1 protein, which therapeutic route exists per allele, which passes its own positive
control, and which lab test separates them?

```mermaid
flowchart LR
  G["the child's two BUB1B alleles<br/>(genomic, entry 114 records)"]:::raw
  C["the 8 HPO terms<br/>(clinical)"]:::raw
  G --> R1["R1 · stop allele<br/>readthrough + dosage<br/>entry 158"]:::machine
  G --> R2["R2 · protein level<br/>corrected proteomics + LINCS<br/>entry 159"]:::machine
  G --> R3["R3 · literature<br/>quote-verified rows<br/>entry 160"]:::machine
  R1 --> K1{"held-out control<br/>passes for 3 compounds"}:::decision
  R2 --> K2{"HSP90 → HSPA1A passes<br/>corrected LINCS fails"}:::decision
  R3 --> K3{"recall 3/3 · 3/3"}:::decision
  K1 --> T["*_candidates.tsv<br/>one schema, a branch column"]:::good
  K2 --> T
  K3 --> T
  C --> S["per-child safety<br/>(entries 152, 155)"]:::machine
  T --> R4["R4 · decision + value of information<br/>entry 161"]:::machine
  S --> R4
  R4 --> Q{"missense protein<br/>unstable or inactive?<br/>EVPI 0.180, all of it here"}:::decision
  Q --> B["cycloheximide-chase blot<br/>EVSI 0.106 = 59 % of EVPI"]:::good
  R1 -.-> X["transfer check · Bloom syndrome<br/>entry 162"]:::machine
  R2 -.-> X
  R3 -.-> X
  classDef raw fill:#e0d4f7,stroke:#7a5cab
  classDef machine fill:#cfe8ff,stroke:#3d7ebd
  classDef decision fill:#ffe9b3,stroke:#c98f1e
  classDef good fill:#8fd18f,stroke:#3f8f47
```

> **Legend** purple = the two raw inputs (genomic, clinical) · blue = a route's machinery ·
> yellow = a control or a question that decides what may be read · green = the shared candidate
> tables and the measurement the step recommends · dashed edge = the same three routes re-run on
> a second disease, which produces no candidate for this child.

## Entries

| entry | route | what it found |
|---|---|---|
| [158](methodology/158-the-stop-allele-can-be-read-through-and-it-is-not-the-lever.md) | R1 — stop-codon readthrough, allele dosage | the stop allele is NMD-competent and loses the kinase domain; readthrough is worth at most a small fraction of the gap, so the missense allele is the lever |
| [159](methodology/159-which-drugs-raise-bubr1-protein-once-proliferation-is-removed.md) | R2 — proliferation-corrected drug proteomics; corrected LINCS | control passes; BUB1B protein is proliferation-bound; approved risers are weak; the strongest raisers point at degradation; the corrected LINCS control fails |
| [160](methodology/160-every-bubr1-intervention-in-the-literature-with-a-verified-quote.md) | R3 — quote-verified literature mining | control passes; NAD⁺, HDAC, proteasome, hypomethylating and senolytic classes; safety evidence from MVA patients |
| [161](methodology/161-the-decision-and-what-the-next-measurement-is-worth.md) | R4 — decision and value of information | the hand-worked control reproduces exactly; the choice turns entirely on `missense_class` (EVPPI 0.180 of an EVPI of 0.180, 0 on readthrough); the cycloheximide-chase blot is worth 0.106, 59 % of the ceiling, and stays positive over every range swept, while the top-ranked drug flips under three assumptions |
| [162](methodology/162-the-three-routes-on-bloom-syndrome.md) | transfer check — R1–R3 on Bloom syndrome | all three transfer by case card (587 configuration lines + 271 of one-time parameterisation, against entry 156's 378-line driver); every first-case table byte-identical; R1 passes an external check against a published measurement (Spearman 0.70, p 0.036); R3's declared control **fails** (extraction 0/3) and its rows are uninterpretable |
| [163](methodology/163-cross-iteration-synthesis-and-calibrated-decision-analysis.md) | R5 — cross-iteration synthesis and calibrated decision analysis | merges Iterations 2, 4, and 5 (52 drugs); calibrating `route:R2 = 0.25` aligns single-line screen residuals below Rung-3 *in vivo* `Bub1b^{H/H}` mouse rescues (`NMN` 0.480; FDA-approved `niacin`/`nicotinamide` 0.192 > `gliclazide`/`migalastat` 0.175; `dasatinib` 0.400 if inactive), restores `simvastatin`/`lovastatin` for tumour-context D4, and proves `EVPI = 0.1800` and `EVSI(chx_chase_blot) = 59.1–69.1%` of EVPI across all 20 route weights |

## Figures

All in [`figures/it5/`](../../../figures/it5/), each with a `.provenance.json` and an
interactive `.html` twin. Captions: [`narrative.json`](narrative.json).

| route | figures |
|---|---|
| R1 | `r1-stop-anatomy.svg`, `r1-control.svg`, `r1-plus4.svg`, `r1-dosage.svg` |
| R2 | `r2-proliferation.svg`, `r2-control.svg`, `r2-hits.svg` |
| R3 | `r3-extraction-funnel.svg`, `r3-evidence-map.svg`, `r3-mva-exposures.svg` |
| R4 | `r4-decision-tree.svg`, `r4-voi-curve.svg`, `r4-heatmap.svg`, `r4-tornado.svg` |
| transfer | `s1-transfer.svg` |
| R5 | `r5-cross-iteration.svg`, `r6-pitch-overview.svg` |

## Tables

In [`ressources/track2/it5/`](../../../ressources/track2/it5/), each with a
`.provenance.json`; recorded in `warehouse.data_lineage` as `track2.it5.*` once their entry is
filed (`uv run python tools/record_track2_lineage.py`).

| route | tables |
|---|---|
| R1 | `readthrough.tsv`, `allele_dosage.tsv`, `readthrough_candidates.tsv` |
| R2 | `proteome_hits.tsv`, `proteome_control.tsv`, `lincs_cc_control.tsv`, `protein_candidates.tsv` |
| R3 | `litmine_corpus.tsv`, `litmine_extraction.tsv`, `litmine_exposure_extraction.tsv`, `litmine_interventions.tsv`, `litmine_mva_exposures.tsv`, `litmine_rejected.tsv`, `literature_candidates.tsv` |
| R4 | `decision_utilities.tsv`, `decision_states.tsv`, `decision_voi.tsv`, `decision_flips.tsv`, `decision_sweep.tsv`, `decision_tornado.tsv`, `decision_avoid.tsv`, `candidate_safety.tsv`, `decision_config.json`, `decision_summary.json` |
| transfer | under `transfer/`: `transfer_summary.tsv`, `transfer_diffstat.tsv`, and each route's own tables in `r1/`, `r2/`, `r3/` — recorded as `track2.it5.transfer.*`, never mixed with the first case's |
| R5 | under `unified/`: `cross_iteration_candidates.tsv`, `model_comparison.tsv`, `route_weight_sweep.tsv`, `unified_summary.json` |

Every `*_candidates.tsv` shares the plan's columns (`drug_name, route, branch, evidence_kind,
evidence_strength, positive_control_passed, source, notes`); `evidence_strength` is a per-route
triage rubric, not a probability.

## Submissions

[`submissions/track2/iteration-5/`](../../../submissions/track2/iteration-5/README.md) (draft) ·
[`submissions/track2/iteration-6/`](../../../submissions/track2/iteration-6/README.md) (unified cross-iteration synthesis).
