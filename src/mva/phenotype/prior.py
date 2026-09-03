"""The bridge from a phenotype ranking into the pair ranker.

:func:`mva.pipeline.ranking.rank_pairs` already accepts ``gene_prior: dict[str, float]``
and multiplies a pair's score by its gene's entry. Today nothing supplies one in
production - ``{"BUB1B": 2.0}`` appears in tests and nowhere else - and
:mod:`mva.science.dossier` treats any prior other than 1.0 as **neutral evidence of
strength zero**, recording that "the ranking reflects a stated assumption, not the data
alone". That is the correct treatment of a number somebody typed.

This module supplies the same dict from a phenotype ranking instead, and the difference is
not cosmetic. A hand-set prior is an assertion about which gene matters; a derived one is a
measurement of how well the child's recorded features match what each gene is known to
cause, over five thousand genes, computed by something that never saw the candidate panel.
The first cannot carry evidence weight. The second can - and once it does, the dossier
entry changes from a disclosure into a citation.

**Nothing in** :mod:`mva.pipeline` **changes.** That package is a leaf and imports no
sibling; the adapter lives here, on the phenotype side of the seam, and the caller wires
the two together. The whole integration is one dict.

**The shape of the multiplier is a choice, and it is stated rather than tuned.** Scores
arrive on ``0..1``; a prior is a multiplier centred on 1.0. Mapping one onto the other with
``1 + strength * score`` keeps three properties that matter more than any fitted curve:

* an unranked gene gets exactly 1.0, so a gene HPO has never curated is neither rewarded
  nor punished - missing knowledge stays missing, it does not become a negative finding;
* the multiplier is monotone in the score, so the ordering the phenotype produced survives;
* ``strength`` is one number, visible at the call site, and setting it to zero disables the
  whole mechanism. With N=1 and no training data, a transparent knob that can be turned off
  is defensible in the methods write-up in a way a fitted transform is not.
"""

from collections.abc import Iterable

from .prioritise import Ranking

#: How far the strongest possible phenotype match may move a pair's score. At 1.0 a perfect
#: match doubles it and a non-match leaves it untouched - deliberately modest, because the
#: phenotype says which *gene* is likely broken and the pair score is about the alleles.
DEFAULT_STRENGTH = 1.0


def gene_prior(
    ranking: Ranking,
    *,
    strength: float = DEFAULT_STRENGTH,
    limit: int | None = None,
    genes: Iterable[str] | None = None,
) -> dict[str, float]:
    """A ``{symbol: multiplier}`` dict for :func:`mva.pipeline.ranking.rank_pairs`.

    ``limit`` keeps only the top *n* genes; ``genes`` keeps only named ones. Both default
    to off. A gene left out is simply absent from the dict, and ``rank_pairs`` already
    falls back to 1.0 for a gene it cannot find - so "not in the prior" and "no phenotype
    signal" reduce to the same neutral multiplier, which is the honest default.
    """
    if strength < 0:
        raise ValueError(f"strength must not be negative; got {strength}")

    wanted = {symbol.upper() for symbol in genes} if genes is not None else None
    selected = ranking.top(limit) if limit is not None else ranking.scores

    prior: dict[str, float] = {}
    for score in selected:
        if wanted is not None and score.symbol not in wanted:
            continue
        prior[score.symbol] = 1.0 + strength * score.score
    return prior


def explain(ranking: Ranking, symbol: str, *, strength: float = DEFAULT_STRENGTH) -> str:
    """One sentence saying why a gene got the multiplier it got.

    Written for the evidence register, which refuses an observation that does not name its
    source. The sentence quotes the rank, the population it was drawn from, and the feature
    match that drove it - never a genomic position, which the register also refuses.
    """
    score = ranking.by_symbol(symbol)
    if score is None:
        return (
            f"{symbol.upper()} carries no curated phenotype annotation in this HPO "
            f"release, so it takes the neutral prior of 1.0 - an absence of knowledge, "
            f"not evidence against it."
        )
    multiplier = 1.0 + strength * score.score
    return (
        f"{score.symbol} ranks {score.rank} of {ranking.considered} genes against the "
        f"{ranking.term_set.name} term set ({len(ranking.term_set)} terms), scoring "
        f"{score.score:.3f} on {score.summary}; gene prior {multiplier:.3f}."
    )
