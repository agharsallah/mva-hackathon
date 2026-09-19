# 133 — The card at version 5: step 8's second instrument, and the ladder that did not move again

**Written:** 2026-09-20. **Step:** `step-7` (iteration 2). **Hypotheses:** **H065** settled here
(supported, 0.90), filed before the re-grade. Supersedes nothing;
[120](120-the-card-at-version-4-and-the-second-submission-draft.md) stands and is the entry this
one extends.

## Question

Card v4 wrote fact **F8** from step 8's allele-balance route and recorded, honestly, that the
k-mer dosage route *had not run* and that H054 was open. It has since run
([121](../../step-8/methodology/121-the-second-instrument-and-the-shards-it-did-not-need.md),
read back by [123](../../step-8/methodology/123-the-denominator-that-assumes-nothing-read-back.md);
H054 **supported, 0.85**). Two questions follow, the same two 120 asked: **what does F8 say once
the second instrument is on it, and does any rung move?** The second is pre-registered, because
"the new fact changed nothing" is a test, not an assertion.

## Hypothesis and prediction

**H065** — *the drug evidence ladder is independent of step 8's second instrument: revising the
mechanism card to version 5 with the k-mer dosage route changes no rung, no shortlist row and no
do-not row; F8 acts only on how the report argues direction D2 and on what the card can say about
X, Y and the detection floor.* Predicted: a re-grade on card v5 returns `evidence_ladder.tsv`,
`shortlist.tsv` and `do_not.tsv` with **unchanged sha256** (`47d1e415…`, `77b6b352…`,
`a7b09e9f…`), while every manifest the re-grade rewrites names card version 5.

## What would refute it

Any row of `evidence_ladder.tsv`, `shortlist.tsv` or `do_not.tsv` differing between the card-v4
and the card-v5 run — a rung, a flag, a verdict or a rank moving with no input table changed.

## Inputs

| Source | What was read | Receipt |
|---|---|---|
| step 8 | X dosage **0.4873**, Y **0.5083** against 0.5 expected — the positive control the allele-balance route could not supply; chromosome-GC regressor chosen (Pearson **0.904**, explains **81.7 %**), residual spread **0.802 %**, honest floor **1.6 %** of cells; chr21's apparent signal dissolved under tail trimming (2.33 σ → 1.60 σ), a probe half-split (0.77 % against a 0.76 % median) and a depth check (mean 61.68× but median 45 against 43, p99 247 against 66–69 — mismapping pileups); 32 of 272 flowcell shards, a thinning unbiased for a ratio | [121](../../step-8/methodology/121-the-second-instrument-and-the-shards-it-did-not-need.md), H054 |
| step 8 | the absolute k-mer-mass denominator, which assumes nothing about chromosomes, agrees with the autosomal median on all 24 contigs to **0.017 %** | [123](../../step-8/methodology/123-the-denominator-that-assumes-nothing-read-back.md) |
| step 8 | still true and kept on the card: sub-arm events untestable by either route; the sequenced tissue unnamed by the delivery; copy-neutral loss of heterozygosity invisible to the dosage route | [121](../../step-8/methodology/121-the-second-instrument-and-the-shards-it-did-not-need.md), step-8 README |
| card v4 | everything else, unchanged | [120](120-the-card-at-version-4-and-the-second-submission-draft.md) |
| the cached replies | `build/track2-cache/` — the re-grade makes zero live requests | [111](111-the-automated-stages-literature-trials-and-labels-per-drug.md) |

## Method

1. **H065 filed first**, with its prediction and its refutation condition, before the card was
   touched.
2. **Card v4 → v5** by a `history` entry: F8's `value`, `source` and `implication` rewritten to
   carry **both** routes and their limits; `_standing` extended to name the v5 revision and
   entries 121 and 123. Nothing else on the card changed — no seed, no direction, no
   anti-direction, no rung definition, no allele, no literature row.
3. `tools/track2_enrich.py --skip-live` — the re-grade, from the tables already on disk.
4. Digests compared against the committed card-v4 tables.
5. Figures re-rendered; lineage edges appended; the register mirror exported.

## Commands

```bash
uv run mva-science hypothesis-add --step step-7 ...          # H065, before the card was edited
uv run python - <<'EOF'  ...  EOF                            # card v4 -> v5 (in the commit)
uv run python tools/track2_enrich.py --skip-live
shasum -a 256 ressources/track2/{evidence_ladder,shortlist,do_not}.tsv
uv run python tools/render_track2_figures.py
uv run python tools/record_track2_lineage.py --dry-run && uv run python tools/record_track2_lineage.py
uv run mva-science evidence-add --hypothesis H065 ... ; uv run mva-science verdict H065 --commit ...
uv run mva-science export
```

## Observed

```
re-grade (--skip-live)    evidence_ladder 432 rows · shortlist 61 · do_not 23 · decoy_comparison 12
                          pediatric_trials 11,698 · drug_mechanism_literature 658
digests                   evidence_ladder 47d1e415…8f8e0   shortlist 77b6b352…5d081e   do_not a7b09e9f…6472c94
                          identical to the card-v4 run, on the first attempt
drugs by best rung        5: 62 · 3: 2 · 2: 5 · 1: 260      (unchanged)
ladder rows by rung       5: 62 · 3: 2 · 2: 7 · 1: 361      (unchanged)
manifests naming card v5  7 of 7 rewritten by this run; the other 5 manifests belong to the live
                          snapshot stage, which --skip-live did not rerun, and still name v3
grep measured_facts       src/ and tools/: one comment in mva.warehouse.track2_lineage; app/src only
                          (display). The grading path never reads the block F8 lives in
figures                   5 PNGs byte-identical; figures/track2-report.html differs by its header
                          alone: "card v4 … 05d7326" -> "card v5 … d076959"
lineage                   12 edges appended (one card edge per table, source_version v5), 51 already
                          present; 104 edges under target_schema track2 in total
```

## Verdict

**H065 — supported, 0.90.** The three digests are unchanged on the first re-grade — no reader
fault this time — the row counts and the rung histogram are identical, and all seven manifests the
run rewrote name card version 5. Held below the suggested 0.96 because the two evidence rows are
not independent (the grep explains why the digests *could* not move) and because the card change
is prose attached to a fact the grader never reads, so the test can only ever confirm a structural
property. Evidence rows 155 (supports, 0.85) and 156 (supports, 0.70).

## What the second instrument changes for the report — and what it does not

- **F8 now has a positive control.** The dosage route reads one copy of X at 0.4873 and one of Y
  at 0.5083 where 0.5 is the truth for a male proband. A negative result from an instrument that
  has never been shown to detect anything is worth little; this one lands on a known answer to
  within 2.5 % before it is asked about the autosomes.
- **The X/Y gap in F8 is closed.** Card v4 had to say allele balance cannot read the sex
  chromosomes in a male. It still cannot; the second route can, and does.
- **The floor is stated honestly, and it went up.** 1.6 % of cells, twice the 0.802 % residual
  spread — not the ±1 % the bootstrap interval suggested, because that interval resamples probes
  and is blind to a GC bias every probe on a chromosome shares.
- **chr21 is named and dismissed in the open**, with the four checks that dismissed it, rather
  than omitted.
- **D2 is unchanged in substance.** Two routes now say no aneuploid population is above the
  detectable floor in the sequenced sample, so D2 (aneuploidy-selective stress) stays a
  tumour-context and chemoprevention angle argued from published aneuploid-cell biology, ranked
  below D3 and D4 — the same standing card v4 gave it, on stronger evidence.
- **D1, D3, D4, the shortlist and the do-not table are untouched.** Raising BubR1 and the spindle
  poisons' caution both act on the constitutional genotype whatever the burden.
- **Nothing on the ladder moved** — that is H065.

## Conclusion

The card carries nine measured facts, and F8 is now the only one written from two instruments
that share nothing past the raw reads. The gap card v4 declared — "the dosage route has not run" —
is closed; the gaps step 8 itself declares (sub-arm events, the unnamed tissue, copy-neutral loss
of heterozygosity) are carried forward on the card in the same sentence as the result, not dropped.
The Track 2 submission draft in `submissions/track2/iteration-2/` is written from card v4 and its
F8 text is now one version behind — which is the follow-up its own README already names ("if step
8's dosage pass (H054) lands, add its row to F8 on the card (version 5, a history entry)"). The
card half of that item is done here; the draft has not been rewritten by this entry.

## Assumptions, limitations, quality checks

- **Limitation:** F8 remains a statement about the **sequenced sample**, whose tissue the delivery
  does not name. It is not a severity statement and not the diagnosis.
- **Limitation:** sub-arm events are outside both routes (the probe set is coordinate-free by
  design), and copy-neutral loss of heterozygosity is invisible to the dosage route by
  construction.
- **Limitation:** the lineage recorder reads the card version off `mechanism.json` at recording
  time, so all twelve tables received a `v5` card edge — including the five (`targets`, `trials`,
  `literature`, `pathways`, `drug_candidates`) that were built under v3 and were not rebuilt by
  `--skip-live`. The ledger is append-only and their v3 edges remain beside the new ones; the
  per-table build-time version is the manifest's, not the edge's. The same happened at v4
  (card edges: v2 5, v3 12, v4 12, v5 12).
- **Limitation:** the dashboard's offline fixture `app/src/fixtures/data/track2.json` still holds
  the card at v4. The live API serves v5; recapturing the fixture also requires re-blessing
  `app/src/test/fixtureHashes.json`, which a parallel session is editing, so it is left for that
  session rather than merged blind. Flagged, not done.
- **Quality check:** the pre-registered digest test passed on the first run. Entry 120's run did
  not, and the fault it caught (a CSV quoting bug) is the reason this test is worth re-running for
  every card revision rather than reasoned about.
- **Quality check:** the five PNG figures are byte-identical after the re-render — the only
  difference in `figures/track2-report.html` is the card version in its header, which is what a
  card revision that changes no data should look like.
- **Quality check:** `uv run python tools/check_coordinates.py` clean; no genomic position enters
  the card, the entry or the register.
