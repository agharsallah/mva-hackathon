# 112 — Two decoy cards through the same pipeline: which directions nominate drugs for any gene?

**Written:** 2026-09-18. **Step:** `step-7` (iteration 2). **Hypotheses:** **H049** settled here
(supported, 0.85). Filed in [110](110-the-card-revised-and-the-claims-filed-before-the-search.md),
which also fixed the two decoys before their snapshots ran.

## Question

Track 1 gave every ranker a null: matched decoys, permutations, a held-out recall. Track 2's
evidence rungs had none, and the iteration-2 plan flagged the asymmetry (§10, gap N3). The
cheapest honest control is to **hold the child fixed and swap the gene**: a card with the same
disease, tumour context and clinical terms, the gene replaced by one that is not the answer, and
the unchanged pipeline run on it. Whatever the automated stages return for the decoy as readily
as for `BUB1B` was nominated by the clinical queries or by drug-database density — not by the
mechanism.

## Hypothesis and prediction

**H049** — *the automated stages are not specific: at least one of the four directions' approved
drug sets overlaps a decoy card's approved set at Jaccard ≥ 0.10.* Predicted: D4 (broadly
drugged cancer targets — TP53, MTOR, CDK4/6, IGF1R, HMGCR) is the direction that overlaps, and
the decoys' automated rungs look like `BUB1B`'s because the tumour-context trial query is
gene-independent.

## What would refute it

Every direction below Jaccard 0.10 against both decoys.

## Inputs

| Source | What was read | Receipt |
|---|---|---|
| decoy NTRK3 | card + snapshot: 14 targets (1 seed, 13 from 6 of 10 Reactome pathways matching `/NTRK\|neurotrophin\|Trk/`), 771 candidate rows, **174** approved drugs, 502 trial rows | `ressources/track2/decoys/NTRK3/` (110) |
| decoy XDH | card + snapshot: 14 targets (1 of 3 pathways matching `/purine/`), 91 candidate rows, **47** approved drugs, 136 trial rows | `ressources/track2/decoys/XDH/` (110) |
| real card | `drug_candidates.tsv` (3,859 rows, **325** approved base names in the comparison's fold) and `trials.tsv` | 110 |

Decoy choice, restated: NTRK3 is the first row of `results.it2_decoys` ordered by
`md5(symbol || '20260918')` — a seeded draw over step 1's 396 size-matched decoys, made before
the run. It happens to be a receptor kinase with approved inhibitors (larotrectinib,
entrectinib), which makes it a *harder* control than a random gene, not an easier one. XDH is
the deliberately unrelated, well-drugged metabolic enzyme.

## Method

`mva.drugs.compare.compare`: per real direction (and `pathway`, and `all`), the approved drugs
folded to base names; Jaccard against the decoy's approved set; the shared drugs listed; the
decoy's own automated flags counted (drugs with a tumour-context trial, drugs with a US label).
Curated rungs are **not** compared — a decoy has no hand-read literature, and comparing a number
to its absence is not a comparison.

## Commands

```bash
uv run python tools/track2_decoys.py --symbol NTRK3 ...   # 110
uv run python tools/track2_decoys.py --symbol XDH ...     # 110
uv run python tools/track2_enrich.py                      # writes decoy_comparison.tsv
```

## Observed

| decoy | direction | real approved | decoy approved | shared | **Jaccard** | decoy drugs with a rhabdomyosarcoma trial | with a US label |
|---|---|---|---|---|---|---|---|
| NTRK3 | D1 | 30 | 171 | 12 | 0.064 | 64 | 150 |
| NTRK3 | D2 | 82 | 171 | 19 | 0.081 | | |
| NTRK3 | D3 | 48 | 171 | 5 | 0.023 | | |
| NTRK3 | **D4** | 205 | 171 | **75** | **0.249** | | |
| NTRK3 | pathway | 115 | 171 | 56 | 0.244 | | |
| NTRK3 | all | 325 | 171 | 105 | 0.269 | | |
| XDH | D1 | 30 | 45 | 1 | 0.014 | 8 | 35 |
| XDH | D2 | 82 | 45 | 5 | 0.041 | | |
| XDH | D3 | 48 | 45 | 3 | 0.033 | | |
| XDH | D4 | 205 | 45 | 15 | 0.064 | | |
| XDH | pathway | 115 | 45 | 8 | 0.053 | | |
| XDH | all | 325 | 45 | 23 | 0.066 | | |

(The 171 / 45 in the table are the comparison's fold of the decoys' 174 / 47 distinct names.)

**The 75 drugs D4 shares with NTRK3** are the cancer pharmacopoeia: the CDK4/6 inhibitors, the
mTOR inhibitors, the checkpoint antibodies, the tyrosine-kinase inhibitors — everything Open
Targets and DGIdb attach to TP53, MTOR, CDK4/6 and IGF1R also attaches to a receptor kinase's
pathway neighbours. **The gene-independent part is visible in the last two columns:** 64 of
NTRK3's approved drugs have a registered rhabdomyosarcoma trial, with NTRK3 never consulted by
that query.

**What the first grading run showed.** Before 113 refined the rule, the trial-based automated
rung was applied on every direction: **85** `BUB1B` drugs sat at automated rung 5, most on D1–D3,
because they had a rhabdomyosarcoma trial and a paediatric pointer. A trial in the tumour says
nothing about a checkpoint or a proteostasis mechanism. The rule now grades the tumour-context
direction (D4, `context: true` on the card) with trial evidence and leaves the mechanism
directions to their curated rungs. Recorded here because the decoy is what made it obvious.

## Verdict

**H049 — supported, 0.85.** D4 at 0.249 against NTRK3 is above the pre-registered line;
D1–D3 stay below it against both decoys, and XDH never crosses it. The plan's consequence
applies: **D4's automated stage is non-specific and only its curated rung counts.** The two
evidence rows rest on the same two decoy snapshots, so the confidence is held below the
arithmetic's 0.94.

## Conclusion

The mechanism directions D1–D3 are specific to the gene by this test; the tumour-context
direction is not, and could not be — it was built from the clinical side of the card, which the
decoys share. That is not a flaw in D4; it is the reason D4 must be argued from curated
mechanism results (a statin in rhabdomyosarcoma cells) and never from "this drug has a
rhabdomyosarcoma trial".

## Assumptions, limitations, quality checks

- **Limitation:** two decoys. Enough to settle a ≥ 0.10 claim in one direction, not enough
  for a distribution; a third decoy chosen by the same seeded rule would be the next step.
- **Limitation:** the decoy's pathway pattern is a choice per decoy (stated in every manifest
  by `rule_text`); a pattern matching Reactome's top-level pathways would pull in thousands of
  targets and is a different experiment.
- **Quality check:** `tests/test_drugs_ladder.py` checks Jaccard over base names on invented
  rows (a drug with two salts counts once); the decoy card builder is tested to keep the
  clinical side verbatim and replace the gene.
- **Quality check:** every decoy table carries a manifest and every decoy row is a gene
  symbol, a drug name, a trial id or a PMID — no patient data can reach a decoy by construction.
