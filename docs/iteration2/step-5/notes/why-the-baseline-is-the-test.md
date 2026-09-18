# Why the citation baseline *is* the test, and not a caveat on it

**Standing:** written 2026-09-18 with step 5. Holds for any literature or knowledge route in
this repository, including Track 2's evidence ladder.

## The result in one sentence

A literature route must clear **two** pre-registered conditions before it may contribute a
*ranking* to anything: it must separate symptom-nominated genes from **matched decoys**, and
it must reorder a ranking built from **publication counts alone**. Either one failing makes
it a confirmation route at weight zero.

## Why

Iteration 2 has now twice measured a route that looked convincing and ordered nothing.

* The **read route** enumerated biallelic candidates in target and decoy genes at *exactly*
  the same rate — 10 of 396 each, Fisher one-sided p = 0.589 — which refuted H020 on its own
  pre-registered condition and demoted the route to confirmation
  ([090](../../step-2/methodology/090-the-alleles-the-vendor-never-reported.md)).
* The **symptom ranker** measured held-out recall@300 of 0.360 against a filed prediction of
  ≥ 0.90, which turned the target set from coverage into an enrichment
  ([084](../../step-1/methodology/084-the-blind-target-set.md)).

A literature route is more exposed to this than either of them, for a reason that has
nothing to do with our code:

> The gene at the top of any biomedical search is the gene most has been written about, and
> in a candidate set derived from a patient's symptoms, the gene most has been written about
> is very often the one somebody already solved.

A route can therefore produce a beautiful, correct-looking top row **and have learned
nothing about this patient**. Nothing in its output distinguishes the two cases. Only a
comparison does.

## The two comparisons, and why neither alone is enough

| Comparison | What it catches | What it misses |
|---|---|---|
| **matched decoys** — 396 control genes matched on coding length and exon count, through the identical queries | a route that fires on any gene at all | a route that separates *because* nominated genes are better studied; famous genes are both more nominated and more published |
| **citation-volume baseline** — the same genes ranked by raw PubMed hit count | a route that has reproduced how much has been written | a route that reorders the count but cannot tell a candidate from a control, i.e. reorders it into noise |

They fail in opposite directions, so the condition is **conjunctive**. Implemented in
`mva.knowledge.baselines.weigh`, which returns both measurements and the route's entitlement
in one object rather than leaving the conjunction to a caller's discretion.

## The design consequence that is easy to miss

**The knowledge score must not contain the thing it is measured against.** So it is
lexicographic on `(best paper's matched-term count, published alleles this child carries)`
and breaks its ties on the **gene symbol** — which carries nothing — rather than on
publication count. A tie-break on citations would have been the obvious, tidy choice, and it
would have quietly made the comparison unanswerable.

**Length-matching the decoys matters more here than anywhere else in the iteration.** A
longer gene carries more alleles *and* attracts more papers. Step 1 drew the decoys matched
on coding length and exon count for a different reason; in this step that matching is what
stops the decoy null from measuring gene size and reporting it as knowledge.

## What this note does not claim

It does not claim the conditions are sufficient. A route could clear both and still be
riding some third confound nobody has named. It claims only that a route which clears
*neither* has not been shown to know anything, and that saying so in advance is cheaper than
arguing about it afterwards.

Related: [`../../../notes/`](../../../notes/) for the cross-step decisions;
[102](../methodology/102-the-sources-and-what-they-could-be-asked.md) for the instruments.
