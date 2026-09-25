"""The whole replication, declared once as a configuration and executed.

:mod:`~mva.drugs.screen_replication` is the statistics, ``_prism`` the readers and
``_report`` the artifacts. This module is the **plan**: which drugs, which contrasts, which
controls, in which order, written down as a :class:`ReplicationPlan` so that running the
same analysis on another lineage, another annotation or another screen is a different
configuration rather than a different script.

Everything case-specific — the candidate list, the Oncotree codes, the positive control —
arrives as a field of the plan. Nothing in here names a gene, a disease or a patient, and
no output it writes can carry a genomic position.

The order is fixed and matters:

1. read the screen and the line annotations,
2. build the groups (the contrast definitions are frozen before any p value is computed),
3. the two **primary** contrasts, Benjamini-Hochberg over the candidates inside each,
4. the **sensitivity** contrasts (other group definition, line-level offset removed, other
   release and metric) — raw p only, because correcting a robustness check against the
   result it checks would be double counting,
5. the drugs the screen never tested, one row each,
6. the background sweep over every compound, for the "where do the candidates sit?" figure,
7. the controls: negative band, positive control, literature direction, confounders,
8. the provenance manifest.
"""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

from mva.drugs import provenance
from mva.drugs.screen_replication_prism import (
    CompoundIndex,
    ResponseMatrix,
    normalise_name,
)

__all__ = [
    "ReplicationPlan",
    "SourceFile",
    "candidates",
    "fetch_files",
    "fetch_sources",
    "match_drug",
]


@dataclass(frozen=True)
class SourceFile:
    """One public download: where it comes from, what release it is, how it is licensed."""

    role: str
    name: str
    url: str
    release: str
    licence: str = "CC BY 4.0"


@dataclass(frozen=True)
class ReplicationPlan:
    """Every choice the run makes, in one object, so the manifest can record all of them."""

    sources: tuple[SourceFile, ...]
    raw_dir: Path
    build_dir: Path
    out: Path
    entry: str
    candidate_tables: tuple[Path, ...]
    """Repository tables the candidate list is derived from (recorded as inputs)."""
    shortlist: Path
    shortlist_verdict: str
    in_group_codes: tuple[str, ...]
    in_group_label: str
    in_group_lineage: str
    """The Oncotree lineage used for the lineage-matched sensitivity contrast."""
    annotation_column: str
    extra_drugs: tuple[str, ...]
    extra_drug_direction: str
    extra_drug_source: str
    class_moa: tuple[tuple[str, str], ...]
    literature_moa: tuple[str, ...]
    literature_note: str
    positive_control_drugs: tuple[str, ...]
    positive_control_lineage: str
    positive_control_note: str
    control_exclude: tuple[str, ...]
    seed: int = 0
    resamples: int = 2000
    negative_control_size: int = 200
    source_note: str = ""
    patient_data: str = "none; public data only"
    software: dict[str, str] = field(default_factory=dict)

    def path(self, role: str) -> Path:
        """The local path of the source file registered under ``role``."""
        return self.raw_dir / next(s.name for s in self.sources if s.role == role)


def fetch_sources(plan: ReplicationPlan) -> int:
    """Download any missing source file and write one provenance manifest beside each.

    Re-running is cheap and idempotent: an existing file is only re-digested, and the
    original ``fetched_at`` is preserved while ``verified_at`` moves.
    """
    return fetch_files(plan.sources, plan.raw_dir, source_note=plan.source_note)


def fetch_files(sources: Sequence[SourceFile], raw_dir: Path, *, source_note: str = "") -> int:
    """:func:`fetch_sources` for any list of files, so another plan can reuse the fetcher."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    for source in sources:
        path = raw_dir / source.name
        stamp = datetime.now(UTC).isoformat(timespec="seconds")
        if not path.exists() or path.stat().st_size == 0:
            print(f"fetching {source.name} ...")
            with urllib.request.urlopen(source.url) as reply, path.open("wb") as out:
                while chunk := reply.read(1 << 20):
                    out.write(chunk)
        manifest = path.with_suffix(path.suffix + ".provenance.json")
        previous = json.loads(manifest.read_text()) if manifest.exists() else {}
        sha, size = provenance.digest(path)
        manifest.write_text(
            json.dumps(
                {
                    "name": source.name,
                    "role": source.role,
                    "url": source.url,
                    "fetched_at": previous.get("fetched_at", stamp),
                    "verified_at": stamp,
                    "bytes": size,
                    "sha256": sha,
                    "licence": source.licence,
                    "release": source.release,
                    "source_note": source_note,
                },
                indent=2,
            )
            + "\n"
        )
        print(f"  {source.name}: {size:,} bytes  sha256 {sha[:16]}...")
    return 0


def candidates(plan: ReplicationPlan, index: CompoundIndex) -> list[tuple[str, str, str]]:
    """``(normalised name, direction id, where it came from)`` for every drug to be tested.

    Derived, never typed: the argued rows come out of the shortlist, the drug *class* out
    of the screen's own MOA annotation, the extras out of the table the caller names.
    """
    rows = pl.read_csv(plan.shortlist, separator="\t", infer_schema_length=10000)
    argued = (
        rows.filter(pl.col("verdict").str.starts_with(plan.shortlist_verdict))
        .select("drug_name", "direction_id")
        .unique()
        .sort("drug_name")
    )
    spec: dict[str, tuple[str, str]] = {}
    for name, direction in argued.rows():
        spec.setdefault(
            normalise_name(str(name)),
            (str(direction), f"{plan.shortlist.name} verdict={plan.shortlist_verdict}"),
        )
    for moa, direction in plan.class_moa:
        for name in sorted(set(index.by_moa(moa)["name"].to_list())):
            spec.setdefault(normalise_name(name), (direction, f"screen MOA '{moa}' class"))
    for name in plan.extra_drugs:
        spec.setdefault(normalise_name(name), (plan.extra_drug_direction, plan.extra_drug_source))
    return [(key, direction, source) for key, (direction, source) in sorted(spec.items())]


def match_drug(index: CompoundIndex, screen: ResponseMatrix, key: str) -> list[str]:
    """One normalised drug name to screen item ids, matched by name **and** by BRD id."""
    hits = index.table.filter(pl.col("name_key") == key)
    ids = set(hits["item_id"].to_list())
    cores = {c for c in hits["broad_core"].to_list() if c}
    if cores:
        ids |= set(index.table.filter(pl.col("broad_core").is_in(list(cores)))["item_id"].to_list())
    return sorted(ids & set(screen.item_ids))


def meta_by_item(
    spec: Sequence[tuple[str, str, str]], matches: dict[str, list[str]]
) -> dict[str, tuple[str, str, str]]:
    return {
        item: (direction, source, key) for key, direction, source in spec for item in matches[key]
    }


def absent_rows(
    spec: Sequence[tuple[str, str, str]],
    matches: dict[str, list[str]],
    screen: ResponseMatrix,
    contrast: str,
) -> list[dict[str, Any]]:
    """A candidate the screen never tested is a result, so it gets a row of its own."""
    blank: dict[str, Any] = {
        "prism_item_id": "",
        "prism_name": "",
        "contrast": contrast,
        "contrast_role": "primary",
        "release": screen.release,
        "metric": screen.metric,
        "group_definition": "",
        "in_group": "",
        "out_group": "",
        "n_in": 0,
        "n_out": 0,
        "median_in": None,
        "median_out": None,
        "cliffs_delta": None,
        "ci_low": None,
        "ci_high": None,
        "p_raw": None,
        "p_adjusted": None,
        "representative": False,
        "status": "absent",
        "direction_of_effect": "",
    }
    return [
        {"candidate": key, "direction_id": direction, "candidate_source": source, **blank}
        for key, direction, source in spec
        if not matches[key]
    ]


def coverage_table(
    plan: ReplicationPlan,
    spec: Sequence[tuple[str, str, str]],
    primary: ResponseMatrix,
    matches: dict[str, list[str]],
    sec_matches: dict[str, list[str]],
    inside: frozenset[str],
) -> pl.DataFrame:
    cols = [primary.lines.index(line) for line in sorted(inside)]
    return pl.DataFrame(
        [
            {
                "candidate": key,
                "direction_id": direction,
                "source": source,
                "in_primary": bool(matches[key]),
                "primary_items": len(matches[key]),
                "in_secondary": bool(sec_matches[key]),
                "secondary_items": len(sec_matches[key]),
                "in_group_lines_measured": max(
                    (
                        int(np.isfinite(primary.matrix[primary.item_ids.index(i)][cols]).sum())
                        for i in matches[key]
                    ),
                    default=0,
                ),
            }
            for key, direction, source in spec
        ]
    )
