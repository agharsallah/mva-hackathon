# Track 2 — iteration 5 (2026-09-25)

**Standing:** draft — complete on 2026-09-25 from iteration 5, step 1. All five entries are filed
(158–162), `report.md` and `methods-form.json` are written in full, both deliverables are
rendered, and the pitch script is outlined shot by shot. **Not uploaded**: no pitch video
exists and no URL is published. Track 2 accepts **one** submission per team, due around 2026-10-20; the user plans to
merge the Track 2 iterations into one upload, and this folder is an input to that.

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
- **Which branch, and which test.** The whole choice turns on one unmeasured fact — is the
  missense protein unstable or inactive? EVPI is 0.180 and *all* of it sits on that fact; a
  cycloheximide-chase blot captures 0.106 of it (59 %) and stays worth running under every
  assumption swept, while the top-ranked drug flips under three of them (entry 161).
- **The routes move to a second disease by configuration.** All three re-ran on Bloom syndrome
  from case cards — 587 configuration lines plus 271 of one-time parameterisation against
  iteration 4's 378-line purpose-built driver — with every first-case table byte-identical, and
  with R3's control failing there and reported as failed (entry 162).

## How this folder answers the four judged criteria

| criterion | weight | report section | the evidence on disk |
|---|---|---|---|
| **Scientific rigor** | 35 % | §3–§7, §10 | entries [158](../../../docs/iteration5/step-1/methodology/158-the-stop-allele-can-be-read-through-and-it-is-not-the-lever.md)–[160](../../../docs/iteration5/step-1/methodology/160-every-bubr1-intervention-in-the-literature-with-a-verified-quote.md); a **positive control per route**, declared before the child's data were touched, with two controls reported as failed; `ressources/track2/it5/` (every table with a `.provenance.json`) |
| **Potential impact** | 25 % | §9 | `ressources/track2/it5/litmine_mva_exposures.tsv` (what MVA patients were actually given); `readthrough_candidates.tsv` (the aminoglycoside class ruled out on this child's own terms); [`decision_avoid.tsv`](../../../ressources/track2/it5/decision_avoid.tsv) (35 sourced avoid/caution rows); [161](../../../docs/iteration5/step-1/methodology/161-the-decision-and-what-the-next-measurement-is-worth.md)'s priced next measurement |
| **Innovation** | 25 % | §5–§8, §10 | a readthrough **context** model priced per allele against a dosage arithmetic; **proliferation-corrected** protein-level drug screening for a cell-cycle gene; a **code-enforced quote gate** over model-read literature; `src/mva/drugs/readthrough*`, `proteome*`, `signature_cc*`, `litmine_*` |
| **Scalability** | 15 % | §11 | measured, not asserted: entry [162](../../../docs/iteration5/step-1/methodology/162-the-three-routes-on-bloom-syndrome.md) re-ran R1–R3 on Bloom syndrome from case cards (`tools/it5_litmine_params_blm.py`, `mva.drugs.readthrough_case_blm`); `ressources/track2/it5/transfer/transfer_summary.tsv` holds the line counts, the control verdicts and the byte-identity check |

## What to upload

| Deliverable | File | Status |
|---|---|---|
| Report (PDF or Markdown) | [`agharsallah_track2_report.pdf`](agharsallah_track2_report.pdf), rendered from [`report.md`](report.md) | **ready** — 14 numbered sections plus an appendix, 15 embedded figures |
| Methods form | `agharsallah_track2_methods_form.xlsx`, from [`methods-form.json`](methods-form.json) | **complete** — rows 7–16 answered from entries 158–162; the abstract (row 16) is 482 words, under the 500-word limit |
| GitHub repository URL | `https://github.com/agharsallah/mva-hackathon` | public; code and committed tables only, no patient data |
| Pitch video URL (3 minutes) | **not recorded** — full shot-by-shot script in [`pitch-script.md`](pitch-script.md) | all 8 shots written; nothing filmed |

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
| **iteration 5, step 1, R4** | the decision analysis: the utility table over world-states, the derived readthrough prior, the 35-row avoid list, EVPI/EVPPI/EVSI, the exact flip points and the tornado | [161](../../../docs/iteration5/step-1/methodology/161-the-decision-and-what-the-next-measurement-is-worth.md) |
| **iteration 5, step 1, transfer check** | the same three routes re-run on Bloom syndrome: what the transfer cost in configuration and code, the byte-identity check on the first case, and R1's external check against a published measurement | [162](../../../docs/iteration5/step-1/methodology/162-the-three-routes-on-bloom-syndrome.md) |

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

# R4 — the decision and what the next measurement is worth (entry 161)
C=ressources/track2/it5
uv run python tools/it5_decision.py safety-drugs --out build/it5/r4/safety/drugs.tsv \
  --candidates $C/readthrough_candidates.tsv $C/protein_candidates.tsv $C/literature_candidates.tsv
uv run python tools/it5_decision.py run \
  --candidates $C/readthrough_candidates.tsv $C/protein_candidates.tsv $C/literature_candidates.tsv \
  --safety ressources/track2/it4/candidate_safety.tsv $C/candidate_safety.tsv --out $C
uv run python tools/render_it5_r4.py --work $C --out figures/it5   # figures/it5/r4-*.svg

# The second disease, and what the transfer cost (entry 162)
uv run python tools/it5_readthrough.py all --card mva.drugs.readthrough_case_blm
uv run python tools/it5_proteome.py run --target BLM --branch stop_allele
uv run python tools/it5_litmine.py corpus --card it5_litmine_params_blm
uv run python tools/it5_transfer_summary.py
uv run python tools/render_it5_s1.py                  # figures/it5/s1-transfer.svg

uv run python tools/record_track2_lineage.py      # track2.it5.* edges into warehouse.data_lineage
uv run python tools/check_coordinates.py
uv run python tools/check_step_narrative.py
uv run python tools/check_iteration.py submissions/track2/iteration-5

# The deliverables in this folder
uv run python tools/fill_methods_form.py --sheet "Track 2 methods" \
  --answers submissions/track2/iteration-5/methods-form.json \
  --out submissions/track2/iteration-5/agharsallah_track2_methods_form.xlsx
uv run python tools/md_to_html.py submissions/track2/iteration-5/report.md \
  build/track2-it5-report.html --repo-url https://github.com/agharsallah/mva-hackathon/blob/main
node tools/md_to_pdf.mjs build/track2-it5-report.html \
  submissions/track2/iteration-5/agharsallah_track2_report.pdf
```

Each route's exact flags live in its entry's `## Commands` section; the lines above are the
short form. The transfer commands write under `ressources/track2/it5/transfer/`.

## Before the upload

1. Both deliverables are built (the PDF from `report.md`, the xlsx from `methods-form.json`);
   re-render either one if its source changes — `tools/check_iteration.py` fails on a stale render.
2. Record the 3-minute pitch from `pitch-script.md` and paste the URL into the upload table above.
3. The user merges the Track 2 iterations into one folder; run `tools/check_iteration.py`;
   upload once; mark the uploaded folder frozen.

## Lineage

Every table this folder cites has a `.provenance.json` beside it under
`ressources/track2/it5/` (inputs with URL, sha256 and licence; parameters; assumptions;
limitations; validation; the producing entry), and each figure has one under `figures/it5/`.
Every table is now recorded in `warehouse.data_lineage` as `track2.it5.*` — **169 edges over 33
target tables**, of which **38 over 13 targets** are the Bloom-syndrome transfer's
(`track2.it5.transfer.*`, never mixed with the first case's). Appended 2026-09-25 by
`tools/record_track2_lineage.py` through `mva.warehouse.track2_lineage_it5`, which records a
table only once the methodology entry that built it is filed; R4's and the transfer's 126 edges
went in once entries 161 and 162 were filed. The transfer's manifests declare
`sources.clinical: "none"` and get no `clinical` edge: that case is published literature only,
with no patient and no HPO term.
The dashboard's `/submissions` page lists this folder, and `/steps?iteration=iteration5`
carries step 1 with its entries and figures.
