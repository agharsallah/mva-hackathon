"""The HPO graph: parents, ancestors, and how surprising a term is.

An ontology is a vocabulary whose terms are wired parent-to-child, and HPO's wiring is a
**DAG** (directed acyclic graph): arrows run general to specific, a term may have more
than one parent, and no path loops back. That shape is the whole reason phenotype ranking
works at all. A patient annotated "Rhabdomyosarcoma" also, automatically, has "Neoplasm"
and "Abnormality of the musculature" — so two records that share no literal string can
still share a great deal of meaning. **Walk the arrows; never compare the words.**

Three things live here and nothing else does.

**Ancestor closure.** :meth:`Ontology.ancestors` returns every term reachable upward
through ``is_a``, the term itself included (the reflexive closure - a term is its own most
specific ancestor, which is what makes the common-ancestor search below terminate on an
exact match). Computed once per term and cached: the graph is ~19k nodes and a naive
re-walk per comparison turns a one-second run into a minute.

**Information content.** ``IC(t) = -log(p(t))`` where ``p(t)`` is the share of annotated
genes carrying ``t`` *or any of its descendants*. "Abnormality of the body" is carried by
nearly everything and says nothing; "Rhabdomyosarcoma" is carried by a handful of genes
and says a great deal. This is the number that stops a ranker rewarding vague matches, and
it is why the counts must be **propagated up the graph** before the log is taken - a gene
annotated to a child term is evidence for every ancestor of that term.

**Obsolete terms and alternate ids.** HPO retires terms and merges them, leaving ``alt_id``
aliases behind and ``is_obsolete`` markers with an optional ``replaced_by``. A delivered
term list is written by a clinician against whatever release they had, so an id that no
longer exists in the current release is an expected input, not a corrupt one.
:meth:`Ontology.resolve` maps an alias or a retired id onto the live term, and returns
``None`` when it genuinely cannot - a caller that silently dropped it would produce a
ranking over seven terms while reporting eight.

The parser is hand-rolled over the plain-text ``.obo`` stanza format for the same reason
the VCF reader is (``docs/notes/hand-rolled-vcf-reader.md``): the four fields needed are
trivially delimited, and the alternative is a dependency that ships its own copy of the
ontology and its own opinion about releases.
"""

import math
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path

#: Key the stanza parser stores the block type under. Not an OBO field - the ``[Term]``
#: / ``[Typedef]`` header is a line shape, not a ``key: value`` pair, so it needs a slot of
#: its own that no real field can collide with.
STANZA_TYPE = "__stanza_type__"

#: The root. Every term descends from it, so it carries every gene and its information
#: content is zero - the formal way of saying "this term tells you nothing".
ROOT = "HP:0000001"


@dataclass(frozen=True)
class Concept:
    """One HPO term as the ``.obo`` file declares it."""

    hpo_id: str
    name: str
    parents: frozenset[str] = frozenset()
    alt_ids: frozenset[str] = frozenset()
    obsolete: bool = False
    replaced_by: str | None = None


@dataclass
class Ontology:
    """The parsed graph, plus the caches that make repeated questions cheap.

    ``information_content`` is empty until :meth:`with_counts` is called. That split is
    deliberate: the graph is a property of the release, while the information content is a
    property of the *annotation corpus* laid over it, and a package that imported one to
    compute the other would make the ontology unusable on its own.
    """

    concepts: dict[str, Concept]
    #: alt_id or obsolete id -> the live term it resolves to.
    aliases: dict[str, str] = field(default_factory=dict)
    #: term -> IC. Empty until :meth:`with_counts` has run.
    information_content: dict[str, float] = field(default_factory=dict)
    _ancestors: dict[str, frozenset[str]] = field(default_factory=dict, repr=False)
    _depths: dict[str, int] = field(default_factory=dict, repr=False)
    _ranked: dict[str, tuple[tuple[str, float], ...]] = field(default_factory=dict, repr=False)

    def __len__(self) -> int:
        return len(self.concepts)

    def __contains__(self, hpo_id: str) -> bool:
        return hpo_id in self.concepts

    def resolve(self, hpo_id: str) -> str | None:
        """The live term this id names, following aliases and merges. ``None`` if unknown.

        Returning ``None`` rather than raising or passing the id through is the honest
        answer: a term the current release has never heard of cannot be scored, and the
        caller has to be able to say so in the report.
        """
        if hpo_id in self.concepts and not self.concepts[hpo_id].obsolete:
            return hpo_id
        target = self.aliases.get(hpo_id)
        # One hop only. A chain of merges is rare and a loop would hang the run; an
        # unresolved second hop is reported as unknown, which is the truthful outcome.
        if target and target in self.concepts and not self.concepts[target].obsolete:
            return target
        return None

    def name(self, hpo_id: str) -> str:
        """The term's label, or the id itself when the release does not carry it."""
        concept = self.concepts.get(hpo_id)
        return concept.name if concept else hpo_id

    def parents(self, hpo_id: str) -> frozenset[str]:
        """The immediate ``is_a`` parents."""
        concept = self.concepts.get(hpo_id)
        return concept.parents if concept else frozenset()

    def ancestors(self, hpo_id: str) -> frozenset[str]:
        """Every term reachable upward, **including** ``hpo_id`` itself.

        Reflexive on purpose: an exact match between two annotations must come out as the
        most specific common ancestor, and it only does if a term is in its own closure.
        """
        cached = self._ancestors.get(hpo_id)
        if cached is not None:
            return cached
        if hpo_id not in self.concepts:
            return frozenset()
        seen: set[str] = set()
        stack = [hpo_id]
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            stack.extend(self.parents(current) - seen)
        closure = frozenset(seen)
        self._ancestors[hpo_id] = closure
        return closure

    def closure_of(self, ids: Iterable[str]) -> frozenset[str]:
        """The union of the ancestor closures of several terms."""
        out: set[str] = set()
        for hpo_id in ids:
            out |= self.ancestors(hpo_id)
        return frozenset(out)

    def depth(self, hpo_id: str) -> int:
        """Longest path from the root, as a readable proxy for how specific a term is.

        Never used by the scoring - information content is the real measure, and depth and
        IC disagree wherever the graph is unevenly annotated. It exists for the exhibit,
        where a reader wants to see roughly where in the tree a match happened.
        """
        if hpo_id not in self.concepts:
            return -1
        cached = self._depths.get(hpo_id)
        if cached is not None:
            return cached
        # Memoised for the same reason the closure is: the exhibit asks for the depth of
        # every term it draws, and an unmemoised walk repeats the whole upper graph each
        # time. Written iteratively over the already-computed closure so a deep or
        # unexpectedly cyclic release cannot blow the recursion limit.
        order = sorted(self.ancestors(hpo_id), key=lambda t: len(self.ancestors(t)))
        for term in order:
            if term in self._depths:
                continue
            parents = self.parents(term)
            self._depths[term] = 1 + max((self._depths.get(p, 0) for p in parents), default=-1)
        return self._depths.get(hpo_id, 0)

    def with_frequencies(self, counts: Mapping[str, int], total: int) -> "Ontology":
        """Attach information content from **already-propagated distinct-entity counts**.

        ``counts[t]`` must be the number of genes whose *ancestor closure* contains ``t`` -
        not the number that name ``t`` directly, and not a sum of per-term row counts.
        The distinction is not pedantry. Summing the direct counts of a term's descendants
        double-counts any gene annotated to two of them, which is common in a real release
        and makes an internal node look rarer, and therefore more informative, than it is.
        Counting distinct genes over the closure is the only form that cannot.

        Doing the expansion is :meth:`mva.phenotype.associations.Corpus.apply_to`'s job,
        because it is the side that knows which terms belong to the same gene. This method
        takes the finished counts and does the arithmetic, so the two steps can be tested
        apart - a wrong information content is otherwise indistinguishable from a wrong count.
        """
        if total <= 0:
            raise ValueError(f"total annotated genes must be positive; got {total}")

        content: dict[str, float] = {}
        for hpo_id in self.concepts:
            seen = counts.get(hpo_id, 0)
            if seen <= 0:
                # A term no gene is annotated to has no measured frequency. Leaving it out
                # is the honest record; ic() then reports 0.0, which cannot inflate a score.
                continue
            # ``or 0.0`` kills the negative zero -log(1.0) produces for the root and every
            # other universally-annotated term. Numerically identical, but "-0.00" in a
            # report reads as a bug and invites a question that has no answer.
            content[hpo_id] = -math.log(min(seen, total) / total) or 0.0
        self.information_content = content
        # The ranking is a function of the content just replaced, so a stale cache would
        # silently order by the previous corpus.
        self._ranked.clear()
        return self

    def ic(self, hpo_id: str) -> float:
        """Information content, or ``0.0`` where the corpus never annotated the term."""
        return self.information_content.get(hpo_id, 0.0)

    def ranked_ancestors(self, hpo_id: str) -> tuple[tuple[str, float], ...]:
        """This term's closure as ``(term, ic)`` pairs, most informative first.

        Cached, and the reason the genome-wide run finishes in seconds. Scoring five
        thousand genes in both directions is on the order of ten million common-ancestor
        lookups; intersecting two closures and taking the max over the result costs the
        size of the intersection every time. Walking one side in descending information
        content instead lets the search stop at the **first** shared term, because the
        first one found is by construction the most informative one - typically one or two
        probes rather than thirty.

        Requires :meth:`with_counts` to have run. Before that every information content is
        zero, the order is arbitrary, and the early exit would return an arbitrary
        ancestor - so callers must attach a corpus first.
        """
        cached = self._ranked.get(hpo_id)
        if cached is not None:
            return cached
        pairs = tuple(
            sorted(
                ((term, self.ic(term)) for term in self.ancestors(hpo_id)),
                key=lambda pair: pair[1],
                reverse=True,
            )
        )
        self._ranked[hpo_id] = pairs
        return pairs

    def most_informative_common_ancestor(self, left: str, right: str) -> tuple[str | None, float]:
        """The shared ancestor carrying the most information, and how much.

        This is Resnik similarity: two terms are alike to the extent that the most
        specific thing they have in common is itself rare. ``("Rhabdomyosarcoma",
        "Nephroblastoma")`` meet at "Neoplasm", which is informative; ``("Short stature",
        "Rhabdomyosarcoma")`` meet near the root, which is not.
        """
        shared = self.ancestors(right)
        if not shared:
            return None, 0.0
        # First hit wins: ranked_ancestors is ordered by descending information content.
        for term, ic in self.ranked_ancestors(left):
            if term in shared:
                return term, ic
        return None, 0.0


def parse_obo(path: str | Path) -> Ontology:
    """Read an ``hp.obo`` release into an :class:`Ontology`.

    Only ``[Term]`` stanzas are read. ``[Typedef]`` blocks declare relation types and
    carry no terms, and reading them would put relation ids into the graph as if they
    were phenotypes.
    """
    concepts: dict[str, Concept] = {}
    aliases: dict[str, str] = {}

    for stanza in _stanzas(path):
        if _first(stanza, STANZA_TYPE) != "Term":
            continue
        hpo_id = _first(stanza, "id")
        if not hpo_id:
            continue
        concept = Concept(
            hpo_id=hpo_id,
            name=_first(stanza, "name") or hpo_id,
            parents=frozenset(_is_a(value) for value in stanza.get("is_a", [])),
            alt_ids=frozenset(stanza.get("alt_id", [])),
            obsolete=_first(stanza, "is_obsolete") == "true",
            replaced_by=_first(stanza, "replaced_by"),
        )
        concepts[hpo_id] = concept
        for alt in concept.alt_ids:
            aliases[alt] = hpo_id
        if concept.obsolete and concept.replaced_by:
            aliases[hpo_id] = concept.replaced_by

    # A parent naming a term this release does not carry would make the closure walk
    # depend on a missing node. Drop those edges rather than inventing the node.
    cleaned = {
        hpo_id: Concept(
            hpo_id=concept.hpo_id,
            name=concept.name,
            parents=frozenset(p for p in concept.parents if p in concepts),
            alt_ids=concept.alt_ids,
            obsolete=concept.obsolete,
            replaced_by=concept.replaced_by,
        )
        for hpo_id, concept in concepts.items()
    }
    return Ontology(concepts=cleaned, aliases=aliases)


def _stanzas(path: str | Path) -> Iterator[dict[str, list[str]]]:
    """Yield one dict per ``[Type]`` stanza, keys repeated into lists."""
    current: dict[str, list[str]] = {}
    with Path(path).open(encoding="utf-8") as handle:
        for raw in handle:
            line = raw.rstrip("\n")
            if line.startswith("[") and line.endswith("]"):
                if current:
                    yield current
                current = {STANZA_TYPE: [line[1:-1]]}
                continue
            if not line or ":" not in line or not current:
                continue
            key, _, value = line.partition(":")
            current.setdefault(key.strip(), []).append(value.strip())
    if current:
        yield current


def _first(stanza: dict[str, list[str]], key: str) -> str | None:
    values = stanza.get(key)
    return values[0] if values else None


def _is_a(value: str) -> str:
    """``"HP:0000118 ! Phenotypic abnormality"`` -> ``"HP:0000118"``."""
    return value.split("!", 1)[0].strip()
