"""The controls that make a phenotype-twin result mean something.

A single rank ("the best Bub1b mouse is 40th of 77k") is uninterpretable on its own:
maybe *any* eight terms that specific would land a Bub1b mouse near the top, maybe the
method finds nobody's gene. So every twin claim ships with:

* **An IC-matched null** (:func:`matched_null_sets`). Replace each query term with a random
  mappable HP term of similar projected information content, re-score, record where the
  gene's best genotype lands. The empirical p-value is the share of random sets that do at
  least as well (with the +1 correction, so it is never zero).
* **A gene lookup** (:func:`best_for_gene`): the best-scoring genotype carrying the gene,
  used for the gene under test, the positive control and the within-pathway comparison.
* **Allele classes** (:func:`allele_class`) from MGI's own attributes.
* **Leave-one-term-out** (:func:`leave_one_out`): which query terms carry the match.

All gene- and disease-agnostic; the case lives in the CLI.
"""

import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from .cross_species import Bridge, MouseCorpus, Scores, self_score
from .cross_species_io import Allele, Genotype

HYPOMORPH = "hypomorph"
NULL = "null"
KNOCK_IN = "knock-in"
OTHER = "other"


def allele_class(genotype: Genotype, alleles: Mapping[str, Allele], marker_id: str) -> str:
    """The class of a genotype at one gene, from MGI's allele attributes.

    * ``hypomorph`` - at least one allele of the gene is labelled ``Hypomorph``.
    * ``null`` - every non-wild-type allele of the gene is ``Null/knockout`` (homozygous,
      compound null, or heterozygous over ``+``).
    * ``knock-in`` - otherwise, when some allele carries a changed sequence (patient
      mutation, point mutation, humanised or modified isoform).
    * ``other`` - anything else (transgenes, reporters with no function label).
    """
    mine = [
        alleles[s]
        for s in genotype.allele_symbols
        if s in alleles and alleles[s].marker_id == marker_id and not s.endswith("<+>")
    ]
    if any("Hypomorph" in a.attributes for a in mine):
        return HYPOMORPH
    if mine and all("Null/knockout" in a.attributes for a in mine):
        return NULL
    changed = {"Humanized sequence", "Modified isoform(s)", "Not Applicable", "Not Specified"}
    if any(changed & set(a.attributes) or a.allele_type == "Targeted" for a in mine):
        return KNOCK_IN
    return OTHER


def genotypes_of(
    corpus: MouseCorpus, genotypes: Mapping[str, Genotype], marker_id: str
) -> list[int]:
    """Corpus rows of every scored genotype that involves ``marker_id``."""
    return [
        corpus.row_of[g.genotype_id]
        for g in genotypes.values()
        if marker_id in g.marker_ids and g.genotype_id in corpus.row_of
    ]


@dataclass(frozen=True)
class GeneHit:
    """The best genotype of one gene against one query."""

    genotype_id: str
    row: int
    score: float
    rank: int
    percentile: float
    n_genotypes: int


def best_for_gene(
    scores: Scores, corpus: MouseCorpus, rows: Sequence[int], metric: str = "symmetric"
) -> GeneHit | None:
    """The top-scoring genotype among ``rows``, with its pessimistic rank; ``None`` if empty."""
    if not rows:
        return None
    values = scores.metric(metric)
    best = max(rows, key=lambda r: float(values[r]))
    return GeneHit(
        genotype_id=corpus.genotype_ids[best],
        row=best,
        score=float(values[best]),
        rank=scores.rank(best, metric),
        percentile=scores.percentile(best, metric),
        n_genotypes=len(rows),
    )


def projected_ic(corpus: MouseCorpus, bridge: Bridge) -> dict[str, float]:
    """Every mappable HP term -> the IC of its most informative MP projection (> 0 only)."""
    out = {hp: self_score(corpus, bridge, hp) for hp in bridge.mappable()}
    return {hp: ic for hp, ic in out.items() if ic > 0}


def matched_null_sets(
    query: Sequence[str],
    pool: Mapping[str, float],
    n: int,
    window: float = 0.25,
    seed: int = 0,
) -> list[tuple[str, ...]]:
    """``n`` random term sets, each query term swapped for a pool term of similar IC.

    The pool excludes the query's own terms. A query term whose ±``window`` band holds
    fewer than 10 pool terms widens the band to its 10 nearest pool terms, so a rare
    term is never matched to itself by exhaustion.
    """
    rng = random.Random(seed)
    candidates = sorted((ic, hp) for hp, ic in pool.items() if hp not in set(query))
    ics = np.array([ic for ic, _ in candidates])
    bands: list[list[str]] = []
    for hp in query:
        target = pool.get(hp, 0.0)
        band = [candidates[i][1] for i in np.flatnonzero(np.abs(ics - target) <= window)]
        if len(band) < 10:
            nearest = np.argsort(np.abs(ics - target))[:10]
            band = [candidates[i][1] for i in nearest]
        bands.append(band)
    sets: list[tuple[str, ...]] = []
    for _ in range(n):
        drawn: list[str] = []
        for band in bands:
            choice = rng.choice(band)
            while choice in drawn and len(set(band) - set(drawn)) > 0:
                choice = rng.choice(band)
            drawn.append(choice)
        sets.append(tuple(drawn))
    return sets


def empirical_p(observed_percentile: float, null_percentiles: Sequence[float]) -> float:
    """(1 + #null at least as good) / (1 + n). Lower percentile = better."""
    hits = sum(1 for p in null_percentiles if p <= observed_percentile)
    return (1 + hits) / (1 + len(null_percentiles))


def draws(terms: Sequence[str], k: int, n: int, seed: int = 0) -> list[tuple[str, ...]]:
    """``n`` seeded samples of ``k`` terms (all of them if there are no more than ``k``)."""
    rng = random.Random(seed)
    pool = list(dict.fromkeys(terms))
    if len(pool) <= k:
        return [tuple(pool)] * n
    return [tuple(rng.sample(pool, k)) for _ in range(n)]


@dataclass(frozen=True)
class Dropout:
    """The gene's best genotype with one query term removed."""

    dropped: str
    genotype_id: str
    rank: int
    percentile: float


def leave_one_out(
    corpus: MouseCorpus,
    bridge: Bridge,
    query: Sequence[str],
    rows: Sequence[int],
    metric: str = "symmetric",
) -> list[Dropout]:
    """Re-score with each term dropped; a big rank loss marks a term that carries the match."""
    out: list[Dropout] = []
    for term in query:
        reduced = [t for t in query if t != term]
        hit = best_for_gene(corpus.score(reduced, bridge), corpus, rows, metric)
        if hit is not None:
            out.append(Dropout(term, hit.genotype_id, hit.rank, hit.percentile))
    return out
