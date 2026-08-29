# Functional annotation enters through a port, not a direct VEP call

**Standing:** the port is settled; the backend behind it is deliberately open. Revisit
once a real annotator is wired and we know which fields actually carry the ranking.

The proband VCF carries no annotation worth ranking on: `INFO` holds caller statistics
only, and its `AF` field is *within-sample* — 0.5 or 1.0 for a single sample — so reading
it as a population frequency would be a serious and silent error. The only usable raw
signal is the dbSNP membership flag, a weak novelty proxy.

Everything the ranker needs therefore comes from outside. `annotation.py` defines an
`Annotator` protocol returning gene, consequence and gnomAD frequency; `DictAnnotator` is a
lookup table used as the test fake and usable as a production cache. Ranking logic is fully
testable today against known consequences, and choosing a real backend — offline VEP cache,
Ensembl REST, a prebuilt table — becomes a swap rather than a rewrite.

## Considered options

Wiring VEP directly was rejected because it would have made every ranking test depend on a
multi-gigabyte cache download, and because the backend choice is genuinely still open: the
offline cache is right for the genome-wide run and wrong for annotating the
[panel](../../ideation/data-findings.md) today.

## Consequences

An unseen variant returns an empty `Annotation` rather than raising. A genome-wide run will
always reach variants outside any cache, and crashing there would lose the run.
