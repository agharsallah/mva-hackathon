# 113 — The ladder, the shortlist and the do-not table: what the drug evidence says for each direction

**Written:** 2026-09-18. **Step:** `step-7` (iteration 2). **Hypotheses:** **H045, H046, H047,
H048, H050** settled here (all supported; 0.80, 0.70, 0.60, 0.80, 0.70). H049 is
[112](112-two-decoy-cards-through-the-same-pipeline.md)'s. Claims filed in
[110](110-the-card-revised-and-the-claims-filed-before-the-search.md); the automated tables are
[111](111-the-automated-stages-literature-trials-and-labels-per-drug.md)'s.

## Question

The step's goal: *what does the drug evidence say for each direction?* Answered by placing every
approved drug on every direction it touches onto one rung of the pre-registered ladder, then
reading the four directions off the result — and by saying, in the same table, which drugs the
mechanism argues *against*.

## Hypothesis and prediction / What would refute it

Filed in 110, restated per claim in the verdicts below.

## Inputs

| Source | What was read |
|---|---|
| card v3 | the ladder rungs and rule; `anti_directions[].moa_pattern`; `case.context_standard_of_care`; `repurposing_directions[].context` |
| derived | `drug_candidates.tsv`, `trials.tsv` (110); `drug_mechanism_literature.tsv`, `pediatric_trials.tsv`, `labels.json` (111); `evidence.tsv` (110, 13 curated rows) |

## Method

`mva.drugs.ladder.assign`, one row per (drug, direction):

- **automated rung** — 5 if approved **and** a registered trial in the tumour context **and**
  a paediatric pointer (label section 8.4 or a study admitting children); 4 if a context trial;
  else 1. **Applied only to the direction the card marks `context: true` (D4).** On a
  mechanism direction the same trial is a fact about the tumour, and the automated rung stays 1.
- **curated rung** — the highest `evidence.tsv` row for that drug and direction (2 cell,
  3 in vivo), its PMIDs and whether every row is a proxy.
- **rung** = the higher of the two; both printed.
- **flags** — `A1`/`A2` when an anti-direction's `moa_pattern` matches the drug's action types or
  mechanism text; `standard_of_care`; `curated_only` (no source drugs a target for it);
  `approval_unverified` (no candidate row and no US label).

`mva.drugs.shortlist`: rows at rung ≥ 2, not standard of care, not anti-direction, on a named
direction; ordered curated-first, then rung, molecule-level before proxy, paediatric evidence,
literature. Verdict `argue` for a curated row, `context trial only – not a mechanism finding`
for an automated rung alone. The do-not table lists every flagged drug once with the card's
status for it.

### The refinement made after the first run — stated as such

The first grading run applied the trial-based rung on every direction. It put **85 drugs at
automated rung 5**, most on D1–D3, on the strength of a rhabdomyosarcoma trial and a paediatric
pointer — tetracycline on the proteostasis direction, fluconazole on the stress direction. The
decoy comparison (112) showed why: that rung is gene-independent. The rule was narrowed to the
tumour-context direction, the card gained `context: true` on D4 and a sentence in its ladder
rule, and the run was repeated from the cached tables. **This is a post-hoc change to a
pre-registered rule**, made before any verdict was committed and recorded here with the
before/after counts (91 → 61 shortlist rows; 85 → 62 drugs at rung 5, all 62 now on D4).

## Commands

```bash
uv run python tools/track2_enrich.py --skip-live     # after the rule change; zero requests
uv run mva-science evidence-add ... × 12             # rows 107-118
uv run mva-science verdict H045..H050 --commit ...   # revisions 3 (and 4 where the number was held)
uv run python tools/render_track2_figures.py
```

## Observed

```
evidence_ladder.tsv   432 rows   329 drugs
drugs by best rung    5: 62 · 3: 2 · 2: 5 · 1: 260
per direction         D1 30 drugs, 0 at rung >= 2 | D2 84, 4 | D3 50, 4 (2 at rung 3) | D4 205, 63 (62 at rung 5) | pathway 63, 0
shortlist.tsv          61 rows: 11 'argue' (a curated rung) + 50 'context trial only'
do_not.tsv             23 drugs: 13 caution (A2, spindle poisons) + 10 standard of care; 0 'do not' (no A1 drug is approved)
```

**The eleven rows the report may argue** (rank · drug · direction · rung · automated / curated · proxy · paediatric pointer):

| # | drug | dir. | rung | auto / cur. | proxy | paediatric | PMID |
|---|---|---|---|---|---|---|---|
| 1 | lovastatin | D4 | **5** | 5 / 2 | no | label 8.4 + child study | 41249736 |
| 2 | simvastatin | D4 | 5 | 5 / 2 | yes (lovastatin) | child study | 41249736 |
| 3 | nicotinamide | D3 | **3** | 1 / 3 | yes (NMN) | child study | 24825348 |
| 4 | niacin | D3 | 3 | 1 / 3 | yes (NMN) | child study | 24825348 |
| 5 | chloroquine | D2 | 2 | 1 / 2 | **no** | child study | 21315436 |
| 6 | bortezomib | D2 | 2 | 1 / 2 | yes (proteasome-inhibitor class) | label 8.4 + child study | 39247952, 31530568 |
| 7 | valproic acid | D3 | 2 | 1 / 2 | yes (HDAC2/3 loss) | label 8.4 + child study | 28985013, 19407811 |
| 8 | metformin | D2 | 2 | 1 / 2 | yes (AICAR) | label 8.4 + child study | 21315436 |
| 9 | vorinostat | D3 | 2 | 1 / 2 | yes (HDAC2/3 loss) | label 8.4 + child study | 28985013 |
| 10 | hydroxychloroquine | D2 | 2 | 1 / 2 | yes (chloroquine) | label 8.4 + child study | 21315436 |
| 11 | atorvastatin | D4 | 2 | 1 / 2 | yes (lovastatin) | label 8.4 + child study | 41249736 |

Lovastatin is the one row where a molecule-level curated result and the automated
tumour-context tests agree: a rhabdomyosarcoma trial exists for it, and the paper tested
lovastatin itself. Bortezomib also carries an automated rung 5 — on **D4**, where its
rhabdomyosarcoma trials belong; on D2 it is a rung-2 proxy, and the ladder keeps the two rows
apart.

**Direction D1 has no row.** Thirty approved drugs attach to D1's seed targets; none reaches
rung 2, and the one with a stated mechanism class — paclitaxel, a tubulin stabiliser — is caught
by anti-direction A2. The other D1 rows are DGIdb associations with no action type (omeprazole,
erythromycin, acitretin): not candidates, and not evidence against the claim either.

**The do-not table.** Thirteen spindle poisons carry `caution` — vincristine and vinorelbine
among them, which are also the tumour context's own backbone drugs — and ten standard-of-care
cytotoxics are named as considered and set aside. No approved drug matched A1 (further
checkpoint weakening): every Mps1/TTK and Aurora inhibitor in the candidate table is phase ≤ 3,
which is the fact behind the card's "none market-approved".

## Verdicts

| Id | Verdict | Conf. | Why, in one line |
|---|---|---|---|
| H045 (D1) | **supported** | 0.80 | 0 of 30 D1 drugs at rung ≥ 2; the one with a mechanism is a spindle poison in the do-not table. The action-type clause is untestable on DGIdb rows with no action type, and the neutral row says so |
| H046 (D2) | **supported** | 0.70 | chloroquine is molecule-level rung 2 (PMID 21315436); the other three D2 drugs are proxies and print it. Held down: cell results only, and F8 is unmeasured |
| H047 (D3) | **supported** | 0.60 | niacin and nicotinamide inherit rung 3 from NMN in BubR1-hypomorphic mice (PMID 24825348). The prediction's snapshot clause **failed** — no approved SIRT2-axis molecule came out of the automated stage (111) — and the refuting row carries it |
| H048 (D4) | **supported** | 0.80 | lovastatin: molecule-level rung 2 (PMID 41249736), automated 5, non-cytotoxic, paediatric pointers on both sides. The paper's in-vivo half is genetic, so curated stays 2 |
| H050 | **supported** | 0.70 | all 11 argued rows have a study admitting children; 8 have a label section. Held down: a pointer, not safety data |

The register shows revisions 2 → 3 → 4 for these claims. Revision 2 was committed at the
default 0.50 before its evidence rows had landed (a shell quoting error dropped the
`evidence-add` calls); revision 3 weighed the evidence; revision 4 wrote the held-down numbers
the reasoning had stated. The record is append-only, so the mistake is visible rather than
erased.

## Conclusion — what the drug evidence says, direction by direction

- **D1, reinforce the checkpoint: nothing to submit.** The direction is the do-not table.
- **D2, exploit aneuploidy stress: one molecule-level cell result** (chloroquine) and three
  proxies. A tumour-context and chemoprevention angle, argued from aneuploid cells in the
  literature, not from a measured burden in this child.
- **D3, stabilise the remaining BubR1: the mechanistically deepest lead and the thinnest
  automated support.** One mouse paper on the NAD⁺/SIRT2 axis, inherited by two approved
  precursors; an acetylation argument for HDAC inhibitors at class level.
- **D4, the child's tumour: statins**, with a molecule-level result in rhabdomyosarcoma cells
  and an existing trial — the direction the automated stage cannot distinguish from any
  cancer gene (112), so the curated rung is what carries it.

## Assumptions, limitations, quality checks

- **Limitation:** the curated rungs are one person's reading of thirteen abstracts; every row
  carries its PMID and its `proxy` flag so the reading can be checked and the inheritance seen.
- **Limitation:** rung 5 by the automated test is "already being tried in this tumour", which
  is why 50 of the 61 shortlist rows say *context trial only – not a mechanism finding*.
- **Limitation:** F8 — no measured aneuploid fraction; D2's whole argument inherits that gap.
- **Quality check:** the post-hoc rule change is recorded with counts before and after; no
  verdict was committed before it.
- **Quality check:** `tests/test_drugs_ladder.py` (12 tests) covers the rung arithmetic, the
  context-only rule, the flags, the shortlist order and the do-not table on an invented card.
