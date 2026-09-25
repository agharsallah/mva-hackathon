"""Signature reversal, the order of the run: signature first, then every query, then tables.

The order is the pre-registration made mechanical: :func:`execute` writes the signature
file (and prints its sha256) **before** it issues a single drug query, and the manifest
records that file's digest, so a reader can check the query was not tuned after seeing
drugs.

Queries, in order: the real signature on the drug library of both engines; the decoys on
SigCom's drug library; the real signature and the decoys on each genetic library (the
positive control, and its chance rate). Every reply is cached by the shared fetcher.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

from . import provenance
from .screen_replication_report import write_provenance
from .signature_reversal import (
    Ranked,
    Signature,
    decoy_signatures,
    ilincs_reverser_hits,
    pick_signature,
    rank_by_label,
    read_consensus_row,
    sigcom_hits,
    top_keys,
)
from .signature_reversal_approval import (
    approve,
    canonical,
    chembl_phase4_index,
    looks_like_code,
    openfda_labels,
)
from .signature_reversal_controls import consensus_check, positive_controls, sigcom_query
from .signature_reversal_plan import (
    Clients,
    ReversalPlan,
    landmark_genes,
    load_libraries,
    stream_lines,
)
from .signature_reversal_tables import (
    COMPOUND_COLUMNS,
    GENERATOR_COLUMNS,
    JOIN_RULE,
    compound_rows,
    engine_overlap,
    generator_rows,
    join_key,
    verdict_inputs,
    write_tsv,
)
from .sources import ilincs, sigcom

__all__ = ["execute"]


def execute(plan: ReversalPlan) -> int:
    clients = Clients.open(plan)
    try:
        return _execute(plan, clients)
    finally:
        clients.close()


def _execute(plan: ReversalPlan, clients: Clients) -> int:
    plan.build_dir.mkdir(parents=True, exist_ok=True)
    space = landmark_genes(plan.raw_dir / plan.gene_info.name, plan.gene_space)
    coefficients = read_consensus_row(
        stream_lines(plan.raw_dir / plan.consensus.name), plan.perturbation
    )
    signature = pick_signature(
        coefficients,
        space=space,
        size=plan.size,
        exclude=(plan.perturbation,),
        name=f"{plan.perturbation} CRISPR-knockout consensus",
        source=plan.consensus.url,
    )
    libraries = load_libraries(plan, clients)
    check = consensus_check(plan, clients, libraries, coefficients, space)
    signature_path = _write_json(
        plan.build_dir / "signature.json",
        {"signature": asdict(signature), "gene_space_size": len(space), "check": check},
    )
    signature_sha = provenance.digest(signature_path)[0]
    print(f"signature fixed: {signature_path} sha256 {signature_sha}")

    decoys = decoy_signatures(
        space,
        n_up=plan.size,
        n_down=plan.size,
        count=plan.decoys,
        seed=plan.seed,
        exclude=(plan.perturbation,),
    )
    uuids = sigcom.entity_ids(clients.sigcom, space)
    chembl_index = chembl_phase4_index(clients.chembl)

    def key(label: str) -> str:
        return canonical(label, chembl_index)

    drug_labels = libraries.sigcom_labels[plan.drug_database]
    drug_contexts = libraries.sigcom_contexts[plan.drug_database]

    def sigcom_reversers(query: Signature) -> list[Ranked]:
        reply = sigcom_query(plan, clients, uuids, query, plan.drug_database)
        hits = sigcom_hits(reply, drug_labels, direction="reversers", contexts=drug_contexts)
        return rank_by_label(hits, key=key)

    real_sigcom = sigcom_reversers(signature)
    il_reply = ilincs.concordance(clients.ilincs, signature.up, signature.down)
    real_ilincs = rank_by_label(ilincs_reverser_hits(il_reply["rows"]), key=key)
    decoy_rankings = [sigcom_reversers(decoy) for decoy in decoys]
    _require_depth(plan, real_sigcom, real_ilincs, decoy_rankings)

    controls, control_null = positive_controls(plan, clients, libraries, uuids, signature, decoys)

    sigcom_universe = {key(label) for label in drug_labels.values() if label}
    ilincs_universe = {key(label) for label in libraries.ilincs_labels.values() if label}
    both = sigcom_universe & ilincs_universe
    to_ask = sorted(k for k in both if k not in chembl_index and not looks_like_code(k))
    fda, fda_failed = openfda_labels(clients.openfda, to_ask)
    seen = both | {r.key for r in real_sigcom} | {r.key for r in real_ilincs}
    approvals = approve(seen, chembl_index, fda)
    decoy_tops = [top_keys(ranking, plan.top_n) for ranking in decoy_rankings]
    rows = compound_rows(
        real_sigcom,
        real_ilincs,
        sigcom_universe=sigcom_universe,
        ilincs_universe=ilincs_universe,
        approvals=approvals,
        decoy_tops=decoy_tops,
        top_n=plan.top_n,
        decoy_max_hits=plan.decoy_max_hits,
    )
    verdict = verdict_inputs(rows, controls, decoy_max_hits=plan.decoy_max_hits)
    universe = sorted(k for k in both if approvals[k].approved)
    counts = {
        "landmark_genes": len(space),
        "signature_genes_with_sigcom_entity": sum(1 for g in signature.genes() if g in uuids),
        "ilincs_genes_used": il_reply["genes_used"],
        "ilincs_rows_p_below_0_05": len(il_reply["rows"]),
        "sigcom_compounds_ranked": len(real_sigcom),
        "ilincs_compounds_ranked": len(real_ilincs),
        "sigcom_compound_universe": len(sigcom_universe),
        "ilincs_compound_universe": len(ilincs_universe),
        "compounds_in_both": len(both),
        "openfda_names_asked": len(to_ask),
        "openfda_labelled": len(fda),
        "openfda_failed": len(fda_failed),
        "chembl_phase4_names": len(chembl_index),
        "approved_in_both": len(universe),
        **libraries.counts,
    }
    summary = {
        "verdict_inputs": verdict,
        "counts": counts,
        "control_null": control_null,
        "engine_overlap_top": engine_overlap(
            [top_keys(real_sigcom, plan.top_n), *decoy_tops],
            top_keys(real_ilincs, plan.top_n),
            both,
        ),
        "signature_sha256": signature_sha,
        "openfda_failed_names": fda_failed,
    }
    _write_json(plan.build_dir / "summary.json", summary)
    _write_json(
        plan.build_dir / "rankings.json",
        {
            "sigcom": [asdict(r) for r in real_sigcom[: 10 * plan.top_n]],
            "ilincs": [asdict(r) for r in real_ilincs[: 10 * plan.top_n]],
            "decoy_tops": [sorted(top) for top in decoy_tops],
        },
    )
    _write_outputs(plan, clients, rows, universe, approvals, summary, signature_path)
    print(json.dumps(summary["verdict_inputs"], indent=1))
    return 0


def _require_depth(
    plan: ReversalPlan,
    real_sigcom: Sequence[Ranked],
    real_ilincs: Sequence[Ranked],
    decoys: Sequence[Sequence[Ranked]],
) -> None:
    """Top ``n`` compounds are exact only if the retrieved depth reaches ``n`` compounds."""
    short = [len(r) for r in (real_sigcom, *decoys) if len(r) < plan.top_n]
    if short:
        raise ValueError(f"SigCom depth {plan.sigcom_limit} gave < {plan.top_n} compounds")
    if len(real_ilincs) < plan.top_n:
        print(f"note: iLINCS ranked only {len(real_ilincs)} compounds at p < 0.05")


def _write_outputs(
    plan: ReversalPlan,
    clients: Clients,
    rows: Sequence[Mapping[str, Any]],
    universe: Sequence[str],
    approvals: Mapping[str, Any],
    summary: Mapping[str, Any],
    signature_path: Path,
) -> None:
    write_tsv(plan.out, rows, COMPOUND_COLUMNS)
    generator = generator_rows(rows, entry=plan.entry)
    gen_path = write_tsv(plan.generator_dir / "lincs.tsv", generator, GENERATOR_COLUMNS)
    folded = sorted({join_key(k) for k in universe})
    uni_rows = [{"drug": k, "approved": True} for k in folded]
    uni_path = write_tsv(plan.generator_dir / "lincs.universe.tsv", uni_rows, ("drug", "approved"))
    inputs = _inputs(plan, clients, signature_path)
    common: dict[str, Any] = {
        "built_by": "tools/signature_reversal.py",
        "entry": plan.entry,
        "inputs": inputs,
        "parameters": {**plan.parameters(), "counts": summary["counts"]},
        "test": _test_text(plan),
        "software": {"numpy": np.__version__},
        "patient_data": plan.patient_data,
    }
    write_provenance(plan.out, name="lincs_reversal", rows=len(rows), **common)
    manifest = provenance.envelope("lincs", "tools/signature_reversal.py")
    manifest.update({k: v for k, v in common.items() if k != "built_by"})
    manifest["list_rule"] = (
        f"approved drugs (ChEMBL max_phase 4 or an openFDA label) in the top {plan.top_n} "
        "compound reversers of both SigCom LINCS l1000_cp and iLINCS LIB_5"
    )
    manifest["universe_rule"] = "every approved compound present in both engines' libraries"
    manifest["join_key_rule"] = JOIN_RULE + (
        "; applied to ChEMBL's folded preferred name where ChEMBL knows the library label"
    )
    manifest["verdict_inputs"] = summary["verdict_inputs"]
    if summary["verdict_inputs"]["status"] == "uninterpretable":
        manifest["caution"] = (
            "the registered positive control failed, so H092 is uninterpretable: this list is "
            "the step-10 rule applied to the run, not a supported result"
        )
    manifest["outputs"] = [
        provenance.output(gen_path, len(generator)),
        provenance.output(uni_path, len(uni_rows)),
    ]
    provenance.write(manifest, plan.generator_dir / "lincs.provenance.json")


def _inputs(plan: ReversalPlan, clients: Clients, signature_path: Path) -> list[dict[str, Any]]:
    files = []
    for source in (plan.consensus, plan.gene_info):
        sha, size = provenance.digest(plan.raw_dir / source.name)
        files.append(
            {
                "name": source.name,
                "role": source.role,
                "url": source.url,
                "sha256": sha,
                "bytes": size,
                "licence": source.licence,
                "release": source.release,
            }
        )
    sha, size = provenance.digest(signature_path)
    files.append(
        {
            "name": "signature.json",
            "role": "the fixed query, written before any drug query",
            "url": None,
            "sha256": sha,
            "bytes": size,
            "licence": "this repository",
            "release": None,
        }
    )
    apis: list[tuple[str, str, Any]] = [
        ("SigCom LINCS", sigcom.DATA, clients.sigcom),
        ("iLINCS", ilincs.BASE, clients.ilincs),
        ("ChEMBL", "https://www.ebi.ac.uk/chembl/api/data", clients.chembl),
        ("openFDA drug label", "https://api.fda.gov/drug/label.json", clients.openfda),
    ]
    return files + [
        provenance.api_input(name, url, role="connectivity / approval", fetcher=fetcher)
        for name, url, fetcher in apis
    ]


def _test_text(plan: ReversalPlan) -> str:
    return (
        f"{plan.claim}. Signature: top {plan.size} raised and lowered {plan.gene_space} genes "
        f"of the {plan.perturbation} consensus, {plan.perturbation} itself excluded. Compound "
        f"rank = rank of its best reverser signature (SigCom z-sum; iLINCS concordance). "
        f"Decoys: {plan.decoys} random {plan.size}+{plan.size} draws from the same space, seed "
        f"{plan.seed}, through SigCom {plan.drug_database}. Positive control: "
        f"{', '.join(plan.control_genes)} gene-level mimicker rank in "
        f"{', '.join(plan.control_databases)}, pass at <= {plan.control_cut:.0%} of genes."
    )


def _write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1, default=str) + "\n", encoding="utf-8")
    return path
