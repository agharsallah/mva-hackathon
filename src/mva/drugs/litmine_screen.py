"""Point the reader at the sentences worth reading: a lexical screen over the cached corpus.

Hundreds of papers are too many to read end to end, so the extraction is two-stage:

1. **Screen (code, this module).** Split every cached text into sentences and keep a
   sentence when it names the subject (the gene or an alias) *and* an effect word *and* an
   intervention cue — the three things a row needs. A second screen, for clinical reports,
   keeps a sentence naming a drug-exposure word *and* an outcome word.
2. **Read (the model).** The reader opens the kept sentences, with their neighbours, and
   writes structured rows whose quote is copied from the text. The verifier then checks each
   quote against the cached file; the screen never produces a row itself.

A sentence the screen drops cannot become a row, so the screen is a recall ceiling — which is
why the positive control is measured *after* it, on the verified rows.

Lexicons are parameters (:class:`Lexicon`); the defaults a driver passes are stated in its
provenance, not hidden here.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = ["Lexicon", "load_texts", "screen_corpus", "sentences", "write_reading_pack"]

#: A sentence ends at . ! or ? followed by whitespace and an upper-case letter or digit.
#: Crude on purpose: the verifier works on the whole text, so a bad split costs context,
#: never a false quote.
_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\[])")


@dataclass(frozen=True)
class Lexicon:
    """Three word lists; a sentence passes when it matches one word from each."""

    name: str
    subject: tuple[str, ...]
    effect: tuple[str, ...]
    cue: tuple[str, ...]

    def pattern(self, words: Sequence[str]) -> re.Pattern[str]:
        return re.compile("|".join(re.escape(w) for w in words), re.IGNORECASE)


def sentences(text: str) -> list[str]:
    """The text split into sentences (see ``_SPLIT``)."""
    return [s.strip() for s in _SPLIT.split(text or "") if s.strip()]


def screen_corpus(
    texts: Mapping[str, Mapping[str, str]],
    lexicon: Lexicon,
    *,
    only: Iterable[str] | None = None,
    window: int = 1,
) -> list[dict[str, Any]]:
    """Every passing sentence as ``{pmid, text_kind, index, sentence, context}``.

    ``texts`` maps pmid → {text kind → text}. When a paper has full text its abstract is
    also screened (they overlap; the verifier accepts a quote from either). ``context`` is
    the sentence with ``window`` neighbours either side, for the reader only.
    """
    subject = lexicon.pattern(lexicon.subject)
    effect = lexicon.pattern(lexicon.effect)
    cue = lexicon.pattern(lexicon.cue)
    keep = set(only) if only is not None else None
    hits: list[dict[str, Any]] = []
    for pmid in sorted(texts, key=int):
        if keep is not None and pmid not in keep:
            continue
        seen: set[str] = set()
        for kind, text in texts[pmid].items():
            parts = sentences(text)
            for index, sentence in enumerate(parts):
                if sentence in seen:
                    continue
                if subject.search(sentence) and effect.search(sentence) and cue.search(sentence):
                    seen.add(sentence)
                    lo, hi = max(0, index - window), min(len(parts), index + window + 1)
                    hits.append(
                        {
                            "pmid": pmid,
                            "text_kind": kind,
                            "index": index,
                            "sentence": sentence,
                            "context": " ".join(parts[lo:hi]),
                        }
                    )
    return hits


def load_texts(directory: Path) -> dict[str, dict[str, str]]:
    """``<pmid>.<kind>.txt`` files → pmid → {kind → text}."""
    out: dict[str, dict[str, str]] = {}
    for path in sorted(directory.glob("*.txt")):
        pmid, kind = path.name.split(".")[:2]
        out.setdefault(pmid, {})[kind] = path.read_text(encoding="utf-8")
    return out


def write_reading_pack(
    hits: Sequence[Mapping[str, Any]], titles: Mapping[str, str], path: Path
) -> Path:
    """A Markdown reading pack, one heading per paper, for the reader. Lives in ``build/``."""
    lines: list[str] = []
    current = ""
    for hit in hits:
        if hit["pmid"] != current:
            current = str(hit["pmid"])
            lines.append(f"\n## {current} — {titles.get(current, '')}")
        lines.append(f"- [{hit['text_kind']}#{hit['index']}] {hit['sentence']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).lstrip() + "\n", encoding="utf-8")
    return path
