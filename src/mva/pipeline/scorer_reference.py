"""Grade a written submission with the organisers' own scorer, next to our replica.

:mod:`mva.pipeline.scorer` is a transcription of the published ``evaluation.py``. A
transcription can drift — a rounding, a tie rule, a sort key — and a rehearsal that only
consults the replica proves the replica agrees with itself. This module loads the
organisers' file by path (it is a plain Python module with no dependencies), grades the
same CSV bytes with it, and reports any disagreement field by field.

The organisers' code is *not* imported at module level and is *not* a dependency: when the
file is absent the cross-check simply reports that it could not run.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from dataclasses import dataclass
from pathlib import Path

from .scorer import ScoreResult
from .variant import Variant

__all__ = ["DEFAULT_REFERENCE", "Disagreement", "compare", "grade_with_reference", "load_reference"]

#: Where the organisers' scoring code sits when their repository is checked out beside ours.
DEFAULT_REFERENCE = Path("ressources/hackathon-rules/rare-diseas-repo/evaluation.py")

#: The fields the endpoint exposes; ``n_predictions_at_f_max`` is internal to the scorer.
COMPARED_FIELDS = (
    "full_match_rank",
    "partial_match_rank",
    "rank_points",
    "f_max",
    "f_max_threshold",
)


@dataclass(frozen=True)
class Disagreement:
    field: str
    replica: object
    reference: object

    def __str__(self) -> str:
        return f"{self.field}: replica={self.replica!r} reference={self.reference!r}"


def load_reference(path: Path = DEFAULT_REFERENCE) -> types.ModuleType | None:
    """Import the organisers' ``evaluation.py`` from ``path``; ``None`` when it is absent."""
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("organiser_evaluation", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    # ``@dataclass`` looks the defining module up in ``sys.modules``; register it first.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def grade_with_reference(
    reference: types.ModuleType, csv_path: Path, truth: frozenset[Variant]
) -> ScoreResult:
    """Grade the CSV file at ``csv_path`` against ``truth`` with the organisers' code."""
    submissions = reference.load_submission(str(csv_path))
    proband_id = next(iter(submissions))
    key = frozenset((v.chrom, v.pos, v.ref, v.alt) for v in truth)
    result = reference.score_proband(proband_id, submissions[proband_id], key)
    return ScoreResult(
        full_match_rank=result.full_match_rank,
        partial_match_rank=result.partial_match_rank,
        rank_points=float(result.rank_points),
        f_max=float(result.f_max),
        f_max_threshold=result.f_max_threshold,
        n_predictions_at_f_max=int(result.n_predictions_at_f_max),
    )


def compare(replica: ScoreResult, reference: ScoreResult) -> list[Disagreement]:
    """Every exposed field on which the two scorers disagree; empty means they agree."""
    found: list[Disagreement] = []
    for name in COMPARED_FIELDS:
        a, b = getattr(replica, name), getattr(reference, name)
        same = abs(a - b) < 1e-9 if isinstance(a, float) and isinstance(b, float) else a == b
        if not same:
            found.append(Disagreement(name, a, b))
    return found
