"""The model zoo — every credible open model behind one contract.

Nothing here is trained: every model is a frozen published artefact, and the package's
job is organisational. One record shape and one adapter protocol (:mod:`.types`), one
registry of model cards (:mod:`.registry`), and one tier-3 contract with its spend ledger
(:mod:`.modal_contract`, :mod:`.modal_budget`, :mod:`.modal_apps`) for the lanes that need
a GPU.

Adding a model is a TOML entry plus one adapter module — never an edit to a shared file.

Layering: ``mva.zoo`` may import ``mva.io``; only ``mva.viz`` may import it
(``pyproject.toml``, import-linter).
"""

from .types import Adapter, Coverage, RemoteJob, ScoreRow, SequenceRecord, Tier, item_id

__all__ = [
    "Adapter",
    "Coverage",
    "RemoteJob",
    "ScoreRow",
    "SequenceRecord",
    "Tier",
    "item_id",
]
