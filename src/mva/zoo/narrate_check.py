"""Does the written interpretation rest on the numbers it was given?

The LLM in :mod:`mva.zoo.narrate` is an **explainer**, not a ranker: it is handed a list of
rows, each with a stable id (``cov.missense_variant``, ``pair.rank``, ``hpo.rank``), and told
to interpret them in ≤ 200 words with every sentence ending in a citation ``[id]``. This
module is the mechanical check that it obeyed — the thing that turns "the prose looks fine"
into a number a claim can be refuted by (plan §5 step 5, ``P4-7``).

Three rules, checked independently so a failure names which one broke:

``cited``
    every sentence ends with at least one ``[id]``;
``resolves``
    every cited id is one of the input rows — a citation to ``[pair.rank]`` when no such row
    was sent is an invention, not a citation;
``no new names``
    no gene-symbol-shaped or disease-shaped token appears that is not already in the rows'
    own text. This is the rule that catches the failure mode the plan names (R3): the model
    knows MVA → BUB1B from training text, so a sentence naming a gene that the rows never
    mentioned is the model recalling an answer rather than reading the table.

The checker is pure string work over the reply and the rows. It never reads the warehouse and
never needs the model, so a reply stored months ago can be re-checked from its row.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "CheckResult",
    "SentenceCheck",
    "check_narrative",
    "split_sentences",
]

#: A citation as the prompt asks for it: the row id in square brackets. Ids are
#: ``[a-z0-9_.-]`` by construction (:func:`mva.zoo.narrate.citable_rows`), so the pattern is
#: tight enough not to swallow a Markdown link.
CITATION = re.compile(r"\[([A-Za-z0-9_.\-]+)\]")

#: A sentence ends at ``.``/``!``/``?`` followed by whitespace-or-end. Split on the *end* so
#: the citation that precedes the full stop stays with its own sentence.
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")

#: What a gene symbol looks like when written out: two or more characters, upper-case letters
#: and digits, starting with a letter (``BUB1B``, ``TP53``, ``CEP57``). Deliberately shaped
#: rather than looked up in a gene list: a checker that needs a 40k-symbol table to run is a
#: checker that stops running.
_SYMBOL = re.compile(r"\b[A-Z][A-Z0-9]{1,9}\b")

#: Upper-case words that are *not* gene symbols in this repository's vocabulary. Anything
#: here may appear in a reply without being a row value. Kept small and explicit: every
#: addition widens the hole the "no new names" rule exists to close.
SAFE_UPPER: frozenset[str] = frozenset(
    {
        "AI",
        "API",
        "CPU",
        "DNA",
        "GPU",
        "HPO",
        "I",
        "JSON",
        "LLM",
        "RNA",
        "UTR",
        "A",
    }
)

#: Disease names the model might reach for from training text. A reply may name a disease
#: only if the rows do. Lower-cased comparison; multi-word entries are matched as phrases.
DISEASE_WORDS: tuple[str, ...] = (
    "mosaic variegated aneuploidy",
    "aneuploidy",
    "cancer",
    "carcinoma",
    "leukaemia",
    "leukemia",
    "microcephaly",
    "rhabdomyosarcoma",
    "wilms",
    "premature chromatid separation",
    "mosaic variegated",
)


@dataclass(frozen=True)
class SentenceCheck:
    """One sentence of the reply and what the three rules said about it."""

    index: int
    text: str
    ids: tuple[str, ...] = ()
    unknown_ids: tuple[str, ...] = ()

    @property
    def cited(self) -> bool:
        """True when the sentence carries at least one citation that resolves to a row."""
        return bool(self.ids) and not self.unknown_ids


@dataclass(frozen=True)
class CheckResult:
    """The verdict on one narrative: the per-sentence detail and the rate ``P4-7`` tests."""

    sentences: tuple[SentenceCheck, ...] = ()
    unknown_ids: tuple[str, ...] = ()
    new_names: tuple[str, ...] = ()
    words: int = 0
    max_words: int = 0
    errors: tuple[str, ...] = field(default=())

    @property
    def n_sentences(self) -> int:
        return len(self.sentences)

    @property
    def cited_sentences(self) -> int:
        return sum(1 for item in self.sentences if item.cited)

    @property
    def uncited_sentences(self) -> int:
        return self.n_sentences - self.cited_sentences

    @property
    def uncited_rate(self) -> float:
        """Share of sentences with no resolving citation, in ``[0, 1]``. Empty reply = 1.0."""
        if not self.sentences:
            return 1.0
        return self.uncited_sentences / self.n_sentences

    @property
    def over_length(self) -> bool:
        return bool(self.max_words) and self.words > self.max_words

    @property
    def ok(self) -> bool:
        """Every sentence cited, no invented id, no new name, inside the word budget."""
        return (
            bool(self.sentences)
            and self.uncited_sentences == 0
            and not self.unknown_ids
            and not self.new_names
            and not self.over_length
        )

    def summary(self) -> dict[str, Any]:
        """The row a report, a table or an entry prints — no objects, all plain JSON."""
        return {
            "sentences": self.n_sentences,
            "cited_sentences": self.cited_sentences,
            "uncited_sentences": self.uncited_sentences,
            "uncited_rate": round(self.uncited_rate, 4),
            "unknown_ids": list(self.unknown_ids),
            "new_names": list(self.new_names),
            "words": self.words,
            "max_words": self.max_words,
            "over_length": self.over_length,
            "ok": self.ok,
        }


def split_sentences(text: str) -> list[str]:
    """Split a reply into sentences, dropping blank lines and Markdown list bullets.

    Sentence splitting is a heuristic everywhere; here it only has to be *stable*, because
    the same splitter runs on both modes' replies and on every re-check of a stored one.
    """
    flat = " ".join(line.strip().lstrip("-*•").strip() for line in text.splitlines())
    flat = re.sub(r"\s+", " ", flat).strip()
    if not flat:
        return []
    return [piece.strip() for piece in _SENTENCE_END.split(flat) if piece.strip()]


def check_narrative(
    text: str,
    rows: Sequence[Mapping[str, Any]] | Mapping[str, Any],
    *,
    max_words: int = 0,
    extra_safe: Iterable[str] = (),
) -> CheckResult:
    """Check one narrative against the rows it was written from.

    ``rows`` is the citable-row list :func:`mva.zoo.narrate.citable_rows` produced (or the
    same ``{"id": ..., "text": ...}`` mappings, or an ``{id: text}`` dict). ``max_words`` is
    the budget from the config's ``[llm] max_words``; 0 means "do not check length".
    ``extra_safe`` adds upper-case tokens that are legitimate in this case's prose (a model
    key such as ``ESM1b`` already comes through the rows, so it is rarely needed).
    """
    pairs = _rows_as_pairs(rows)
    known = {row_id for row_id, _ in pairs}
    corpus = " ".join(text_value for _, text_value in pairs)
    sentences: list[SentenceCheck] = []
    unknown: list[str] = []
    for index, sentence in enumerate(split_sentences(text), start=1):
        ids = tuple(CITATION.findall(sentence))
        bad = tuple(sorted({row_id for row_id in ids if row_id not in known}))
        unknown += [row_id for row_id in bad if row_id not in unknown]
        sentences.append(SentenceCheck(index=index, text=sentence, ids=ids, unknown_ids=bad))
    return CheckResult(
        sentences=tuple(sentences),
        unknown_ids=tuple(sorted(unknown)),
        new_names=_new_names(text, corpus, extra_safe),
        words=len(text.split()),
        max_words=max_words,
    )


def _rows_as_pairs(
    rows: Sequence[Mapping[str, Any]] | Mapping[str, Any],
) -> list[tuple[str, str]]:
    """``[{id, text}, …]`` or ``{id: text}`` → ``[(id, text), …]``; the checker takes both."""
    if isinstance(rows, Mapping):
        return [(str(key), str(value)) for key, value in rows.items()]
    out: list[tuple[str, str]] = []
    for row in rows:
        row_id = str(row.get("id", ""))
        if row_id:
            out.append((row_id, f"{row.get('label', '')} {row.get('text', '')}"))
    return out


def _new_names(text: str, corpus: str, extra_safe: Iterable[str]) -> tuple[str, ...]:
    """Gene- or disease-shaped tokens in the reply that the rows never mentioned."""
    safe = SAFE_UPPER | {str(item).upper() for item in extra_safe}
    in_rows = {token.upper() for token in _SYMBOL.findall(corpus)}
    body = _without_citations(text)
    found = {
        token
        for token in _SYMBOL.findall(body)
        if token.upper() not in safe and token.upper() not in in_rows
    }
    lowered_reply, lowered_rows = body.lower(), corpus.lower()
    found |= {word for word in DISEASE_WORDS if word in lowered_reply and word not in lowered_rows}
    return tuple(sorted(found))


def _without_citations(text: str) -> str:
    """The prose with its ``[id]`` citations removed, so an id never reads as a gene name."""
    return CITATION.sub(" ", text)
