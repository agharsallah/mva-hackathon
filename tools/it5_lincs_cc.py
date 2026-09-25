#!/usr/bin/env python3
"""Iteration 5, route R2 (b): does a cell-cycle-corrected BUB1B-loss signature pass?

Entry 153's BUB1B-knockout signature read as generic arrest, and its positive control (the
signature should resemble loss of other checkpoint genes) failed. This driver removes the
shared cell-cycle component from every LINCS CRISPR-knockout consensus signature, re-runs the
control on the corrected matrix, and runs reversal only if the control passes.

    uv run python tools/it5_lincs_cc.py control    # corrected control (+ uncorrected baseline)
    uv run python tools/it5_lincs_cc.py reversal   # refuses unless the primary control passed

**Analysis choices, fixed 2026-09-25 before any corrected similarity was computed.**

**Analysis choices** (each line: choice - fixed value - why):

* matrix - LINCS 2021 ``xpr_mean_coeff_mat.tsv.gz`` (entry 153's file, same sha256),
  7,234 knockout consensus rows - the same input entry 153 used.
* gene space - the 978 landmark genes (``geneinfo_beta``), BUB1B's own column excluded -
  as entry 153; landmark genes are measured, not inferred.
* scores - S and G2/M = mean coefficient over the Tirosh 2016 lists (over all 12,327
  columns), BUB1B and the five named control genes removed - a control gene must not help
  define the correction that is then credited with finding it.
* primary correction - per landmark column, OLS on [1, S, G2/M] across all knockouts,
  residuals kept - Seurat-style cell-cycle regression, transposed.
* sensitivities (reported, do not gate) - none (raw, column-centred) and top-k principal
  components removed, k in {1, 3, 10} - the uncorrected baseline and a data-driven variant.
* similarity - Pearson r of corrected rows over the corrected landmark space - a whole
  signature comparison, no top-100 gene cut.
* named siblings - BUB1, BUB3, MAD1L1, MAD2L1, TTK (entry 153's list); those with a
  consensus row are used, a missing one never counts as a pass.
* **control pass** - (i) any sibling in the top 5 % of the other knockouts **and**
  (ii) the siblings' mean percentile beats 10,000 random same-size draws at p < 0.05
  (seed 20260925) - (i) is entry 153's rule, (ii) calibrates it.
* descriptive siblings - AURKB, CENPE, ZWINT, PLK1, MAD2L1BP - context, never a gate.
* reversal (only if the primary control passes) - ``cp_mean_coeff_mat.tsv.gz``, same
  landmark space, compounds corrected by their own S/G2/M regression; a reverser is the
  most negative r - query and library corrected the same way.
* specificity - 20 decoy knockout queries (random rows, seed 20260925) through the same
  pipeline; a compound in >= 2 decoys' top 100 is not specific - entry 153's rule.
* candidate rubric - ``lincs_strength`` below; branch ``any``, because a loss-of-function
  signature does not know which of the child's two alleles it stands for.

Sources: the genomic source at one remove (the knockout gene is the child's BUB1B); no
patient value, sequence or position is read. HPO cross-reference is in the entry.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

from mva.drugs import provenance
from mva.drugs.cache import Fetcher
from mva.drugs.proteome_sets import TIROSH_G2M, TIROSH_S, members
from mva.drugs.proteome_tables import CANDIDATE_COLUMNS, write_tsv
from mva.drugs.signature_cc import (
    Consensus,
    cc_residuals,
    pc_residuals,
    read_consensus,
    row_scores,
    sibling_control,
    similarity,
)
from mva.drugs.signature_cc_reversal import decoy_counts, rank_reversers, top_labels
from mva.drugs.signature_reversal_approval import approve, canonical, chembl_phase4_index

XPR = Path("build/it4/track2-e3/raw/xpr_mean_coeff_mat.tsv.gz")
GENEINFO = Path("build/it4/track2-e3/raw/geneinfo_beta.txt")
CP = Path("build/it5/r2/raw/cp_mean_coeff_mat.tsv.gz")
BUILD = Path("build/it5/r2")
OUT = Path("ressources/track2/it5")
ENTRY = "docs/iteration5/step-1/work/r2-entry.md"
URLS = {
    XPR: "https://lincs-dcic.s3.amazonaws.com/LINCS-sigs-2021/means/xpr_mean_coeff_mat.tsv.gz",
    GENEINFO: "https://s3.amazonaws.com/macchiato.clue.io/builds/LINCS2020/geneinfo_beta.txt",
    CP: "https://lincs-dcic.s3.amazonaws.com/LINCS-sigs-2021/means/cp_mean_coeff_mat.tsv.gz",
}
TARGET = "BUB1B"
SIBLINGS = ("BUB1", "BUB3", "MAD1L1", "MAD2L1", "TTK")
CONTEXT = ("AURKB", "CENPE", "ZWINT", "PLK1", "MAD2L1BP")
EVIDENCE_KIND = "LINCS: reverses cell-cycle-corrected BUB1B-knockout signature"
GENOMIC_SOURCE = "the knockout gene only (BUB1B, entry 083); no patient value or position"
FRAMING = "research exercise; no row advises for or against giving any drug to any patient"
LIMITS = (
    "LINCS consensus rows are cancer-cell-line knockouts; regression on two scores removes "
    "only what they capture; similarity is correlation over 977 landmark genes"
)
CUT, DRAWS, SEED, TOP_N, DECOYS = 0.05, 10_000, 20260925, 100, 20
PCS = (1, 3, 10)


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _landmarks() -> list[str]:
    lines = GENEINFO.read_text().splitlines()
    head = lines[0].split("\t")
    sym, space = head.index("gene_symbol"), head.index("feature_space")
    return sorted({f[sym] for f in (ln.split("\t") for ln in lines[1:]) if f[space] == "landmark"})


def _load(path: Path) -> tuple[Consensus, list[str], list[str], list[str]]:
    land = _landmarks()
    exclude = {TARGET, *SIBLINGS}
    wanted = set(land) | set(TIROSH_S) | set(TIROSH_G2M) | {"MLF1IP", "FAM64A", "HN1"}
    cons = read_consensus(path, wanted, progress=lambda n: _log(f"  {path.name}: {n} rows"))
    have = set(cons.columns)
    s = list(members(TIROSH_S, have, exclude))
    g = list(members(TIROSH_G2M, have, exclude))
    space = [x for x in land if x in have and x != TARGET]
    return cons, space, s, g


def _variants(
    cons: Consensus, space: list[str], s: list[str], g: list[str]
) -> dict[str, np.ndarray]:
    y = cons.col(space).astype(float)
    cc, _ = cc_residuals(y, [row_scores(cons, s), row_scores(cons, g)])
    out = {"cc_primary": cc, "raw": pc_residuals(y, 0)}
    out.update({f"pc{k}": pc_residuals(y, k) for k in PCS})
    return out


def control() -> dict[str, Any]:
    cons, space, s, g = _load(XPR)
    at = cons.row_index()[TARGET]
    rows: list[dict[str, Any]] = []
    results: dict[str, Any] = {}
    for name, mat in _variants(cons, space, s, g).items():
        sims = similarity(mat, mat[at])
        res = sibling_control(cons.rows, sims, TARGET, SIBLINGS, cut=CUT, draws=DRAWS, seed=SEED)
        ctx = sibling_control(cons.rows, sims, TARGET, CONTEXT, cut=CUT, draws=DRAWS, seed=SEED)
        results[name] = {
            "passed": res.passed,
            "any_in_cut": res.any_in_cut,
            "mean_percentile": res.mean_percentile,
            "permutation_p": res.permutation_p,
            "context_percentiles": ctx.percentiles,
        }
        for gene in SIBLINGS + CONTEXT:
            src = res if gene in SIBLINGS else ctx
            rows.append(
                {
                    "variant": name,
                    "gates": name == "cc_primary",
                    "gene": gene,
                    "role": "named sibling" if gene in SIBLINGS else "context",
                    "has_consensus_row": gene in src.ranks,
                    "rank": src.ranks.get(gene, ""),
                    "percentile": src.percentiles.get(gene, ""),
                    "universe": src.universe,
                    "any_in_top5pct": src.any_in_cut,
                    "mean_percentile": src.mean_percentile,
                    "permutation_p": src.permutation_p,
                    "control_passed": res.passed if gene in SIBLINGS else "",
                }
            )
    summary = {
        "target": TARGET,
        "knockouts": len(cons.rows),
        "landmark_space": len(space),
        "s_members": len(s),
        "g2m_members": len(g),
        "variants": results,
        "primary_passed": results["cc_primary"]["passed"],
    }
    BUILD.mkdir(parents=True, exist_ok=True)
    (BUILD / "lincs_cc_summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    path = OUT / "lincs_cc_control.tsv"
    n = write_tsv(path, rows, list(rows[0]))
    _manifest(path, n, "control", [XPR, GENEINFO], summary)
    print(json.dumps(summary, indent=1))
    return summary


def lincs_strength(rank: int, decoys: int, in_pc3: bool) -> tuple[float, list[str]]:
    """0.30 top-100 reverser; +0.20 specific (≤ 1 decoy); +0.15 top 25; +0.20 also top 100
    with 3 PCs removed. Rows exist only when the corrected control passed."""
    score, why = 0.30, ["top-100 corrected reverser"]
    if decoys <= 1:
        score, why = score + 0.20, [*why, "specific"]
    if rank <= 25:
        score, why = score + 0.15, [*why, "top 25"]
    if in_pc3:
        score, why = score + 0.20, [*why, "survives PC3 variant"]
    return round(score, 2), why


def reversal() -> None:
    summary = json.loads((BUILD / "lincs_cc_summary.json").read_text())
    if not summary["primary_passed"]:
        write_tsv(BUILD / "lincs_rows.tsv", [], CANDIDATE_COLUMNS)
        print("primary control failed: reversal not run (by declaration); no LINCS candidate rows")
        return
    ko, space, s, g = _load(XPR)
    cc_ko = _variants(ko, space, s, g)
    cp, cp_space, cs, cg = _load(CP)
    if cp_space != space:
        raise SystemExit("compound and knockout landmark spaces differ")
    y = cp.col(space).astype(float)
    cp_cc, _ = cc_residuals(y, [row_scores(cp, cs), row_scores(cp, cg)])
    cp_pc3 = pc_residuals(y, 3)
    at = ko.row_index()[TARGET]
    ranked = rank_reversers(cp.rows, cp_cc, cc_ko["cc_primary"][at])
    pc3_top = top_labels(rank_reversers(cp.rows, cp_pc3, cc_ko["pc3"][at]), TOP_N)
    rng = np.random.default_rng(SEED)
    pool = [i for i, r in enumerate(ko.rows) if r not in {TARGET, *SIBLINGS}]
    decoy_rows = rng.choice(pool, size=DECOYS, replace=False)
    counts = decoy_counts(cp.rows, cp_cc, [cc_ko["cc_primary"][i] for i in decoy_rows], TOP_N)
    index = chembl_phase4_index(Fetcher(source="chembl"))
    approvals = approve({canonical(r.label, index) for r in ranked[:TOP_N]}, index, {})
    rows, cands = [], []
    for r in ranked[:TOP_N]:
        key = canonical(r.label, index)
        a = approvals[key]
        row = {
            "label": r.label,
            "canonical_name": key,
            "approved": a.approved,
            "chembl": a.evidence,
            "r": round(r.r, 4),
            "rank": r.rank,
            "decoys_top100": counts[r.label],
            "in_pc3_top100": r.label in pc3_top,
        }
        rows.append(row)
        if a.approved:
            strength, why = lincs_strength(r.rank, counts[r.label], r.label in pc3_top)
            cands.append(
                {
                    "drug_name": key,
                    "route": "R2",
                    "branch": "any",
                    "evidence_kind": EVIDENCE_KIND,
                    "evidence_strength": strength,
                    "positive_control_passed": True,
                    "source": f"LINCS 2021 cp consensus; {a.evidence}",
                    "notes": f"r {row['r']}, rank {r.rank}, decoys {counts[r.label]}; "
                    + ", ".join(why),
                }
            )
    path = OUT / "lincs_cc_reversal.tsv"
    n = write_tsv(path, rows, list(rows[0]))
    write_tsv(BUILD / "lincs_rows.tsv", cands, CANDIDATE_COLUMNS)
    _manifest(
        path,
        n,
        "reversal",
        [XPR, GENEINFO, CP],
        {"compounds": len(cp.rows), "decoy_rows": [ko.rows[i] for i in decoy_rows]},
    )
    print(f"wrote {path} ({n} rows, {len(cands)} approved)")


def _manifest(path: Path, n: int, what: str, files: list[Path], validation: dict[str, Any]) -> None:
    m = provenance.envelope(path.stem, built_by=f"tools/it5_lincs_cc.py {what}")
    m.update(
        {
            "entry": ENTRY,
            "tool": f"tools/it5_lincs_cc.py {what}",
            "inputs": [
                {
                    "file": p.as_posix(),
                    "url": URLS[p],
                    "sha256": provenance.digest(p)[0],
                    "bytes": provenance.digest(p)[1],
                }
                for p in files
            ],
            "parameters": {
                "target": TARGET,
                "siblings": SIBLINGS,
                "cut": CUT,
                "draws": DRAWS,
                "seed": SEED,
                "top_n": TOP_N,
                "decoys": DECOYS,
                "pcs": PCS,
                "scores": "Tirosh 2016 S and G2/M, target + siblings removed",
            },
            "sources": {
                "genomic": GENOMIC_SOURCE,
                "clinical": "not used by this table; cross-referenced in the entry",
            },
            "limitations": LIMITS,
            "validation": validation,
            "rows": n,
            "outputs": [provenance.output(path, n)],
            "clinical_framing": FRAMING,
        }
    )
    provenance.write(m, path.with_suffix(".provenance.json"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("command", choices=["control", "reversal"])
    args = parser.parse_args()
    control() if args.command == "control" else reversal()


if __name__ == "__main__":
    main()
