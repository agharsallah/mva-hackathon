"""The contracts every zoo module shares — pinned in wave 0, read-only afterwards.

Three shapes and one function:

* :class:`AlleleRecord` — step 1's row: one allele, every spelling a model class reads.
* :class:`ScoreRow` — one model's verdict on one allele, as cached in
  ``warehouse.allele_scores``.
* :class:`Coverage` — how much of a record set a model can score, by consequence class.
* :func:`allele_id` — the stable, coordinate-free key. The coordinate stays in ``build/``;
  the id is what leaves.

The :class:`Adapter` protocol is what a model looks like to the workflow: tier 1 and 2 score
locally, tier 3 submits a remote job and the workflow collects it later.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

__all__ = [
    "ALLELE_SCORES_COLUMNS",
    "ALLELE_SCORES_TABLE",
    "CATALOGUE_FIELDS",
    "MODES",
    "RECORDS_TABLE",
    "RECORD_COLUMNS",
    "Adapter",
    "AlleleRecord",
    "Coverage",
    "Mode",
    "RemoteJob",
    "ScoreRow",
    "Tier",
    "allele_id",
]

#: Inference tiers: 1 = precomputed table lookup, 2 = local CPU process, 3 = remote GPU.
Tier = Literal[1, 2, 3]

#: ``catalogue-free`` nulls every field a ClinVar-trained model could have learned from;
#: ``aware`` keeps them. Both are reported (plan D4).
Mode = Literal["catalogue-free", "aware"]
MODES: tuple[str, ...] = ("catalogue-free", "aware")

#: The record fields ``--mask-catalogue`` nulls.
CATALOGUE_FIELDS: tuple[str, ...] = ("clin_sig",)


def allele_id(chrom: str, pos: int, ref: str, alt: str) -> str:
    """The stable key of one allele: 16 hex chars of SHA-256 over ``chrom:pos:ref:alt``.

    ``chrom`` is normalised to the VCF spelling (no ``chr`` prefix, uppercase) before hashing
    so the two contig conventions in the repo yield one id. The id carries no coordinate and
    is the only allele key allowed in any tracked file.
    """
    contig = chrom.removeprefix("chr").removeprefix("CHR").upper()
    text = f"{contig}:{int(pos)}:{ref.upper()}:{alt.upper()}"
    return hashlib.sha256(text.encode()).hexdigest()[:16]


@dataclass(frozen=True)
class AlleleRecord:
    """One allele, spelled every way a model class reads it. Everything but the id is
    nullable: a tier-1 lookup keys on HGVS, a DNA language model on the window."""

    allele_id: str
    gene: str | None = None
    transcript: str | None = None
    consequence: str | None = None
    hgvs_c: str | None = None
    hgvs_p: str | None = None
    #: UniProt accession of the protein ``hgvs_p`` is spelled on (ESM1b's join key).
    uniprot: str | None = None
    protein_window_ref: str | None = None
    protein_window_alt: str | None = None
    dna_window_ref: str | None = None
    dna_window_alt: str | None = None
    is_read_only: bool = False
    af_gnomad: float | None = None
    clin_sig: str | None = None

    def masked(self) -> AlleleRecord:
        """The same record with every catalogue field nulled (``catalogue-free`` mode)."""
        return AlleleRecord(**{**self.__dict__, **dict.fromkeys(CATALOGUE_FIELDS)})


#: ``results.it4_allele_records`` — the coordinate-free half of the record. The sequence
#: windows and the coordinate live only in ``build/it4/records.parquet``.
RECORDS_TABLE = "it4_allele_records"
RECORD_COLUMNS: tuple[tuple[str, str], ...] = (
    ("allele_id", "VARCHAR"),
    ("gene", "VARCHAR"),
    ("transcript", "VARCHAR"),
    ("consequence", "VARCHAR"),
    ("hgvs_c", "VARCHAR"),
    ("hgvs_p", "VARCHAR"),
    ("uniprot", "VARCHAR"),
    ("is_read_only", "BOOLEAN"),
    ("af_gnomad", "DOUBLE"),
    ("clin_sig", "VARCHAR"),
    ("built_at", "TIMESTAMP"),
    ("source", "VARCHAR"),
)


@dataclass(frozen=True)
class ScoreRow:
    """One model's score for one allele — the row shape of ``warehouse.allele_scores``.

    ``score`` is the model's primary number, higher = more damaging, as the adapter
    defines it; ``aux`` holds anything else the model emitted (classes, per-site deltas).
    ``venue`` is where it ran (``laptop``, ``vep-rest``, ``modal:<gpu>``); ``licence`` the
    model's terms; ``digest`` the weights or table digest the adapter read.
    """

    allele_id: str
    model: str
    version: str
    score: float | None
    aux: dict[str, Any] = field(default_factory=dict)
    digest: str = ""
    venue: str = "laptop"
    licence: str = ""
    run_id: str = ""


#: ``warehouse.allele_scores`` — append-only; a re-run on the same (model, version,
#: allele_id) is a no-op. This is the feature store the plan describes (step 3).
ALLELE_SCORES_TABLE = "allele_scores"
ALLELE_SCORES_COLUMNS: tuple[tuple[str, str], ...] = (
    ("allele_id", "VARCHAR"),
    ("model", "VARCHAR"),
    ("version", "VARCHAR"),
    ("digest", "VARCHAR"),
    ("score", "DOUBLE"),
    ("aux", "VARCHAR"),  # JSON text
    ("venue", "VARCHAR"),
    ("licence", "VARCHAR"),
    ("run_id", "VARCHAR"),
    ("ts", "TIMESTAMP"),
)


@dataclass(frozen=True)
class Coverage:
    """How much of a record set one model can score, by consequence class."""

    model: str
    scored: int
    total: int
    by_consequence: dict[str, tuple[int, int]] = field(default_factory=dict)

    @property
    def fraction(self) -> float:
        return self.scored / self.total if self.total else 0.0


@dataclass(frozen=True)
class RemoteJob:
    """A tier-3 submission the workflow polls: where it went and how to fetch the parquet."""

    model: str
    job_id: str
    venue: str
    submitted: int


class Adapter(Protocol):
    """What a model looks like to the workflow. One module per model under
    :mod:`mva.zoo.adapters`; a new lane is a new file, never an edit to a shared one."""

    name: str
    version: str
    tier: Tier
    catalogue_adjacent: bool

    def coverage(self, records: Sequence[AlleleRecord]) -> Coverage: ...

    def score(self, records: Sequence[AlleleRecord]) -> Iterator[ScoreRow]:
        """Tier 1 and 2: score locally, yielding one row per record it can score."""
        ...

    def submit(self, records: Sequence[AlleleRecord]) -> RemoteJob:
        """Tier 3: send sequence windows and ``allele_id`` only — never a coordinate."""
        ...
