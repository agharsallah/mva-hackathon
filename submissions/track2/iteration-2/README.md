# Track 2 — iteration 2 (2026-09-19)

**Standing:** draft — the curated report, the methods-form answers, the pitch script and the
evidence tables, written from **all eight steps of iteration 2** and the mechanism card at
**version 4**; **not uploaded**. Supersedes [`../iteration-1/`](../iteration-1/README.md),
which was drafted from step 7 alone (card v3, F8 unmeasured) and was never uploaded. Track 2
accepts **one** submission per team, due around 2026-10-20 (intel §5).

## What changed since iteration 1

| | iteration 1 (2026-09-18) | iteration 2 (2026-09-19) |
|---|---|---|
| mechanism card | v3 — F8 *unmeasured* | **v4 — F8 measured** by step 8: no autosome above its 2–3 % detection limit in the sequenced sample ([120](../../../docs/iteration2/step-7/methodology/120-the-card-at-version-4-and-the-second-submission-draft.md)) |
| direction D2 | argued from the literature, gap stated | **literature only**, ranked below D3 and D4 for a measured reason |
| the ladder | 11 argued · 50 context-trial-only · 23 set aside | **identical, byte for byte** — pre-registered and tested (H061); the test also caught a file-reading fault, fixed |
| the report | the drug section | the whole path: steps 1–6 (the blind rediscovery), step 8 (the burden), step 7 (the grading), with what each step gave the drug argument |
| claims cited | H045–H050, H011 | + H061, H051–H053 (step 8), H041/H043 (step 6) |

## What to upload

| Deliverable | File | Notes |
|---|---|---|
| Report (PDF or Markdown) | `agharsallah_track2_report.pdf`, rendered from [`report.md`](report.md) | filename carries the HF username, as the form asks |
| Methods form | `agharsallah_track2_methods_form.xlsx`, from [`methods-form.json`](methods-form.json) | sheet *Track 2 methods*, rows 7–16; abstract under 500 words |
| GitHub repository URL | `https://github.com/agharsallah/mva-hackathon` | public; code and committed tables only, no patient data |
| Pitch video URL (3 minutes) | **not recorded yet** — script in [`pitch-script.md`](pitch-script.md) | YouTube or Vimeo; record from the script, paste the link here |
| Notes for judges (optional) | *the report is written for a non-specialist; every claim links to a registered hypothesis and a methodology entry; the pipeline ran on two decoy genes as its own control; the do-not table is the half we think matters most clinically* | |

No predictions CSV, selectors or decode table: Track 2 is panel-judged, and
`tools/check_iteration.py` applies the Track 2 rules to this folder.

## How to read this folder

- [`report.md`](report.md) — §1 the answer in one page; §2 the whole path as one diagram; §3
  steps 1–6 and 8, what each measured and what it gave the drug argument; §4 the mechanism
  (methods form Q14) and the nine measured facts; §5 the search, the ladder and the decoy
  control; §6 the eleven argued drugs in the order the report argues them, the fifty already in
  trials, the do-not table, the paediatric pointers; §7 what it cannot tell you; §8
  reproducibility; §9 where every claim lives.
- [`methods-form.json`](methods-form.json) — the ten answers, row-numbered as the template lays
  them out.
- [`pitch-script.md`](pitch-script.md) — the 3-minute video, shot by shot, with the figure each
  shot shows.
- The evidence itself is **not copied here**: tables `ressources/track2/*.tsv` (a
  `.provenance.json` each), figures `figures/track2/*.png`, reasoning
  `docs/iteration2/step-7/methodology/110–114, 120`, the genotype steps
  `docs/iteration2/step-1 … step-8`.

## Which steps contributed

| Step | Contribution | Methodology |
|---|---|---|
| iteration 1, step 6 | the oracle confirmed the trans pair (F1) | [083](../../../docs/iteration1/step-6/methodology/083-oracle-reply-submission-1.md) |
| iteration 1, step 8 | the mechanism card v1–v2, the data layer `mva.drugs`, H010/H011 | [078](../../../docs/iteration1/step-8/methodology/078-track2-data-layer.md) |
| iteration 2, step 1 | the symptom-only target set and its 396 matched decoys — the decoy pool the drug control draws from | [084](../../../docs/iteration2/step-1/methodology/084-the-blind-target-set.md) |
| iteration 2, step 2 | alleles from the raw reads; no structural variant in the gene; phase unmeasured (F4) | [088](../../../docs/iteration2/step-2/methodology/088-the-alleles-the-reads-carry.md), [092](../../../docs/iteration2/step-2/methodology/092-depth-per-exon-and-the-phasing-drawn.md) |
| iteration 2, step 3 | both alleles at one copy; every exon at two (F2, F3) | [096](../../../docs/iteration2/step-3/methodology/096-the-alleles-at-their-multiplicity.md), [097](../../../docs/iteration2/step-3/methodology/097-copy-number-without-an-aligner.md) |
| iteration 2, step 4 | the missense's pathogenicity lane; P(trans) undetermined (F6, F7) | [099](../../../docs/iteration2/step-4/methodology/099-every-gene-ordered-with-nothing-filtered-out.md), [101](../../../docs/iteration2/step-4/methodology/101-the-phase-that-cannot-be-measured.md) |
| iteration 2, step 5 | the missense outside every curated domain (F5); the literature is a poor ranker | [105](../../../docs/iteration2/step-5/methodology/105-does-the-literature-beat-a-hit-count.md), [106](../../../docs/iteration2/step-5/methodology/106-where-the-missense-sits-in-the-protein.md) |
| iteration 2, step 6 | the blind mirror found the same pair (F9); one route carried it | [107](../../../docs/iteration2/step-6/methodology/107-the-routes-and-which-of-them-earned-a-rank.md)–[109](../../../docs/iteration2/step-6/methodology/109-what-the-mirror-found.md) |
| iteration 2, step 8 | **F8 measured**: nothing above 2–3 % of cells in the sequenced sample, at 80 % power | [115](../../../docs/iteration2/step-8/methodology/115-the-callset-reduced-to-what-a-mosaic-model-needs.md)–[118](../../../docs/iteration2/step-8/methodology/118-the-baseline-and-what-a-variegated-genome-does-to-it.md) |
| **iteration 2, step 7** | card v3 → v4; the ladder; the shortlist and do-not table; the decoy control; H045–H050, H061; the dashboard surface | [110](../../../docs/iteration2/step-7/methodology/110-the-card-revised-and-the-claims-filed-before-the-search.md)–[114](../../../docs/iteration2/step-7/methodology/114-the-dashboard-surface-for-step-7.md), [120](../../../docs/iteration2/step-7/methodology/120-the-card-at-version-4-and-the-second-submission-draft.md) |

Both datasets: the genomic data fixed the gene, the alleles, their dosage and the absence of a
detectable aneuploid population in the sample; the clinical terms fixed the disease, step 1's
target set, the tumour context (rhabdomyosarcoma) and, through it, direction D4 and the
paediatric questions.

## Regenerate this folder

```bash
uv run mva-drugs snapshot
uv run python tools/track2_decoys.py --symbol NTRK3 --uniprot Q16288 --protein "NT-3 growth factor receptor (TrkC)" --pattern "NTRK|neurotrophin|Trk" --picked-by "seeded draw from results.it2_decoys"
uv run python tools/track2_decoys.py --symbol XDH --uniprot P47989 --protein "xanthine dehydrogenase/oxidase" --pattern purine --picked-by "an unrelated, well-drugged metabolic enzyme"
uv run python tools/track2_enrich.py
uv run python tools/render_track2_figures.py
uv run python tools/md_to_html.py submissions/track2/iteration-2/report.md build/track2-report.html --repo-url https://github.com/agharsallah/mva-hackathon/blob/main
node tools/md_to_pdf.mjs build/track2-report.html submissions/track2/iteration-2/agharsallah_track2_report.pdf
uv run python tools/fill_methods_form.py --sheet "Track 2 methods" --answers submissions/track2/iteration-2/methods-form.json --out submissions/track2/iteration-2/agharsallah_track2_methods_form.xlsx
uv run python tools/check_iteration.py submissions/track2/iteration-2
```

## Before the upload

1. Record the 3-minute pitch from `pitch-script.md`; paste the URL into the table above.
2. If step 8's dosage pass (H054) lands, add its row to F8 on the card (version 5, a history
   entry) and re-render; nothing on the ladder should move (H061's test re-runs in seconds).
3. Re-run `tools/check_iteration.py`; set this README's standing to *ready*; re-render the PDF.
4. Upload once. Then mark this README frozen (the gate reads that word in bold at the top) and
   never edit the folder again.

## Lineage

Every table this folder cites has a `.provenance.json` beside it and rows under
`target_schema = 'track2'` in `warehouse.data_lineage` (63 edges); the dashboard's `/track2`
page opens with the approach, the suggestion and the output, and `/submissions` lists this
folder as panel-judged.
