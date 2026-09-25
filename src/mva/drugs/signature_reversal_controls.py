"""Signature reversal, the checks: is the input what it claims, and can the query find biology?

Two checks that decide whether a reversal result may be read at all:

* :func:`consensus_check` — the consensus row against the plain mean of the perturbation's
  per-cell-line signatures (a quality check on the input, not a test).
* :func:`positive_controls` — the real signature against each genetic library, read as
  **mimickers** (knockouts / knockdowns whose expression change looks like the query's),
  aggregated per perturbed gene; the registered control passes when a named sibling gene
  lands in the top cut. The decoys run the same control, which gives its chance rate.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from .names import base_name
from .signature_reversal import Ranked, Signature, rank_by_label, sigcom_hits
from .signature_reversal_plan import (
    Clients,
    Libraries,
    ReversalPlan,
    per_signature_sources,
    stream_lines,
)
from .signature_reversal_tables import ControlResult, control_result
from .sources import sigcom

__all__ = ["consensus_check", "positive_controls", "sigcom_query"]


def consensus_check(
    plan: ReversalPlan,
    clients: Clients,
    libraries: Libraries,
    coefficients: Mapping[str, float],
    space: frozenset[str],
) -> dict[str, Any]:
    """Is the consensus row the mean of the perturbation's per-cell-line signatures?

    Pearson r over the gene space between the consensus and the plain mean of every
    per-signature file ``fetch`` downloaded. A quality check on the input, not a test.
    """
    sources = per_signature_sources(plan, clients, libraries)
    folder = plan.raw_dir / "per-signature"
    genes = sorted(g for g in space if g in coefficients)
    columns = []
    for source in sources:
        values: dict[str, float] = {}
        for line in list(stream_lines(folder / source.name))[1:]:
            gene, _, value = line.rstrip("\n").partition("\t")
            values[gene] = float(value)
        columns.append([values.get(g, np.nan) for g in genes])
    mean = np.nanmean(np.array(columns), axis=0)
    consensus = np.array([coefficients[g] for g in genes])
    r = float(np.corrcoef(mean, consensus)[0, 1])
    return {"per_signature_files": len(sources), "pearson_r_consensus_vs_mean": round(r, 4)}


def sigcom_query(
    plan: ReversalPlan,
    clients: Clients,
    uuids: Mapping[str, str],
    query: Signature,
    database: str,
) -> dict[str, Any]:
    return sigcom.rank_two_sided(
        clients.sigcom,
        [uuids[g] for g in query.up if g in uuids],
        [uuids[g] for g in query.down if g in uuids],
        database=database,
        limit=plan.sigcom_limit,
    )


def positive_controls(
    plan: ReversalPlan,
    clients: Clients,
    libraries: Libraries,
    uuids: Mapping[str, str],
    signature: Signature,
    decoys: Sequence[Signature],
) -> tuple[list[ControlResult], dict[str, Any]]:
    """The control per genetic library, plus how often a decoy would have passed it."""
    controls = []
    null: dict[str, Any] = {}
    for database in plan.control_databases:
        labels = libraries.sigcom_labels[database]
        genes = {base_name(v) for v in labels.values() if v} - {plan.perturbation}

        def ranked(
            query: Signature, db: str = database, lab: Mapping[str, str] = labels
        ) -> list[Ranked]:
            reply = sigcom_query(plan, clients, uuids, query, db)
            hits = sigcom_hits(reply, lab, direction="mimickers")
            return rank_by_label(hits, key=base_name, exclude=(plan.perturbation,))

        def result(
            ranking: Sequence[Ranked], db: str = database, n: int = len(genes)
        ) -> ControlResult:
            return control_result(db, ranking, plan.control_genes, universe=n, cut=plan.control_cut)

        real = result(ranked(signature))
        controls.append(real)
        decoy_results = [result(ranked(decoy)) for decoy in decoys]
        null[database] = {
            "decoys_passing": sum(1 for d in decoy_results if d.passed),
            "decoys": len(decoy_results),
            "decoy_best_ranks": [
                min((r for r in d.ranks.values() if r is not None), default=None)
                for d in decoy_results
            ],
            "real_ranks": dict(real.ranks),
            "universe_genes": len(genes),
        }
    return controls, null
