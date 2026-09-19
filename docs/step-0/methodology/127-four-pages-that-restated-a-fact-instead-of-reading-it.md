# 127 — Four places that restated a fact instead of reading it

**Date:** 2026-09-19
**Question:** Entry 126 left three known gaps and found a fourth. All four are the same
defect: a page stating a number, a version or a status that some other file owns, and going
stale when the owner changed. Which were still wrong, and can each be made to read its
source instead of repeating it?

_(step-0 platform machinery: a delivery-surface defect and its fix, not a hypothesis. Per
[`docs/method.md`](../../method.md) step 0 takes no hypotheses. Filed in step 0 because the
four sites span `/track2`, `/learn`, the docs index and iteration 4's own index. Supersedes
nothing; it closes items entry 126 listed as "not done, and known".)_

## What was observed

| # | Site | Said | Truth |
|---|---|---|---|
| 1 | `STRATEGY` in `src/mva/viz/track2.py`, rendered verbatim on `/track2` | "the mechanism card (… version 2)" and "*F8 is the one fact still marked unmeasured: step 8 has not run*" | the card is at **version 4** and its history row for 2026-09-19 records F8 measured by step 8 (`ressources/track2/mechanism.json`) |
| 2 | `docs/iteration4/README.md` | "**all `planned`**. No step has run; no claim is filed"; "the first iteration-4 entry is **111**" | steps 1 and 2 **done**, step 3 **open**, four claims filed (H058-H060, H062); the entries are **114**, **119**, **122** |
| 3 | `docs/README.md` §Iteration 4 | "Nothing trained, nothing fine-tuned, **nothing run yet**" | same as above; the plan row was describing the plan and being read as the status |
| 4 | The `/learn` page and three files behind it | "in **fifteen** chapters" | the generator reports **24 chapters, 615 entries** |

A fifth, of the same kind, in the dictionary itself: `Measured fact (on the card)` described
"mechanism card v3's `measured_facts`" and said one of the nine is "honestly *unmeasured*".

Separately, six `terms.draft.md` files under `docs/iteration4/step-*/` held drafted
vocabulary that had never reached `docs/dictionary.md`, so `allele record`, `adapter`,
`inference tier`, `catalogue-adjacent` and fifteen other words in daily use in iteration 4
were absent from `/learn` — the app's only glossary.

## What was changed

**1 — the strategy reads the card.** `STRATEGY` is now `PHASES` plus a `strategy(card)`
function. The two sentences that are facts *about the card* — its version, and what its last
revision changed — are formatted from `card["version"]` and the newest row of
`card["history"]`, which is the card's own authored sentence, quoted rather than restated.
The rest of the list stays written down: it is a *plan*, and no measurement can say that the
merge waits on the last oracle reply. Two tests pin it, including one for a card with no
history at all.

**2, 3 — the two indexes** now carry per-step status, the methodology entry and the verdicts,
and say plainly that they were wrong before, with a pointer to entry 126. `docs/README.md`
gains a row for `iteration4/README.md` and one for its three run steps; the plan row now ends
by naming the index as the thing that says how far the work got, instead of answering that
question itself.

**4 — the chapter count** is gone from prose in four files. A generated chapter list had its
length typed beside it, which is a copy of a number with an owner.

**5 — the dictionary merge.** Chapter **24, "The model zoo — words for iteration 4"**: 18
entries in dependency order, from the drafts of the three iteration-4 steps that have run.
Three drafted terms were folded into entries that already existed rather than appended —
`HGVS` (which gains `hgvs_c`/`hgvs_p` and the reason an allele with no HGVS spelling cannot be
looked up at all), `UniProt accession` (the isoform suffix and why the zoo drops it) and
`Zero-shot` (the full definition the zoo works from) — because the one-dictionary rule makes
improving an entry the only alternative to duplicating it. The three merged drafts are marked
as merged and are no longer the source of their definitions; the drafts for steps 4-6 stay
unmerged, because those steps have not run and their words name machinery that does not exist.

`Measured fact (on the card)` was rewritten to say that the card is append-only and that F8
read unmeasured on version 3 and was measured on version 4 — which is the fact, rather than a
snapshot of it.

## Commands

```bash
uv run pytest tests/test_viz_track2.py -q          # 16 passed, incl. the two new ones
cd app && pnpm run dictionary && pnpm run check
uv run ./tools/check-python.sh
# rendered against the live API, Chromium headless:
#   /track2 (after ?refresh=true — the whole payload is one cache entry), /learn#24-...
```

## Observed output

```
16 passed                                   tests/test_viz_track2.py
gen-dictionary: wrote 24 chapters, 615 entries, 20 figures, 22 diagrams, 192 context lines
python gate: green                          2956 passed, 5 skipped
app: 45 files, 649 tests passed             typecheck, lint, format, theme, dictionary clean

# /api/track2, verdicts phase, before and after the cache was refreshed
cached : … so the mechanism card m[oved to version 3 … step 8 has not run]
refresh: … so the mechanism card is revised rather than edited: a new version and a history
         entry each time a measured fact lands. It is at version 4; its last revision
         (2026-09-19) records: F8 measured by step 8: no autosome above its 2-3 % detection
         limit in the sequenced sample …
```

Read in a browser: `/track2`'s strategy timeline shows "now at version 4" on phase 1 and the
card's own v4 history sentence on phase 5; `/learn` chapter 24 of 24 renders its 18 terms with
every `related:` chip resolving.

**The cache is worth noting.** `/api/track2` is one cache entry on disk, so the corrected text
did not appear until `?refresh=true` — the route documents this, and it is why the first
browser check showed the old sentence against new code. Nothing was wrong with the fix.

## Conclusion

The defect class, not the four instances, is the result: a page that *restates* a fact goes
stale silently, and nothing fails when it does. Where the fact had an owner the page now reads
it (the card's version and history); where the number was generated the prose stopped naming
it (the chapter count); where the statement was a status somebody had to write, it now sits in
one index with a date and a pointer to what it was corrected from.

**Not done, and known:** iteration 4 still has no step detail pages and no `/api/zoo/*` routes
(its `todo.md` wave 3 declares them), so `/steps?iteration=iteration4` remains its whole
surface. The `terms.draft.md` files for its steps 4-6 stay unmerged by design.
