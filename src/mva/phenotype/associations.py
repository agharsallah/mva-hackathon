"""Which genes are known to produce which phenotypes.

``genes_to_phenotype.txt`` is HPO's join of gene to clinical feature, assembled from the
curated disease annotations: one row per (gene, term) pair, ~1.1 million rows over roughly
five thousand genes. It is the entire human-only knowledge base this package ranks
against, and it is plain TSV - which is why the phenotype half of Exomiser is
reimplementable in Python while the variant half is not.

Two details decide whether the join is right.

**The file has had two column layouts.** The current release leads with
``ncbi_gene_id, gene_symbol, hpo_id, hpo_name``; the copy shipped inside Exomiser's
phenotype bundle is the older ``entrez-gene-id, entrez-gene-symbol, HPO-Term-Name,
HPO-Term-ID`` - the id and the name are **swapped**. Reading by position would silently
load term *labels* into the id column against one of the two, and produce a ranking in
which nothing ever matches. So the term id is found by shape (``HP:`` followed by seven
digits), which is unambiguous in both and survives a third layout.

**The join key is the gene symbol, not the Entrez id.** Everything upstream of this
package speaks HGNC symbols: the panel BED is symbol-keyed, and
:func:`mva.pipeline.vep_response.parse` returns ``gene_symbol`` already uppercased. Adding
an Entrez id here would mean carrying a symbol-to-id mapping nothing else needs, and a
second identifier space is a second place for the join to fail. The Entrez id is kept on
the record anyway, because it is what the Phen2Gene and Monarch cross-checks want back.

Symbols are uppercased on the way in for the same reason ``vep_response`` uppercases them:
a case mismatch is a join that returns nothing while looking like a gene with no
phenotypes.
"""

import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

from .ontology import Ontology

#: An HPO term id. Seven digits, zero-padded - the shape is what identifies the column.
TERM_PATTERN = re.compile(r"^HP:\d{7}$")

#: Placeholders the release writes where it has an NCBI gene id but no symbol. Measured in
#: the 2026-06-23 release: 375 rows carry ``-``, and they belong to **seven different
#: genes**. Loading them would fuse those seven into one fabricated gene whose curated
#: feature list is the union of all of them - which then scores highly against almost any
#: query, because a long enough feature list eventually contains something. Dropped rather
#: than repaired: the join is by symbol, and a row with no symbol cannot participate in it.
UNNAMED_SYMBOLS = frozenset({"-", ".", ""})


@dataclass(frozen=True)
class GeneAnnotation:
    """One gene and every phenotype term curated against it."""

    symbol: str
    terms: frozenset[str]
    #: NCBI/Entrez gene id, kept for the hosted cross-checks that key on it.
    entrez_id: str | None = None

    def __len__(self) -> int:
        return len(self.terms)


@dataclass(frozen=True)
class Corpus:
    """Every annotated gene, and the term frequencies computed from them.

    ``direct_counts`` is how many genes name each term **directly**, before any upward
    propagation - kept because it is the raw observation, and because a direct count is
    what a reader checks a parse against. The propagated form the information content
    needs is computed by :meth:`apply_to`, which is the only side that knows which terms
    belong to the same gene.
    """

    genes: dict[str, GeneAnnotation]
    direct_counts: dict[str, int]

    def __len__(self) -> int:
        return len(self.genes)

    def __contains__(self, symbol: str) -> bool:
        return symbol.upper() in self.genes

    def get(self, symbol: str) -> GeneAnnotation | None:
        """One gene's annotation, matched case-insensitively."""
        return self.genes.get(symbol.upper())

    def symbols(self) -> tuple[str, ...]:
        """Every annotated gene symbol, sorted, so a run is reproducible."""
        return tuple(sorted(self.genes))

    def closure_counts(self, ontology: Ontology) -> dict[str, int]:
        """Per term, how many **distinct genes** have it anywhere in their closure.

        Counted by expanding each gene's own term set once and incrementing every term in
        the union - never by summing per-term counts up the graph. A gene annotated to both
        "Rhabdomyosarcoma" and "Neoplasm" must contribute **one** to Neoplasm, and the
        summing form contributes two, which makes the parent look rarer than it is.
        """
        counts: dict[str, int] = {}
        for annotation in self.genes.values():
            for term in ontology.closure_of(annotation.terms):
                counts[term] = counts.get(term, 0) + 1
        return counts

    def apply_to(self, ontology: Ontology) -> Ontology:
        """Give the ontology this corpus's information content.

        Convenience for the one thing a caller always does next, so the two-step (expand
        here, take the log there) cannot be half-performed.
        """
        return ontology.with_frequencies(self.closure_counts(ontology), total=len(self.genes))


def parse_genes_to_phenotype(path: str | Path, ontology: Ontology | None = None) -> Corpus:
    """Read ``genes_to_phenotype.txt`` into a :class:`Corpus`.

    When an ``ontology`` is given, every term is resolved through it: aliases and merged
    ids become the live term, and an id the release does not carry is dropped. Without one
    the ids are taken verbatim, which is what the parser's own tests want.
    """
    by_symbol: dict[str, set[str]] = {}
    entrez: dict[str, str] = {}
    counts: dict[str, int] = {}

    for entrez_id, symbol, hpo_id in _rows(path):
        term = ontology.resolve(hpo_id) if ontology is not None else hpo_id
        if term is None:
            # An id the current release retired without a replacement. Dropping it is the
            # only honest option: it cannot be placed in the graph, so it cannot be scored.
            continue
        terms = by_symbol.setdefault(symbol, set())
        if term not in terms:
            terms.add(term)
            counts[term] = counts.get(term, 0) + 1
        if entrez_id and symbol not in entrez:
            entrez[symbol] = entrez_id

    # A gene whose every term was unplaceable never reaches ``by_symbol`` and is
    # therefore absent from the corpus entirely. That is deliberate: it contributes
    # nothing to any count, and carrying it as an empty annotation would still enlarge
    # the denominator that every information content is divided by - making every term in
    # the release look rarer than it is on the strength of a gene we know nothing about.
    genes = {
        symbol: GeneAnnotation(symbol, frozenset(terms), entrez.get(symbol))
        for symbol, terms in by_symbol.items()
    }
    return Corpus(genes=genes, direct_counts=counts)


def _rows(path: str | Path) -> Iterator[tuple[str, str, str]]:
    """Yield ``(entrez_id, UPPERCASE_SYMBOL, hpo_id)`` per data line.

    Rows whose term column does not hold a well-formed HPO id are skipped rather than
    guessed at: that covers the header line, the ``#Format:`` comment the bundled copy
    carries, and any trailing blank.
    """
    with Path(path).open(encoding="utf-8") as handle:
        for raw in handle:
            line = raw.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            fields = line.split("\t")
            if len(fields) < 3:
                continue
            term = next((field for field in fields if TERM_PATTERN.match(field)), None)
            if term is None:
                continue
            symbol = fields[1].strip().upper()
            if symbol in UNNAMED_SYMBOLS:
                continue
            yield fields[0].strip(), symbol, term


def counts_from(annotations: Mapping[str, GeneAnnotation]) -> dict[str, int]:
    """Direct per-term gene counts over an arbitrary annotation map.

    Used by the tests and by any caller assembling a corpus from something other than the
    HPO file, so the counting rule has exactly one implementation.
    """
    counts: dict[str, int] = {}
    for annotation in annotations.values():
        for term in annotation.terms:
            counts[term] = counts.get(term, 0) + 1
    return counts
