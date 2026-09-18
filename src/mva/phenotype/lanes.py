"""Building step 4's three gene-level lanes from the files that hold their evidence.

A likelihood-ratio ranker needs, per gene: how well the child's symptoms match it, how close
it sits to the genes that *do* match when nobody has curated it, and what its mode of
inheritance implies. All three are phenotype evidence, and all three are read from files
rather than computed here — this module is the wiring, and :mod:`mva.pipeline.likelihood`
holds the arithmetic.

The phenotype lane is the interesting one. Rather than inventing a conversion from a
similarity score to a likelihood ratio, it *is* the ranker's own measured performance: step
1 ran the ranker on 3,240 held-out recessive diseases and recorded where each causal gene
landed, and :mod:`mva.pipeline.rank_lr` reads that curve as a ratio per rank. A gene at rank
1 is worth what a gene at rank 1 has historically been worth.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..pipeline.acmg import Strength, likelihood_ratio
from ..pipeline.inheritance import explain as explain_inheritance
from ..pipeline.inheritance import factor as inheritance_factor
from ..pipeline.rank_lr import RankLikelihood, from_benchmark
from .associations import parse_genes_to_phenotype
from .modes import gene_inheritance

__all__ = ["NETWORK_CEILING", "inheritance_lane", "network_lane", "phenotype_likelihood"]

#: The ceiling on the network-proximity lane. A neighbour has no phenotype evidence of its
#: own, only a neighbour that has some, so the lane can never reach past *supporting*.
NETWORK_CEILING = likelihood_ratio(Strength.SUPPORTING)


def phenotype_likelihood(benchmark: Path, summary: Path) -> RankLikelihood:
    """The measured recall curve of step 1, read as a likelihood ratio per rank.

    This is the step's one methodological liberty and its most defensible number: rather
    than inventing a conversion from a similarity score to a ratio, the ratio *is* the
    ranker's own held-out performance — how often the causal gene really landed in each
    band of ranks, over how often a gene drawn at random would.
    """
    curve = json.loads(benchmark.read_text(encoding="utf-8"))
    totals = json.loads(summary.read_text(encoding="utf-8"))
    return from_benchmark(
        curve["curve"],
        ranked=int(totals["genes_considered"]["proband-only"]),
        universe=int(totals["protein_coding_total"]),
        unrankable=curve["unrankable"] / curve["diseases_run"],
        source=f"{benchmark} (held-out recall, {curve['diseases_run']} recessive diseases)",
    )


def network_lane(path: Path) -> tuple[dict[str, float], str]:
    """Proximity per uncurated gene, scaled so the strongest reaches the lane's ceiling."""
    if not path.is_file():
        return {}, ""
    rows = [line.split("\t") for line in path.read_text(encoding="utf-8").splitlines()[1:]]
    proximity = {row[0]: float(row[1]) for row in rows if len(row) > 1}
    top = max(proximity.values(), default=0.0)
    if top <= 0:
        return {}, ""
    return (
        {gene: NETWORK_CEILING ** (value / top) for gene, value in proximity.items()},
        f"{path} (STRING high-confidence partners of the top-ranked genes)",
    )


def inheritance_lane(
    corpus_path: Path, *, enabled: bool
) -> tuple[dict[str, float], dict[str, str]]:
    """The pre-registered mode-of-inheritance multiplier per gene, and its one-line reason."""
    if not enabled or not corpus_path.is_file():
        return {}, {}
    corpus = parse_genes_to_phenotype(corpus_path)
    genes = gene_inheritance(corpus)
    factors = {symbol: inheritance_factor(gene) for symbol, gene in genes.items()}
    reasons = {
        symbol: explain_inheritance(gene)
        for symbol, gene in genes.items()
        if factors[symbol] != 1.0
    }
    return {symbol: value for symbol, value in factors.items() if value != 1.0}, reasons
