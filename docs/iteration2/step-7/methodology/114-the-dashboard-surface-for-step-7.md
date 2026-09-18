# 114 — The dashboard surface for step 7: where a reader sees the approach, the suggestion and the output

**Written:** 2026-09-18. **Step:** `step-7` (iteration 2). **Hypotheses:** none — this is a
machinery entry inside a research step ([method.md](../../../method.md): a tool a step needs is
recorded in that step's log). It records what `/track2` and `/submissions` gained, and the one
rule that made the page honest: **every number on the page is computed from the API payload,
never typed.**

## Question

Steps 110–113 produced twelve tables, five figures and a submission folder. A reader of the
dashboard saw a 24,000-pixel page whose first screen was a strategy timeline and whose
suggestion appeared after the mechanism card. The user's ask, verbatim: *"place it well to
understand the approach and see the suggestion and the output, use visualization and clear
communication."* What does the page have to show first, and from what?

## Inputs

| Source | What is read |
|---|---|
| `GET /api/track2` | the whole surface: card v3 (`measured_facts`, `anti_directions`, `evidence_ladder`, `repurposing_directions[].context`), the twelve tables, `decoys`, the register for step-7 and step-8 |
| `GET /api/submissions` | the Track 2 folder (`submissions/track2/iteration-1/`, state draft, panel-judged) beside the two Track 1 iterations |
| `docs/dictionary.md` chapter 23 | the fourteen step-7 terms the page links to `/learn` |

Both are captured as fixtures (`app/src/fixtures/data/track2.json`, sha256
`d3e563ba…`, hash `4d20555cf73904be`; `submissions.json`, hash `27fd706881726b73`) so the
hosted page renders with the API down, and the fixture badge says so.

## What was built (all under `app/`, commits `be31c53` and `284910a`)

**The hero, "Track 2 in one screen"**, first thing after the callout:

| Panel | Shows | Computed from |
|---|---|---|
| the approach | five stages left to right — [purple] the confirmed pair + the clinical terms → [blue] card v3 → [blue] 7 public sources, 359 approved drugs on 277 targets → [yellow] the ladder, 13 curated papers, 2 decoy genes → [green] 11 argued · [red] 23 set aside; each box anchors to its section | `card.version`, `summary`, `evidence.length`, `decoys.length`, `shortlist` verdicts, `do_not.length` |
| the suggestion | the 11 `argue` rows as cards grouped D4 → D3 → D2, each with rung badge, `proxy · <compound tested>`, the paper's sentence (read-more), paediatric pointers, `PMID nnnnnnnn` links; a red strip of the 13 caution drugs with vincristine and vinorelbine marked standard of care; one grey line for the 50 context-trial-only rows | `shortlist`, `evidence`, `do_not` |
| the output | a funnel 359 → 329 → 69 → 11, 23 set aside beside it; the F8-unmeasured chip; links to the report, the tables, the figures, entries 110–113, H045–H050 | `evidence_ladder`, `card.measured_facts` |

**The pathway diagram** in the mechanism section: the spine (alleles → less BubR1 → premature
separation → aneuploid cells, burden UNMEASURED → rhabdomyosarcoma) with the three yellow
direction branches carrying their shortlisted drug names, and two dotted red branches (D1: no
approved drug; A2: spindle poisons need the checkpoint).

**Order**: header → hero → beginner guide → mechanism (card, pathway, directions) → measured
facts → ladder → shortlist → do-not → decoy control → paediatric pointers → targets →
candidates → trials/literature → strategy (moved down, "how this page was produced") → linked
iterations → register (step-7 and step-8 claims, step badge) → catalog → lineage.

**`/submissions`**: a panel-judged folder shows "what the panel receives" (report, methods
form, repository, video) instead of the decode table, CSV and selectors, and gets its own
six-step beginner walkthrough built from its payload.

## Rules the page keeps

- **Colour discipline** on every exhibit with a legend line: green = the goal / a curated
  result at rung ≥ 4; yellow = a decision point / a curated result at rung 2–3 / the 0.10
  line; blue = machinery / automated-only cells (already being tried, not a finding); red =
  set aside; purple = raw input.
- **No bare 8-digit number** in body text: PMIDs render as `PMID nnnnnnnn` links, so the
  page's coordinate check (`renders no genomic position anywhere`) keeps its meaning.
- **Nothing typed.** The beginner guide's last step, the stat tiles, the funnel and every
  count read the payload; a re-run of `tools/track2_enrich.py` and a fixture recapture move
  every number on the page at once.

## Observed

```
pnpm run check   lint · format · theme · dictionary green; vitest 22 passed in the two Track 2
                 suites (track2-page 16, track2-hero 6); submissions-page 15 (3 new)
                 typecheck: 5 errors in src/pages/steps/step8/{Deviation,Models}.tsx - another
                 session's committed step-8 work, outside this entry; reported to that session
screenshots      scratchpad hero-0..13.png, subs-0..3.png reviewed; two fixes made before
                 commit: the funnel's widest label was clipped; proxy compounds were being
                 title-cased ("Hdac2/3 Loss") - only a >=7-char all-caps word is folded now
```

## Conclusion

The first screen now answers the three questions in order — how the answer was reached, what
the answer is, and what it rests on — with the disclaimers in the same frame ("hypotheses for
follow-up, not evidence that a medicine works"; "never advice to withhold treatment"). The
long-form sections below are unchanged and remain the audit trail.

## Assumptions, limitations, quality checks

- **Limitation:** the fixture is 6.8 MB because `pediatric_trials` carries 11,698 rows; it is
  a lazy chunk (888 kB gzip) and not in the entry bundle. The bundle budget was already ~1.3 kB
  over before this work (measured against HEAD in a throwaway worktree) and is noted in
  `app/README.md`.
- **Limitation:** the hero reads `summary.card.tumour_context` rather than
  `card.case.tumour_context` because the latter embeds an HPO id whose digits trip the
  coordinate-shaped-number check; the text shown is the same word.
- **Quality check:** `track2-hero.test.tsx` asserts the five approach boxes, the 11 cards, the
  funnel, the caution strip naming vincristine, the F8 chip, the pathway's "no approved drug"
  text, and that the hero precedes the strategy heading in document order.
