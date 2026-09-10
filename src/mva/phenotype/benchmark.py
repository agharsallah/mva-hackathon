"""How often does the symptom ranker find the causal gene? Measured, not assumed.

A cutoff without a recall number is a guess. Step 1 fixes the target set at the top *N*
genes, and this module is what makes that number defensible: for each of many held-out
diseases, take its curated term list, degrade it the way a real clinic would record it,
rank, and see where the causal gene lands.

**The held-out rule.** Scoring a disease's gene against that same disease's curated terms
is scoring a lookup. So the gene's annotations *from the disease under test* are removed
before ranking; annotations it has from its **other** diseases stay. A gene with no other
disease becomes unrankable, and that is recorded as a miss rather than hidden — it is a
real failure mode of a curation-driven ranker.

**Degradation, from Exomiser's own benchmark.** Zemojtel 2014 did not rank pristine term
lists: it replaced terms by their parents (imprecision — a clinician records "seizure",
not the exact subtype) and added unrelated terms (noise — the child has features the
disease does not explain). Both are reproduced here, with the counts as parameters.

**What this number is not.** The ground truth and the scoring database come from the same
curators, so the curve is an *internal consistency check*, not an external validation, and
it carries no genomic background — every gene here is a candidate, where a real case has a
whole exome of them. The comparable external number is step 4's spike-in recall. Anywhere
this figure is quoted it is labelled as such.

Case-agnostic: nothing here knows about the case. It takes an annotation corpus and gives
back a curve.
"""

from __future__ import annotations

import csv
import random
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from statistics import median

from .associations import Corpus, GeneAnnotation
from .ontology import ROOT, Ontology
from .prioritise import rank_genes
from .terms import Term, TermSet

#: The HPO term that marks a disease as autosomal recessive, as the annotation files spell
#: it. The case is a recessive disease, so the benchmark population is drawn to match.
RECESSIVE = "HP:0000007"

#: How many terms a sampled query carries. Matches the proband's own term count, so the
#: benchmark measures the ranker under the case's conditions rather than ideal ones.
QUERY_TERMS = 7

#: Where the curve is read: the plan's candidate cutoffs, plus top-1 as its own number.
DEFAULT_N = (1, 10, 50, 300, 1000)


@dataclass(frozen=True)
class Disease:
    """One disease as the annotation corpus records it: its gene, and its curated terms."""

    disease_id: str
    gene_symbol: str
    terms: frozenset[str]
    recessive: bool

    def __len__(self) -> int:
        return len(self.terms)


@dataclass(frozen=True)
class Outcome:
    """Where one held-out disease's causal gene landed."""

    disease_id: str
    gene_symbol: str
    #: Rank of the causal gene, or ``None`` when the ranker could not place it at all.
    rank: int | None
    query: tuple[str, ...]

    def within(self, n: int) -> bool:
        return self.rank is not None and self.rank <= n


@dataclass(frozen=True)
class Result:
    """The curve, and enough of its provenance to reproduce it."""

    outcomes: tuple[Outcome, ...]
    seed: int
    n_values: tuple[int, ...] = DEFAULT_N

    def recall_at(self, n: int) -> float:
        """Fraction of held-out diseases whose causal gene ranked at or above ``n``."""
        if not self.outcomes:
            return 0.0
        return sum(o.within(n) for o in self.outcomes) / len(self.outcomes)

    def curve(self) -> tuple[tuple[int, float], ...]:
        return tuple((n, self.recall_at(n)) for n in self.n_values)

    def interval(
        self, n: int, *, resamples: int = 1000, level: float = 0.95
    ) -> tuple[float, float]:
        """Bootstrap interval for ``recall_at(n)`` — a recall with no interval is a guess.

        Resampled from the outcomes themselves, seeded from :attr:`seed` so the interval is
        as reproducible as the point estimate.
        """
        if not self.outcomes:
            return (0.0, 0.0)
        rng = random.Random(self.seed + n)
        size = len(self.outcomes)
        draws = sorted(
            sum(rng.choice(self.outcomes).within(n) for _ in range(size)) / size
            for _ in range(resamples)
        )
        tail = (1.0 - level) / 2.0
        return (
            draws[int(tail * resamples)],
            draws[min(int((1 - tail) * resamples), resamples - 1)],
        )

    @property
    def unrankable(self) -> int:
        """Held-out diseases whose gene the ranker could not place at all."""
        return sum(1 for o in self.outcomes if o.rank is None)

    @property
    def median_rank(self) -> float | None:
        placed = [o.rank for o in self.outcomes if o.rank is not None]
        return median(placed) if placed else None


def read_diseases(path: str | Path) -> tuple[Disease, ...]:
    """Group ``genes_to_phenotype.txt`` by disease.

    The file is one row per (gene, term, disease), so a disease's term list is the union
    of its rows. Inheritance is read from the annotation itself rather than from a second
    source, which keeps the benchmark to one file and one release.
    """
    terms: dict[tuple[str, str], set[str]] = {}
    with Path(path).open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            disease = (row.get("disease_id") or "").strip()
            gene = (row.get("gene_symbol") or "").strip()
            term = (row.get("hpo_id") or "").strip()
            if disease and gene and term:
                terms.setdefault((disease, gene), set()).add(term)
    return tuple(
        Disease(
            disease_id=disease,
            gene_symbol=gene,
            terms=frozenset(found),
            recessive=RECESSIVE in found,
        )
        for (disease, gene), found in sorted(terms.items())
    )


def population(
    diseases: Iterable[Disease], *, recessive_only: bool = True, minimum_terms: int = QUERY_TERMS
) -> tuple[Disease, ...]:
    """The diseases the benchmark may draw from, filtered once and reported.

    A disease with fewer curated terms than a query needs cannot be subsampled without
    repeating terms, which would make the query easier than a real one.
    """
    return tuple(
        d
        for d in diseases
        # The inheritance term is not a phenotype; it must not become a query term.
        if len(d.terms - {RECESSIVE}) >= minimum_terms and (d.recessive or not recessive_only)
    )


def degrade(
    terms: Sequence[str],
    ontology: Ontology,
    rng: random.Random,
    *,
    size: int = QUERY_TERMS,
    imprecision: tuple[int, int] = (1, 2),
    noise: tuple[int, int] = (1, 2),
    vocabulary: Sequence[str] = (),
) -> tuple[str, ...]:
    """One clinic-grade query: subsample, blur some terms upward, add some unrelated ones.

    Imprecision replaces a term by a parent — a real record says "seizure" where the
    curation says the exact subtype. Noise adds terms the disease does not explain. Both
    counts are inclusive ranges, drawn per query, as Zemojtel 2014 did it.
    """
    pool = [t for t in terms if t != RECESSIVE]
    query = rng.sample(pool, min(size, len(pool)))
    for index in rng.sample(range(len(query)), min(rng.randint(*imprecision), len(query))):
        parents = sorted(p for p in ontology.parents(query[index]) if p != ROOT)
        if parents:
            query[index] = rng.choice(parents)
    if vocabulary:
        query.extend(rng.choice(vocabulary) for _ in range(rng.randint(*noise)))
    # Deduplicated: a blurred term can collide with one already present, and a query that
    # names a term twice is not a query a clinic would produce.
    return tuple(dict.fromkeys(query))


def _held_out(corpus: Corpus, disease: Disease) -> Corpus:
    """The corpus with this disease's contribution to its own gene removed.

    The gene keeps whatever its *other* diseases curated; if that leaves nothing, the gene
    drops out of the corpus and the run records a miss. That is the honest outcome — a
    ranker built on curation cannot find a gene curation has only ever described through
    the disease being withheld.
    """
    key = disease.gene_symbol.upper()
    annotation = corpus.genes.get(key)
    if annotation is None:
        return corpus
    remaining = annotation.terms - disease.terms
    genes = dict(corpus.genes)
    if remaining:
        genes[key] = GeneAnnotation(annotation.symbol, remaining, annotation.entrez_id)
    else:
        del genes[key]
    return Corpus(genes=genes, direct_counts=corpus.direct_counts)


def run(
    diseases: Sequence[Disease],
    corpus: Corpus,
    ontology: Ontology,
    *,
    seed: int,
    sample: int | None = None,
    n_values: tuple[int, ...] = DEFAULT_N,
    size: int = QUERY_TERMS,
    imprecision: tuple[int, int] = (1, 2),
    noise: tuple[int, int] = (1, 2),
) -> Result:
    """Rank each held-out disease and record where its causal gene landed.

    ``sample`` caps how many diseases are run — the full population is thousands and each
    one is a full ranking pass. The subsample is drawn from ``seed``, so a smaller run is
    a reproducible subset of the larger one rather than a different experiment.
    """
    rng = random.Random(seed)
    chosen = list(diseases)
    if sample is not None and sample < len(chosen):
        chosen = rng.sample(chosen, sample)
    vocabulary = tuple(sorted(ontology.concepts))
    outcomes: list[Outcome] = []
    for disease in sorted(chosen, key=lambda d: d.disease_id):
        query = degrade(
            sorted(disease.terms),
            ontology,
            rng,
            size=size,
            imprecision=imprecision,
            noise=noise,
            vocabulary=vocabulary,
        )
        term_set = TermSet(
            name=f"held-out:{disease.disease_id}",
            terms=tuple(Term(hpo_id=t, label=ontology.name(t), note="") for t in query),
            rationale=(
                f"{disease.disease_id} with its own annotation of {disease.gene_symbol} removed"
            ),
        )
        ranking = rank_genes(term_set, _held_out(corpus, disease), ontology)
        outcomes.append(
            Outcome(
                disease_id=disease.disease_id,
                gene_symbol=disease.gene_symbol,
                rank=ranking.rank_of(disease.gene_symbol),
                query=query,
            )
        )
    return Result(outcomes=tuple(outcomes), seed=seed, n_values=n_values)
