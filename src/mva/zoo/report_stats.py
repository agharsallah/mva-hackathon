"""The numbers behind a model report: coverage, distribution, the clinical sentence.

Every figure in ``sections`` of a model report is computed here, once, and stored. The
renderers in :mod:`mva.zoo.report_sections` only print what this module produced — which is
what makes a rendered report diffable against the run that produced it.

Percentile convention, as everywhere in this package: a position **from the top**, in percent.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

__all__ = [
    "HPO_TERM_COUNT",
    "QUANTILES",
    "coverage_json",
    "distribution_json",
    "histogram_path",
    "hpo_sentence",
]

#: The quantiles every lane reports, so two lanes' distributions can be read side by side.
QUANTILES: tuple[float, ...] = (0.01, 0.10, 0.25, 0.50, 0.75, 0.90, 0.99)

#: How many bins the stored histogram carries. The raw scores are not stored (40k floats per
#: lane); the binned counts are, so the figure script can draw the exact histogram the report
#: describes without reopening the score cache.
HISTOGRAM_BINS = 40

#: How many HPO terms the proband's clinical record carries
#: (``ressources/hackathon-rules/Challenge_Clinical_Phenotype_1.md``).
HPO_TERM_COUNT = 8


def histogram_path(key: str) -> str:
    """Where ``tools/render_it4_figures.py`` writes this lane's score histogram."""
    return f"figures/it4/score-histogram-{key}.svg"


# ---------------------------------------------------------------------------------------
# JSON builders
# ---------------------------------------------------------------------------------------


def coverage_json(coverage: Any) -> dict[str, Any]:
    """Section 2: how much of the record set this lane could score, by consequence class.

    Accepts a :class:`mva.zoo.types.Coverage` or any object/mapping with the same fields, so
    a caller can hand in a plain dict in a test without importing the type.
    """
    scored = int(_get(coverage, "scored", 0) or 0)
    total = int(_get(coverage, "total", 0) or 0)
    by_consequence = _get(coverage, "by_consequence", {}) or {}
    classes = [
        {
            "consequence": name,
            "scored": int(pair[0]),
            "total": int(pair[1]),
            "fraction": round(pair[0] / pair[1], 4) if pair[1] else None,
        }
        for name, pair in sorted(by_consequence.items())
    ]
    return {
        "scored": scored,
        "total": total,
        "fraction": round(scored / total, 4) if total else None,
        "by_consequence": classes,
    }


def distribution_json(
    scores: Mapping[str, float], marks: Sequence[Mapping[str, Any]] = ()
) -> dict[str, Any]:
    """Section 3: the shape of the lane's scores, plus the marked alleles.

    ``marks`` are the alleles the histogram calls out — the confirmed pair's two halves. Each
    mark is ``{"allele_id": ..., "role": "left"|"right"}``; its score and percentile are
    filled in here so the figure script and the Markdown read the same two numbers.
    """
    values = sorted(scores.values())
    n = len(values)
    quantiles = {f"p{int(q * 100):02d}": _quantile(values, q) for q in QUANTILES} if n else {}
    marked: list[dict[str, Any]] = []
    for mark in marks:
        allele = str(mark.get("allele_id", ""))
        value = scores.get(allele)
        marked.append(
            {
                "allele_id": allele,
                "role": mark.get("role", ""),
                "score": value,
                "percentile": _percentile(values, value) if value is not None else None,
            }
        )
    return {
        "n": n,
        "min": values[0] if n else None,
        "max": values[-1] if n else None,
        "mean": round(sum(values) / n, 6) if n else None,
        "quantiles": quantiles,
        "histogram": _bins(values),
        "marks": marked,
        "figure": "",
    }


def _bins(sorted_values: Sequence[float], bins: int = HISTOGRAM_BINS) -> dict[str, Any]:
    """The histogram as edges plus counts, so the figure needs no second pass over the scores.

    Storing the picture's numbers rather than its inputs is what lets the figure script run
    from the report JSON alone — and means a figure can never show a distribution the report
    does not describe.
    """
    n = len(sorted_values)
    if not n:
        return {"bins": 0, "edges": [], "counts": []}
    low, high = float(sorted_values[0]), float(sorted_values[-1])
    if high == low:  # one distinct value: one bin wide enough to see
        return {"bins": 1, "edges": [low, low], "counts": [n]}
    width = (high - low) / bins
    counts = [0] * bins
    for value in sorted_values:
        index = min(int((value - low) / width), bins - 1)
        counts[index] += 1
    edges = [round(low + i * width, 6) for i in range(bins + 1)]
    return {"bins": bins, "edges": edges, "counts": counts}


def _quantile(sorted_values: Sequence[float], q: float) -> float | None:
    """Linear-interpolated quantile; ``None`` for an empty list."""
    n = len(sorted_values)
    if not n:
        return None
    if n == 1:
        return round(float(sorted_values[0]), 6)
    position = q * (n - 1)
    low = int(position)
    high = min(low + 1, n - 1)
    weight = position - low
    return round(float(sorted_values[low] * (1 - weight) + sorted_values[high] * weight), 6)


def _percentile(sorted_values: Sequence[float], value: float) -> float | None:
    """Position from the top, in percent (1 = the single highest score's lane position)."""
    if not sorted_values:
        return None
    higher = sum(1 for other in sorted_values if other > value)
    return round(100.0 * (higher + 1) / len(sorted_values), 4)


def hpo_sentence(
    row: Mapping[str, Any] | None,
    *,
    gene: str,
    model: str,
    uses_phenotype: bool = False,
    term_set: str = "with-parental",
    n_terms: int = HPO_TERM_COUNT,
) -> str:
    """Section 5: the one sentence every model's report carries about the clinical terms.

    ``row`` is a ``warehouse.hpo_gene_scores`` row for the gene under ``term_set`` — the
    phenotype-only ranking of genes against the child's HPO terms (Human Phenotype Ontology:
    the standard vocabulary a clinician's observations are coded in). The sentence is fixed
    text with the row's numbers slotted in, so the clinical half of the evidence appears in
    every model's report whether or not the model can see it.
    """
    blind = (
        f"`{model}` scores the molecular change only and never sees the phenotype, so this "
        f"line is context for the reader, not an input to the score above."
    )
    aware = (
        f"`{model}` takes the phenotype as an input, so its score and this ranking are not "
        f"independent evidence."
    )
    tail = aware if uses_phenotype else blind
    if row is None:
        return (
            f"The child's {n_terms} HPO terms produced no `{gene}` row under term set "
            f"`{term_set}` in `warehouse.hpo_gene_scores`. {tail}"
        )
    return (
        f"Against the child's {n_terms} HPO terms, `{gene}` ranks #{row.get('rank')} of "
        f"{row.get('genes_considered')} genes considered (phenotype score "
        f"{row.get('score')}, term set `{term_set}`, `warehouse.hpo_gene_scores`). {tail}"
    )


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)
