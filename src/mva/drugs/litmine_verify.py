"""The reproducible gate of route R3: a quote must be a verbatim substring of its source.

A language model read the corpus and wrote rows. Nothing it wrote is trusted until code has
checked the one thing that can be checked mechanically: **the quoted sentence exists, word
for word, in the cached text of the paper the row cites.** A row that fails is *rejected*,
with a reason, never repaired — repairing would mean the model editing its own evidence.

Normalisation is limited to what differs between two renderings of the same sentence and
never changes a word (think of it as ``git diff -w`` plus Unicode folding):

* Unicode NFKC (``NAD⁺`` → ``NAD+``, non-breaking space → space, ligatures split);
* typographic quotes → ASCII quotes; every dash and minus → ``-``;
* soft hyphens and zero-width characters removed;
* runs of whitespace → one space, and no space before closing punctuation.

Case is kept. A quote shorter than ``min_quote`` characters after normalisation is rejected
too: a six-word fragment matches too many papers to be evidence of any one of them.

Field checks are schema checks (``enums``): an ``effect_on`` outside the pinned vocabulary is
a rejected row, not a new category.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

__all__ = [
    "EXPOSURE_ENUMS",
    "INTERVENTION_ENUMS",
    "INTERVENTION_FIELDS",
    "normalise",
    "verify_rows",
]

#: The columns every extracted intervention row carries (the reader writes all of them).
INTERVENTION_FIELDS = (
    "intervention",
    "intervention_type",
    "mode",
    "target",
    "effect_on",
    "direction",
    "model_system",
    "pmid",
    "quote",
)

INTERVENTION_ENUMS: Mapping[str, frozenset[str]] = {
    "intervention_type": frozenset({"drug", "genetic", "diet", "other"}),
    # gain = more of the target (overexpression, transgene, activation, supplement);
    # loss = less of it (knockout, knockdown, inhibition, removal of cells expressing it).
    "mode": frozenset({"gain", "loss", "exposure"}),
    "effect_on": frozenset(
        {
            "bubr1_level",
            "acetylation",
            "function",
            "aneuploidy",
            "senescence",
            "lifespan",
            "tumour",
            "other",
        }
    ),
    "direction": frozenset({"increase", "decrease", "no_change"}),
    "model_system": frozenset(
        {"human_patient", "human_cells", "mouse_in_vivo", "mouse_cells", "other_organism"}
    ),
}

EXPOSURE_ENUMS: Mapping[str, frozenset[str]] = {
    "outcome_kind": frozenset({"toxicity", "response", "death", "tolerated", "other"}),
}

_QUOTES = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "‚": "'",
        "‛": "'",
        "′": "'",
        "“": '"',
        "”": '"',
        "„": '"',
        "‟": '"',
        "″": '"',
        "‐": "-",
        "‑": "-",
        "‒": "-",
        "–": "-",
        "—": "-",
        "―": "-",
        "−": "-",
        "­": None,
        "\u200b": None,
        "‌": None,
        "‍": None,
        "﻿": None,
    }
)
_SPACE = re.compile(r"\s+")
_BEFORE_PUNCT = re.compile(r"\s+([,.;:)\]])")
_AFTER_OPEN = re.compile(r"([(\[])\s+")


def normalise(text: str) -> str:
    """The comparison form of a text: see the module docstring. Words are never changed."""
    folded = unicodedata.normalize("NFKC", text or "").translate(_QUOTES)
    collapsed = _SPACE.sub(" ", folded).strip()
    return _AFTER_OPEN.sub(r"\1", _BEFORE_PUNCT.sub(r"\1", collapsed))


def verify_rows(
    rows: Iterable[Mapping[str, Any]],
    texts: Mapping[str, Mapping[str, str]],
    *,
    required: Sequence[str],
    enums: Mapping[str, frozenset[str]],
    min_quote: int = 30,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split rows into ``(kept, rejected)``.

    ``texts`` maps pmid → {text kind → cached text}. A kept row gains ``verified_in`` (the
    text kind that holds the quote; ``abstract`` wins a tie). A rejected row gains
    ``reject_reason``; the first failing check is the one reported.
    """
    normalised = {
        pmid: {kind: normalise(text) for kind, text in kinds.items()}
        for pmid, kinds in texts.items()
    }
    kept: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for raw in rows:
        row = {key: ("" if value is None else str(value).strip()) for key, value in raw.items()}
        reason = _field_problem(row, required, enums)
        if not reason:
            reason, where = _quote_problem(row, normalised, min_quote)
        if reason:
            rejected.append({**row, "reject_reason": reason})
        else:
            kept.append({**row, "verified_in": where})
    return kept, rejected


def _field_problem(
    row: Mapping[str, str], required: Sequence[str], enums: Mapping[str, frozenset[str]]
) -> str:
    for name in required:
        if not row.get(name):
            return f"empty:{name}"
    for name, allowed in enums.items():
        if name in row and row[name] not in allowed:
            return f"bad_value:{name}"
    return ""


def _quote_problem(
    row: Mapping[str, str], texts: Mapping[str, Mapping[str, str]], min_quote: int
) -> tuple[str, str]:
    kinds = texts.get(row.get("pmid", ""))
    if not kinds:
        return "no_cached_text", ""
    quote = normalise(row.get("quote", ""))
    if len(quote) < min_quote:
        return "quote_too_short", ""
    for kind in sorted(kinds, key=lambda k: (k != "abstract", k)):
        if quote in kinds[kind]:
            return "", kind
    return "quote_not_in_source", ""
