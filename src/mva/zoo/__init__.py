"""The model zoo — every credible open variant-effect model, one contract, one cache.

Iteration 4 (``docs/iteration4/plan.md``). Nothing here is trained: every model is a frozen
published artefact, and the package's job is organisational — one input record
(:mod:`.record`), one registry (:mod:`.registry`), one adapter protocol and one score cache
(:mod:`.adapters`, :mod:`.cache`), one workflow (:mod:`.workflow`), one ranking
(:mod:`.rank`), one report template (:mod:`.report`) and three merge methods
(:mod:`.merge`). The shared types every module agrees on live in :mod:`.types`.

Layering: ``mva.zoo`` may import ``mva.io``, ``mva.pipeline`` and ``mva.warehouse``; only
``mva.viz`` may import it (``pyproject.toml``, import-linter).
"""

from .types import (
    ALLELE_SCORES_COLUMNS,
    ALLELE_SCORES_TABLE,
    RECORD_COLUMNS,
    RECORDS_TABLE,
    Adapter,
    AlleleRecord,
    Coverage,
    ScoreRow,
    allele_id,
)

__all__ = [
    "ALLELE_SCORES_COLUMNS",
    "ALLELE_SCORES_TABLE",
    "RECORDS_TABLE",
    "RECORD_COLUMNS",
    "Adapter",
    "AlleleRecord",
    "Coverage",
    "ScoreRow",
    "allele_id",
]
