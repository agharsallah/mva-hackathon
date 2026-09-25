#!/usr/bin/env python3
"""Iteration 5, route R2 (a): which compounds raise BUB1B *protein* beyond proliferation?

Direction D3 ("raise stable BubR1") is about protein amount. BUB1B protein, like its mRNA,
follows the cell cycle, so a drug that piles cells up in mitosis raises it and one that
stops division lowers it. This driver asks which perturbations raise BUB1B **after**
regressing out a declared proliferation score, in public drug-perturbation proteomes, and
only after a textbook protein induction passes in the same data.

    uv run python tools/it5_proteome.py run          # controls → BUB1B → tables
    uv run python tools/it5_proteome.py candidates   # merge R2 candidate rows (after it5_lincs_cc)

**Analysis choices, fixed 2026-09-25 before BUB1B was ranked in any dataset.** (While
checking that the files quantify BUB1B at all, BUB1B's values under the first six Mitchell
columns were printed once; no ranking, score or correction had been computed.)

**Analysis choices** (each line: choice - fixed value - why):

* primary dataset - Mitchell 2023 Supp. Data 3: HCT116, 875 compounds, 10 uM (28 at 1 uM),
  24 h, log2 FC vs DMSO - the largest public compound x proteome matrix quantifying BUB1B.
* replication - ProTargetMiner deep sets (Saei 2019 Supp. Data 4-6): A549, MCF-7, RKO;
  9 drugs x 3 replicates, ratios to log2, replicates averaged - independent lab, 3 lines.
* unavailable - decryptE (Eckert 2024, MassIVE MSV000093659): the repository's FTP did not
  answer from this machine - stated, not substituted.
* proliferation score - median log2 FC over the Tirosh 2016 G2/M set (54 genes), BUB1B
  removed, >= 10 members - a published, drug-free definition of the mitotic program.
* sensitivity score - the same minus the checkpoint/kinetochore module
  (``proteome_sets.SAC_MODULE``) - a compound lifting that whole module is not corrected away.
* model - OLS across perturbations, target = a + b*score + residual; robust z =
  residual / (1.4826 * MAD) - the Seurat "regress out the cell-cycle score" idea.
* hit - robust z >= 3 **and** raw log2 FC > 0 (Mitchell); z >= 2 and rank 1 of 9 (deep
  sets) - the protein must actually rise; 9 drugs cannot carry a z of 3 honestly.
* breadth - share of all proteins that are hits under the same compound, > 5 % = broad -
  an "everything up" proteome is not a specific lead.
* **gating control, Mitchell** - HSPA1A (HSP70) under both HSP90 inhibitors (NVP-BEP800,
  radicicol), each a hit in the top 2 % of 875 - HSP90 block to HSF1 to HSP70 is textbook.
* gating control, deep sets - HSPA1A under bortezomib and MDM2 under nutlin, rank 1 of 9
  and z >= 2 - proteasome block to HSP70; MDM2 block to p53 to MDM2.
* secondary controls (reported, do not gate) - CDT1 under MLN4924 (a stabilisation, not a
  transcriptional induction); MDM2 and CDKN1A under nutlin-3a and idasanutlin.
* approval - ChEMBL max_phase 4 (bulk index) or an openFDA label for non-code names - the
  challenge's two evidences.
* candidate rubric - ``proteome_tables.protein_strength``, stated before the run.
* branch - ``missense_unstable``: more of the same unstable missense protein; the
  stop_gained allele makes none for a compound to stabilise.

Sources: the genomic source only at one remove (the target gene comes from the child's
BUB1B alleles, entry 083); no patient value, sequence or position is read. The clinical
HPO terms are cross-referenced in the entry, not used here.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

from mva.drugs import provenance
from mva.drugs.cache import Fetcher
from mva.drugs.proteome_baseline import baseline
from mva.drugs.proteome_manifest import file_input, write_manifests
from mva.drugs.proteome_run import ControlSpec, DatasetResult, ProteomePlan, run_dataset
from mva.drugs.proteome_sets import TIROSH_G2M
from mva.drugs.proteome_sources import (
    compound_of,
    drug_means,
    read_ratio_workbook,
    read_wide_log2fc,
)
from mva.drugs.proteome_tables import (
    CANDIDATE_COLUMNS,
    control_rows,
    hit_rows,
    protein_strength,
    write_tsv,
)
from mva.drugs.signature_reversal_approval import (
    approve,
    canonical,
    chembl_phase4_index,
    looks_like_code,
    openfda_labels,
)

RAW = Path("build/it5/r2/raw")
BUILD = Path("build/it5/r2")
OUT = Path("ressources/track2/it5")
#: The gene whose protein this route ranks. A second case changes this flag and nothing else:
#: the datasets, the proliferation score and the gating controls are dataset properties.
#: Which allele branch a "more protein" lead can help, in the plan's branch vocabulary.
DEFAULT_BRANCH = "missense_unstable"
ENTRY = (
    "docs/iteration5/step-1/methodology/"
    "159-which-drugs-raise-bubr1-protein-once-proliferation-is-removed.md"
)
#: The gene whose protein this route ranks by default.
TARGET = "BUB1B"
CONTRACT = "iteration-5 route contract (docs/iteration5/plan.md)"
FRAMING = "research exercise; no row advises for or against giving any drug to any patient"
GENOMIC_SOURCE = (
    "the target gene only (BUB1B, from the child's two alleles, entry 083); "
    "no patient value or position"
)
LIMITS = (
    "cancer cell lines, one dose and one time point (Mitchell), 9 drugs (deep sets); "
    "protein level, not BubR1 function or stability; a regression on one score removes "
    "only what that score captures"
)
PLAN = ProteomePlan(
    target=TARGET, score_set=TIROSH_G2M, z_min=3.0, top_fraction=0.02, broad_share=0.05
)
MITCHELL = RAW / "mitchell/MOESM3.csv"
PTM = {
    "A549": RAW / "ptm/MOESM7.xlsx",
    "MCF-7": RAW / "ptm/MOESM8.xlsx",
    "RKO": RAW / "ptm/MOESM9.xlsx",
}
CCLE = RAW / "ccle/protein_quant_current_normalized.csv.gz"
HALF_LIFE = RAW / "halflife/MOESM5.xlsx"
URLS = {
    MITCHELL: "https://static-content.springer.com/esm/art%3A10.1038%2Fs41587-022-01539-0/MediaObjects/41587_2022_1539_MOESM3_ESM.csv",
    PTM[
        "A549"
    ]: "https://static-content.springer.com/esm/art%3A10.1038%2Fs41467-019-13582-8/MediaObjects/41467_2019_13582_MOESM7_ESM.xlsx",
    PTM[
        "MCF-7"
    ]: "https://static-content.springer.com/esm/art%3A10.1038%2Fs41467-019-13582-8/MediaObjects/41467_2019_13582_MOESM8_ESM.xlsx",
    PTM[
        "RKO"
    ]: "https://static-content.springer.com/esm/art%3A10.1038%2Fs41467-019-13582-8/MediaObjects/41467_2019_13582_MOESM9_ESM.xlsx",
    CCLE: "https://gygi.hms.harvard.edu/data/ccle/protein_quant_current_normalized.csv.gz",
    HALF_LIFE: "https://static-content.springer.com/esm/art%3A10.1038%2Fs41467-018-03106-1/MediaObjects/41467_2018_3106_MOESM5_ESM.xlsx",
}
MITCHELL_ROLE = "Mitchell 2023 Nat Biotechnol 41:845 (PMID 36593396) Supp. Data 3, log2 FC vs DMSO"
PTM_ROLE = "Saei 2019 Nat Commun 10:5715 (PMID 31844049) deep set {line}, fold change vs control"
HIT_COLUMNS = {
    "robust_z": "proliferation-corrected response / robust spread",
    "hit": "z ≥ cut and raw log2 FC > 0",
    "breadth": "share of all proteins that are hits under the same perturbation",
    "sensitivity_z": "z with the SAC/kinetochore module removed from the score",
}
CONTROL_COLUMNS = {
    "control_passed": "every inducer a hit inside the top cut",
    "gates": "true = the dataset is uninterpretable if this control fails",
}
HSP90I = ("NVP-BEP800_HSP90AA1;HSP90B1", "Radicicol_HSP90AA1")
NUTLINS = ("Nutlin3a_MDM2", "Idasanutlin_MDM2")
MITCHELL_CONTROLS = (
    ControlSpec("HSPA1A", HSP90I, True, "HSP90 inhibition → HSF1 → HSP70 (textbook)"),
    ControlSpec(
        "CDT1", ("MLN4924_NAE1",), False, "neddylation block stabilises CRL4 substrate CDT1"
    ),
    ControlSpec("MDM2", NUTLINS, False, "MDM2 inhibition → p53 → MDM2 transcription"),
    ControlSpec("CDKN1A", NUTLINS, False, "MDM2 inhibition → p53 → p21"),
)
PTM_CONTROLS = (
    ControlSpec("HSPA1A", ("Bortezomib",), True, "proteasome inhibition → HSF1 → HSP70"),
    ControlSpec("MDM2", ("Nutlin",), True, "MDM2 inhibition → p53 → MDM2 transcription"),
)


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _approval() -> tuple[Any, Fetcher, Fetcher]:
    chembl_fetch = Fetcher(source="chembl")
    fda_fetch = Fetcher(source="openfda")
    index = chembl_phase4_index(chembl_fetch)
    return index, chembl_fetch, fda_fetch


def run(args: argparse.Namespace) -> None:
    target, branch = args.target, args.branch
    build, out_dir = Path(args.build), Path(args.out)
    plan = replace(PLAN, target=target)
    index, chembl_fetch, fda_fetch = _approval()
    results: list[tuple[DatasetResult, Any]] = []
    mitchell = read_wide_log2fc(MITCHELL)
    _log(f"mitchell: {len(mitchell.genes)} proteins x {len(mitchell.perturbations)}")
    res = run_dataset(
        "mitchell2023", "HCT116, 10 µM, 24 h", mitchell, plan, MITCHELL_CONTROLS, progress=_log
    )
    results.append((res, compound_of))
    for line, path in PTM.items():
        deep = drug_means(read_ratio_workbook(path))
        r = run_dataset(
            f"protargetminer_{line}",
            f"{line}, 9 drugs, replicate mean",
            deep,
            plan,
            PTM_CONTROLS,
            z_min=2.0,
            top_fraction=1 / 9,
            progress=_log,
        )
        results.append((r, lambda label: label))

    names = {c for res, of in results for c in map(of, res.sensitivity)}
    keys = {canonical(n, index) for n in names}
    ask = sorted(k for k in keys if k not in index and not looks_like_code(k))
    fda, failed = openfda_labels(fda_fetch, ask)
    approvals = approve(keys, index, fda)

    def canon(name: str) -> tuple[str, bool, str]:
        key = canonical(name, index)
        a = approvals[key]
        return key, a.approved, a.evidence

    hits: list[dict[str, Any]] = []
    controls: list[dict[str, Any]] = []
    for res, of in results:
        hits += hit_rows(res, of, canon, broad_share=plan.broad_share)
        controls += control_rows(res)
    summary: dict[str, Any] = {
        "target": target,
        "datasets": {
            res.name: {
                "context": res.context,
                "interpretable": res.interpretable,
                "fit": res.fit,
                "controls": {s.protein: o.passed for s, o in res.controls},
                "hits": sum(1 for r in res.responses if r.hit),
            }
            for res, _ in results
        },
        "approval": {
            "chembl_phase4_names": len(index),
            "openfda_asked": len(ask),
            "openfda_labelled": len(fda),
            "openfda_failed": failed,
        },
        "baseline": baseline(target, ccle_path=CCLE, half_life_path=HALF_LIFE),
    }
    build.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    (build / "proteome_summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    hit_cols = list(hits[0])
    ctrl_cols = list(controls[0])
    n_hits = write_tsv(out_dir / "proteome_hits.tsv", hits, hit_cols)
    n_ctrl = write_tsv(out_dir / "proteome_control.tsv", controls, ctrl_cols)
    write_manifests(
        out=out_dir,
        entry=ENTRY,
        inputs=[
            file_input(MITCHELL, MITCHELL_ROLE, URLS),
            *(file_input(p, PTM_ROLE.format(line=k), URLS) for k, p in PTM.items()),
            file_input(CCLE, "Nusinow 2020 Cell 180:387 CCLE protein (baseline only)", URLS),
            file_input(HALF_LIFE, "Mathieson 2018 Nat Commun 9:689 half-lives (baseline)", URLS),
            provenance.api_input(
                "ChEMBL",
                "https://www.ebi.ac.uk/chembl/api/data",
                role="max_phase 4 index",
                fetcher=chembl_fetch,
            ),
            provenance.api_input(
                "openFDA",
                "https://api.fda.gov/drug/label.json",
                role="label for non-ChEMBL names",
                fetcher=fda_fetch,
            ),
        ],
        parameters={
            "target": target,
            "score_set": "Tirosh 2016 G2/M (54)",
            "z_min": plan.z_min,
            "top_fraction": plan.top_fraction,
            "broad_share": plan.broad_share,
            "deep_sets": "z_min 2, rank 1 of 9",
        },
        sources={
            "genomic": args.genomic_source or GENOMIC_SOURCE,
            "clinical": "not used by this table; the entry cross-references the 8 HPO terms",
        },
        framing=FRAMING,
        limits=LIMITS,
        tables=[
            ("proteome_hits", n_hits, HIT_COLUMNS),
            ("proteome_control", n_ctrl, CONTROL_COLUMNS),
        ],
        validation={k: v["controls"] for k, v in summary["datasets"].items()},
    )
    _protein_rows(hits, target=target, branch=branch, build=build)
    print(json.dumps(summary, indent=1))


def _protein_rows(hits: list[dict[str, Any]], *, target: str, branch: str, build: Path) -> None:
    """Approved hits → candidate rows (build/, merged by ``candidates``)."""
    hit_studies: dict[str, set[str]] = {}
    for h in hits:
        if h["hit"]:
            hit_studies.setdefault(h["canonical_name"], set()).add(h["dataset"].split("_")[0])
    rows = []
    for h in hits:
        if not (h["hit"] and h["approved"]):
            continue
        replicated = len(hit_studies.get(h["canonical_name"], set())) > 1
        z_cut = 3.0 if h["dataset"].startswith("mitchell") else 2.0
        strength, why = protein_strength(h, replicated=replicated, z_min=z_cut)
        rows.append(
            {
                "drug_name": h["canonical_name"],
                "route": "R2",
                "branch": branch,
                "evidence_kind": (f"proteome: {target} protein raised beyond proliferation score"),
                "evidence_strength": strength,
                "positive_control_passed": h["dataset_interpretable"],
                "source": f"{h['dataset']} ({h['context']}); {h['chembl_id']}",
                "notes": (
                    f"z {h['robust_z']}, rank {h['rank']}, log2FC {h['raw_log2fc']}, "
                    f"breadth {h['breadth']}; " + ", ".join(why)
                ),
            }
        )
    write_tsv(build / "protein_rows.tsv", rows, CANDIDATE_COLUMNS)
    _log(f"protein candidate rows: {len(rows)}")


def candidates(args: argparse.Namespace) -> None:
    """Merge the protein rows and the LINCS rows into the route's candidate file."""
    build, out_dir = Path(args.build), Path(args.out)
    rows: list[dict[str, Any]] = []
    parts = [build / "protein_rows.tsv", build / "lincs_rows.tsv"]
    for part in parts:
        if part.exists():
            lines = part.read_text().splitlines()
            head = lines[0].split("\t")
            rows += [dict(zip(head, line.split("\t"), strict=True)) for line in lines[1:]]
    rows.sort(key=lambda r: (-float(r["evidence_strength"] or 0), r["drug_name"]))
    path = out_dir / "protein_candidates.tsv"
    n = write_tsv(path, rows, CANDIDATE_COLUMNS)
    manifest = provenance.envelope(
        "protein_candidates", built_by="tools/it5_proteome.py candidates"
    )
    manifest.update(
        {
            "entry": ENTRY,
            "inputs": [
                {"file": p.as_posix(), "sha256": provenance.digest(p)[0]}
                for p in parts
                if p.exists()
            ],
            "rubric": (
                "proteome rows: proteome_tables.protein_strength; LINCS rows: "
                "tools/it5_lincs_cc.py lincs_strength (both stated in the entry)"
            ),
            "columns": dict.fromkeys(CANDIDATE_COLUMNS, CONTRACT),
            "rows": n,
            "outputs": [provenance.output(path, n)],
            "clinical_framing": FRAMING,
            "sources": {
                "genomic": args.genomic_source or "target gene only",
                "clinical": "cross-referenced in entry",
            },
        }
    )
    provenance.write(manifest, path.with_suffix(".provenance.json"))
    print(f"wrote {path} ({n} rows)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("command", choices=["run", "candidates"])
    parser.add_argument("--target", default=TARGET, help="the protein to rank")
    parser.add_argument("--branch", default=DEFAULT_BRANCH, help="branch the rows are filed under")
    parser.add_argument("--out", default=str(OUT), help="where the tables are written")
    parser.add_argument("--build", default=str(BUILD), help="working directory for this case")
    parser.add_argument("--genomic-source", default="", help="override the sources.genomic line")
    args = parser.parse_args()
    run(args) if args.command == "run" else candidates(args)


if __name__ == "__main__":
    main()
