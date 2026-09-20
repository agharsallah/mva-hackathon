# Track 2 — iteration 2 (2026-09-19)

**Standing:** draft — the curated report, the methods-form answers, the pitch script and the
evidence tables, written from **all eight steps of iteration 2**, the mechanism card at
**version 5** and a **transfer run** of the whole pipeline on a second, different case;
**not uploaded**. Supersedes [`../iteration-1/`](../iteration-1/README.md),
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

Revised 2026-09-20 with two results that landed after the draft was written:

| | what landed | where it shows |
|---|---|---|
| mechanism card | **v4 → v5**: step 8's k-mer dosage route ran (H054 supported), giving F8 a second instrument, an X/Y positive control and a 1.6 % floor; a pre-registered digest test (H065, 0.90) showed the revision moved no rung, no shortlist row and no do-not row ([133](../../../docs/iteration2/step-7/methodology/133-the-card-at-version-five-and-the-second-instrument.md)) | report §2, §4, §5.2, §6.2, §11, §13 |
| a transfer run | the pipeline ran **unchanged** on a `TRIP13` / MVA3 card — a different gene, disease, tumour and phenotype-term set — and produced a complete second output. Its pre-registered claim (**H066**) was a conjunction of five limbs: four held, the fifth (the spindle-poison caution firing there too) **failed**, so the claim is recorded **refuted · 0.10** rather than reworded ([138](../../../docs/iteration2/step-7/methodology/138-a-second-case-through-the-same-pipeline.md)) | report §10, and §1's weakest-point column |

## How this folder answers the four judged criteria

The panel scores four weighted criteria. Each one has a section of the report that owns it and
an artefact on disk behind it.

| criterion | weight | report section | the evidence on disk |
|---|---|---|---|
| **Scientific rigor** | 35 % | §2–§7 | `ressources/track2/mechanism.json` (card v5, nine measured facts, append-only history); `ressources/track2/{evidence_ladder,shortlist,do_not,decoy_comparison}.tsv` with a `.provenance.json` each; `docs/science-register.json` (every claim with its prediction and refutation condition) |
| **Potential impact** | 25 % | §8 | the do-not table `ressources/track2/do_not.tsv`; step 8's two instruments ([121](../../../docs/iteration2/step-8/methodology/121-the-second-instrument-and-the-shards-it-did-not-need.md), [123](../../../docs/iteration2/step-8/methodology/123-the-denominator-that-assumes-nothing-read-back.md)); §8.1's proposed experiment is a **proposal, not a run** |
| **Innovation** | 25 % | §9 | the card-driven query path (`src/mva/drugs/`), the pre-registered ladder, the decoy control, the transfer card, the do-not table, the append-only register; prior-art notes in `docs/iteration4/cards/{primekg,txgnn}.json` (neither was run) |
| **Scalability** | 15 % | §10, §12 | `ressources/track2/transfer_comparison.tsv` (both cases, every count); `ressources/track2/transfer/TRIP13/` (card, spec, tables, manifests); `figures/track2/transfer-scalability.png`; the refuted claim [H066](../../../docs/iteration2/step-7/hypotheses/h066-trip13.md) and entry [138](../../../docs/iteration2/step-7/methodology/138-a-second-case-through-the-same-pipeline.md) |

## What to upload

| Deliverable | File | Notes |
|---|---|---|
| Report (PDF or Markdown) | `agharsallah_track2_report.pdf`, rendered from [`report.md`](report.md) | filename carries the HF username, as the form asks |
| Methods form | `agharsallah_track2_methods_form.xlsx`, from [`methods-form.json`](methods-form.json) | sheet *Track 2 methods*, rows 7–16; abstract under 500 words |
| GitHub repository URL | `https://github.com/agharsallah/mva-hackathon` | public; code and committed tables only, no patient data |
| Pitch video URL (3 minutes) | **not recorded yet** — script in [`pitch-script.md`](pitch-script.md) | YouTube or Vimeo; record from the script, paste the link here |
| Notes for judges (optional) | *the report is written for a non-specialist; every claim links to a registered hypothesis and a methodology entry; the pipeline ran on two decoy genes and one whole transfer case as its own controls; one of our pre-registered claims came back refuted and is reported as refuted (report §10.5); the do-not table is the half we think matters most clinically* | |

No predictions CSV, selectors or decode table: Track 2 is panel-judged, and
`tools/check_iteration.py` applies the Track 2 rules to this folder.

## How to read this folder

- [`report.md`](report.md) — **§1 the four judged criteria**, where each is answered and the
  weakest point we know in it; §2 the answer in one page; §3 the whole path as one diagram; §4
  steps 1–6 and 8, what each measured and what it gave the drug argument; §5 the mechanism
  (methods form Q14) and the nine measured facts; §6 the search, the ladder and the decoy
  control; §7 the eleven argued drugs in the order the report argues them, the fifty already in
  trials, the do-not table, the paediatric pointers; **§8 potential impact** — for this child,
  for others living with MVA, for diagnosis; **§9 what is new here** against standard practice;
  **§10 scalability** — the transfer run, its cost and what breaks at scale; §11 what it cannot
  tell you; §12 reproducibility and cost; §13 where every claim lives. Every `##` heading carries
  a one-line `> **Rubric:**` saying which criterion it serves.
- [`methods-form.json`](methods-form.json) — the ten answers, row-numbered as the template lays
  them out.
- [`pitch-script.md`](pitch-script.md) — the 3-minute video, shot by shot, with the figure each
  shot shows.
- The evidence itself is **not copied here**: tables `ressources/track2/*.tsv` (a
  `.provenance.json` each), figures `figures/track2/*.png`, reasoning
  `docs/iteration2/step-7/methodology/110–114, 120, 133, 138`, the genotype steps
  `docs/iteration2/step-1 … step-8`. The transfer case lives beside them:
  `ressources/track2/transfer/TRIP13/` (card, spec, tables, manifests) and
  `ressources/track2/transfer_comparison.tsv`.

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
| iteration 2, step 8 | **the second instrument**: k-mer dosage recovers one copy of X and one of Y as a positive control and sets a 1.6 % floor (H054 supported) | [121](../../../docs/iteration2/step-8/methodology/121-the-second-instrument-and-the-shards-it-did-not-need.md), [123](../../../docs/iteration2/step-8/methodology/123-the-denominator-that-assumes-nothing-read-back.md) |
| **iteration 2, step 7** | card v4 → **v5**; the pre-registered digest test that the revision moved no rung, no shortlist row and no do-not row (H065, 0.90) | [133](../../../docs/iteration2/step-7/methodology/133-the-card-at-version-five-and-the-second-instrument.md) |
| **iteration 2, step 7** | the transfer run: the whole pipeline on a `TRIP13` / MVA3 case with no code change; the comparison table and figure; H066 **refuted** (0.10) on its anti-direction limb, with the cause diagnosed | [138](../../../docs/iteration2/step-7/methodology/138-a-second-case-through-the-same-pipeline.md) |

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

1. **Record the 3-minute pitch** from `pitch-script.md`; paste the URL into the table above.
   This is the only open item that needs new work.
2. ~~If step 8's dosage pass (H054) lands, add its row to F8 on the card (version 5, a history
   entry) and re-render; nothing on the ladder should move.~~ **Done 2026-09-20**: H054 landed
   supported, the card is at v5, and the pre-registered re-grade returned the three tables with
   unchanged digests (H065, 0.90 — entry 133). The report, the methods form and this README were
   rewritten from it.
3. Re-run `tools/check_iteration.py`; set this README's standing to *ready*; re-render the PDF.
4. Upload once. Then mark this README frozen (the gate reads that word in bold at the top) and
   never edit the folder again.

## Lineage

Every table this folder cites has a `.provenance.json` beside it and rows under
`target_schema = 'track2'` in `warehouse.data_lineage` (63 edges); the dashboard's `/track2`
page opens with the approach, the suggestion and the output, and `/submissions` lists this
folder as panel-judged.
