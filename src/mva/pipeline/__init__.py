"""The diagnosis pipeline: VCF records in, a scored submission out.

One bounded concern per module, each usable on its own:

``variant``
    Variant identity in the exact representation the scorer compares, including the
    bare-contig to ``chr``-prefixed bridge.
``vcf``
    Reading a VCF into :class:`~mva.pipeline.vcf.Call` records — genotype, depths,
    filters, phasing — one ALT allele per record.
``compound_het``
    Pairing two calls in one gene and deciding cis, trans, or unknown phase.
``annotation``
    The port for what an external source says about a variant's consequence and
    population frequency, plus a dictionary-backed implementation.
``ranking``
    Ordering candidate pairs by rarity and severity.
``scorer``
    A local replica of the challenge scorer, so a submission can be graded before it
    is spent.
``submission``
    The Track 1 CSV: row shape, validation, and writing.

The quick path::

    from mva.pipeline import candidate_pairs, rank_pairs, read_calls, write_submission

    calls = read_calls("proband.vcf.gz")
    pairs = candidate_pairs(calls)
"""

from .annotation import (LOSS_OF_FUNCTION, MISSENSE, UNKNOWN, Annotation,
                         Annotator, DictAnnotator)
from .compound_het import Phase, VariantPair, candidate_pairs, classify_phase
from .ranking import RARE_AF, PairEvidence, RankedPair, rank_pairs
from .scorer import RankedRow, ScoreResult, rank_rows, score
from .submission import (FINDING_TYPES, HEADER, MAX_ROWS, PROBAND_ID, Row,
                         validate, write_submission)
from .variant import Variant, to_submission_contig
from .vcf import Call, iter_calls, read_calls

__all__ = [
    "Annotation", "Annotator", "DictAnnotator", "LOSS_OF_FUNCTION", "MISSENSE", "UNKNOWN",
    "Phase", "VariantPair", "candidate_pairs", "classify_phase",
    "RARE_AF", "PairEvidence", "RankedPair", "rank_pairs",
    "RankedRow", "ScoreResult", "rank_rows", "score",
    "FINDING_TYPES", "HEADER", "MAX_ROWS", "PROBAND_ID", "Row", "validate",
    "write_submission",
    "Variant", "to_submission_contig",
    "Call", "iter_calls", "read_calls",
]
