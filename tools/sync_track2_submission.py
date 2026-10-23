"""Refresh/check submission tables against canonical generated decision artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "ressources/track2/it5/unified"
REPORT = ROOT / "submissions/track2/iteration-6/report.md"

NOTICE = (
    "> **Current model and protocol:** All priors, utilities, route weights, safety multipliers "
    "and assay accuracies are assumed research-triage weights, not calibrated probabilities "
    "of benefit, a validated diagnostic assay, or clinical prescriptions. Current assumed "
    "Se = Sp = 0.85 gives P(low) = 0.535, P(normal) = 0.465, "
    "P(unstable | low) = 0.8738 and P(inactive | normal) = 0.8226. "
    "EVPI = prior(inactive) × 0.4 = 0.18 is structural over the reported route-weight sweep, "
    "not independent biological confirmation. Readthrough information value is zero because "
    "the strict dosage-feasibility prior is zero; context heuristic 0.10 is a separate score. "
    "Use primary patient and parental fibroblasts, CHX 0, 2, 4, 8 h ±MG132. "
    "These are assay sampling hours; culture and turnaround are weeks 1–2, with no guaranteed "
    "48h clinical result. Candidate doses are literature context only, not a dosing plan. "
    "Embedded R4/R5 decision SVGs are historical illustrations: any .90-specificity "
    "or .912/.831 labels in those figures are superseded by the current .85 model.\n\n"
)


def normalize(text: str) -> str:
    if "**Embedded historical images:**" not in text:
        boundary = text.index("\n\n") + 2
        text = (
            text[:boundary]
            + (
                "> **Embedded historical images:** R2–R5 images are retained as historical "
                "analysis illustrations, not current numerical authority. Any image label "
                "1.47/1.44 as BUB1B log2FC is incorrect: canonical raw values are 0.22/0.20. "
                "Any historical .90-specificity or .912/.831 posterior label is superseded "
                "by assumed .85 specificity and the generated section 6 table.\n\n"
            )
            + text[boundary:]
        )
    if "**Sensitivity headline:**" not in text:
        text = text.replace(
            "> **Current model and protocol:**",
            "> **Sensitivity headline:** Only 3,815/7,425 assumption-grid settings "
            "(51.38% unweighted coverage, not confidence) capture at least half of EVPI; "
            "EVSI/EVPI spans 0–0.98. The often-quoted 69.1% is the nominal assumed-point "
            "scenario, not a robust universal result. See section 6 for all six axes.\n\n"
            "> **Current model and protocol:**",
        )
    replacements = {
        "tools/stability_atlas.py": "tools/variant_atlas.py",
        "0.9122": "0.8738",
        "0.8308": "0.8226",
        "0.912": "0.874",
        "0.831": "0.823",
        "0.5125": "0.5350",
        "0.4875": "0.4650",
        "Sp=0.90": "Sp=0.85",
        "Sp = 0.90": "Sp = 0.85",
        "48-Hour": "Weeks 1–2",
        "48-hour": "weeks 1–2",
        "48-HOUR": "WEEKS 1–2",
        "48h blot": "weeks 1–2 blot",
        "patient vs. parental fibroblasts/PBMCs": "primary patient and parental fibroblasts",
        "patient/parental fibroblasts or lymphoblastoid cells": (
            "primary patient and parental fibroblasts"
        ),
        ("patient fibroblasts or lymphoblastoid cells alongside parental heterozygous controls"): (
            "primary patient fibroblasts alongside parental fibroblast controls"
        ),
        "cycloheximide + MG132 proteasome-inhibitor control": (
            "cycloheximide ±MG132 proteasome-inhibitor control"
        ),
        "522-edge provenance DAG": "recorded provenance DAG",
        "522 recorded lineage edges": "recorded lineage edges",
        "0.91: NAD": "0.87: NAD",
        "0.83: dasatinib": "0.82: dasatinib",
        "catalytically impaired BubR1": "functionally impaired BubR1",
        "catalytically dead": "functionally impaired",
        "Only candidates supported across all 3": "Candidates with cross-iteration evidence across",
        "**Only candidates supported across all 3": (
            "**Candidates with cross-iteration evidence across"
        ),
        "Standard laboratory assay": "Proposed research assay; assumed accuracy",
        "FDA-approved choice": "approved-drug triage hypothesis",
        "FDA-approved prescription": "approved prescription",
        "+1.47": "+0.22",
        "+1.44": "+0.20",
        "8,793": "875",
        "8793": "875",
        "38942016": "36593396",
        "empirical-Bayes shrinkage": "robust residual standardization",
        "empirical-Bayes": "robust residual",
        "$+1.40$ EB": "legacy EB output (unvalidated)",
        "$+1.37$ EB": "legacy EB output (unvalidated)",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    # The previously hand-copied prescribing table is not a verified paediatric protocol.
    if "### 8.1 Paediatric PK/PD" in text:
        start = text.index("### 8.1 Paediatric PK/PD")
        end = text.index("\n## 9.", start)
        text = (
            text[:start]
            + (
                "### 8.1 Translation boundary: no patient dosing recommendation\n\n"
                "The archived `paediatric_pkpd_dosing.tsv` is exploratory literature metadata, "
                "not a verified paediatric MVA dosing protocol. No regimen, formulation, tissue "
                "exposure, or regulatory indication is established here for this child. Any "
                "drug-selection or dosing decision belongs to the treating clinical team and "
                "requires independent source verification and prospective research safeguards. "
                "Preclinical assays, not administration to the child, "
                "are the proposed next step.\n\n"
            )
            + text[end:]
        )
    # Historical point estimates elsewhere must not masquerade as measured readthrough feasibility.
    text = text.replace(
        r"$P(\text{readthrough}) = 0.10$", "context heuristic `0.10` (not the decision prior)"
    )
    if "**Current model and protocol:**" not in text:
        boundary = text.index("\n\n") + 2
        text = text[:boundary] + NOTICE + text[boundary:]
    return text


def rows(name: str) -> list[dict[str, str]]:
    with (DATA / name).open() as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def table(headers: list[str], records: list[list[str]]) -> str:
    def line(values: list[str]) -> str:
        return "| " + " | ".join(str(v).replace("|", r"\|") for v in values) + " |"

    return "\n".join([line(headers), line(["---"] * len(headers)), *(line(r) for r in records)])


def refresh(text: str) -> str:
    config = json.loads((DATA.parent / "decision_config.json").read_text())
    summary = json.loads((DATA / "unified_summary.json").read_text())
    ledger = rows("cross_iteration_candidates.tsv")
    assert len(ledger) == summary["n_candidates"]
    for record, canonical in zip(ledger, summary["ledger"], strict=True):
        assert record["drug"] == canonical["drug"]
        for key in ("calibrated_eu", "calibrated_u_unstable", "calibrated_u_inactive"):
            assert abs(float(record[key]) - canonical[key]) < 1e-8
    records = [
        [r["metric"], r["uncalibrated_it5_r4"], r["calibrated_it6_unified"]]
        for r in rows("model_comparison.tsv")
    ]
    test = next(t for t in config["tests"] if t["name"] == "chx_chase_blot")
    prior = config["state_variables"]["missense_class"]["prior"]
    low = prior["unstable"] * test["sensitivity"] + prior["inactive"] * (1 - test["specificity"])
    normal = 1 - low
    post_low = prior["unstable"] * test["sensitivity"] / low
    post_normal = prior["inactive"] * test["specificity"] / normal
    numeric = (
        "<!-- generated: tools/sync_track2_submission.py -->\n"
        + table(["Metric", "R4 uncalibrated", "R5 calibrated"], records)
        + f"\n\nAssumed assay sensitivity = {test['sensitivity']:.2f}; specificity = "
        f"{test['specificity']:.2f}. P(low) = {low:.4f}; P(normal) = {normal:.4f}; "
        f"P(unstable | low) = {post_low:.4f}; P(inactive | normal) = {post_normal:.4f}.\n\n"
        "These are Bayesian updates of assumed triage weights, "
        "not validated diagnostic probabilities. "
        "EVPI = 0.45 × 0.4 = 0.18 is structural: the inactive-state optimum contributes "
        "0.18 while the prior and perfect-information unstable contributions "
        "cancel over this sweep. "
        "It is not independent biological confirmation. Zero readthrough EVPPI/EVSI follows "
        "the strict dosage-threshold feasibility prior of zero; the separate context heuristic "
        "0.10 is not the decision-model prior.\n"
    )
    sensitivity = json.loads((DATA / "sensitivity_summary.json").read_text())
    numeric += (
        "\n**Joint sensitivity (not confidence):** "
        f"{sensitivity['n_captures_half_evpi']:,}/{sensitivity['n_grid']:,} settings "
        f"({100 * sensitivity['fraction_grid_captures_half_evpi']:.2f}%) capture at least "
        "half of EVPI. The unweighted Cartesian grid varies prior 0.30–0.80 by 0.05; "
        "Se and Sp independently in {0.60, 0.75, 0.85, 0.95, 0.99}; R2 weight "
        "{0.05, 0.25, 1}; unassessed safety {0.3, 0.6, 1}; inactive-branch "
        "unstable-state applicability {0, 0.25, 0.5}. EVPI spans 0.012–0.240; "
        "blot EVSI 0–0.2352; EVSI/EVPI 0–0.98. The prior action differs from canonical "
        "NMN in 4,525/7,425 settings; assay outcomes change the pretest action in "
        "5,996/7,425. These are grid coverage counts, not frequencies of clinical success. "
        "See `sensitivity_summary.json` and `multidimensional_sensitivity.tsv`.\n"
    )
    marker = "<!-- generated: tools/sync_track2_submission.py -->"
    start = text.index(marker) if marker in text else text.index("| Decision-analytic metric |")
    end = text.index("\n![Value-of-Information", start)
    text = text[:start] + numeric + text[end:]
    start = text.index("\n\n", text.index("## Appendix A")) + 2
    ordered = sorted(
        ledger, key=lambda r: (-float(r["calibrated_eu"]), -float(r["uncalibrated_eu"]), r["drug"])
    )
    fields = [
        "drug",
        "iterations",
        "it5_routes",
        "safety_class",
        "safety_factor",
        "uncalibrated_u_unstable",
        "uncalibrated_u_inactive",
        "uncalibrated_eu",
        "calibrated_u_unstable",
        "calibrated_u_inactive",
        "calibrated_eu",
        "clinical_role",
    ]
    values = [
        [str(i), *[f"{float(r[k]):.4f}" if k in fields[4:11] else r[k] for k in fields]]
        for i, r in enumerate(ordered, 1)
    ]
    return text[:start] + (
        "Generated from `unified_summary.json`, `model_comparison.tsv`, and "
        "`cross_iteration_candidates.tsv`; run `uv run python tools/sync_track2_submission.py` "
        "to refresh or add `--check` to detect drift. All 52 candidates are shown. "
        "Utilities and safety multipliers are assumed triage weights, "
        "not efficacy or safety estimates. "
        "A zero utility is not a clinical contraindication; `unflagged` is not proven safe. "
        "Approval is not inferred from phase metadata.\n\n"
        + table(
            [
                "Rank",
                "Drug",
                "Iterations",
                "Routes",
                "Safety class",
                "Safety factor",
                "R4 unstable",
                "R4 inactive",
                "R4 EU",
                "R5 unstable",
                "R5 inactive",
                "R5 EU",
                "Role",
            ],
            values,
        )
        + "\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    old = REPORT.read_text()
    new = refresh(normalize(old))
    if args.check:
        if new != old:
            raise SystemExit(
                "Submission numeric tables are stale; run tools/sync_track2_submission.py"
            )
        print("Submission numeric tables match canonical artifacts (52 rows).")
    else:
        REPORT.write_text(new)
        for name in ("README.md", "pitch-script.md"):
            path = REPORT.parent / name
            path.write_text(normalize(path.read_text()))
        path = REPORT.parent / "methods-form.json"
        methods = json.loads(
            subprocess.check_output(
                ["git", "show", "HEAD:submissions/track2/iteration-6/methods-form.json"],
                cwd=ROOT,
                text=True,
            )
        )
        detailed = {
            key: value.replace("+1.47", "+0.22").replace("+1.44", "+0.20")
            for key, value in methods.items()
        }
        methods["8"] = (
            "Final iteration 6: 52-candidate cross-iteration ledger; mechanism characterization, "
            "public-data discovery, per-child safety flags and assumed-weight decision triage. "
            "Appendix A and section 6 are generated and checked against canonical TSV/JSON. "
            "No clinical efficacy, validated assay accuracy, or patient dosing is claimed."
        )
        methods["10"] = (
            "Manual curation records literature mechanisms and class analogues, not patient "
            "efficacy. Genetic p16-positive-cell clearance is not direct dasatinib treatment "
            "evidence. Eight published MVA allele abundance labels (5 low, 3 stable) give "
            "ThermoMPNN AUROC .60 with broad interval [.133,1]; the registered test failed. "
            "The .55/.45 prior is an assumed triage weight, not established by calibration."
        )
        methods["14"] = (
            "BUB1B compound-heterozygous loss of function is the mechanistic hypothesis. "
            "Abundance and functional impairment remain unmeasured in this child. "
            "Proposed primary patient/parental fibroblast CHX chase at 0,2,4,8h ±MG132; "
            "culture and turnaround weeks 1–2, no guaranteed 48h clinical result."
        )
        methods["16"] = (
            "Research-only synthesis of 52 candidates. Under canonical assumed Se=Sp=.85, "
            "P(low)=.535, P(unstable|low)=.8738, P(inactive|normal)=.8226; EVPI=.18, "
            "EVSI=.124455 (69.14%). EVPI invariance is structurally .45×.4; zero readthrough "
            "information value follows strict dosage feasibility prior zero, distinct from "
            "context heuristic .10. Joint sensitivity: 3815/7425 settings (51.38% unweighted "
            "grid coverage, not confidence) achieve EVSI>=50% EVPI; EVPI .012–.240, EVSI "
            "0–.2352. No patient-tested therapy or validated assay. FANCA third-disease "
            "transfer: partial cached-public MGI/PrimeKG computation, 34 HPO terms, 27.78s; "
            "Fanca rank37/76699 symmetric, rank102 Phenodigm; raw top50 graph overlap "
            "Jaccard .098901 vs MVA, .041667 vs Bloom. No full PRISM/LINCS/safety transfer "
            "or therapeutic validation."
        )
        for key, value in methods.items():
            if isinstance(value, str):
                methods[key] = (
                    value.replace("+1.47", "+0.22")
                    .replace("+1.44", "+0.20")
                    .replace("8,793", "875")
                    .replace("38942016", "36593396")
                    .replace("empirical-Bayes", "robust residual")
                )
        methods["16"] += (
            " Bounded primary-source audit: raw HCT116 10µM 24h BUB1B log2FC .22 gliclazide "
            "and .20 migalastat, one published summary column each. Earlier 1.47/1.44 "
            "values are not raw BUB1B log2FC. No independent candidate replication or "
            "validated abundance-label expansion found in inspected datasets."
        )
        for key in ("8", "10", "14"):
            # Preserve the complete approach and curation detail, but explicitly
            # separate historical narrative from the final audited corrections.
            methods[key] = (
                methods[key]
                + "\n\nHistorical methodology context (superseded where audited above):\n"
                + detailed[key]
            )
        path.write_text(json.dumps(methods, indent=2) + "\n")
        print("Refreshed section 6 and all 52 Appendix A rows.")


if __name__ == "__main__":
    main()
