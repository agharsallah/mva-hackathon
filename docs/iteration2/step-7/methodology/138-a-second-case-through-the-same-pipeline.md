# 138 — A second case through the same pipeline: what transferred, and the one limb that did not

**Written:** 2026-09-20. **Step:** `step-7` (iteration 2). **Hypotheses:** **H066** settled here
(**refuted as a conjunction**, 0.10), filed before the transfer run. Four of its five limbs hold —
including every limb that tests portability — and the fifth failed. Why the fifth failed is the
useful half of the result.

## Question

The decoy control ([112](112-two-decoy-cards-through-the-same-pipeline.md)) swaps the *gene* and
keeps everything else. It cannot answer the harder question: **is the Track 2 pipeline
case-agnostic in fact, or only in claim?** A transfer run swaps the whole case — a different
disease with its own OMIM/MONDO identifiers, its own HPO terms, its own tumour context and its
own standard of care — and asks whether `mva-drugs snapshot` and the step-7 enrichment execute on
it with no code change and no hand-written query.

The second case is **TRIP13 / mosaic variegated aneuploidy syndrome 3 (MVA3)**: chosen because it
shares the spindle assembly checkpoint with the proband's case — so a transfer that works is a
statement about the pipeline, not about how unalike the cases are — while sharing **no** disease
query, **no** clinical term list, **no** tumour context (nephroblastoma, not rhabdomyosarcoma)
and **no** standard-of-care drug with it.

## Hypothesis and prediction

**H066** — *the pipeline is portable to a different case, not only a different gene.* Predicted:

1. `tools/track2_transfer.py` completes against the live public APIs with **no edit to any
   module**; the transfer folder gains the five snapshot tables plus `evidence_ladder.tsv`,
   `shortlist.tsv` and `do_not.tsv` with a provenance manifest each, and
   `transfer_comparison.tsv` carries one row per case.
2. **No D1 row above rung 1** — the checkpoint-reinforcement direction again yields no
   submittable drug.
3. **No D1 row in the shortlist.**
4. **`do_not.tsv` carries at least one drug flagged `A2`** — the spindle-poison anti-direction
   again populates the do-not table.
5. **The context direction D4 is the only one reaching rung 2 or higher.**

## What would refute it

Any edit to a module needed to complete the run; or a D1 row at rung 2 or higher, or any D1 row
in the shortlist, which would mean a tumour-context trial leaking onto a mechanism direction (the
fault [113](113-the-ladder-the-shortlist-and-the-do-not-table.md) fixed); or a `do_not.tsv`
carrying no `A2`-flagged drug; or a rung-2-or-higher row on any non-context direction of a card
that has no `evidence.tsv`.

## Inputs

| Source | What was read | Receipt |
|---|---|---|
| `ressources/track2/transfer/TRIP13/transfer_spec.json` | the case: gene TRIP13 (UniProt Q15645, HGNC:12307), MVA3 (OMIM 617598, MONDO:0054736), tumour context nephroblastoma, the context standard of care, four directions and two anti-directions. Every identifier resolved live before the file was committed | the file's `_standing` and `_verified` fields |
| `build/reference-scratch/phenotype.hpoa` | the HPO terms for OMIM:617598, read by `mva.drugs.transfer` — **not** the proband's terms | `mechanism.json` → `case.clinical_terms` |
| Open Targets, ChEMBL, DGIdb, Reactome, ClinicalTrials.gov, PubMed, openFDA | the whole snapshot and enrichment, **cold** (an empty cache for this case) | the seven `*.provenance.json` in the transfer folder |
| `ressources/track2/mechanism.json` (card v5) + its tables | the real case's side of the comparison; re-read, not re-run | [133](133-the-card-at-version-five-and-the-second-instrument.md) |

## Method

1. **The spec is written, not the card.** `mva.drugs.transfer.transfer_card` builds
   `mechanism.json` from `transfer_spec.json` plus the HPO terms it reads out of
   `phenotype.hpoa`. Exactly three blocks are copied verbatim from the template card —
   `anti_directions`, `evidence_ladder`, `constraints` — and the card's `transfer` block records
   that it copied them and why. There are **no alleles** and **no `evidence.tsv`**.
2. **The same two stages, unchanged.** `mva-drugs snapshot` on the transfer card, then
   `mva.drugs.enrich.run`. No module was edited for the run.
3. **The comparison row** is read back from each case's `snapshot.json` and enrichment analysis
   by `mva.drugs.compare`; only the automated rungs (1, 4, 5) are comparable, and `curated_rows`
   records the difference.
4. **The four limbs verified** directly against the three written tables (counts below), then
   filed as evidence rows and the claim settled.

## Commands

```bash
uv run python tools/track2_transfer.py                  # the cold run, against the live APIs
uv run mva-science evidence-add --hypothesis H066 ...   # five rows, four limbs + the cause
uv run mva-science verdict H066                         # then --commit with a reason
uv run python tools/render_track2_figures.py            # figures/track2/transfer-scalability.png
uv run python tools/record_track2_lineage.py --dry-run  # then for real
```

## Observed

```
the run                     completed with no module edit; 8 tables + 8 provenance manifests written
                            targets 28 · candidate rows 1,329 · trials 258 · literature 138
                            drug_mechanism_literature 530 · pediatric_trials 9,950

limb 1  artifacts           MET   snapshot's five + evidence_ladder/shortlist/do_not, a manifest each;
                            transfer_comparison.tsv carries one row per case
limb 2  D1 above rung 1     MET   0 of 30 D1 rows above rung 1
limb 3  D1 in the shortlist  MET  0 of 53 shortlist rows are D1 (all 53 are D4)
limb 4  A2 in do_not.tsv    FAILED  do_not.tsv holds 3 rows, all D4, all flagged standard_of_care;
                            0 rows flagged A2 anywhere in the transfer ladder
limb 5  only D4 at rung >=2 MET   D4 55 rows at rung 5 · D1 30/30, D2 82/82, D3 39/39 all at rung 1

ladder by direction         D1 30 · D2 82 · D3 39 · D4 219   (370 rows)
flags in the ladder         standard_of_care 5 · A2 0        (real case: A2 11, A2|standard_of_care 2)

why limb 4 failed           the A2 flag is a regex (tubulin|microtubule|vinca|taxane) over each drug's
                            action_type + interaction_or_moa text (mva.drugs.ladder._flags).
                            Reactome returned 0 pathways matching /checkpoint|kinetochore|mitotic/i for
                            Q15645, so pathways.tsv is header-only and every one of the 1,329 candidate
                            rows has target_role = seed. 261 of them carry any MOA text at all.
                            The real case has 2,276 pathway rows and 2,200 rows with MOA text, and
                            11 of its 13 A2 drugs sit on direction_id = pathway.
                            Spindle poisons are present in the transfer candidate set
                            (DOCETAXEL ANHYDROUS, PACLITAXEL PROTEIN-BOUND) but arrive from DGIdb with
                            an empty action_type and an empty interaction_or_moa, so the regex has
                            nothing to match. The anti-direction is not wrong; it is unreachable
                            without the ChEMBL mechanism text that pathway expansion brings in.

cross-case comparison       (ressources/track2/transfer_comparison.tsv)
                            BUB1B / MVA1   277 targets · 3,859 candidate rows · 359 approved drugs
                                           rung 5: 62 · rung 3: 2 · rung 2: 5 · rung 1: 260
                                           shortlist 61 · do-not 23 · curated 13
                                           85 live requests · 1,965 cached replies (warm)
                            TRIP13 / MVA3   28 targets · 1,329 candidate rows · 277 approved drugs
                                           rung 5: 55 · rungs 4/3/2: 0 · rung 1: 210
                                           shortlist 53 · do-not 3 · curated 0
                                           2,077 live requests · 0 cached · 1,693.7 s cold, 9.0 s warm
```

## Verdict

**H066 — refuted, 0.10** (register revision 2). Four of the five predicted limbs hold, including
every limb that tests *portability*: the run completed unchanged, D1 stayed at rung 1 in full, D1
reached no shortlist row, and the context direction was the only one above rung 1 on a card with
no curated evidence. The fourth limb — that the spindle-poison anti-direction would again
populate the do-not table — **failed**, against a refutation condition written before the run
("a `do_not.tsv` carrying no `A2`-flagged drug"). H066 was filed as a conjunction, so a measured
false limb refutes it as written; it is recorded that way rather than reworded.

The confidence is the confidence in **the conjunction**, not in portability. The heuristic
suggested **0.98** — it sums independent evidence rows and cannot see that the claim is an AND —
and that suggestion is rejected on the record. The weighing is a transparent triage heuristic,
not a calibrated posterior.

The failed limb is not a nuisance. It shows the do-not table is a **derived** artefact of how
much mechanism-of-action text the candidate set happens to carry, not a property of the card's
anti-directions: a case whose gene Reactome cannot expand gets a nearly empty do-not table while
the same spindle poisons sit in its candidate set unflagged. **Portability itself is not asserted
by this verdict** — it is the finding of this entry, resting on the four limbs that hold, and a
claim about it would have to be filed and tested on its own.

## What the transfer run does not show

- **Nothing clinical, for anyone.** The transfer case is a demonstration that the code is
  case-agnostic. It is not a finding about MVA3, not a drug suggestion for any person, and no
  allele in any person is asserted anywhere in the transfer folder.
- **No curated evidence on the transfer side.** A transfer card has no `evidence.tsv`, so rungs 2
  and 3 cannot exist for it. Only the automated rungs (1, 4, 5) are comparable between the cases;
  `curated_rows` in the comparison table (13 vs 0) is the honest zero bar, not a deficit.
- **The cost numbers are asymmetric.** The real case's **85 live requests / 1,965 cached** is a
  *warm* re-run against a cache filled over earlier entries; the transfer's **2,077 live / 0
  cached** is the cold pass that filled its own. The comparable figure — what a case the pipeline
  has never seen costs — is the transfer row's cold pass: 2,077 requests, 1,693.7 s wall. The
  warm re-derivation is 9.0 s.
- **Not a statement about drug quality.** Fifty-three shortlist rows on a case with no curated
  evidence are *context-trial only* rows, exactly as the 50 such rows are on the real case. A
  bigger shortlist is not a better one.

## Assumptions, limitations, quality checks

- **Assumption:** `phenotype.hpoa` (release 2026-09-02) is the source for the transfer case's
  clinical terms. No proband term reaches the transfer card, by construction — `transfer.py`
  reads the OMIM id, never the delivery.
- **Limitation:** Reactome states no release version in its replies, so the pathway manifest's
  `version` is `null` rather than a date copied from the run. The empty pathway expansion is
  therefore reproducible from the cache but not pinned to a named Reactome release.
- **Limitation:** the A2 gap above is *not* fixed here. Widening the flag to match drug names, or
  seeding tubulin targets on the card, would be a change to the ladder rule and must be filed as
  its own pre-registered test, not folded into a refuted claim.
- **Quality check:** the failed limb was found by reading the three written tables against the
  prediction one limb at a time, and each limb is its own evidence row with the table as its
  source — the refuting row cites `do_not.tsv` and the ladder's flag counts.
- **Quality check:** no coordinate appears in the transfer folder by construction (public API
  replies only — gene symbols, drug names, trial ids, PMIDs); `tools/check_coordinates.py` is
  part of the gate this entry was committed behind.
- **Quality check:** the comparison figure `figures/track2/transfer-scalability.png` is rendered
  from `transfer_comparison.tsv` by `tools/render_track2_figures.py`, not typed.
- **Quality check:** the dashboard's offline fixture `app/src/fixtures/data/track2.json` was
  re-captured from the live API against a reachable warehouse (the endpoint's disk cache was
  invalidated first — it was serving a card-v4 payload from 2026-09-19) and its hash re-blessed.
  The card now reads **v5** and the payload carries `transfers` (1) and `transfer_comparison` (2).
- **Quality check, and two gate fixes recorded rather than suppressed.** The re-captured fixture
  broke the Track 2 page's *no genomic position anywhere on the page* test twice, both false
  positives caused by the new transfer panel, both fixed at the cause:
  1. HPO term ids are zero-padded to seven digits (`HP:0002667`) and the transfer card carries 18
     of them plus `MONDO:0054736`. The guard strips labelled ids before looking for a bare digit
     run; the ontology prefixes were added to that strip list, with the reason inline. A
     seven-digit run with **no** prefix still fails the test.
  2. `wall_seconds` was rendered raw beside two `int()`-grouped cost columns, so
     `2,077` · `0` · `1693.7` concatenated in `textContent` into `2,07701693.7`. Fixed in the
     component (`seconds()` groups it as `1,693.7`), not in the test — the guard reads
     `textContent`, so adjacent ungrouped numbers are a real reporting defect as well.
  `pnpm test`: 709 of 709 pass.
