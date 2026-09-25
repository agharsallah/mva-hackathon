# Track 2 — iteration 4 (2026-09-25)

**Standing:** draft — the Track 2 report built from **iteration 4 only** (steps 1–11), user
decision 2026-09-25; **not uploaded**. Iteration 2's folder ([`../iteration-2/`](../iteration-2/README.md))
stays a separate, unfrozen draft; the user plans to merge the Track 2 iterations into one
upload later. Track 2 accepts **one** submission per team, due around 2026-10-20.

Opened by hand, not with `tools/new_iteration.py`: that tool would open iteration 3, freeze
iteration 2 and bump `ITERATION`, none of which is wanted here (iteration 2 was never uploaded).

## What this iteration answers, in one line each

- **Mechanism:** loss of function of the hypomorphic kind: too little stable BubR1. Four of
  five independent instruments support it; a structure prediction is inconclusive.
- **Drugs:** four generators fixed before any join agree on **one** drug, dasatinib, at the
  level chance gives (H094 refuted, p 0.263). It survives every check (H095, weak).
- **For this child:** a pharmacogenomic test request, a two-source flag on vincristine, an
  incidental RYR1 call.

## How this folder answers the four judged criteria

| criterion | weight | report section | the evidence on disk |
|---|---|---|---|
| **Scientific rigor** | 35 % | §3–§6, §10 | entries 142–155 under `docs/iteration4/step-*/methodology/`; `ressources/track2/it4/` (generator tables, sweep, candidates, safety, each with `.provenance.json`); `docs/science-register.json` (every claim with its prediction and refutation) |
| **Potential impact** | 25 % | §7 | `ressources/track2/it4/candidate_safety.tsv`; entry 152 (the child's pharmacogenome); entry 150 (which mouse to test in) |
| **Innovation** | 25 % | §8 | `mva.drugs.convergence*`, `checks*`, `mva.phenotype.cross_species*`, `mva.drugs.variant_atlas*`, `mva.drugs.patient_safety*` |
| **Scalability** | 15 % | §9 | step 11 (Bloom syndrome, entry 156); the tool table in §9 |

## What to upload

| Deliverable | File | Notes |
|---|---|---|
| Report (PDF or Markdown) | `agharsallah_track2_report.pdf`, rendered from [`report.md`](report.md) | filename carries the HF username |
| Methods form | `agharsallah_track2_methods_form.xlsx`, from [`methods-form.json`](methods-form.json) | sheet *Track 2 methods*, rows 7–16; abstract under 500 words |
| GitHub repository URL | `https://github.com/agharsallah/mva-hackathon` | public; code and committed tables only, no patient data |
| Pitch video URL (3 minutes) | **not recorded** — script in [`pitch-script.md`](pitch-script.md) | YouTube or Vimeo |

No predictions CSV, selectors or decode table: Track 2 is panel-judged, and
`tools/check_iteration.py` applies the Track 2 rules to this folder.

## How to read this folder

- [`report.md`](report.md): §1 the four criteria and the weakest point in each; §2 the answer
  in one page; §3 the mechanism (form Q14) from five instruments; §4 the drug directions; §5
  the four generators and the convergence test; §6 the checks and the survivor; §7 impact for
  this child; §8 what is new; §9 scalability; §10 limits; §11 reproducibility; §12 every claim;
  Appendix A every drug any generator named. Each `##` heading carries a `> **Rubric:**` line.
- [`methods-form.json`](methods-form.json): the ten answers, keyed by template row.
- [`pitch-script.md`](pitch-script.md): the 3-minute video, shot by shot.
- The evidence is **not copied here**; the folder links to it.

## Which steps contributed

| step | contribution | methodology |
|---|---|---|
| Track 1, iteration 1, step 6 | the oracle confirmed the pair (the one input from outside iteration 4) | [083](../../../docs/iteration1/step-6/methodology/083-oracle-reply-submission-1.md) |
| iteration 4, step 1 | the pair in the normalised records: one missense, one stop_gained | [114](../../../docs/iteration4/step-1/methodology/114-one-record-per-allele-and-what-it-can-be-spelled-as.md) |
| iteration 4, steps 5, 6, 8 | the variant-effect models on the pair; the fusion that does not find it; GPN-MSA 0.93 %; Boltz-2 inconclusive | [129](../../../docs/iteration4/step-5/methodology/129-what-each-lane-says-about-a-pair-it-can-only-half-see.md), [130](../../../docs/iteration4/step-6/methodology/130-a-consensus-of-lanes-that-declined-to-vote.md), [147](../../../docs/iteration4/step-8/methodology/147-boltz2-folds-bubr1-and-a-conservative-swap-drops-as-much.md), [148](../../../docs/iteration4/step-8/methodology/148-the-gpu-lanes-and-the-consensus.md) |
| iteration 4, step 7 | generator G1, the PrimeKG walk, and its decoy (H074) | [142](../../../docs/iteration4/step-7/methodology/142-a-graph-walk-from-the-disease-node.md) |
| iteration 4, step 9 | E1 stability atlas; E2 phenotype twin (generator G2); E4 the measured do-not leg; E5+E6 the child's pharmacogenome and safety method; E3 LINCS (generator G4) | [149](../../../docs/iteration4/step-9/methodology/149-the-stability-atlas-and-the-childs-missense.md), [150](../../../docs/iteration4/step-9/methodology/150-the-childs-phenotype-twin-among-mgi-mice.md), [151](../../../docs/iteration4/step-9/methodology/151-prism-replication-of-the-track2-leads.md), [152](../../../docs/iteration4/step-9/methodology/152-is-each-candidate-safe-for-this-child.md), [153](../../../docs/iteration4/step-9/methodology/153-lincs-signature-reversal-of-bub1b-loss.md) |
| **iteration 4, step 10** | generator G3 (the screen-wide sweep); convergence against a null; the checks; the candidate table | [154](../../../docs/iteration4/step-10/methodology/154-screen-wide-prism-sweep.md), [155](../../../docs/iteration4/step-10/methodology/155-convergence-and-checks.md) |
| iteration 4, step 11 | the second disease (Bloom syndrome) | 156 (pending) |

**Both datasets.** The genome fixed the gene, the alleles and their predicted effect (steps 1–9)
and the child's pharmacogenome (entry 152). The clinical terms fixed the phenotype twin (entry
150), generator G2, and the safety check against the child's own phenotypes (entries 152, 155).

## Regenerate this folder

```bash
uv run python tools/screen_sweep.py run
uv run python tools/converge.py run --generator walk --generator twin --generator lincs --generator prism  # full flags: entry 155
uv run python tools/render_step10_s2.py
uv run python tools/md_to_html.py submissions/track2/iteration-4/report.md build/track2-it4-report.html --repo-url https://github.com/agharsallah/mva-hackathon/blob/main
node tools/md_to_pdf.mjs build/track2-it4-report.html submissions/track2/iteration-4/agharsallah_track2_report.pdf
uv run python tools/fill_methods_form.py --sheet "Track 2 methods" --answers submissions/track2/iteration-4/methods-form.json --out submissions/track2/iteration-4/agharsallah_track2_methods_form.xlsx
uv run python tools/check_iteration.py submissions/track2/iteration-4
```

## Before the upload

1. The user merges the Track 2 iterations into one folder (planned); this folder is an input.
2. Record the 3-minute pitch; paste the URL above.
3. Run `tools/check_iteration.py`; upload once; mark the uploaded folder frozen.

## Lineage

Every table this folder cites has a `.provenance.json` beside it under `ressources/track2/it4/`
(inputs with URL, sha256 and licence; parameters; the producing entry). Every figure has a
`.provenance.json` beside it under `figures/it4/`. The dashboard's `/submissions` page lists this
folder, and `/steps?iteration=iteration4` carries steps 7–11 with their claims and entries.
