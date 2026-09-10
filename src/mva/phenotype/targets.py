"""The blind target set: which genes the child's symptoms alone nominate.

Step 1 of iteration 2 picks the genes later steps will read DNA for, **with the DNA never
read**. This module turns one or more symptom rankings into a tiered target set, and draws
the matched decoy set that gives the read route a null.

Three things here are the plan's answers to a bias, and each is worth stating:

**Tiers, not a truncation.** ``core`` is the top 50 by symptom score, ``net`` is ranks
51-300, ``uncurated`` is the blind spot — genes the human-only ranker cannot score at all
because nobody has curated a phenotype for them. Steps 2-3 read every tier; the tier says
where human review starts, not what is looked at.

**A mechanism-term row is prior knowledge, not evidence.** "Every gene the ontology
annotates with a chromosome-instability term, whatever its rank" pre-loads exactly the gene
class the disease name points at. The rule stays — a clinician would use the disease name —
but such a gene is tagged :data:`MECHANISM`, its *pure symptom-score rank* travels beside
it, and a rediscovery claim may only be made on the pure-score ranking.

**A decoy is the read route's null.** Steps 2-3 otherwise have no way to say how often a
random gene set yields a "biallelic candidate" by chance. The decoys are matched on coding
length and exon count, carry no annotation for the case's terms, and are drawn from a
recorded seed once and never edited.

Case-agnostic by construction: nothing here knows about this child. It takes rankings, an
annotation corpus and gene features, and gives back rows.
"""

from __future__ import annotations

import random
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from .associations import Corpus
from .ontology import Ontology
from .prioritise import Ranking

#: Top-``CORE_N`` by symptom score is the tier human review starts with.
CORE_N = 50

#: The target set's size, fixed in advance. Raising it is a recorded decision, not a knob
#: turned after seeing where a gene landed.
TARGET_N = 300

CORE = "core"
NET = "net"
UNCURATED = "uncurated"
MECHANISM = "mechanism-term"

#: How a gene got into the set. ``score`` is the only route that earns a rediscovery claim.
BY_SCORE = "score"
BY_MECHANISM = "mechanism-term"

#: The two HPO roots whose descendants mean "this gene breaks chromosome segregation or
#: chromosome stability". Roots, not a gene list: the selection is term-driven, so a new
#: HPO release that curates another gene under them picks it up without a code change.
MECHANISM_ROOTS: tuple[str, ...] = (
    "HP:0002916",  # Abnormality of chromosome segregation
    "HP:0003220",  # Abnormality of chromosome stability
)


@dataclass(frozen=True)
class GeneFeature:
    """What a decoy is matched on: the shape of the gene, not its biology."""

    symbol: str
    coding_length: int
    exon_count: int


@dataclass(frozen=True)
class Target:
    """One row of the target set."""

    symbol: str
    tier: str
    #: Rank in the pure symptom-score ranking, or ``None`` when the gene has no score at
    #: all. The rediscovery claim of step 6 is made on this column alone.
    score_rank: int | None
    score: float
    entered_by: str
    #: Every term set that nominated this gene — the union is co-primary, so a gene may be
    #: nominated by one ranking and not the other, and the report shows which.
    term_sets: tuple[str, ...] = ()

    @property
    def earned_its_place(self) -> bool:
        """Whether the symptom ranking, and not the disease name, put this gene here."""
        return self.entered_by == BY_SCORE


@dataclass(frozen=True)
class Decoy:
    """One matched decoy gene, and the target it was matched to."""

    symbol: str
    matched_to: str
    coding_length: int
    exon_count: int


def mechanism_genes(
    corpus: Corpus, ontology: Ontology, roots: Iterable[str] = MECHANISM_ROOTS
) -> frozenset[str]:
    """Every gene the corpus annotates at or under one of ``roots``.

    Read through the ancestor closure, so a gene curated to "Premature chromatid
    separation" is found by the "Abnormality of chromosome segregation" root without that
    child being listed anywhere.
    """
    wanted = frozenset(roots)
    return frozenset(
        annotation.symbol
        for annotation in corpus.genes.values()
        if any(wanted & ontology.ancestors(term) for term in annotation.terms)
    )


def _score_ranks(rankings: Sequence[Ranking]) -> dict[str, tuple[int, float, list[str]]]:
    """Best (rank, score) per gene across the rankings, and which term sets nominated it.

    "Best" is the smallest rank: the term sets are co-primary and their target sets are
    unioned, so neither reading of the family-history term can hide a gene.
    """
    best: dict[str, tuple[int, float, list[str]]] = {}
    for ranking in rankings:
        name = ranking.term_set.name
        for gene in ranking.scores:
            current = best.get(gene.symbol)
            if current is None:
                best[gene.symbol] = (gene.rank, gene.score, [name])
            else:
                rank, score, sets = current
                sets.append(name)
                best[gene.symbol] = (min(rank, gene.rank), max(score, gene.score), sets)
    return best


def build(
    rankings: Sequence[Ranking],
    *,
    mechanism: Iterable[str] = (),
    core_n: int = CORE_N,
    target_n: int = TARGET_N,
) -> tuple[Target, ...]:
    """The tiered target set: the union of the rankings, plus the mechanism-term genes.

    Ordered by pure score rank, mechanism-term rows with no score last — so reading the
    table top-down is reading the symptom ranking, which is the only ordering a
    rediscovery claim may be made on.
    """
    scored = _score_ranks(rankings)
    mechanism_set = frozenset(mechanism)
    rows: list[Target] = []
    for symbol, (rank, score, sets) in scored.items():
        in_mechanism = symbol in mechanism_set
        if rank > target_n and not in_mechanism:
            continue
        tier = CORE if rank <= core_n or in_mechanism else NET
        rows.append(
            Target(
                symbol=symbol,
                tier=MECHANISM if in_mechanism and rank > core_n else tier,
                score_rank=rank,
                score=score,
                entered_by=BY_SCORE if rank <= target_n else BY_MECHANISM,
                term_sets=tuple(sorted(set(sets))),
            )
        )
    # A mechanism-term gene the ranker never scored still belongs in core: it is exactly
    # the case the term-driven rule exists for, and its empty score rank says so.
    rows.extend(
        Target(
            symbol=symbol,
            tier=MECHANISM,
            score_rank=None,
            score=0.0,
            entered_by=BY_MECHANISM,
        )
        for symbol in sorted(mechanism_set - set(scored))
    )
    return tuple(sorted(rows, key=lambda t: (t.score_rank is None, t.score_rank or 0, t.symbol)))


def uncurated_count(corpus: Corpus, protein_coding: Iterable[str]) -> tuple[int, int]:
    """``(uncurated, total)`` protein-coding genes — the blind spot, measured not assumed.

    The human-only ranker scores only genes with an HPO annotation. How large that blind
    spot is decides whether the ``uncurated`` tier is a footnote or the headline
    limitation, so it is counted and reported rather than described.
    """
    total = tuple(protein_coding)
    return sum(1 for symbol in total if symbol.upper() not in corpus.genes), len(total)


def _bucket(feature: GeneFeature, length_step: int, exon_step: int) -> tuple[int, int]:
    """The matching stratum: coding length and exon count, both coarsened.

    Coarse on purpose. Exact matching on two integers leaves most targets unmatched; the
    strata are wide enough to always hold candidates and narrow enough that a decoy is the
    same *kind* of gene — which is all the null needs.
    """
    return (feature.coding_length // length_step, feature.exon_count // exon_step)


def draw_decoys(
    targets: Sequence[Target],
    features: Iterable[GeneFeature],
    *,
    seed: int,
    excluded: Iterable[str] = (),
    length_step: int = 500,
    exon_step: int = 5,
) -> tuple[Decoy, ...]:
    """One decoy per target, matched on gene shape, drawn once from ``seed``.

    ``excluded`` is every gene that must not be a decoy: the targets themselves, and every
    gene the corpus annotates with any of the case's terms. A decoy that shares the
    phenotype would not be a null.

    A target with no eligible gene in its own stratum falls back to the nearest stratum by
    absolute distance in both coordinates; a target with no eligible gene at all is
    skipped, and the shortfall is visible as a decoy set smaller than the target set.
    """
    banned = {s.upper() for s in excluded} | {t.symbol.upper() for t in targets}
    pool: dict[tuple[int, int], list[GeneFeature]] = {}
    by_symbol: dict[str, GeneFeature] = {}
    for feature in features:
        # Every gene's shape is looked up, including a target's own — that is what a decoy
        # is matched against — but only an eligible gene may be drawn as one.
        by_symbol[feature.symbol] = feature
        if feature.symbol.upper() not in banned:
            pool.setdefault(_bucket(feature, length_step, exon_step), []).append(feature)
    for bucket in pool.values():
        bucket.sort(key=lambda f: f.symbol)

    rng = random.Random(seed)
    taken: set[str] = set()
    drawn: list[Decoy] = []
    for target in targets:
        shape = by_symbol.get(target.symbol)
        if shape is None:
            continue
        wanted = _bucket(shape, length_step, exon_step)
        candidate = _pick(pool, wanted, taken, rng)
        if candidate is None:
            continue
        taken.add(candidate.symbol)
        drawn.append(
            Decoy(
                symbol=candidate.symbol,
                matched_to=target.symbol,
                coding_length=candidate.coding_length,
                exon_count=candidate.exon_count,
            )
        )
    return tuple(drawn)


def _pick(
    pool: dict[tuple[int, int], list[GeneFeature]],
    wanted: tuple[int, int],
    taken: set[str],
    rng: random.Random,
) -> GeneFeature | None:
    """A free gene from ``wanted``, else from the nearest stratum that has one."""
    order = sorted(pool, key=lambda b: (abs(b[0] - wanted[0]) + abs(b[1] - wanted[1]), b))
    for bucket in order:
        free = [f for f in pool[bucket] if f.symbol not in taken]
        if free:
            return rng.choice(free)
    return None
