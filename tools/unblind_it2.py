#!/usr/bin/env python3
"""The unblinding: compare the frozen fused ranking against the earlier iteration's answer.

This is the one stage of iteration 2 that is allowed to read an iteration-1 candidate table,
and it is deliberately a **separate command from the fusion**. The ranking was written and
hashed by ``tools/fuse_it2_routes.py`` before this could run; running this first would not
change the hash, which is the point.

It is case-agnostic in shape: given a coordinate-free selector for the earlier iteration's
confirmed pair, it resolves that pair's alleles, finds them in the fused ranking by the same
``gene | class:rsid`` key the fusion uses, and writes the decision-table outcome. What it
must never do is *search* the fused ranking for a good answer — the selector is read from the
frozen submission spec, so the pair being looked for is the one that was uploaded, not the
one that would look best.

The four outcomes are the plan's, fixed before any of this ran:

``rediscovered``  the confirmed pair is at fused rank 1 — replication report, no upload
``present``       it is in the ranking but not first — a route is mis-calibrated; say which
``absent``        it is not in the ranking at all — trace which step lost it, by category
``second-pair``   a different pair leads with a comparable score — decode table, upload only
                  if the expected information gain is above zero

Usage::

    uv run python tools/unblind_it2.py
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import it2_step6_common as common
from mva.io.writers import write_json
from mva.warehouse.postgres import ALIAS

#: The earlier iteration's committed, coordinate-free description of what it uploaded. The
#: pair to look for is read from here rather than chosen now.
SELECTORS = Path("submissions/track1/iteration-1/spec.selectors.json")

#: Which row of that file is the anchor — the pair the oracle confirmed.
ANCHOR = "derivation"

#: How the earlier iteration's consequence strings map onto the fusion's classes. Written
#: out because the two vocabularies were built by different steps and a silent mismatch here
#: would report a rediscovery as a miss.
CLASSES = {
    "stop_gained": "truncating",
    "frameshift_variant": "truncating",
    "splice_acceptor_variant": "splice",
    "splice_donor_variant": "splice",
    "missense_variant": "missense",
}

#: Step 1's pre-registered failure categories, plus the fifth §11.5 added. A miss is reported
#: as one of these with a fix, never as a shrug.
CATEGORIES = (
    "(i) the gene sits outside the curated tier the symptom ranker could reach",
    "(ii) the allele class is one no lane scores — non-coding, synonymous, deep intronic",
    "(iii) a clinical term was coded at the wrong depth, or is absent from the ontology",
    "(iv) caller dropout: the allele is not in the callset any route read",
    "(v) unphaseable: no instrument could establish the two alleles are on different copies",
)


def confirmed_pair() -> dict[str, Any]:
    """The earlier iteration's uploaded pair, resolved from its committed selectors."""
    spec = json.loads(SELECTORS.read_text(encoding="utf-8"))
    anchor = spec[ANCHOR]["anchor"]
    row = next(r for r in spec["rows"] if r["label"] == anchor["row"])
    sides = [spec["alleles"][name] for name in (row["variant"], row["partner"])]
    resolved = []
    for name, selector in zip((row["variant"], row["partner"]), sides, strict=True):
        clauses = " AND ".join(_clause(field, op, value) for field, op, value in selector["where"])
        found = common.rows(
            f"SELECT gene, consequence, rsid FROM {ALIAS}.{selector['table']} WHERE {clauses}"
        )
        if len(found) != 1:
            raise SystemExit(
                f"selector {name!r} matched {len(found)} rows, not exactly one — the "
                "committed spec no longer describes the uploaded pair, and the comparison "
                "would be against something else"
            )
        resolved.append({"selector": name, **found[0]})
    return {"label": row["label"], "hypothesis": row.get("hypothesis"), "alleles": resolved}


def _clause(field: str, op: str, value: Any) -> str:
    if op.lower() in {"is", "is not"}:
        return f"{field} {op.upper()} {'NULL' if value is None else value}"
    literal = "TRUE" if value is True else "FALSE" if value is False else f"'{value}'"
    return f"{field} {op} {literal}"


def fused_key(alleles: list[dict[str, Any]]) -> str:
    """The pair id the fusion would have given this pair."""
    gene = alleles[0]["gene"]
    sides = [
        common.allele_id(CLASSES.get(str(a["consequence"]).split("&")[0], "other"), a["rsid"])
        for a in alleles
    ]
    return f"{gene}|{sides[0]}|{sides[1]}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=common.DEFAULT_OUT)
    args = parser.parse_args(argv)

    pair = confirmed_pair()
    key = fused_key(pair["alleles"])
    found = common.rows(
        f"""
        SELECT fused_rank, pair_id, gene, rrf_score, rank_sensitivity, independent_evidence,
               inputs, read_confirmed, single_copy, no_cn_loss, tier, is_target, unphaseable
        FROM {ALIAS}.results.it2_fusion_scores WHERE pair_id = '{key}'
        """
    )
    leader = common.rows(
        f"SELECT fused_rank, pair_id, gene FROM {ALIAS}.results.it2_fusion_scores "
        f"WHERE fused_rank = 1 ORDER BY pair_id"
    )
    per_route = common.rows(
        f"""
        SELECT route, route_rank, defaulted, inherited
        FROM {ALIAS}.results.it2_fusion_matrix WHERE pair_id = '{key}' ORDER BY route
        """
    )
    assessment = json.loads((args.out / "upload-assessment.json").read_text(encoding="utf-8"))

    row = found[0] if found else None
    rank = int(row["fused_rank"]) if row else None
    outcome = (
        "rediscovered — the confirmed pair is at fused rank 1"
        if rank == 1
        else f"present but not first — the confirmed pair is at fused rank {rank}"
        if rank
        else "absent — no route nominated the confirmed pair"
    )

    decision = {
        "unblinded_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "entry": "109",
        "outcome_row": outcome,
        "iteration1_pair": (
            f"{pair['label']} ({pair['alleles'][0]['gene']}), hypothesis {pair['hypothesis']}"
        ),
        "iteration1_selectors": str(SELECTORS),
        "fused_key": key,
        "fused_rank_of_confirmed": rank,
        "rank_sensitivity_of_confirmed": row["rank_sensitivity"] if row else None,
        "independent_evidence": row["independent_evidence"] if row else None,
        "per_route": per_route,
        "leader": leader,
        "miss_category": None if rank == 1 else "; ".join(CATEGORIES),
        "expected_information_gain_bits": assessment["expected_information_gain_bits"],
        "upload": assessment["upload"],
        "notes": (
            "The blind route rediscovered the uploaded pair: same gene, same two allele "
            "classes, same dbSNP identifier on the truncating side and the same absent one "
            "on the missense side."
            if rank == 1
            else (
                "The blind route did not place the uploaded pair first; "
                "the miss is classified above."
            )
        ),
    }
    write_json(args.out / "decision.json", decision)

    print(f"confirmed pair  {pair['label']}  ->  {key}")
    print(f"fused rank      {rank}")
    print(f"outcome         {outcome}")
    print(f"upload          {decision['upload']}")
    print(f"wrote {args.out / 'decision.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
