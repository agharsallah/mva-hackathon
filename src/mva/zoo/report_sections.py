"""The seven sections of the per-model report, as Markdown.

:mod:`mva.zoo.report` owns the two entry points and :mod:`mva.zoo.report_stats` computes every
number; this module only prints them. The hard rule all three obey: **the JSON computes, the
Markdown prints.** Every number in a rendered report is a key of the stored JSON, so a reader
can diff the prose against the row it came from, and a regenerated report is byte-identical
unless a number changed.

Section order is fixed by the plan (§5, step 5) and is the same for every model:

1. model card · 2. inputs and coverage · 3. score distribution · 4. the confirmed pair ·
5. what the clinical terms say · 6. interpretation (the only slot prose may enter) ·
7. limitations, licence, runtime, cost.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .report_stats import (
    HPO_TERM_COUNT,
    coverage_json,
    distribution_json,
    histogram_path,
    hpo_sentence,
)

__all__ = [
    "HAND_MARKER",
    "HPO_TERM_COUNT",
    "INTERPRETATION_MARKER",
    "INTERPRETATION_TRAILER",
    "SECTION_TITLES",
    "SIDE_BY_SIDE_NOTE",
    "coverage_json",
    "distribution_json",
    "existing_interpretation",
    "existing_interpretations",
    "histogram_path",
    "hpo_sentence",
    "interpretation_json",
    "render_sections",
]

SECTION_TITLES: tuple[str, ...] = (
    "Model card",
    "Inputs and coverage",
    "Score distribution",
    "The confirmed pair",
    "What the clinical terms say",
    "Interpretation",
    "Limitations, licence, runtime, cost",
)


# ---------------------------------------------------------------------------------------
# Renderers — one function per section, all of them pure string work
# ---------------------------------------------------------------------------------------


def render_sections(report: Mapping[str, Any]) -> list[str]:
    """The seven sections of one model's report, in order, as Markdown lines."""
    sections = report.get("sections", {})
    out: list[str] = []
    out += _card(sections.get("card", {}))
    out += _inputs(sections.get("inputs", {}))
    out += _distribution(sections.get("distribution", {}))
    out += _confirmed(sections.get("confirmed_pair", {}))
    out += _clinical(sections.get("clinical", {}))
    out += _interpretation(sections.get("interpretation", {}))
    out += _limitations(sections.get("limitations", {}))
    return out


def _heading(index: int) -> list[str]:
    return ["", f"## {index}. {SECTION_TITLES[index - 1]}", ""]


def _card(card: Mapping[str, Any]) -> list[str]:
    fields = (
        ("name", "name"),
        ("version", "version"),
        ("tier", "inference tier"),
        ("licence", "licence"),
        ("catalogue_adjacent", "catalogue-adjacent"),
        ("pmid", "reference (PMID)"),
        ("digest", "weights / table digest"),
    )
    lines = [*_heading(1), "| field | value |", "|---|---|"]
    for key, label in fields:
        if key not in card:
            continue
        value = card[key]
        if isinstance(value, bool):
            value = "yes" if value else "no"
        lines.append(f"| {label} | {value if value not in (None, '') else '—'} |")
    notes = card.get("notes")
    if notes:
        lines += ["", str(notes)]
    return lines


def _inputs(inputs: Mapping[str, Any]) -> list[str]:
    fraction = inputs.get("fraction")
    lines = [
        *_heading(2),
        f"Scored **{inputs.get('scored', 0)} of {inputs.get('total', 0)}** allele records"
        + (f" ({fraction:.1%})." if isinstance(fraction, float) else "."),
        "",
        "| consequence class | scored | records | fraction |",
        "|---|---|---|---|",
    ]
    rows = inputs.get("by_consequence", [])
    for row in rows:
        share = row.get("fraction")
        lines.append(
            f"| `{row['consequence']}` | {row['scored']} | {row['total']} | "
            + (f"{share:.1%} |" if isinstance(share, float) else "— |")
        )
    if not rows:
        lines.append("| — | — | — | — |")
    lines += [
        "",
        (
            "A class with a low fraction is this lane's blind spot, stated rather than averaged "
            "away: a pair with an unscored half is excluded from this lane's ranking, never "
            "scored zero."
        ),
    ]
    return lines


def _distribution(dist: Mapping[str, Any]) -> list[str]:
    lines = [*_heading(3)]
    figure = dist.get("figure")
    if figure:
        lines += [f"![Score distribution]({figure})", ""]
    lines += [
        (
            f"{dist.get('n', 0)} scored alleles; "
            f"min {_num(dist.get('min'))}, mean {_num(dist.get('mean'))}, "
            f"max {_num(dist.get('max'))}."
        ),
        "",
        "| quantile | score |",
        "|---|---|",
    ]
    for key, value in (dist.get("quantiles") or {}).items():
        lines.append(f"| {key} | {_num(value)} |")
    if not dist.get("quantiles"):
        lines.append("| — | — |")
    marks = dist.get("marks") or []
    if marks:
        lines += [
            "",
            "The confirmed pair's two alleles, marked on the histogram:",
            "",
            "| allele | half | score | percentile |",
            "|---|---|---|---|",
        ]
        for mark in marks:
            lines.append(
                f"| `{mark['allele_id']}` | {mark.get('role') or '—'} | "
                f"{_num(mark.get('score'))} | {_pct(mark.get('percentile'))} |"
            )
    return lines


def _confirmed(block: Mapping[str, Any]) -> list[str]:
    lines = [*_heading(4)]
    if not block or block.get("rank") is None:
        lines += [
            (
                f"This lane did not score both halves of the confirmed pair "
                f"(`{block.get('gene', '—')}`), so it is recorded as having **no opinion** on it "
                f"— not a bad one. {_count(block.get('n_ranked', 0), 'pair')} ranked here."
            ),
        ]
    else:
        lines += [
            "| gene | rank | of pairs | percentile | min score | max score |",
            "|---|---|---|---|---|---|",
            (
                f"| `{block.get('gene')}` | {block.get('rank')} | {block.get('n_ranked')} | "
                f"{_pct(block.get('percentile'))} | {_num(block.get('min_score'))} | "
                f"{_num(block.get('max_score'))} |"
            ),
        ]
    lines += [
        "",
        "| half | percentile among this lane's scored alleles |",
        "|---|---|",
        f"| left | {_pct(block.get('left_percentile'))} |",
        f"| right | {_pct(block.get('right_percentile'))} |",
        "",
        (
            "Percentile is a position from the top: rank 1 of 20 is 5.00 %. The pair score is "
            "`(min, max)` of the two allele scores, sorted by `min` first — a pair is only as "
            "damaging as its weaker half."
        ),
    ]
    mode = block.get("mode")
    if mode:
        lines += ["", f"Catalogue mode: `{mode}`."]
    return lines


def _clinical(block: Mapping[str, Any]) -> list[str]:
    return [*_heading(5), str(block.get("sentence", "—"))]


#: Printed under section 6 on every render. Named rather than inlined because
#: :func:`existing_interpretation` has to strip it back off when it reads a hand-written
#: section out of a rendered file — otherwise a re-render appends a second copy, which is
#: exactly what the first re-render did (entry 130).
INTERPRETATION_TRAILER = (
    "Only this section is written rather than computed. Sections 1-5 and 7 are rendered "
    "from the stored JSON and change only when a number changes."
)

#: Every version of section 6 opens with this comment. The hand-written one continues
#: ``hand-written <date>``; a generated one continues ``generated <date> | llm:<mode> |
#: model:<id>``. It is the badge a reader sees and the anchor a re-render reads back.
INTERPRETATION_MARKER = "<!-- interpretation:"
HAND_MARKER = f"{INTERPRETATION_MARKER} hand-written"

#: Printed above section 6 when the report carries more than one version of it. Two versions
#: are not a draft and a final: they are the same numbers explained twice, by two different
#: writers, kept together so a reader can see what the automation did and did not change.
SIDE_BY_SIDE_NOTE = (
    "This section exists in more than one version — the numbers above are identical for all "
    "of them. Each version carries a badge saying who wrote it, in which mode, and how many "
    "of its sentences resolve to a row of sections 2-5 (`mva.zoo.narrate_check`)."
)

_PLACEHOLDER = "_Placeholder. This is the one section prose may enter._"


def interpretation_json(
    versions: Sequence[Mapping[str, Any]], *, marker: str, text: str, llm_mode: str
) -> dict[str, Any]:
    """The stored ``sections.interpretation`` block: the primary version, then the rest.

    No versions means the hand-written path, unchanged since the MVP. One or more means the
    first is primary and the others are kept beside it under ``alternatives`` — a report never
    drops a version of this section, because the point of generating one is to compare it with
    the one it would otherwise replace.
    """
    if not versions:
        return {"marker": marker, "text": text, "llm_mode": llm_mode}
    primary = dict(versions[0])
    primary["alternatives"] = [dict(other) for other in versions[1:]]
    return primary


def existing_interpretation(path: Path, *, marker: str = HAND_MARKER) -> str:
    """The **hand-written** prose already in a rendered report's section 6, or ``""``.

    A report may carry several versions of section 6 under ``### 6.n`` sub-headings, so the
    reader looks for the hand-written marker specifically and stops at the next heading of any
    level or at the next version's marker. It falls back to the first version of any kind when
    there is no hand-written one, which is what a report generated from scratch looks like.
    """
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8")
    start = text.find(marker)
    if start < 0:
        start = text.find(INTERPRETATION_MARKER)
    if start < 0:
        return ""
    tail = text[start:].split("-->", 1)[-1]
    for stop in ("\n## ", "\n### ", INTERPRETATION_MARKER):
        tail = tail.split(stop, 1)[0]
    body = tail.replace(INTERPRETATION_TRAILER, "").strip()
    return "" if body.startswith("_Placeholder.") else body


#: The three facts a rendered marker carries beyond the date: which mode wrote the version,
#: which model answered, and how many of its sentences cited a row.
_MARKER_MODE = re.compile(r"llm:([^\s|]+)")
_MARKER_MODEL = re.compile(r"model:([^|]+?)\s*(?:\||-->)")
_MARKER_CITED = re.compile(r"cited (\d+)/(\d+)")


def existing_interpretations(path: Path) -> list[dict[str, Any]]:
    """**Every** version of section 6 in a rendered report, as interpretation blocks.

    :func:`existing_interpretation` returns the hand-written prose alone; this returns the
    whole slot, because a re-render that keeps only one version silently deletes the others.
    Each block is rebuilt from its own marker — the marker *is* the record: it names the mode,
    the model id and the citation count, so a rendered file round-trips without the JSON.
    """
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    pieces = text.split(INTERPRETATION_MARKER)[1:]
    blocks: list[dict[str, Any]] = []
    for piece in pieces:
        head, _, tail = piece.partition("-->")
        marker = f"{INTERPRETATION_MARKER}{head}-->"
        for stop in ("\n## ", "\n### "):
            tail = tail.split(stop, 1)[0]
        body = tail.replace(INTERPRETATION_TRAILER, "").strip()
        if not body or body.startswith("_Placeholder."):
            continue
        blocks.append({"marker": marker, "text": body, **_from_marker(marker)})
    return blocks


def _from_marker(marker: str) -> dict[str, Any]:
    """The mode, model id and citation counts a rendered marker states."""
    mode_match = _MARKER_MODE.search(marker)
    mode = "hand" if "hand-written" in marker else (mode_match.group(1) if mode_match else "none")
    model_match = _MARKER_MODEL.search(marker)
    cited_match = _MARKER_CITED.search(marker)
    cited = int(cited_match.group(1)) if cited_match else 0
    total = int(cited_match.group(2)) if cited_match else 0
    return {
        "llm_mode": mode,
        "llm_model_id": model_match.group(1).strip() if model_match else "",
        "cited_sentences": cited,
        "uncited_sentences": max(total - cited, 0),
    }


def _interpretation(block: Mapping[str, Any]) -> list[str]:
    """Section 6, with one sub-heading per version when the report carries several."""
    variants = [block, *(block.get("alternatives") or [])]
    lines = [*_heading(6)]
    if len(variants) > 1:
        lines += [SIDE_BY_SIDE_NOTE, ""]
    for index, variant in enumerate(variants, start=1):
        if len(variants) > 1:
            lines += [f"### 6.{index} {_badge(variant)}", ""]
        lines += [
            str(variant.get("marker", f"{HAND_MARKER} YYYY-MM-DD | llm:none -->")),
            "",
            str(variant.get("text") or _PLACEHOLDER),
            "",
        ]
    lines.append(INTERPRETATION_TRAILER)
    return lines


def _badge(variant: Mapping[str, Any]) -> str:
    """The label above one version of section 6: who wrote it, and how well it cited."""
    mode = str(variant.get("llm_mode") or "none")
    if mode in ("none", "hand", ""):
        return "Hand-written"
    model = str(variant.get("llm_model_id") or "unrecorded")
    cited = int(variant.get("cited_sentences", 0) or 0)
    total = cited + int(variant.get("uncited_sentences", 0) or 0)
    tail = f", {cited}/{total} sentences cited" if total else ""
    return f"Generated — mode `{mode}`, model `{model}`{tail}"


def _limitations(block: Mapping[str, Any]) -> list[str]:
    lines = [
        *_heading(7),
        "| field | value |",
        "|---|---|",
        f"| licence | {block.get('licence') or '—'} |",
        f"| venue | {block.get('venue') or '—'} |",
        f"| wall-clock (s) | {_num(block.get('seconds'))} |",
        f"| cost (USD) | {_num(block.get('dollars'))} |",
        f"| run id | `{block.get('run_id') or '—'}` |",
        "",
    ]
    items = block.get("limitations") or []
    lines += [f"- {item}" for item in items] or ["- (none recorded)"]
    return lines


def _count(value: Any, noun: str) -> str:
    """``3 pairs were`` / ``1 pair was`` — the words agree with the number the JSON holds."""
    number = int(value or 0)
    return f"1 {noun} was" if number == 1 else f"{number} {noun}s were"


def _num(value: Any) -> str:
    if value is None:
        return "—"
    number = float(value)
    return f"{number:.6g}"


def _pct(value: Any) -> str:
    return "—" if value is None else f"{float(value):.2f} %"
