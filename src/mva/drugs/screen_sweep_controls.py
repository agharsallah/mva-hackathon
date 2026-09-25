"""The controls a screen-wide sweep is read against — none of them is part of the claim.

* **Negative band** — entry 151's band, re-drawn from the sweep's own eligible set: 200
  seeded compounds whose MOA names nothing tied to either contrast, through the same test.
  A one-sided 0.05 test should fire on about 5 % of them.
* **Calibration** — the whole family's raw-p rate and the p a drug needs at rank 1.
* **Positive-control sweep** — the same sweep, the same BH, over a lineage with a textbook
  dependency (RAF/MEK inhibitors in skin/melanoma lines). If screen-wide BH cannot find
  that, a null on the real contrast means nothing.
* **Confounders** — the in-group's generic fragility, its overlap with the other contrast,
  and *which* in-group lines the compounds were actually measured on.
* **Retrospective rows** — drugs named in advance only so their place can be reported.

No patient data; the identifiers are drug names, BRD ids and cell-line names.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

from mva.drugs.screen_replication import Group
from mva.drugs.screen_replication_prism import ResponseMatrix, lineage_group, normalise_name
from mva.drugs.screen_replication_report import confounder_summary, negative_control_band
from mva.drugs.screen_sweep import Eligibility, FamilyRow, eligible_items, family, sweep_contrast
from mva.drugs.screen_sweep_prism import prism_join_key
from mva.drugs.screen_sweep_report import calibration

__all__ = ["drug_keys", "in_group_line_sets", "positive_control_sweep", "sweep_controls"]


def drug_keys(items: Sequence[str], info: Mapping[str, Mapping[str, Any]]) -> dict[str, str]:
    """``{item: drug key}``: the PRISM join key, unified over copies sharing a core BRD id."""
    by_core: dict[str, str] = {}
    return {
        item: by_core.setdefault(info[item]["broad_core"], prism_join_key(info[item]["name"]))
        for item in sorted(items)
    }


def _rank(row: FamilyRow) -> int:
    return row.rank if row.rank is not None else 1 << 30


def positive_control_sweep(
    screen: ResponseMatrix,
    models: pl.DataFrame,
    candidates: Sequence[str],
    info: Mapping[str, Mapping[str, Any]],
    *,
    lineage: str,
    drugs: Sequence[str],
    alpha: float,
    seed: int,
    out: Path,
) -> dict[str, Any]:
    """Lineage vs rest over every candidate with >= 3 lines each side; BH over the family."""
    codes = tuple(
        models.filter(pl.col("OncotreeLineage") == lineage)["OncotreeCode"]
        .drop_nulls()
        .unique()
        .sort()
        .to_list()
    )
    group = lineage_group(
        models,
        codes=codes,
        screened=screen.lines,
        name="positive-control",
        in_label=lineage,
        out_label="rest",
    )
    items = eligible_items(screen, candidates, [Eligibility(group, 3, 3)])
    names = {i: info[i]["name"] for i in items}
    results = sweep_contrast(screen, group, items, names, seed=seed, resamples=0, workers=1)
    fam = family(screen, group, results, drug_keys(items, info))
    reps = sorted((r for r in fam if r.representative and r.rank is not None), key=_rank)
    pl.DataFrame(
        [
            {
                "rank": r.rank,
                "drug": r.drug,
                "item_id": r.result.item_id,
                "n_in": r.result.n_in,
                "n_out": r.result.n_out,
                "delta": r.result.delta,
                "p": r.result.p_raw,
                "q": r.result.p_adjusted,
                "moa": info[r.result.item_id]["moa"],
            }
            for r in reps
        ]
    ).write_csv(out, separator="\t")
    wanted = {normalise_name(d) for d in drugs}
    return {
        "group": group.definition,
        "calibration": calibration(fam, alpha=alpha),
        "rows": [
            {"drug": r.drug, **asdict(r.result), "rank": r.rank, "percentile": r.percentile}
            for r in reps
            if normalise_name(r.drug) in wanted
        ],
        "top10": [
            {
                "drug": r.drug,
                "delta": r.result.delta,
                "p": r.result.p_raw,
                "q": r.result.p_adjusted,
                "moa": info[r.result.item_id]["moa"],
            }
            for r in reps[:10]
        ],
        "table": out.as_posix(),
    }


def in_group_line_sets(
    screen: ResponseMatrix, group: Group, items: Sequence[str], label: Mapping[str, str]
) -> list[dict[str, Any]]:
    """Which in-group lines each compound was measured on, counted by distinct set."""
    cols = [j for j, line in enumerate(screen.lines) if line in group.inside]
    rows = {item: i for i, item in enumerate(screen.item_ids)}
    sets: Counter[tuple[str, ...]] = Counter()
    for item in items:
        values = screen.matrix[rows[item], cols]
        sets[
            tuple(screen.lines[c] for c, v in zip(cols, values, strict=True) if np.isfinite(v))
        ] += 1
    return [{"lines": [label.get(x, x) for x in key], "copies": n} for key, n in sets.most_common()]


def sweep_controls(
    screen: ResponseMatrix,
    groups: Mapping[str, Group],
    fams: Mapping[str, Sequence[FamilyRow]],
    items: Sequence[str],
    info: Mapping[str, Mapping[str, Any]],
    annotation: Mapping[str, float],
    *,
    lineage_tag: str,
    annotation_name: str,
    exclude_words: Sequence[str],
    band_size: int,
    report_drugs: Sequence[str],
    alpha: float,
    seed: int,
) -> dict[str, Any]:
    """Negative band, calibration, confounders and the retrospective rows, as one dict."""
    clean = [
        i for i in items if not any(w in (info[i]["moa"] or "").upper() for w in exclude_words)
    ]
    band = negative_control_band(
        screen,
        dict(groups),
        universe=clean,
        exclude=[],
        names={i: info[i]["name"] for i in items},
        size=band_size,
        seed=seed,
        definition=(
            "seeded sample of eligible Launched compounds whose MOA mentions none of "
            f"{list(exclude_words)}"
        ),
    )
    wanted = {normalise_name(d) for d in report_drugs}
    retro = [
        {
            "tag": tag,
            "drug": r.drug,
            **asdict(r.result),
            "rank": r.rank,
            "percentile": r.percentile,
            "representative": r.representative,
            "family_size": sum(1 for x in rows if x.representative),
        }
        for tag, rows in fams.items()
        for r in rows
        if normalise_name(r.drug) in wanted
    ]
    return {
        "negative_control": band,
        "calibration": {t: calibration(rows, alpha=alpha) for t, rows in fams.items()},
        "confounders": confounder_summary(
            screen, groups[lineage_tag], annotation, annotation_name=annotation_name
        ),
        "retrospective": retro,
    }
