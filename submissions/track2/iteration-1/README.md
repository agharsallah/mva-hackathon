# Track 2 — iteration 1 (2026-09-18)

**Standing:** draft, **superseded by [`../iteration-2/`](../iteration-2/README.md) on 2026-09-19**
and never uploaded — kept for provenance (card v3, F8 unmeasured). Do not upload this folder.
Original standing: the report, the methods-form answers, the pitch script and the evidence
tables are written from iteration 2's step 7; **not uploaded**. Track 2 accepts **one**
submission per team, due around 2026-10-20 (intel §5), so this folder is re-read, re-rendered
and gated before it goes. Iteration 2's step 8 (the aneuploidy burden) may add one row to the
mechanism card before then; if it does, the report's fact table is regenerated, not edited.

## What this iteration is

Track 1 found and the oracle confirmed the child's two broken `BUB1B` copies. Track 2 asks
which market-approved medicines could act on the mechanism those copies imply, and grades every
candidate on a five-rung evidence ladder written before the search. Eleven drugs carry a cited
mechanism result; fifty more are already in rhabdomyosarcoma trials and are listed as such;
twenty-three are in the do-not table. The argument, the tables and the control are step 7's:
[`docs/iteration2/step-7/`](../../../docs/iteration2/step-7/README.md).

## What to upload

| Deliverable | File | Notes |
|---|---|---|
| Report (PDF or Markdown) | `agharsallah_track2_report.pdf`, rendered from [`report.md`](report.md) | filename carries the HF username, as the form asks |
| Methods form | `agharsallah_track2_methods_form.xlsx`, from [`methods-form.json`](methods-form.json) | sheet *Track 2 methods*, rows 7–16 |
| GitHub repository URL | `https://github.com/agharsallah/mva-hackathon` | public; code and committed tables only, no patient data |
| Pitch video URL (3 minutes) | **not recorded yet** — script in [`pitch-script.md`](pitch-script.md) | YouTube or Vimeo; record from the script and paste the link here before upload |
| Notes for judges (optional) | one line: *the report is written for a non-specialist; every claim links to a registered hypothesis and a methodology entry; the do-not table is the half we think matters most clinically* | |

There is **no predictions CSV** and no decode table for Track 2 — the panel reads the report.
`tools/check_iteration.py` knows this (it reads the track off the folder).

## How to read this folder

- [`report.md`](report.md) — the submission, in plain words: the mechanism (methods form Q14),
  the ladder, the eleven argued drugs, the fifty already-in-trials drugs, the do-not table, the
  decoy control, the limitations, and where every claim lives.
- [`methods-form.json`](methods-form.json) — the ten answers, row-numbered as the organisers'
  template lays them out; the abstract is under 500 words.
- [`pitch-script.md`](pitch-script.md) — the 3-minute video, shot by shot, with the figure each
  shot shows.
- The evidence itself is **not copied here**: the tables are `ressources/track2/*.tsv` (each
  with a `.provenance.json`), the figures `figures/track2/*.png`, the reasoning
  `docs/iteration2/step-7/methodology/110–113`.

## Which steps contributed

| Step | Contribution | Methodology |
|---|---|---|
| iteration 1, step 6 | the oracle confirmed the trans pair (full match at rank 1) — the mechanism argues from a confirmed genotype | [083](../../../docs/iteration1/step-6/methodology/083-oracle-reply-submission-1.md) |
| iteration 1, step 8 | the mechanism card (v1–v2), the data layer `mva.drugs`, H010/H011 | [078](../../../docs/iteration1/step-8/methodology/078-track2-data-layer.md) |
| iteration 2, steps 2–3 | no structural variant in the gene; both alleles at one copy; every exon at two copies (facts F2–F4) | [088](../../../docs/iteration2/step-2/methodology/088-the-alleles-the-reads-carry.md), [096](../../../docs/iteration2/step-3/methodology/096-the-alleles-at-their-multiplicity.md), [097](../../../docs/iteration2/step-3/methodology/097-copy-number-without-an-aligner.md) |
| iteration 2, step 4 | the missense's pathogenicity lane; P(trans) undetermined (F6, F7) | [099](../../../docs/iteration2/step-4/methodology/099-every-gene-ordered-with-nothing-filtered-out.md), [101](../../../docs/iteration2/step-4/methodology/101-the-phase-that-cannot-be-measured.md) |
| iteration 2, step 5 | the missense sits outside every curated domain (F5) | [106](../../../docs/iteration2/step-5/methodology/106-where-the-missense-sits-in-the-protein.md) |
| iteration 2, step 6 | the blind mirror found the same pair (F9) | [109](../../../docs/iteration2/step-6/methodology/109-what-the-mirror-found.md) |
| **iteration 2, step 7** | card v3; the ladder; the shortlist and do-not table; the decoy control; H045–H050 | [110](../../../docs/iteration2/step-7/methodology/110-the-card-revised-and-the-claims-filed-before-the-search.md)–[113](../../../docs/iteration2/step-7/methodology/113-the-ladder-the-shortlist-and-the-do-not-table.md) |
| iteration 2, step 8 | **pending** — the aneuploidy burden (F8) | — |

Both datasets: the genomic data fixed the gene and the alleles; the clinical terms fixed the
disease, the tumour context (rhabdomyosarcoma) and, through it, direction D4 and the paediatric
questions.

## Regenerate this folder

```bash
uv run mva-drugs snapshot
uv run python tools/track2_decoys.py --symbol NTRK3 --uniprot Q16288 --protein "NT-3 growth factor receptor (TrkC)" --pattern "NTRK|neurotrophin|Trk" --picked-by "seeded draw from results.it2_decoys"
uv run python tools/track2_decoys.py --symbol XDH --uniprot P47989 --protein "xanthine dehydrogenase/oxidase" --pattern purine --picked-by "an unrelated, well-drugged metabolic enzyme"
uv run python tools/track2_enrich.py
uv run python tools/render_track2_figures.py
uv run python tools/md_to_html.py submissions/track2/iteration-1/report.md build/track2-report.html --repo-url https://github.com/agharsallah/mva-hackathon/blob/main
node tools/md_to_pdf.mjs build/track2-report.html submissions/track2/iteration-1/agharsallah_track2_report.pdf
uv run python tools/fill_methods_form.py --sheet "Track 2 methods" --answers submissions/track2/iteration-1/methods-form.json --out submissions/track2/iteration-1/agharsallah_track2_methods_form.xlsx
uv run python tools/check_iteration.py submissions/track2/iteration-1
```

## Before the upload

1. Record the 3-minute pitch from `pitch-script.md`; paste the URL into the table above.
2. If step 8 has run, regenerate the card's fact table in the report and re-render.
3. Re-run `tools/check_iteration.py`; set this README's standing to *ready*; re-render the PDF.
4. Upload once. Then mark this README frozen (the gate reads that word in bold at the top) and never edit the folder again.

## Lineage

Every table this folder cites has a `.provenance.json` beside it and a row set under
`target_schema = 'track2'` in `warehouse.data_lineage` (63 edges after step 7); the dashboard's
`/track2` page shows the card, the ladder, the shortlist, the do-not table, the decoy control
and the lineage graph, all read from the same files.
