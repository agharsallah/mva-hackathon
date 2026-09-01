"""A local replica of the challenge's Track 1 scorer.

Transcribed from the evaluation code published with the challenge so that a probe can be
rehearsed offline. The team has eighteen submissions in total and each returns
``rank_points``, ``f_max``, ``full_match_rank`` and ``partial_match_rank``; replaying a
candidate submission here before spending one is what makes those replies decodable.

Two behaviours look like details and are not:

* **Rank points use the full match if there is one, at whatever rank it sits.** A full
  match at rank 6 scores 10 while a partial match at rank 1 would have scored 50, so the
  final submission must carry the confirmed pair at rank 1 with nothing above it.
* **F-max keeps the first (highest) threshold that improves the score**, because the
  comparison is strictly greater-than. Ties therefore resolve upward, which creates the
  ambiguous zone that makes a singles probe unable to distinguish "second allele ranked
  far down" from "second allele absent".
"""

from dataclasses import dataclass

from .submission import Row
from .variant import Variant

RANK_POINT_TIERS = [(1, 100), (3, 50), (5, 25), (10, 10)]


@dataclass(frozen=True)
class ScoreResult:
    """Exactly the fields the submission handler returns to us."""

    full_match_rank: int | None
    partial_match_rank: int | None
    rank_points: float
    f_max: float
    f_max_threshold: float | None
    n_predictions_at_f_max: int


@dataclass(frozen=True)
class RankedRow:
    """A submission row after ranking, in the form the scorer compares."""

    variants: frozenset[Variant]
    epcr: float
    rank: int


def rank_rows(rows: list[Row]) -> list[RankedRow]:
    """Assign ranks by descending epcr, ties broken by file order — as the scorer does."""
    ordered = sorted(enumerate(rows), key=lambda pair: (-pair[1].epcr, pair[0]))
    return [
        RankedRow(row.variants(), row.epcr, index + 1)
        for index, (_, row) in enumerate(ordered)
    ]


def score(rows: list[Row], truth: frozenset[Variant]) -> ScoreResult:
    """Score a candidate submission against a hypothesised answer key."""
    ranked = rank_rows(rows)
    is_compound_het = len(truth) == 2

    full_match_rank = next((r.rank for r in ranked if r.variants == truth), None)

    partial_match_rank = None
    if is_compound_het and full_match_rank is None:
        partial_match_rank = next((r.rank for r in ranked if r.variants & truth), None)

    if full_match_rank is not None:
        rank_points = float(_rank_to_points(full_match_rank))
    elif partial_match_rank is not None:
        # Half weight for recovering only one of the two causal variants.
        rank_points = 0.5 * _rank_to_points(partial_match_rank)
    else:
        rank_points = 0.0

    f_max, threshold, n_at_max = _f_max(ranked, truth)
    return ScoreResult(
        full_match_rank=full_match_rank,
        partial_match_rank=partial_match_rank,
        rank_points=rank_points,
        f_max=f_max,
        f_max_threshold=threshold,
        n_predictions_at_f_max=n_at_max,
    )


def _f_max(ranked: list[RankedRow], truth: frozenset[Variant]):
    """Sweep the epcr thresholds present in the file, scoring at variant level."""
    best_f, best_threshold, best_n = 0.0, None, 0

    for threshold in sorted({r.epcr for r in ranked}, reverse=True):
        above = [r for r in ranked if r.epcr >= threshold]
        predicted: set[Variant] = set().union(*(r.variants for r in above))

        tp = len(predicted & truth)
        fp = len(predicted - truth)
        fn = len(truth - predicted)

        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

        # Strictly greater-than: a tie keeps the higher threshold already recorded.
        if f > best_f:
            best_f, best_threshold, best_n = f, threshold, len(above)

    return best_f, best_threshold, best_n


def _rank_to_points(rank: int) -> int:
    for max_rank, points in RANK_POINT_TIERS:
        if rank <= max_rank:
            return points
    return 0
