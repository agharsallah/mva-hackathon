"""Iteration 2, step 1 as JSON: the target set the symptoms chose, and how far it reaches.

``/api/steps`` shows every step's goal, claims and figure names. This route shows step 1's
*numbers*, because the step's whole output is four measurements and a gene list, and a
figure filename is not a result.

**Why this route reads files and not the warehouse.** Step 1's tables (``it2_targets``,
``it2_decoys``) are gene rows, but the numbers this page needs — the recall curve with its
bootstrap intervals, the two-ranker overlap, the uncurated denominator — were produced by
the run itself and written beside it under ``build/it2/step-1/``. Those files *are* the
record: ``provenance.json`` carries the sha256 of every input and the HPO release, so the
route can state the lineage of each block rather than re-deriving a number a second way
and risking two answers to one question.

**Positions and gene names.** Nothing here carries a genomic coordinate — step 1 never
read the DNA. Gene *symbols* are also withheld: the blocks are counts, fractions and
curves. Step 1 ran blind against iteration 1, and a symbol list on this surface is exactly
what a reader could compare against the earlier candidate before step 6 makes that
comparison on purpose.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from .response import Envelope, live

SOURCE = "build/it2/step-1/*.json (summary, benchmark, benchmark-full, agreement, provenance)"

#: Where the step's run wrote its numbers. One folder, one run, one set of files.
STEP1_ROOT = Path("build/it2/step-1")

#: The N the target set is actually cut at. Marked on the recall curve because a recall
#: without the cutoff it belongs to is a decoration.
TARGET_N = 300

#: What each claim promised **before** the run, as entries 084 and 091 filed it. Constants,
#: not measurements: the observed side of every gate row below is read from the run's own
#: files, so a re-run moves the measurement and never the promise.
GATES: tuple[dict[str, Any], ...] = (
    {
        "claim": "H012",
        "question": "does the symptom-only ranker find the causal gene inside the cutoff?",
        "predicted": 0.90,
        "unit": f"held-out recall@{TARGET_N}",
        "metric": "recall_at_target",
    },
    {
        "claim": "H013",
        "question": "is a recessive chromosome-instability gene in the set at all?",
        "predicted": 1,
        "unit": "such genes present",
        "metric": "mechanism_term_genes",
    },
    {
        "claim": "H014",
        "question": "do two independent rankers agree on their top 300?",
        "predicted": 0.50,
        "unit": "share of the top 300 shared",
        "metric": "ranker_overlap",
    },
    {
        "claim": "H015",
        "question": "how much of the protein-coding genome can this ranker not see?",
        "predicted": 0.20,
        "unit": "fraction of protein-coding genes with no HPO curation",
        "metric": "uncurated_fraction",
        "lower_is_better": True,
    },
)


def _read(root: Path, name: str) -> dict[str, Any] | None:
    """One of the run's JSON files, or ``None`` when that run has not happened.

    A missing file is a true statement about the step — the full-population benchmark did
    not exist until entry 091 — so it is served as ``null`` rather than raised.
    """
    path = root / f"{name}.json"
    if not path.is_file():
        return None
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def _recall_at(benchmark: dict[str, Any] | None, n: int) -> dict[str, Any] | None:
    """The curve point at ``n``, interval included, or ``None``."""
    if not benchmark:
        return None
    for point in benchmark.get("curve", []):
        if int(point["n"]) == n:
            return point
    return None


def _overlap(agreement: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Each hosted ranker's shared / unique split of the window it actually filled.

    Reported over the window the service returned, not over 300: dividing a ranker's own
    truncation by a window it never filled prints truncation as disagreement.
    """
    rows = (agreement or {}).get("all", [])
    return [
        {
            "source": row["source"],
            "window": row["window"],
            "shared": row["shared"],
            "unique": int(row["window"]) - int(row["shared"]),
            "returned": row["returned"],
            "share": (int(row["shared"]) / int(row["window"])) if row["window"] else 0.0,
        }
        for row in rows
    ]


def _measurements(
    summary: dict[str, Any],
    benchmark: dict[str, Any] | None,
    full: dict[str, Any] | None,
    agreement: dict[str, Any] | None,
) -> dict[str, float | None]:
    """The observed value of every gate metric, each from exactly one file."""
    best = _recall_at(full or benchmark, TARGET_N)
    primary = _overlap(agreement)
    return {
        "recall_at_target": float(best["recall"]) if best else None,
        "mechanism_term_genes": float(summary.get("mechanism_term_genes_in_corpus", 0)),
        "ranker_overlap": primary[0]["share"] if primary else None,
        "uncurated_fraction": float(summary.get("uncurated_fraction", 0.0)),
    }


def _gates(measured: dict[str, float | None]) -> list[dict[str, Any]]:
    """One row per pre-registered promise: what was predicted, what was measured, verdict.

    The verdict is computed, never typed, so a re-run that moved a number moves the colour
    on the page with it.
    """
    rows = []
    for gate in GATES:
        observed = measured.get(str(gate["metric"]))
        predicted = float(gate["predicted"])
        lower_is_better = bool(gate.get("lower_is_better"))
        held = None
        if observed is not None:
            held = observed < predicted if lower_is_better else observed >= predicted
        rows.append({**gate, "observed": observed, "held": held})
    return rows


def payload(root: Path = STEP1_ROOT) -> dict[str, Any]:
    """Every block the ``/steps/step-1`` page draws, from the files the run wrote."""
    summary = _read(root, "summary") or {}
    benchmark = _read(root, "benchmark")
    full = _read(root, "benchmark-full")
    agreement = _read(root, "agreement")
    provenance = _read(root, "provenance") or {}
    measured = _measurements(summary, benchmark, full, agreement)

    clinical = provenance.get("clinical_input", {})
    term_sets = clinical.get("term_sets", {})

    return {
        "target_n": TARGET_N,
        "tiers": [
            {"tier": tier, "genes": count}
            for tier, count in sorted((summary.get("by_tier") or {}).items())
        ],
        "set_sizes": {
            "targets": summary.get("targets"),
            "decoys": summary.get("decoys"),
            "earned_by_score": summary.get("earned_by_score"),
            "by_mechanism_rule": (
                int(summary["targets"]) - int(summary["earned_by_score"])
                if summary.get("targets") is not None and summary.get("earned_by_score") is not None
                else None
            ),
        },
        "decoys": {
            "genes": summary.get("decoys"),
            "excluded_by_annotation": summary.get("decoy_exclusions"),
            "matched_on": ["coding length", "exon count"],
            "seed": (provenance.get("parameters") or {}).get("seed"),
        },
        "curation": {
            "uncurated": summary.get("uncurated_protein_coding"),
            "protein_coding": summary.get("protein_coding_total"),
            "fraction": summary.get("uncurated_fraction"),
            "genes_scored": summary.get("genes_scored"),
        },
        "mechanism_term_genes": summary.get("mechanism_term_genes_in_corpus"),
        # Two runs of the same benchmark: the 200-disease sample entry 084 tested H012
        # against, and the full eligible population entry 091 re-tested it on.
        "benchmark": benchmark,
        "benchmark_full": full,
        "overlap": _overlap(agreement),
        "agreement_retrieved_on": (agreement or {}).get("retrieved_on"),
        "gates": _gates(measured),
        "provenance": {
            "built_at": provenance.get("built_at"),
            "built_by": provenance.get("built_by"),
            "code_version": provenance.get("code_version"),
            "hpo_release": provenance.get("hpo_release"),
            "parameters": provenance.get("parameters"),
            "clinical_source": clinical.get("source"),
            "clinical_term_counts": {name: len(ids) for name, ids in term_sets.items()},
            "inputs": [
                {"name": row["name"], "sha256": row["sha256"], "role": row["role"]}
                for row in provenance.get("inputs", [])
            ],
            "genomic_data_read": provenance.get("genomic_data_read"),
        },
    }


def add_routes(api: APIRouter, root: Path = STEP1_ROOT) -> None:
    """Register the step-1 detail route on the warehouse router."""

    @api.get(
        "/steps/step-1",
        response_model=Envelope,
        tags=["science"],
        summary=f"iteration 2 step 1's measurements ({SOURCE})",
    )
    def it2_step_1() -> dict:
        """What the symptoms alone nominated, and the four things measured about it.

        Counts, fractions and curves. No genomic position — step 1 never read the DNA —
        and no gene symbol, because step 1 ran blind against iteration 1's candidate.
        """
        return live(payload(root), SOURCE)
