# Track 2 — iteration 5 (2026-09-25)

**Standing:** draft — scaffolded 2026-09-25 from iteration 5, step 1. Entries 158–160 are filed;
route R4 (decision + value of information) is not, so `report.md`, the §1 scorecard, the
answer-in-one-page, the impact section and the method abstract are still open. **Not uploaded**,
nothing rendered. Track 2 accepts **one** submission per team, due around 2026-10-20; the user
plans to merge the Track 2 iterations into one upload, and this folder is an input to that.

Opened by hand, not with `tools/new_iteration.py`: that tool would freeze another iteration and
bump `ITERATION`, neither of which is wanted here.

## What this iteration answers, in one line each

- **Allele-first.** Start from the child's two `BUB1B` copies and the protein, not from drug
  databases — the shape iterations 2 and 4 showed was needed (entries 142, 153, 154, 155).
- **The stop copy is not the lever.** It is NMD-competent and loses the kinase domain; even a
  perfect readthrough agent adds a fraction of the gap, while stabilising the missense protein
  would close it (entry 158).
- **No approved drug raises BubR1 protein by much** once proliferation is corrected for, and the
  strongest raisers point at degradation (entry 159).
- **The literature holds the mechanism a database cannot express**, with a code-verified quote
  per row — plus MVA patients' own drug-exposure record (entry 160).
- **Which branch, and which test.** TODO (part B): route R4's decision and the value of the
  cycloheximide-chase measurement.

## How this folder answers the four judged criteria

| criterion | weight | report section | the evidence on disk |
|---|---|---|---|
| **Scientific rigor** | 35 % | §3–§7, §10 | entries [158](../../../docs/iteration5/step-1/methodology/158-the-stop-allele-can-be-read-through-and-it-is-not-the-lever.md)–[160](../../../docs/iteration5/step-1/methodology/160-every-bubr1-intervention-in-the-literature-with-a-verified-quote.md); a **positive control per route**, declared before the child's data were touched, with two controls reported as failed; `ressources/track2/it5/` (every table with a `.provenance.json`) |
| **Potential impact** | 25 % | TODO (part B) | `ressources/track2/it5/litmine_mva_exposures.tsv` (what MVA patients were actually given); `readthrough_candidates.tsv` (the aminoglycoside class ruled out on this child's own terms); R4's per-branch recommendation |
| **Innovation** | 25 % | §5–§7, §8 | a readthrough **context** model priced per allele against a dosage arithmetic; **proliferation-corrected** protein-level drug screening for a cell-cycle gene; a **code-enforced quote gate** over model-read literature; `src/mva/drugs/readthrough*`, `proteome*`, `signature_cc*`, `litmine_*` |
| **Scalability** | 15 % | §9 | every route is a case-agnostic module parameterised by a card (`tools/it5_litmine_params.py`, the readthrough case module), one driver per route under `tools/`, one table contract with a `branch` column |

## What to upload

| Deliverable | File | Status |
|---|---|---|
| Report (PDF or Markdown) | `agharsallah_track2_report.pdf`, to render from `report.md` | **TODO (part B)** — `report.md` not yet written |
| Methods form | `agharsallah_track2_methods_form.xlsx`, from [`methods-form.json`](methods-form.json) | rows 7–15 filled from entries 158–160; rows 8 (R4 paragraph), 15 (R4 time) and 16 (abstract) carry TODOs |
| GitHub repository URL | `https://github.com/agharsallah/mva-hackathon` | public; code and committed tables only, no patient data |
| Pitch video URL (3 minutes) | **not recorded** — outline in [`pitch-script.md`](pitch-script.md) | shots 7–8 TODO |

No predictions CSV, selectors or decode table: Track 2 is panel-judged, and
`tools/check_iteration.py` applies the Track 2 rules to this folder.

## How to read this folder

- [`methods-form.json`](methods-form.json): the ten answers, keyed by template row.
- [`pitch-script.md`](pitch-script.md): the 3-minute video, shot by shot.
- The evidence is **not copied here**; the folder links to it. The step's written summary and
  one caption per figure live in
  [`docs/iteration5/step-1/narrative.json`](../../../docs/iteration5/step-1/narrative.json).

## Which steps contributed

| step | contribution | methodology |
|---|---|---|
| Track 1, iteration 1, step 6 | the oracle confirmed the pair (the one input from outside) | [083](../../../docs/iteration1/step-6/methodology/083-oracle-reply-submission-1.md) |
| iteration 4, step 1 | the normalised allele records R1 reads the stop's consequence and offset from | [114](../../../docs/iteration4/step-1/methodology/114-one-record-per-allele-and-what-it-can-be-spelled-as.md) |
| iteration 4, step 9 | reused as is: the stability atlas and published alleles (the unstable/inactive fork), the phenotype twin, the per-child safety method | [149](../../../docs/iteration4/step-9/methodology/149-the-stability-atlas-and-the-childs-missense.md), [150](../../../docs/iteration4/step-9/methodology/150-the-childs-phenotype-twin-among-mgi-mice.md), [152](../../../docs/iteration4/step-9/methodology/152-is-each-candidate-safe-for-this-child.md) |
| iteration 4, step 10 | the failures that set iteration 5's shape (convergence at chance; the sweep past correction) | [154](../../../docs/iteration4/step-10/methodology/154-screen-wide-prism-sweep.md), [155](../../../docs/iteration4/step-10/methodology/155-convergence-and-checks.md) |
| **iteration 5, step 1** | R1 stop-codon readthrough + allele dosage; R2 proliferation-corrected proteomics + corrected LINCS; R3 quote-verified literature mining | [158](../../../docs/iteration5/step-1/methodology/158-the-stop-allele-can-be-read-through-and-it-is-not-the-lever.md), [159](../../../docs/iteration5/step-1/methodology/159-which-drugs-raise-bubr1-protein-once-proliferation-is-removed.md), [160](../../../docs/iteration5/step-1/methodology/160-every-bubr1-intervention-in-the-literature-with-a-verified-quote.md) |
| iteration 5, step 1, R4 | the decision analysis and the value of the separating lab test | **TODO (part B)** |

**Both datasets.** The genome fixed the gene and the two allele classes, and gave R1 the stop's
sequence context (the coding offset never left `build/`; no position appears in any table or
figure). The clinical terms decided usability: nephrocalcinosis (HP:0000121) rules out the
aminoglycoside class independently of its predicted effect; rhabdomyosarcoma (HP:0002859)
argues against RNA-incorporating and cytotoxic chemotypes and makes the published
vincristine/taxol warning directly relevant; short stature (HP:0004322) is what makes the four
growth-hormone reports matter; failure to thrive and muscle atrophy (HP:0001508, HP:0003202)
bound how a 15 % protein rise may be read.

## Regenerate this folder

The route commands are in each entry's `## Commands` section. In order:

```bash
uv run python tools/it5_readthrough.py all        # entry 158 → readthrough, allele_dosage, candidates
uv run python tools/render_it5_r1.py              # figures/it5/r1-*.svg
uv run python tools/it5_proteome.py run           # entry 159 → proteome_{hits,control}.tsv
uv run python tools/it5_lincs_cc.py control       # entry 159 → lincs_cc_control.tsv
uv run python tools/it5_proteome.py candidates    # → protein_candidates.tsv
uv run python tools/render_it5_r2.py              # figures/it5/r2-*.svg
uv run python tools/it5_litmine.py corpus         # entry 160 → litmine_corpus.tsv
uv run python tools/it5_litmine.py screen
uv run python build/it5/r3/extract_rows.py
uv run python tools/it5_litmine.py verify         # the quote gate
uv run python tools/it5_litmine.py translate      # → literature_candidates.tsv
uv run python tools/render_it5_r3.py              # figures/it5/r3-*.svg
uv run python tools/record_track2_lineage.py      # track2.it5.* edges into warehouse.data_lineage
uv run python tools/check_coordinates.py
uv run python tools/check_iteration.py submissions/track2/iteration-5
```

TODO (part B): R4's commands, then the report render
(`tools/md_to_html.py` → `tools/md_to_pdf.mjs`) and `tools/fill_methods_form.py`.

## Before the upload

1. File R4's entry; finish `report.md`, the methods form's three TODOs and the pitch script.
2. Render the PDF and the xlsx; record the 3-minute pitch and paste the URL above.
3. The user merges the Track 2 iterations into one folder; run `tools/check_iteration.py`;
   upload once; mark the uploaded folder frozen.

## Lineage

Every table this folder cites has a `.provenance.json` beside it under
`ressources/track2/it5/` (inputs with URL, sha256 and licence; parameters; assumptions;
limitations; validation; the producing entry), and each figure has one under `figures/it5/`.
The filed routes' tables are recorded in `warehouse.data_lineage` as `track2.it5.*`
(43 edges, appended 2026-09-25 by `tools/record_track2_lineage.py` through
`mva.warehouse.track2_lineage_it5`, which records a table only once its entry is filed).
The dashboard's `/submissions` page lists this folder, and `/steps?iteration=iteration5`
carries step 1 with its entries and figures.
