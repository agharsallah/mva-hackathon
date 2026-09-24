"""Turning contrast results into the artifacts a report and a reviewer can read.

:mod:`mva.drugs.screen_replication` answers "is this drug selective for this group of
lines?". This module answers the three questions a reviewer asks next, and it is the part
worth reusing verbatim on another case because none of it mentions a drug or a disease:

* **Rows** — one flat record per drug x contrast, with the group definition, the effect
  size, both p values and an explicit ``status`` for the drugs that were never screened.
  A candidate missing from the screen is a finding, so it gets a row, not a silent drop.
* **Controls** — a seeded negative-control band (does the pipeline find selectivity
  everywhere?), a positive control on a dependency nobody disputes (can it find one at
  all?), and a confounder summary (is the in-group simply easier to kill?).
* **Provenance** — the manifest that names every input with its digest, the parameters,
  the test and the software versions, in the shape
  :mod:`mva.drugs.provenance` fixes for every table this package writes.

Nothing here reads patient data, and nothing it writes can carry a genomic position: its
identifiers are drug names, screen compound ids and cell-line ids.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from mva.drugs import provenance
from mva.drugs.screen_replication import (
    Group,
    ItemResult,
    contrast_item,
    negative_control_sample,
    run_contrast,
    with_adjusted,
)

__all__ = [
    "CandidateMeta",
    "Screen",
    "confounder_summary",
    "negative_control_band",
    "positive_control",
    "representative",
    "rows_from_results",
    "run_group",
    "write_provenance",
]


class Screen(Protocol):
    """The slice of a response matrix this module needs; see ``ResponseMatrix``.

    Declared structurally so nothing here has to import the PRISM reader: any object with
    these five read-only attributes and three methods is a screen.
    """

    @property
    def item_ids(self) -> list[str]: ...

    @property
    def lines(self) -> list[str]: ...

    @property
    def matrix(self) -> np.ndarray: ...

    @property
    def metric(self) -> str: ...

    @property
    def release(self) -> str: ...

    def __getitem__(self, key: str) -> Mapping[str, float]: ...

    def subset(self, item_ids: Sequence[str]) -> Mapping[str, Mapping[str, float]]: ...

    def line_medians(self) -> dict[str, float]: ...


#: ``{screen item id: (direction id, where the candidate came from, candidate key)}``.
CandidateMeta = Mapping[str, tuple[str, str, str]]


def representative(screen: Screen, item_ids: Sequence[str], group: Group) -> str | None:
    """The item id measured on most of the in-group lines; ties broken by sort order.

    A drug can appear several times in one screen (different compound batches). Reporting
    every copy is honest but correcting for multiplicity over copies would inflate the
    family, so exactly one copy per candidate carries the adjusted p.
    """
    best: str | None = None
    best_n = -1
    for item_id in sorted(item_ids):
        row = screen.matrix[screen.item_ids.index(item_id)]
        measured = sum(
            1
            for line, value in zip(screen.lines, row, strict=True)
            if line in group.inside and np.isfinite(value)
        )
        if measured > best_n:
            best, best_n = item_id, measured
    return best


def rows_from_results(
    results: Sequence[ItemResult],
    *,
    role: str,
    metric: str,
    release: str,
    group: Group,
    meta: CandidateMeta,
    representatives: set[str],
) -> list[dict[str, Any]]:
    """Flatten results into the derived table's records."""
    out: list[dict[str, Any]] = []
    for r in results:
        direction, source, key = meta.get(r.item_id, ("", "", r.item_name))
        out.append(
            {
                "candidate": key,
                "direction_id": direction,
                "candidate_source": source,
                "prism_item_id": r.item_id,
                "prism_name": r.item_name,
                "contrast": r.contrast,
                "contrast_role": role,
                "release": release,
                "metric": metric,
                "group_definition": group.definition,
                "in_group": group.in_label,
                "out_group": group.out_label,
                "n_in": r.n_in,
                "n_out": r.n_out,
                "median_in": r.median_in,
                "median_out": r.median_out,
                "cliffs_delta": r.delta,
                "ci_low": r.ci_low,
                "ci_high": r.ci_high,
                "p_raw": r.p_raw,
                "p_adjusted": r.p_adjusted,
                "representative": r.item_id in representatives,
                "status": r.status,
                "direction_of_effect": (
                    ""
                    if r.delta is None
                    else ("in-group more sensitive" if r.delta > 0 else "in-group less sensitive")
                ),
            }
        )
    return out


def run_group(
    screen: Screen,
    group: Group,
    matches: Mapping[str, Sequence[str]],
    meta: CandidateMeta,
    *,
    role: str,
    family: bool,
    seed: int,
    resamples: int,
) -> list[dict[str, Any]]:
    """One contrast over every matched candidate item, BH-adjusted inside the family.

    ``family=True`` means this contrast is one of the pre-registered primary ones and its
    representative rows form a Benjamini-Hochberg family; sensitivity contrasts carry raw
    p only, because correcting a robustness check against the main result would be double
    counting.
    """
    reps = {
        rep for ids in matches.values() if (rep := representative(screen, ids, group)) is not None
    }
    item_ids = sorted({i for ids in matches.values() for i in ids})
    results = [
        contrast_item(
            item_id,
            meta.get(item_id, ("", "", item_id))[2],
            screen[item_id],
            group,
            resamples=resamples,
            seed=seed + i,
        )
        for i, item_id in enumerate(item_ids)
    ]
    if family:
        adjusted = {
            r.item_id: r.p_adjusted
            for r in with_adjusted([r for r in results if r.item_id in reps])
        }
        results = [
            replace(r, p_adjusted=adjusted[r.item_id]) if r.item_id in adjusted else r
            for r in results
        ]
    return rows_from_results(
        results,
        role=role,
        metric=screen.metric,
        release=screen.release,
        group=group,
        meta=meta,
        representatives=reps,
    )


def negative_control_band(
    screen: Screen,
    groups: Mapping[str, Group],
    *,
    universe: Sequence[str],
    exclude: Sequence[str],
    names: Mapping[str, str],
    size: int,
    seed: int,
    definition: str,
) -> dict[str, Any]:
    """How often the same test calls an unrelated drug selective — the calibration band.

    A one-sided test at 0.05 should fire on about 5 % of drugs with no tie to the contrast.
    Far more means the *contrast*, not the drug, is producing the signal.
    """
    picked = negative_control_sample(universe, exclude=exclude, size=size, seed=seed)
    report: dict[str, Any] = {
        "definition": definition,
        "universe": len(universe),
        "sampled": len(picked),
        "seed": seed,
        "correction": "none; raw one-sided p, outside the candidate family",
    }
    for name, group in groups.items():
        results = run_contrast(screen.subset(picked), group, names=names, resamples=0, seed=seed)
        p = [r.p_raw for r in results if r.p_raw is not None]
        d = [r.delta for r in results if r.delta is not None]
        report[name] = {
            "n": len(p),
            "fraction_p_below_0.05": float(np.mean([x < 0.05 for x in p])) if p else None,
            "fraction_p_below_0.20": float(np.mean([x < 0.20 for x in p])) if p else None,
            "median_delta": float(np.median(d)) if d else None,
            "delta_2.5pct": float(np.percentile(d, 2.5)) if d else None,
            "delta_97.5pct": float(np.percentile(d, 97.5)) if d else None,
        }
    return report


def positive_control(
    screen: Screen,
    group: Group,
    items: Mapping[str, Sequence[str]],
    *,
    definition: str,
    seed: int,
    resamples: int = 1000,
) -> dict[str, Any]:
    """The same code path on a dependency nobody disputes. If this misses, nothing else counts."""
    return {
        "definition": definition,
        "group": group.definition,
        "results": [
            asdict(contrast_item(item, drug, screen[item], group, resamples=resamples, seed=seed))
            for drug, ids in items.items()
            for item in ids
        ],
    }


def confounder_summary(
    screen: Screen,
    group: Group,
    annotation: Mapping[str, float],
    *,
    annotation_name: str,
) -> dict[str, Any]:
    """Is the in-group simply easier to kill, and does it overlap the other contrast's group?

    Two numbers a lineage result needs next to it: the in-group's median response over
    *every* compound (a generically fragile line looks selective for everything), and the
    in-group's median value of the second contrast's annotation (if the two groups are the
    same lines, they are not two independent tests).
    """
    medians = screen.line_medians()

    def take(lines: frozenset[str], source: Mapping[str, float]) -> list[float]:
        return [source[k] for k in sorted(lines) if k in source and np.isfinite(source[k])]

    inside, outside = take(group.inside, medians), take(group.outside, medians)
    in_ann, out_ann = take(group.inside, annotation), take(group.outside, annotation)
    return {
        "generic_sensitivity": {
            "what": "each line's median response over every screened compound",
            "in_group_median_of_medians": float(np.median(inside)) if inside else None,
            "out_group_median_of_medians": float(np.median(outside)) if outside else None,
            "n_in": len(inside),
            "n_out": len(outside),
            "reading": (
                "if the in-group's value is markedly lower, part of any apparent selectivity "
                "is general fragility; the rank-normalised contrast is the check that removes it"
            ),
        },
        f"{annotation_name}_overlap": {
            "in_group_median": float(np.median(in_ann)) if in_ann else None,
            "out_group_median": float(np.median(out_ann)) if out_ann else None,
            "n_in_with_value": len(in_ann),
            "reading": (
                "if the two contrasts share their lines they are not independent tests; this "
                "is the number to read before treating them as two sources"
            ),
        },
        "small_n": (
            f"{len(group.inside)} lines in the in-group. A one-sided Mann-Whitney with "
            f"n_in={len(group.inside)} has a floor of about "
            f"{1 / max(len(group.inside), 1):.3g} on any effect it can resolve, and a "
            "bootstrap CI on Cliff's delta will be wide."
        ),
    }


def write_provenance(
    out: Path,
    *,
    name: str,
    built_by: str,
    entry: str,
    inputs: Sequence[dict[str, Any]],
    parameters: Mapping[str, Any],
    test: str,
    software: Mapping[str, str],
    rows: int,
    patient_data: str,
) -> Path:
    """The manifest for one derived table, in this repository's fixed shape."""
    manifest = provenance.envelope(name, built_by)
    manifest.update(
        {
            "entry": entry,
            "inputs": list(inputs),
            "parameters": dict(parameters),
            "test": test,
            "software": dict(software),
            "patient_data": patient_data,
            "outputs": [provenance.output(out, rows)],
        }
    )
    return provenance.write(manifest, out.with_suffix(".provenance.json"))
