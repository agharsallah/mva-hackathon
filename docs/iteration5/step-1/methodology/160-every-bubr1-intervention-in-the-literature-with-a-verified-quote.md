# 160 — Every intervention the literature reports on BubR1, each backed by a verified quote

**Step:** iteration 5, [step 1](../README.md), route R3. **Date:** 2026-09-25. **Claims:** none — exploratory, a positive control instead ([note](../../notes/exploratory-no-hypotheses.md)).

## Question

Iterations 2 and 4 asked drug databases what to give this child, and the databases answered with
hubs and noise (entries 142, 153, 154). The leads that survived came from *papers*: NAD⁺/SIRT2
raising BubR1 in hypomorph mice, and clearing senescent cells in BubR1 progeroid mice. No
database encodes the sentence "compound X raises BubR1 protein".

So: **read the literature as a data source.** Build a corpus for `BUB1B`/BubR1 from topic
queries, let the model read it, and write one structured row per reported intervention —
`intervention, type, mode, target, effect_on, direction, model_system, pmid, quote`. Then have
**code**, not the model, decide whether each row is evidence: the quoted sentence must appear
verbatim in the cached text of the paper it cites, or the row is rejected.

Two halves:

1. **interventions** — what changes BubR1 level, its acetylation, its function, or the
   downstream phenotypes (aneuploidy, senescence, lifespan, tumours)?
2. **exposures** — what were MVA patients in the published case reports *actually given*, and
   what happened? That is safety evidence from the child's own disease, not from a model.

## Positive control (declared in writing before any query ran)

- The corpus queries are written from the gene symbol, its protein aliases and topic words only.
  **No PMID, author name or paper title is typed into any query** (`tools/it5_litmine_params.py`
  is the whole case card; the query text is in `litmine_corpus.provenance.json`).
- **Part 1, retrieval:** the queries must retrieve PMID 24825348 (North 2014, SIRT2/NAD⁺ raise
  BubR1), 18516091 (Baker 2008, p16^Ink4a in BubR1-insufficient ageing) and 22048312 (Baker 2011,
  clearance of p16^Ink4a-positive cells).
- **Part 2, extraction:** the verified table must hold at least one kept row per control PMID
  whose `effect_on`/`direction` states that paper's known finding.
- Recall is reported as n/3 for each part; below 3/3 the route is uninterpretable.

**Result: retrieval 3/3, extraction 3/3 — the control passes.** `passed: true` is written into
`litmine_interventions.provenance.json` and into every candidate row's
`positive_control_passed` column.

## Inputs

| input | version / identity | role |
|---|---|---|
| Europe PMC `/search` | queried 2026-09-25, `resultType=core`, `SRC:MED` | corpus metadata + abstracts; 6 queries (5 gene × topic, 1 disease phrase) |
| Europe PMC `/{PMCID}/fullTextXML` | same day | open-access full text (JATS XML) for the 307 papers that have one |
| ChEMBL | EBI REST, `max_phase` as served | drug names → molecules; gene symbols → targets → mechanism of action + action type |
| `ressources/hackathon-rules/Challenge_Clinical_Phenotype_1.md` | the proband's 8 HPO terms | the `hpo_overlap` column of the exposure table; which exposures matter for *this* child |
| `ressources/track2/it5/litmine_corpus.tsv` + `build/it5/r3/docs/*.txt` | sha256 per text | the bytes the quote verifier checks against |

Code (case-agnostic, parameterised by the card): `mva.drugs.litmine_corpus` (queries, fetch,
JATS prose, per-text sha256), `litmine_screen` (lexical screen → reading packs),
`litmine_verify` (the quote gate + field vocabulary), `litmine_translate` (ChEMBL mapping,
direction check, rubric, candidates). Drivers `tools/it5_litmine.py`,
`tools/it5_litmine_params.py` (the BUB1B card), `tools/render_it5_r3.py`.

## Commands

```bash
uv run python tools/it5_litmine.py corpus      # 6 queries → 767 papers → 1,065 cached texts
uv run python tools/it5_litmine.py screen      # → build/it5/r3/reading/{interventions,exposures}.md
uv run python build/it5/r3/extract_rows.py     # the reader's rows → litmine_*_extraction.tsv
uv run python tools/it5_litmine.py verify      # the quote gate → interventions / exposures / rejected
uv run python tools/it5_litmine.py translate   # → literature_candidates.tsv
uv run python tools/render_it5_r3.py           # figures/it5/r3-*.svg
uv run pytest -q tests/test_drugs_litmine.py   # 13 passed
uv run python tools/check_coordinates.py       # clean
```

## Method, in software terms

| stage | who does it | what it guarantees |
|---|---|---|
| corpus | code | every text is a file with a sha256 in `litmine_corpus.tsv`; a quote is checked against *that* byte stream |
| screen | code | the reader sees sentences naming the subject **and** an effect **and** an intervention cue — a recall ceiling, stated as such |
| extraction | the model (claude-opus-5-5, this subagent, 2026-09-25) | judgement: which sentence is a finding, and what it says |
| **gate** | **code** | a quote that is not a verbatim substring of the cached text is **rejected, never repaired**; a field outside the pinned vocabulary is rejected too |
| translation | code | a drug must act in the same direction as the experiment it is standing in for |

Normalisation before comparison is limited to what differs between two renderings of the same
sentence — Unicode NFKC, typographic quotes and dashes folded to ASCII, zero-width characters
dropped, whitespace runs collapsed. **No word is ever changed.** Case is kept, and a quote under
30 characters is rejected as too short to identify a paper.

## Output (observed numbers)

**Corpus.** 6 queries → 767 distinct papers, 760 of which yielded a text; 1,065 cached texts
(758 abstracts, 307 open-access full texts); 1 full text failed after three retries and is named
in the manifest.
Per-query hit counts are in `litmine_corpus.provenance.json` (`parameters.query_log`): level
275, modification 243, rescue 192, ageing 92, aneuploidy 238, `"mosaic variegated aneuploidy"`
90. Every query took one page, so no query was truncated.

**Screen.** 1,109 sentences in 283 papers passed the intervention screen; 57 sentences in 26 of
the 107 MVA-mentioning papers passed the exposure screen.

**Extraction and the gate.** 30 intervention rows and 12 exposure rows written
(`litmine_extraction.tsv`, `litmine_exposure_extraction.tsv` — the unverified input to the gate,
carried with their sha256 in the verify manifest's `inputs`); **42 kept, 0 rejected**. Zero rejections is not evidence the gate works, so the gate is tested two ways:
`tests/test_drugs_litmine.py` mutates one word of a true quote (`increases` → `decreases`) and
asserts `quote_not_in_source`, and also covers the too-short, unknown-PMID and bad-vocabulary
paths.

**What the 30 rows say** (`figures/it5/r3-evidence-map.svg`):

| what raises BubR1 protein | model | PMID |
|---|---|---|
| NMN (NAD⁺ precursor) — and SIRT2 overexpression, same sentence | mouse, in vivo | 24825348 |
| trichostatin A (deacetylase inhibition) | human cells | 19407811 |
| MG132 (proteasome inhibition) | human cells | 19407811, 14576821 |
| K250Q acetylation-mimetic BubR1 (genetic) | human cells | 19407811 |
| DNA promoter demethylation; 5-aza-2′-deoxycytidine releases MBD2/HDAC1 from the promoter | human cells | 17464181 |
| UPCP (progerin C-terminal peptide) and FTI-277 (farnesyltransferase inhibition) | human cells + mouse | 37118121 |
| restoring a `BUB1B` copy in PCS/MVA patient cells (chromosome transfer) | human patient cells | 16411201 |

| what helps downstream | model | PMID |
|---|---|---|
| clearing p16^Ink4a-positive senescent cells: less senescence, longer healthspan, less sarcopenia/fat loss/cataract | mouse, in vivo | 22048312, 23300461 |
| p16^Ink4a inactivation in BubR1-insufficient mice: less senescence and ageing | mouse, in vivo | 18516091 |
| BubR1 overexpression: less aneuploidy, fewer tumours, longer healthy lifespan, bigger brain in the hypomorph | mouse, in vivo + cells | 23242215, 27528194, 27848932, 30609266 |
| sFRP3 inhibition rescues body/brain size and neurogenesis in `BubR1^H/H` mice | mouse, in vivo | 30609266 |
| UPCP extends median survival 17 % in a progeroid mouse | mouse, in vivo | 37118121 |

| harm rows — things that **lower** BubR1 (safety signals) | model | PMID |
|---|---|---|
| SU6656 / geraldol drive proteasomal BubR1 degradation | human cells | 21441410 |
| CHK1 knockdown: BubR1 protein −77 % | human cells | 19778378 |
| LSD1 knockdown lowers BUBR1 protein | human cells | 20189264 |
| PELI1 (E3 ligase) overexpression destabilises BubR1 | human cells | 28410192 |
| p19^Arf inactivation *worsens* senescence and ageing in BubR1 mutants | mouse, in vivo | 18516091 |

One deliberately awkward row is kept: SIRT2 **knockdown** raises K250 acetylation but leaves
total BubR1 unchanged (25285631, `direction = no_change`). North's effect is on **K668** in vivo;
the cell-line K250 site does not reproduce it. A route that only recorded the convenient rows
would have hidden that.

**Translation to drugs.** 20 intervention groups → 37 drug mappings → **24 candidate rows**
(`literature_candidates.tsv`), every one carrying `positive_control_passed = true`. Only rows
whose reported direction is the one a hypomorph wants become candidates; the rest stay in the
table as evidence.

| candidate | strength | why | branch |
|---|---|---|---|
| nicotinamide, niacin | 0.192 | approved NAD⁺ precursors, standing in for NMN (24825348) | missense_unstable |
| bortezomib, carfilzomib | 0.192 | approved proteasome inhibitors, standing in for MG132 (19407811, 14576821) | missense_unstable |
| vorinostat, romidepsin, belinostat, panobinostat, valproic acid | 0.144 | approved HDAC inhibitors, standing in for TSA (19407811) | missense_unstable |
| decitabine, azacitidine | 0.144 | approved hypomethylating agents, standing in for promoter demethylation (17464181) | missense_unstable |
| lonafarnib, tipifarnib | 0.144 / 0.072 | farnesyltransferase inhibitors, standing in for FTI-277 (37118121) | missense_unstable |
| dasatinib | 0.134 | approved senolytic partner, standing in for senescent-cell clearance (22048312) | any |
| nicotinamide riboside, quercetin, fisetin, navitoclax | 0.096 / 0.067 | same two classes, not market-approved | missense_unstable / any |
| NMN, MG132, TSA, FTI-277, UPCP | 0.108–0.144 | the tool compounds themselves, unapproved | missense_unstable |

`evidence_strength` = model × directness × replication × translation:

| axis | values |
|---|---|
| model | human_patient 1.0 · mouse_in_vivo 0.8 · human_cells 0.6 · mouse_cells 0.5 · other 0.4 |
| directness | bubr1_level 1.0 · function 0.9 · acetylation / aneuploidy 0.8 · lifespan 0.7 · senescence / tumour / other 0.6 |
| replication | 1 paper 0.6 · 2 papers 0.8 · ≥3 papers 1.0 (reviews excluded) |
| translation | the drug itself, approved 1.0 · itself, unapproved 0.3 · gene analogue approved 0.6 · class analogue approved 0.4 · class analogue unapproved 0.2 |

The ceiling is low by construction: no row scores above 0.192, because nothing here was measured
in a patient and every approved drug is a *class analogue* of the compound that was tested.

**What the gene → drug path returned: nothing.** ChEMBL holds a human target for `SIRT2`,
`CDKN2A`, `PELI1` and `BUB1B` but **zero** mechanism-of-action molecules against any of them, and
no target at all for `SFRP3`/`FRZB`. Every approved candidate above therefore comes from a
*declared* class analogue, written down in the case card where a reader can argue with it — not
from a database that quietly had the answer.

**The direction check, and what it caught.** Two knockdown rows that *lowered* BubR1 do map to
real drugs: `CHEK1` → 9 inhibitors (azd-7762, prexasertib, rabusertib, ucn-01 and five more,
phases 1–2) and `KDM1A` → bomedemstat (phase 3), all `direction_check = match` for a *knockdown*.
Matching the knockdown is exactly why they must not be candidates: the polarity filter drops
them because the effect they reproduce is a **fall** in BubR1. They are recorded in
`build/it5/r3/translation.json` as drugs to keep away from this child. No `mismatch` arose in
this run (no analogue class was declared against its own direction), so the mismatch branch is
exercised by `tests/test_drugs_litmine.py`, not by live data.

**MVA patients' real drug exposures** (12 verified rows, `figures/it5/r3-mva-exposures.svg`):

- **Same gene as the child.** A boy with biallelic `BUB1B` PCS/MVA and bilateral Wilms tumour
  received **dactinomycin** monotherapy; "severe adverse reaction prevented the patient from
  receiving further chemotherapy" (31081598). Chemotherapy was abandoned for surgery + dialysis.
- **A published warning about the child's own tumour type.** In a `BUB1B` PCS/MVA case report:
  "It might be important therefore for PCS/MVA patients to **avoid antimitotic drugs such as
  vincristine or taxol**…" (28611924). Vincristine is standard in rhabdomyosarcoma regimens, and
  rhabdomyosarcoma (HP:0002859) is the proband's presenting tumour.
- **Transplant.** The one reported HSCT in MVA1: treosulfan-based reduced-intensity conditioning
  was "well tolerated" with full haematologic recovery, then rapid graft rejection, pancytopenia,
  sepsis and death on day +156 (31053147). Two rows, `tolerated` and `death`, from one case.
- **Growth hormone does not work in MVA.** Four independent reports (35434947 ×2, 36588761,
  12116237) say GH gave an unsatisfactory or absent response in MVA patients; one adds that GH
  "might have not been prescribed" had the cancer risk been known (30147898). The proband has
  short stature (HP:0004322) — GH is the obvious symptomatic drug, and the disease literature
  says it does not help and may be unwise.
- **Class statement.** Children with genomic-instability disorders show "exquisite sensitivity to
  anticancer treatments such as ionizing radiation and chemotherapy" (39264246); patient
  fibroblasts from another MVA gene were *more resistant* to paclitaxel and etoposide (37796616).
  The two statements point in opposite directions and are both recorded.

## Conclusion

1. **The positive control passes both halves (3/3, 3/3).** Written without seeding, the queries
   retrieve the three landmark papers, and the extraction reproduces each one's known finding.
   This is a *validated method applied once*, not a tested hypothesis.
2. **The literature does contain the mechanism a database cannot express.** Seven distinct ways
   to raise BubR1 protein are on record with a verified sentence each; four of them have an
   approved drug or approved class analogue.
3. **The database has nothing to say about these targets.** `SIRT2`, `CDKN2A`, `PELI1`, `BUB1B`
   carry no mechanism-of-action molecule in ChEMBL and `SFRP3` no target at all: the gene → drug
   path returns zero rows. Every approved candidate comes from a class analogue declared in the
   case card. That is the same lesson as entries 142/153/154, reached from the other side.
4. **Safety evidence exists from the disease itself**, and it is specific: dactinomycin toxicity
   in a `BUB1B` patient, a published warning against vincristine and taxol in PCS/MVA, growth
   hormone repeatedly ineffective. These are quote-verified rows, not inferences from a label
   database (contrast entry 155, which had to infer collisions from label text).
5. **The strongest candidates are the ones iteration 4 already found by hand** — NAD⁺ precursors
   (0.192) and senolytics (dasatinib 0.134) — and the route re-derives them *mechanically*, which
   is the point. It also adds four classes iteration 4 never had: proteasome inhibitors (0.192),
   HDAC inhibitors (0.144), hypomethylating agents (0.144) and farnesyltransferase inhibitors
   (0.144). Every one of the four acts on BubR1 **stability or transcription**, so all four sit on
   the `missense_unstable` branch and are worth nothing if the child's missense protein is
   inactive rather than unstable — which is exactly the question R1 and R4 ask.

## Limits

- **A verified quote proves the sentence exists, not that the row reads it correctly.** The gate
  is a forgery check, not a comprehension check. Two independent readers would be the next step.
- **The screen is a recall ceiling.** A finding phrased without a subject word, an effect word
  and an intervention cue in the *same sentence* never reached the reader: 1,109 of the corpus's
  79,435 sentences were read (1.4 %).
- **Review articles were excluded from the rows** (e.g. two reviews restate North 2014's NAD⁺
  result), so `replication` counts independent studies. That lowers apparent replication for
  NAD⁺ and is the honest choice.
- **One page per query, `SRC:MED` only.** Preprints, non-MEDLINE records and papers whose
  abstract never names the gene are outside the corpus by construction.
- **Only 307 of 767 papers have open-access full text.** For the rest, a finding stated only in
  the body is invisible.
- **`evidence_strength` is a stated heuristic**, not a probability: model × directness ×
  replication × translation, each factor a number in a table in `litmine_translate.RUBRIC`. It
  ranks; it does not calibrate.
- **No dose, no route, no paediatric data.** Every candidate is a literature lead. This is a
  research exercise; no row advises for or against giving any drug to any patient.
- **Harm rows do not yet produce inverted candidates.** That PELI1 *inhibition* should raise
  BubR1 is a reasonable inference the code deliberately does not make.

## Both datasets

- **Genomic.** The route is keyed to the gene and the two allele classes, never to a position:
  the `branch` column says whether an effect can help the `stop_allele` (nothing to stabilise),
  a `missense_unstable` protein (level and acetylation routes) or a `missense_inactive` one
  (function routes); downstream effects are `any`. `tools/check_coordinates.py` is clean.
- **Clinical.** The exposure table's `hpo_overlap` column names the proband's own HPO terms:
  rhabdomyosarcoma (HP:0002859) against the vincristine/taxol warning and the dactinomycin
  toxicity; short stature (HP:0004322) against four growth-hormone reports. The intervention
  table also touches the clinical picture through the phenotypes it scores — sarcopenia and
  muscle wasting in the BubR1 hypomorph is the mouse counterpart of the child's skeletal muscle
  atrophy (HP:0003202) and failure to thrive (HP:0001508).
- A row that uses only one source says so: every intervention row is genomic/mechanistic only,
  and every exposure row names its clinical overlap or states "none directly".

## Figures

- `figures/it5/r3-extraction-funnel.svg` — papers → texts → screened sentences → rows written →
  rows past the quote gate → candidate rows, on a log axis.
  > **Legend** — the raw input; neutral machinery; a decision point; good / safe / the goal.
  > Log x-axis, so a short bar is still hundreds.
- `figures/it5/r3-evidence-map.svg` — intervention × effect, one square per verified row.
  > **Legend** — green good / safe / the goal (the direction a hypomorph wants); red broken /
  > dangerous (the wrong direction); grey context, not the subject (no agreed good direction).
  > A big square is an animal or a patient, a small one is cells.
- `figures/it5/r3-mva-exposures.svg` — what MVA patients were given and how it went.
  > **Legend** — green tolerated; yellow a response question; red toxicity or death; blue an
  > advisory statement.
