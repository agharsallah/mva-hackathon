"""Score a human HPO term set against every mouse genotype, in one vectorised pass.

**The question it answers.** "Which mouse model looks most like this patient?" The patient
is described in HPO (Human Phenotype Ontology); a mouse genotype in MP (Mammalian
Phenotype ontology). Two vocabularies, one comparison.

**How, in three moves.**

1. **Project the query into MP** (:class:`Bridge`). Each HP term is translated into the MP
   terms a mapping source says it corresponds to. Tier 1 = curated or logical mappings;
   tier 2 = a fuzzy fallback used only when tier 1 is empty, and flagged. The mouse side is
   never translated: ~77k genotypes stay in their native vocabulary.
2. **Measure rarity on the mouse corpus** (:class:`MouseCorpus`). The information content
   (IC) of an MP term is ``-ln(share of genotypes whose closure contains it)``. "Abnormal
   body size" is common and says little; "nephrocalcinosis" is rare and says a lot.
3. **Resnik similarity, rolled up best-match-average (BMA)** - the same rule as
   :mod:`mva.phenotype.similarity`. Two terms are as similar as the IC of their most
   informative common ancestor. For each query term, its best partner in the genotype;
   average those (*forward*); the same from the genotype side (*reverse*); the mean of the
   two is *symmetric*, the primary score. A Phenodigm-style score (max and average, each
   over the query's self-score) is kept as a second rollup.

**Why vectorised.** Per query term, one pass over the MP closure matrix gives its Resnik
similarity to *every* MP term (``sim[m] = max IC(a) over shared ancestors a``). A genotype's
best match is then a row-max over its annotation indices. One 8-term query against 77k
genotypes costs milliseconds, which is what makes a 1,000-set null distribution cheap.

**What this is not.** Not OWLSim and not the Monarch Phenodigm service: those reason over
the full uPheno ontology. This is a transparent approximation (project, then Resnik in MP)
whose every number can be traced to a mapping row and an ancestor.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt
from scipy import sparse

from .cross_species_io import BridgeRow, Genotype
from .ontology import Ontology

Vector = npt.NDArray[np.float64]

#: Similarity vectors kept per corpus (one float per MP term each, ~120 kB).
CACHE_LIMIT = 4096


@dataclass(frozen=True)
class Bridge:
    """HP term -> the MP rows it projects onto (tier 1 if any, else tier 2)."""

    rows: Mapping[str, tuple[BridgeRow, ...]]

    def project(self, hp: str) -> tuple[BridgeRow, ...]:
        """The rows used for ``hp``: every tier-1 row, or the tier-2 rows when none exists."""
        rows = self.rows.get(hp, ())
        tier1 = tuple(r for r in rows if r.tier == 1)
        return tier1 or tuple(r for r in rows if r.tier == 2)

    def mp_terms(self, hp: str) -> tuple[str, ...]:
        """The MP ids ``hp`` projects onto, deduplicated, in source order."""
        return tuple(dict.fromkeys(r.mp for r in self.project(hp)))

    def mappable(self) -> tuple[str, ...]:
        """Every HP term with at least one usable row."""
        return tuple(hp for hp in self.rows if self.project(hp))


def build_bridge(rows: Iterable[BridgeRow], mp: Ontology) -> Bridge:
    """Group rows by HP term, keeping only MP targets the MP release resolves."""
    grouped: dict[str, list[BridgeRow]] = {}
    for row in rows:
        live = mp.resolve(row.mp)
        if live is None:
            continue
        fixed = BridgeRow(row.hp, live, row.predicate, row.source, row.tier)
        grouped.setdefault(row.hp, []).append(fixed)
    return Bridge({hp: tuple(dict.fromkeys(rs)) for hp, rs in grouped.items()})


@dataclass(frozen=True)
class Scores:
    """Every genotype scored against one query, all rollups kept."""

    query: tuple[str, ...]
    forward: Vector
    reverse: Vector
    symmetric: Vector
    phenodigm: Vector
    #: genotypes x query terms: each query term's best Resnik partner in the genotype.
    per_term: npt.NDArray[np.float64]

    def metric(self, name: str) -> Vector:
        """One rollup by name: ``symmetric`` (primary), ``forward``, ``reverse``, ``phenodigm``."""
        values: Vector = getattr(self, name)
        return values

    def rank(self, index: int, metric: str = "symmetric") -> int:
        """Pessimistic rank: the number of genotypes scoring at least this one's score."""
        values = self.metric(metric)
        return int(np.count_nonzero(values >= values[index] - 1e-12))

    def percentile(self, index: int, metric: str = "symmetric") -> float:
        """Rank as a percentage of all genotypes (lower = closer to the top)."""
        return 100.0 * self.rank(index, metric) / len(self.symmetric)


@dataclass
class MouseCorpus:
    """The MP graph plus every genotype's annotations, as sparse matrices.

    ``closure[m, a] = 1`` when ``a`` is an ancestor of ``m`` (reflexive).
    ``annotations[g, m] = 1`` when genotype ``g`` is curated to ``m`` directly.
    """

    ontology: Ontology
    terms: tuple[str, ...]
    index: dict[str, int]
    genotype_ids: tuple[str, ...]
    row_of: dict[str, int]
    closure: sparse.csc_matrix
    annotations: sparse.csr_matrix
    ic: Vector
    #: genotype annotations whose MP id the release could not resolve (dropped, counted).
    unresolved: int
    _sizes: Vector = field(repr=False, default_factory=lambda: np.zeros(0))
    _cache: dict[tuple[str, ...], Vector] = field(repr=False, default_factory=dict)

    def __post_init__(self) -> None:
        self._sizes = np.diff(self.annotations.indptr).astype(np.float64)

    def __len__(self) -> int:
        return len(self.genotype_ids)

    def mica(self, left: str, right: str) -> tuple[str | None, float]:
        """Most informative common ancestor of two MP terms, and its IC."""
        return self.ontology.most_informative_common_ancestor(left, right)

    def similarity_to_all(self, mp_terms: Sequence[str]) -> Vector:
        """Resnik similarity of the best of ``mp_terms`` to every MP term in the corpus."""
        key = tuple(sorted(t for t in mp_terms if t in self.index))
        hit = self._cache.get(key)
        if hit is None:
            hit = self._similarity(key)
            if len(self._cache) >= CACHE_LIMIT:
                self._cache.clear()
            self._cache[key] = hit
        return hit

    def _similarity(self, key: tuple[str, ...]) -> Vector:
        """``sim[m] = max IC(a)`` over ancestors ``a`` shared by ``m`` and any term in ``key``.

        The max over query terms of the max over their ancestors equals the max over the
        union of their closures, so one column slice of the closure matrix answers it.
        """
        if not key:
            return np.zeros(len(self.terms))
        ancestors = sorted(
            {self.index[a] for t in key for a in self.ontology.ancestors(t) if a in self.index}
        )
        weights = self.ic[ancestors]
        block = self.closure[:, ancestors].multiply(weights[np.newaxis, :]).tocsr()
        out: Vector = np.asarray(block.max(axis=1).todense()).ravel().astype(np.float64)
        return out

    def genotype_terms(self, genotype_id: str) -> tuple[str, ...]:
        """The MP ids curated to one genotype (resolved), in corpus order."""
        row = self.row_of[genotype_id]
        cols = self.annotations.indices[
            self.annotations.indptr[row] : self.annotations.indptr[row + 1]
        ]
        return tuple(self.terms[c] for c in sorted(cols))

    def score(self, query: Sequence[str], bridge: Bridge) -> Scores:
        """Score the HP ``query`` against every genotype. Unmappable terms score zero."""
        sims = [self.similarity_to_all(bridge.mp_terms(hp)) for hp in query]
        indptr, indices = self.annotations.indptr, self.annotations.indices
        starts = indptr[:-1]
        per_term = np.column_stack([np.maximum.reduceat(s[indices], starts) for s in sims])
        best_for_mouse = np.max(np.vstack(sims), axis=0)
        reverse = np.add.reduceat(best_for_mouse[indices], starts) / self._sizes
        forward = per_term.mean(axis=1)
        symmetric = (forward + reverse) / 2.0
        self_ic = np.array([self_score(self, bridge, hp) for hp in query])
        opt_avg = float(self_ic.mean()) if len(self_ic) else 0.0
        opt_max = float(self_ic.max()) if len(self_ic) else 0.0
        maximum = per_term.max(axis=1)
        zeros = np.zeros_like(symmetric)
        phenodigm: Vector = 50.0 * (
            (maximum / opt_max if opt_max > 0 else zeros)
            + (symmetric / opt_avg if opt_avg > 0 else zeros)
        )
        return Scores(tuple(query), forward, reverse, symmetric, phenodigm, per_term)

    def term_matrix(
        self, genotype_id: str, query: Sequence[str], bridge: Bridge
    ) -> tuple[tuple[str, ...], npt.NDArray[np.float64]]:
        """Query terms x the genotype's MP terms: the Resnik similarity of each pair."""
        mouse_terms = self.genotype_terms(genotype_id)
        cols = [self.index[t] for t in mouse_terms]
        rows = [self.similarity_to_all(bridge.mp_terms(hp))[cols] for hp in query]
        return mouse_terms, np.vstack(rows) if rows else np.zeros((0, len(cols)))


@dataclass(frozen=True)
class TermPair:
    """Why one query term matched one genotype: which MP term, through which ancestor."""

    hp: str
    projected: str | None
    mouse_term: str | None
    common_ancestor: str | None
    ic: float


def explain(
    corpus: MouseCorpus, genotype_id: str, query: Sequence[str], bridge: Bridge
) -> list[TermPair]:
    """The best (projection, mouse term, ancestor) triple behind each query term's score."""
    mouse_terms = corpus.genotype_terms(genotype_id)
    out: list[TermPair] = []
    for hp in query:
        best = TermPair(hp, None, None, None, 0.0)
        for projected in bridge.mp_terms(hp):
            for mouse in mouse_terms:
                ancestor, ic = corpus.mica(projected, mouse)
                if ancestor is not None and ic > best.ic:
                    best = TermPair(hp, projected, mouse, ancestor, ic)
        out.append(best)
    return out


def self_score(corpus: MouseCorpus, bridge: Bridge, hp: str) -> float:
    """The best score ``hp`` could reach: the IC of its most informative projection."""
    return max(
        (float(corpus.ic[corpus.index[m]]) for m in bridge.mp_terms(hp) if m in corpus.index),
        default=0.0,
    )


def build_corpus(mp: Ontology, genotypes: Mapping[str, Genotype]) -> MouseCorpus:
    """Resolve annotations, build the closure and annotation matrices, attach IC.

    Genotypes left with no resolvable MP term are dropped: they cannot be scored.
    IC is attached to ``mp`` too (via :meth:`Ontology.with_frequencies`), so ancestor
    explanations and the vectorised scores use the same numbers.
    """
    terms = tuple(sorted(t for t, c in mp.concepts.items() if not c.obsolete))
    index = {t: i for i, t in enumerate(terms)}
    rows: list[int] = []
    cols: list[int] = []
    for t in terms:
        for a in mp.ancestors(t):
            if a in index:
                rows.append(index[t])
                cols.append(index[a])
    closure = sparse.csr_matrix((np.ones(len(rows)), (rows, cols)), shape=(len(terms), len(terms)))
    kept: list[str] = []
    g_rows: list[int] = []
    g_cols: list[int] = []
    unresolved = 0
    for gid in sorted(genotypes):
        resolved = set()
        for term in genotypes[gid].mp_terms:
            live = mp.resolve(term)
            if live is None or live not in index:
                unresolved += 1
            else:
                resolved.add(index[live])
        if not resolved:
            continue
        for c in sorted(resolved):
            g_rows.append(len(kept))
            g_cols.append(c)
        kept.append(gid)
    annotations = sparse.csr_matrix(
        (np.ones(len(g_rows)), (g_rows, g_cols)), shape=(len(kept), len(terms))
    )
    annotations.sort_indices()
    counts = np.asarray(((annotations @ closure) > 0).sum(axis=0)).ravel()
    total = len(kept)
    with np.errstate(divide="ignore"):
        ic = np.where(counts > 0, -np.log(np.maximum(counts, 1) / total), 0.0)
    ic = np.maximum(ic, 0.0)
    mp.with_frequencies({t: int(counts[i]) for i, t in enumerate(terms)}, total)
    return MouseCorpus(
        ontology=mp,
        terms=terms,
        index=index,
        genotype_ids=tuple(kept),
        row_of={g: i for i, g in enumerate(kept)},
        closure=closure.tocsc(),
        annotations=annotations,
        ic=ic.astype(np.float64),
        unresolved=unresolved,
    )
