# 120 — The card at version 4: step 8's measured burden, the ladder that did not move, and the second submission draft

**Written:** 2026-09-19. **Step:** `step-7` (iteration 2). **Hypotheses:** **H061** settled here
(supported, 0.85), filed before the re-grade. Closes the one row step 7 was open for: card fact
**F8** is now measured.

## Question

Step 7 left the mechanism card with one honest gap: the aneuploid fraction in the sequenced
sample was *unmeasured*, and direction D2 (aneuploidy-selective stress) inherited that gap. Step
8 has run ([115](../../step-8/methodology/115-the-callset-reduced-to-what-a-mosaic-model-needs.md)–[118](../../step-8/methodology/118-the-baseline-and-what-a-variegated-genome-does-to-it.md)).
Two questions follow: **what does the card say once F8 is on it, and does the measured burden
change any rung?** The second is pre-registered as H061 because the honest answer to "did the
new fact move the ranking" has to be a test, not a claim.

## Hypothesis and prediction

**H061** — *the evidence ladder is independent of the measured aneuploid fraction: revising the
card to version 4 changes no rung, no shortlist row and no do-not row; F8 acts only on how D2 is
argued.* Predicted: `evidence_ladder.tsv`, `shortlist.tsv` and `do_not.tsv` come back
byte-identical (same sha256) from a re-grade on card v4, while every manifest names version 4.

## What would refute it

Any row of the three tables differing between the card-v3 and card-v4 runs.

## Inputs

| Source | What was read | Receipt |
|---|---|---|
| step 8 | no autosome above its own detection limit; limit **2 %** of cells (chr1–6) / **3 %** (chr7–22) at 80 % power; fold centre 0.49300; over-dispersion 0.01620; X and Y unreadable by allele balance in a male; the dosage route (H054) not run; sub-arm events never testable; 037's statistic had no power at any fraction tested | [116](../../step-8/methodology/116-the-statistic-that-has-power-and-the-limit-it-buys.md), H051–H053 |
| step 8 | the tissue sequenced is not named by the delivery; a karyotype's fraction is measured in cultured cells — "in the sequenced sample", never the diagnosis | step-8 README, *What this step cannot tell you* |
| card v3 | everything else, unchanged | [110](110-the-card-revised-and-the-claims-filed-before-the-search.md) |
| the cached replies | `build/track2-cache/` — the re-grade makes zero live requests | [111](111-the-automated-stages-literature-trials-and-labels-per-drug.md) |

## Method

1. **Card v3 → v4** by a `history` entry: F8's value, source, step and implication rewritten from
   *unmeasured* to the measured result; the `_standing` line names entries 115–118; nothing else
   on the card changes — no seed, no direction, no anti-direction, no rung definition.
2. **H061 filed**, then `tools/track2_enrich.py --skip-live` (re-grade from the tables on disk).
3. Digests compared against the committed card-v3 tables (`47d1e415…`, `77b6b352…`,
   `a7b09e9f…`).
4. Figures re-rendered; lineage edges appended; the register mirror exported.

## Commands

```bash
uv run mva-science hypothesis-add --step step-7 ...          # H061, before the re-grade
uv run python - <<'EOF'  ...  EOF                            # card v3 -> v4 (in the commit)
uv run python tools/track2_enrich.py --skip-live             # first re-grade: FAILED the digest test
uv run pytest tests/test_drugs_ladder.py                     # the new reader regression test
uv run python tools/track2_enrich.py                         # second re-grade, cache-warm, 0 live calls
shasum -a 256 ressources/track2/{evidence_ladder,shortlist,do_not}.tsv
uv run python tools/render_track2_figures.py
uv run python tools/record_track2_lineage.py
```

## Observed

```
first re-grade (--skip-live)   pediatric_trials.tsv read as 10,770 rows (written 11,698)
                               evidence_ladder 02d0815e…  shortlist 979ba276…  do_not 962eb7ae…   ≠ card-v3 digests
cause                          csv default quoting: a registry title beginning with a double quote opened a
                               multi-line field and swallowed 928 rows; drugs lost their paediatric-trial
                               flag and moved rung
fix                            quoting=csv.QUOTE_NONE in mva.drugs.enrich.read_tsv and mva.viz.track2_reader;
                               regression test on a quoted title (tests/test_drugs_ladder.py)
second re-grade (cache-warm)   pediatric_trials 11,698 rows · pubmed 1,003 replies, 0 live · clinicaltrials 329, 0 live
                               evidence_ladder 47d1e415…  shortlist 77b6b352…  do_not a7b09e9f…   = card-v3 digests
manifests naming card v4       7 of 7
drugs by best rung             5: 62 · 3: 2 · 2: 5 · 1: 260   (unchanged)
lineage                        19 edges appended by the faulty run remain in the append-only ledger (they describe
                               files that existed at that moment); the corrected run added 0 new edges - its
                               digests already matched rows written for card v3, so the ledger records the fact
                               that the tables did not change
```

## Verdict

**H061 — supported, 0.85.** The three digests are identical once the reader fault is removed,
and the ladder reads no aneuploid-fraction field, so the claim is structural as well as
observed. Held below 0.9 because the first run failed for an unrelated reason the test could
not tell from a real change until the reader was fixed — which is also the reason the test was
worth pre-registering: it caught an instrument fault that a "nothing changed" assertion would
have hidden. The same fault had reached the dashboard fixture (10,770 rows); it is recaptured in
the same commit series.

## What F8 changes for the report — and what it does not

- **D2 is argued from the literature only.** Chloroquine's aneuploidy-selective result and the
  proteasome and AMPK proxies stand as published biology of aneuploid cells; in *this* sample no
  aneuploid population above 2–3 % exists for such a drug to act on. The report ranks D2 below
  D3 and D4 for that stated reason, and says the sample's tissue is unknown and the diagnosis is
  clinical.
- **D3 and D4 are untouched.** Raising BubR1 acts on the constitutional genotype whatever the
  burden; the statins act on the tumour.
- **The do-not table is untouched.** Spindle poisons rely on the checkpoint regardless of how
  many cells are currently aneuploid.
- **Nothing on the ladder moved** — that is H061.

## Conclusion

Step 7's open row is closed. The card carries nine measured facts and no stated gap beyond the
ones step 8 itself states (tissue unnamed, X/Y and sub-arm untestable by this route, dosage
pass not run). The second Track 2 submission draft, `submissions/track2/iteration-2/`, is written
from this card and supersedes iteration 1's draft, which was never uploaded.

## Assumptions, limitations, quality checks

- **Limitation:** F8 is a statement about the sequenced sample, whose tissue the delivery does
  not name. It is not a severity statement and not the diagnosis.
- **Limitation:** X, Y and sub-arm events are outside what F8 can say; H054 (the dosage route)
  is open in step 8.
- **Quality check:** the pre-registered digest test caught a reader fault; the fault, its size
  and its fix are recorded above rather than the table simply being re-run until it matched.
- **Quality check:** `mva-science check` passes (61 hypotheses, 134 evidence rows, no
  coordinates); `tests/test_drugs_ladder.py` 13 tests including the quoted-title regression.
