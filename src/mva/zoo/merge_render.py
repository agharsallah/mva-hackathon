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

from collections.abc import Mapping
from typing import Any

__all__ = ["render_merged"]


def render_merged(report: Mapping[str, Any], narrative: str, *, dated: str = "") -> str:
    """The merged report as Markdown — every number read straight out of ``report``.

    ``narrative`` is the hand-written paragraph the MVP's ``fusion`` method requires. The slot
    is marked in the output so a later LLM run (``fusion+synthesis``) can replace exactly that
    paragraph and nothing else.
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
        f"<!-- narrative: hand-written {day} -->",
        "",
        narrative.strip() or "_(narrative not yet written)_",
        "",
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
