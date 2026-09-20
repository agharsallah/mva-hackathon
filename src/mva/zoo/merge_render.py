"""Rendering the merged report to Markdown. Prints the merged JSON; computes nothing.

Split out of :mod:`mva.zoo.merge` so that file stays about *arithmetic* and this one about
*words*. The contract is the same one every report in iteration 4 obeys: a number in the
Markdown is a key in the JSON, so the page can be diffed against the run that produced it.

The hand-written narrative sits under a marker::

    <!-- narrative: hand-written 2026-09-18 -->

which is what lets the optional ``fusion+synthesis`` merge method later replace exactly that
paragraph and nothing else.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .report_sections import SIDE_BY_SIDE_NOTE

__all__ = ["NARRATIVE_MARKER", "existing_narratives", "render_merged"]

#: Every version of section 5 opens with this. `fusion` writes ``hand-written <date>``;
#: `fusion+synthesis` writes ``synthesised <date> | llm:<mode> | model:<id> | cited n/m``.
NARRATIVE_MARKER = "<!-- narrative:"


def existing_narratives(path: str | Path) -> list[dict[str, Any]]:
    """**Every** version of section 5 in a rendered merged report, as narrative blocks.

    The same round trip :func:`mva.zoo.report_sections.existing_interpretations` does for
    section 6 of a per-model report, and for the same reason: a re-render that restores only
    the hand-written version deletes the synthesised one. Each block is rebuilt from its own
    marker, so the rendered file is a complete record without the merged JSON.
    """
    file = Path(path)
    if not file.is_file():
        return []
    text = file.read_text(encoding="utf-8")
    section = text.split("## 5. What this means", 1)[-1].split("\n## ", 1)[0]
    blocks: list[dict[str, Any]] = []
    for piece in section.split(NARRATIVE_MARKER)[1:]:
        head, _, tail = piece.partition("-->")
        marker = f"{NARRATIVE_MARKER}{head}-->"
        for stop in ("\n### ", NARRATIVE_MARKER):
            tail = tail.split(stop, 1)[0]
        body = tail.strip()
        if not body or body.startswith("_("):
            continue
        mode_match = re.search(r"llm:([^\s|]+)", marker)
        model_match = re.search(r"model:([^|]+?)\s*(?:\||-->)", marker)
        cited_match = re.search(r"cited (\d+)/(\d+)", marker)
        cited = int(cited_match.group(1)) if cited_match else 0
        total = int(cited_match.group(2)) if cited_match else 0
        blocks.append(
            {
                "marker": marker,
                "text": body,
                "llm_mode": "hand"
                if "hand-written" in marker
                else (mode_match.group(1) if mode_match else "none"),
                "llm_model_id": model_match.group(1).strip() if model_match else "",
                "cited_sentences": cited,
                "uncited_sentences": max(total - cited, 0),
            }
        )
    return blocks


def render_merged(
    report: Mapping[str, Any],
    narrative: str,
    *,
    dated: str = "",
    narratives: Sequence[Mapping[str, Any]] = (),
) -> str:
    """The merged report as Markdown — every number read straight out of ``report``.

    ``narrative`` is the hand-written paragraph the MVP's ``fusion`` method requires.
    ``narratives`` is the same slot taken as **a list of versions**, which is what the
    ``fusion+synthesis`` method produces: the synthesised paragraph leads, the hand-written one
    stays under it with its own badge, and neither is lost. Each item is a block from
    :func:`mva.zoo.narrate.interpretation_block`.
    """
    day = dated or str(report.get("generated_at", ""))[:10]
    lines = [
        "# Iteration 4 — the merged report",
        "",
        (
            f"**Standing:** generated {report.get('generated_at', '')} by "
            f"`mva.zoo.merge.render_merged` from run `{report.get('run_id', '')}`; "
            f"merge method `{report.get('method', '')}`."
        ),
        "",
        "Every number below is a key of the run's merged JSON; this page computes nothing.",
        "",
        "## 1. The lanes",
        "",
        (
            "| lane | version | tier | catalogue-adjacent | pairs ranked | pairs unscored "
            "| alleles scored | confirmed rank | percentile |"
        ),
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for lane in report.get("lanes", []):
        confirmed = lane.get("confirmed") or {}
        lines.append(
            f"| `{lane['model']}` | {lane.get('version', '') or '—'} | "
            f"{lane.get('tier', '') or '—'} | "
            f"{'yes' if lane.get('catalogue_adjacent') else 'no'} | {lane['n_ranked']} | "
            f"{lane['unscored_pairs']} | {lane['scored_alleles']} | "
            f"{_or_dash(confirmed.get('rank'))} | {_pct(confirmed.get('percentile'))} |"
        )
    lines += [
        "",
        "> Percentile is the pair's position from the top, in percent: rank 1 of 20 is 5.0 %.",
        (
            "> A lane with no rank scored fewer than both alleles of the confirmed pair, and is "
            "recorded as having no opinion rather than a bad one."
        ),
        "",
        "## 2. Agreement between lanes",
        "",
        (
            "Spearman ρ (rank correlation) over the alleles both lanes scored, with the shared-"
            "allele count. An empty cell had too few shared alleles or no variance."
        ),
        "",
    ]
    lines += _matrix_block(report.get("agreement", {}))
    lines += [
        "",
        "## 3. Consensus — reciprocal rank fusion",
        "",
        f"{report.get('citation', '')}",
        "",
        "| run | lanes | excluded | k | confirmed pair's RRF rank | of pairs | fused score |",
        "|---|---|---|---|---|---|---|",
    ]
    for label, key in (("catalogue-free", "catalogue_free"), ("all lanes", "all_lanes")):
        block = report.get("consensus", {}).get(key, {})
        lines.append(
            f"| {label} | {', '.join(block.get('lanes', [])) or '—'} | "
            f"{', '.join(block.get('excluded_lanes', [])) or '—'} | {block.get('k', '')} | "
            f"{_or_dash(block.get('rank'))} | {block.get('n_pairs', 0)} | "
            f"{_round(block.get('fused_score'))} |"
        )
    lines += [
        "",
        "## 4. Where the lanes disagree",
        "",
        (
            "Alleles in the top 1 % of one lane and the bottom half of another. A disagreement is "
            "a finding about the models, not an error in the data."
        ),
        "",
        "| allele | high lane | its percentile | low lane | its percentile |",
        "|---|---|---|---|---|",
    ]
    rows = list(report.get("disagreements", []))
    for row in rows[:20]:
        lines.append(
            f"| `{row['allele_id']}` | `{row['high_model']}` | "
            f"{_pct(row['high_percentile'])} | `{row['low_model']}` | "
            f"{_pct(row['low_percentile'])} |"
        )
    if not rows:
        lines.append("| — | — | — | — | — |")
    if len(rows) > 20:
        lines.append("")
        lines.append(f"{len(rows) - 20} further rows are in the run's merged JSON.")
    lines += [
        "",
        "## 5. What this means",
        "",
        *_narrative_block(narrative, narratives, day),
        "## 6. Lineage",
        "",
        f"- run id: `{report.get('run_id', '')}`",
        f"- merge method: `{report.get('method', '')}`, RRF k = {report.get('rrf_k', '')}",
        "- source tables: "
        + (", ".join(f"`{s}`" for s in report.get("lineage", {}).get("sources", [])) or "—"),
        f"- built by: `{report.get('lineage', {}).get('tool', '')}`",
        "",
    ]
    return "\n".join(lines)


def _narrative_block(
    narrative: str, narratives: Sequence[Mapping[str, Any]], day: str
) -> list[str]:
    """Section 5, with one sub-heading per version when the merge produced more than one."""
    if not narratives:
        return [
            f"{NARRATIVE_MARKER} hand-written {day} -->",
            "",
            narrative.strip() or "_(narrative not yet written)_",
            "",
        ]
    lines: list[str] = []
    if len(narratives) > 1:
        lines += [SIDE_BY_SIDE_NOTE.replace("sections 2-5", "sections 1-4"), ""]
    for index, version in enumerate(narratives, start=1):
        if len(narratives) > 1:
            lines += [f"### 5.{index} {_narrative_badge(version)}", ""]
        lines += [
            str(version.get("marker") or f"{NARRATIVE_MARKER} hand-written {day} -->"),
            "",
            str(version.get("text") or "_(narrative not yet written)_"),
            "",
        ]
    return lines


def _narrative_badge(version: Mapping[str, Any]) -> str:
    """Who wrote this version of the merged narrative, and how well it cited."""
    mode = str(version.get("llm_mode") or "none")
    if mode in ("none", "hand", ""):
        return "Hand-written"
    model = str(version.get("llm_model_id") or "unrecorded")
    cited = int(version.get("cited_sentences", 0) or 0)
    total = cited + int(version.get("uncited_sentences", 0) or 0)
    tail = f", {cited}/{total} sentences cited" if total else ""
    return f"Synthesised — mode `{mode}`, model `{model}`{tail}"


def _matrix_block(agreement: Mapping[str, Any]) -> list[str]:
    models = list(agreement.get("models", []))
    cells = {(c["a"], c["b"]): c for c in agreement.get("cells", [])}
    if not models:
        return ["_(no lane scored anything)_"]
    head = "| ρ (n) | " + " | ".join(f"`{m}`" for m in models) + " |"
    rule = "|---" * (len(models) + 1) + "|"
    out = [head, rule]
    for a in models:
        row = [f"| `{a}` "]
        for b in models:
            cell = cells.get((a, b), {})
            rho, n = cell.get("rho"), cell.get("n", 0)
            row.append(f"| {'—' if rho is None else f'{rho:+.3f}'} ({n}) ")
        out.append("".join(row) + "|")
    return out


def _or_dash(value: Any) -> str:
    return "—" if value is None else str(value)


def _pct(value: Any) -> str:
    return "—" if value is None else f"{float(value):.2f} %"


def _round(value: Any) -> str:
    return "—" if value is None else f"{float(value):.6f}"
