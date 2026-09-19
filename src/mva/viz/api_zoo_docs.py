"""The zoo's file-backed surface: run manifests, per-model reports, and the merged report.

Three kinds of file, all named by the run configuration and none by this module:

* ``<docs_runs_dir>/*.json`` — the **public** copy of a run manifest, written by
  :meth:`mva.zoo.workflow_types.Manifest.public` (identical to the private one minus the
  local output paths). What ran, when, for how long, at what cost, from which config digest.
* ``<reports_dir>/<model>.md`` and ``<merged_report>`` — the rendered reports. Served as
  Markdown text; the browser renders it, exactly as ``/api/submissions`` serves a report.
* ``<out_dir>/merged.json`` — the merge step's own JSON. It lives under ``build/``, which is
  **gitignored and server-side only**; the route reads it and serves the coordinate-free
  fields (lane names, ``allele_id`` hashes, correlations, ranks). It holds no coordinate to
  begin with — :mod:`mva.zoo.merge` works from ``allele_id`` throughout — but it is not a
  committed file, so it is treated as an internal artefact that this module projects.

A missing file is never an error here. A checkout that has not run the workflow has nothing
to declare, and an empty list is the true answer; only asking for *one named* report or run
that does not exist is a 404, and that is raised by the route, not here.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = [
    "MERGED_KEY",
    "disagreement_alleles",
    "figures_in",
    "lanes_by_model",
    "merge_payload",
    "merged_document",
    "read_report",
    "report_keys",
    "runs",
]

#: The key under which the whole-zoo report is served, beside one key per model. Chosen so
#: no model key can collide with it: a registry key is a lane name, never this word.
MERGED_KEY = "merged"

#: A Markdown image link — ``![alt](path)``. The reports point at ``figures/it4/*.svg``
#: relative to the report's own folder; the page needs the list to show them.
IMAGE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")


def _run_row(document: Mapping[str, Any], path: Path) -> dict[str, Any]:
    """One manifest as the API serves it.

    ``wall_clock_seconds`` becomes ``wall_clock_s`` because that is the pinned contract's
    spelling; nothing else is reshaped, and every field the manifest omits stays ``None``.
    """
    return {
        "run_id": document.get("run_id"),
        "started": document.get("started_at"),
        "finished": document.get("finished_at"),
        "wall_clock_s": document.get("wall_clock_seconds"),
        "dollars": document.get("dollars"),
        "models": document.get("models") or {},
        "venues": document.get("venues") or {},
        "config_digest": document.get("config_digest"),
        "config_path": document.get("config_path"),
        "mode": document.get("mode"),
        "merge_method": document.get("merge_method"),
        "stages": document.get("stages") or [],
        "file": str(path),
    }


def _load(path: Path) -> dict[str, Any] | None:
    """One JSON file, or ``None`` when it is absent or unreadable."""
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def runs(docs_runs_dir: Path) -> list[dict[str, Any]]:
    """Every public run manifest in the configured folder, newest start first."""
    if not docs_runs_dir.is_dir():
        return []
    rows = [
        _run_row(document, path)
        for path in sorted(docs_runs_dir.glob("*.json"))
        if (document := _load(path)) is not None
    ]
    return sorted(rows, key=lambda row: str(row["started"] or ""), reverse=True)


def figures_in(markdown: str) -> list[str]:
    """Every image the report links, in order, deduplicated."""
    return list(dict.fromkeys(IMAGE.findall(markdown)))


def _report_path(reports_dir: Path, merged: Path, key: str) -> Path:
    return merged if key == MERGED_KEY else reports_dir / f"{key}.md"


def report_keys(reports_dir: Path, merged: Path) -> list[dict[str, Any]]:
    """The reports that exist, as ``{key, path, bytes, modified}`` — the merged one first.

    The list carries no Markdown: a page shows the index, then asks for the one report a
    reader opened. ``figures`` is included because the index links thumbnails.
    """
    found: list[dict[str, Any]] = []
    candidates = [(MERGED_KEY, merged)]
    if reports_dir.is_dir():
        candidates += [(path.stem, path) for path in sorted(reports_dir.glob("*.md"))]
    for key, path in candidates:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        found.append(
            {
                "key": key,
                "path": str(path),
                "bytes": len(text.encode("utf-8")),
                "modified": datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(),
                "figures": figures_in(text),
                "title": _title(text) or key,
            }
        )
    return found


def _title(markdown: str) -> str | None:
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def read_report(reports_dir: Path, merged: Path, key: str) -> dict[str, Any] | None:
    """One report's Markdown and its figures. ``None`` when there is no such report."""
    path = _report_path(reports_dir, merged, key)
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    return {
        "key": key,
        "title": _title(text) or key,
        "markdown": text,
        "figures": figures_in(text),
        "path": str(path),
        "modified": datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(),
    }


# ---------------------------------------------------------------------------------------
# The merged report
# ---------------------------------------------------------------------------------------


def merged_document(out_dir: Path) -> dict[str, Any] | None:
    """``<out_dir>/merged.json`` as written by :func:`mva.zoo.merge.merged_report`."""
    return _load(out_dir / "merged.json")


def lanes_by_model(document: Mapping[str, Any] | None) -> dict[str, Mapping[str, Any]]:
    """The merged report's per-lane block, keyed by model — what ``/ranks`` borrows."""
    lanes = (document or {}).get("lanes") or []
    return {str(lane["model"]): lane for lane in lanes if isinstance(lane, dict)}


def _matrix(agreement: Mapping[str, Any]) -> dict[str, Any]:
    """The agreement cells as two square matrices, ``rho`` and ``n``, in model order.

    The report stores cells; a heat map wants rows. A cell the merge could not compute
    (too few shared alleles, or no variance on one side) stays ``null`` — an absent
    correlation is not a zero one.
    """
    models = [str(name) for name in agreement.get("models") or []]
    index = {name: position for position, name in enumerate(models)}
    size = len(models)
    rho: list[list[float | None]] = [[None] * size for _ in range(size)]
    counts: list[list[int]] = [[0] * size for _ in range(size)]
    for cell in agreement.get("cells") or []:
        a, b = index.get(str(cell.get("a"))), index.get(str(cell.get("b")))
        if a is None or b is None:
            continue
        rho[a][b] = cell.get("rho")
        counts[a][b] = int(cell.get("n") or 0)
    return {"models": models, "rho": rho, "n": counts}


def _consensus(block: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "rank": block.get("rank"),
        "n": block.get("n_pairs"),
        "fused": block.get("fused_score"),
        "percentile": block.get("percentile"),
        "lanes": block.get("lanes") or [],
        "excluded_lanes": block.get("excluded_lanes") or [],
        "k": block.get("k"),
    }


def merge_payload(
    document: Mapping[str, Any], genes: Mapping[str, str] | None = None
) -> dict[str, Any]:
    """The merged report projected onto the API contract.

    ``disagreements`` is renamed from the merge step's ``high``/``low`` wording to the
    contract's ``top``/``bottom`` and gains the gene symbol, joined in by the caller from
    the record table — the merge step keys on ``allele_id`` and stores no symbol.
    """
    consensus = document.get("consensus") or {}
    return {
        "run_id": document.get("run_id"),
        "method": document.get("method"),
        "rrf_k": document.get("rrf_k"),
        "generated_at": document.get("generated_at"),
        "citation": document.get("citation"),
        "matrix": _matrix(document.get("agreement") or {}),
        "consensus": {
            "catalogue_free": _consensus(consensus.get("catalogue_free") or {}),
            "all_lanes": _consensus(consensus.get("all_lanes") or {}),
        },
        "disagreements": [
            {
                "allele_id": row.get("allele_id"),
                "gene": (genes or {}).get(str(row.get("allele_id"))),
                "top_model": row.get("high_model"),
                "top_pct": row.get("high_percentile"),
                "bottom_model": row.get("low_model"),
                "bottom_pct": row.get("low_percentile"),
            }
            for row in _disagreements(document)
        ],
        "lanes": document.get("lanes") or [],
        "lineage": document.get("lineage") or {},
    }


def _disagreements(document: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
    rows = document.get("disagreements") or []
    return [row for row in rows if isinstance(row, dict)]


def disagreement_alleles(document: Mapping[str, Any]) -> list[str]:
    """The ``allele_id``s the disagreement table names, for the gene join."""
    return [str(row["allele_id"]) for row in _disagreements(document) if row.get("allele_id")]
