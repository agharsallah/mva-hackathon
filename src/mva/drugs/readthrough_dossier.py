"""Route R1's candidate rows: the model's own predictions, plus the literature rows around them.

Two kinds of row land in ``readthrough_candidates.tsv``:

* **model rows** — one per compound in the measured readthrough dataset, carrying the value this
  route predicted for *this* stop context and the verdict of this route's declared positive
  control. A compound whose control failed keeps its row: the failure is the result.
* **literature rows** — facts that no model produces and that decide whether a compound is
  usable at all: regulatory status, paediatric exposure, a toxicity that collides with one of
  the child's own clinical terms, or an intervention that acts on the *missense* allele instead.

Each row states its branch (which allele or allele-state it acts on) and its evidence band from
the rubric in :mod:`mva.drugs.readthrough_notes`. Nothing here is a recommendation.
"""

from __future__ import annotations

import csv
from pathlib import Path

from mva.drugs.readthrough_tables import Candidate

__all__ = ["COMPOUND_NOTES", "LITERATURE", "candidates", "model_rows"]

#: What each compound of the measured panel is, and what bears on using it in this child.
COMPOUND_NOTES = {
    "DAP": (
        "2,6-diaminopurine: UGA-selective readthrough by inhibiting the tRNA-Trp "
        "2'-O-methyltransferase FTSJ1, and it also inhibits NMD at active concentrations "
        "(PMID 32198346). Preclinical, no human dosing. Its UGA selectivity matches this stop"
    ),
    "SRI": (
        "SRI-41315: degrades the release factor eRF1 (PMID 34272367). Preclinical. Depleting "
        "eRF1 also reads through normal stop codons proteome-wide"
    ),
    "G418": (
        "geneticin: the most potent aminoglycoside in vitro and never a medicine - a cell "
        "culture selection reagent, too toxic systemically (PMID 32658832)"
    ),
    "Gentamicin": (
        "approved antibiotic, readthrough use off-label. The predicted value sits at the assay "
        "floor for this context. Class tubular nephrotoxicity collides with the child's "
        "nephrocalcinosis (HP:0000121) and ototoxicity is irreversible and cumulative; MT-RNR1 "
        "m.1555A>G confers profound hearing loss at normal doses (CPIC, PMID 34032273)"
    ),
    "Clitocine": (
        "adenosine analogue incorporated into the message (PMID 28096517). Preclinical; RNA "
        "incorporation is a genotoxicity question in a child with a sarcoma (HP:0002859)"
    ),
    "SJ6986": "GSPT1 degrader: an anticancer chemotype, not a chronic paediatric agent",
    "CC90009": "GSPT1 degrader in oncology trials; the same objection as SJ6986",
    "FUr": "5-fluorouridine: a cytotoxic pyrimidine analogue, not a chronic paediatric agent",
    "Untreated": (
        "the dataset's own no-drug column, carried as this route's negative control: context "
        "must NOT predict readthrough when no drug is present"
    ),
}

#: Rows no model produces. ``(drug, branch, kind, strength, control, source, note)``.
LITERATURE: tuple[tuple[str, str, str, float, str, str, str], ...] = (
    (
        "ataluren (Translarna)",
        "stop_allele",
        "regulatory and assay-validity fact",
        0.0,
        "n/a",
        "EMA EPAR; EC decision 28 Mar 2025; PMID:19208811; PMID:39174735 supp. table 2",
        (
            "ruled out three times over: the EU marketing authorisation was not renewed (EC "
            "decision 28 March 2025, after CHMP non-renewal opinions in 2023 and 2024); it was "
            "discovered in a firefly-luciferase reporter it directly stabilises (PMID "
            "19208811); and it produced no reproducible readthrough in the orthogonal assay "
            "this route's dataset uses, tested at 0.1-400 ug/mL"
        ),
    ),
    (
        "ELX-02 (designer aminoglycoside)",
        "stop_allele",
        "clinical-development fact",
        0.4,
        "n/a",
        "NCT05448755; PMID:33465285; PMID:30650260",
        (
            "the only readthrough agent with an active paediatric-inclusive programme (Alport "
            "phase 2 enrolled from age 6). Renally eliminated largely unchanged; the "
            "multiple-dose phase 1 had an unresolved audiometric signal at 5.0 mg/kg. "
            "Validated in this route's source assay but dropped there on cost, so this stop "
            "context has no prediction for it"
        ),
    ),
    (
        "NMD inhibition (SMG1 inhibitors, NMDI-14)",
        "stop_allele",
        "mechanism and precedent",
        0.2,
        "n/a",
        "PMID:17290305; PMID:24662918; PMID:20566848; PMID:33396210",
        (
            "this route's arithmetic makes the stop allele's message the binding constraint, "
            "and the CF precedent is that the NMD level governs the gentamicin response (PMID "
            "17290305). But NMD is essential - Smg1-null mice die as embryos - and every agent "
            "is preclinical, so this is a mechanism, not a candidate"
        ),
    ),
    (
        "amlexanox",
        "stop_allele",
        "mechanism, approved elsewhere",
        0.2,
        "n/a",
        "PMID:22938201; PMID:39174735 supp. table 2",
        (
            "dual readthrough and NMD inhibition, and already approved (topical aphthous "
            "ulcers). Not reproducible in this route's source assay, so it carries no "
            "prediction here"
        ),
    ),
    (
        "nicotinamide mononucleotide / NAD+ precursors",
        "missense_unstable",
        "in vivo measurement in a BubR1 model",
        0.8,
        "n/a",
        "PMID:24825348; caution PMID:38009412",
        (
            "the one intervention reported to raise BubR1 protein in a living mouse: falling "
            "NAD+ costs SIRT2 the ability to keep BubR1 deacetylated, and NMN raised BubR1 "
            "abundance in vivo; SIRT2 overexpression extended median lifespan in the BubR1 H/H "
            "background. SIRT2 overexpression alone does nothing on a wild-type background, so "
            "the benefit is specific to BubR1 deficiency. Verified at abstract level only"
        ),
    ),
    (
        "proteasome inhibition (MG132 as the tool; bortezomib, carfilzomib in clinic)",
        "missense_unstable",
        "measurement in human MVA patient-derived cells",
        0.5,
        "n/a",
        "PMID:20516114",
        (
            "the missense loss in MVA is degradation, not transcription: mutant BubR1 turns "
            "over about twice as fast, is HSP90-dependent, and MG132 prevents the enhanced "
            "turnover. Supportive mechanism; clinical proteasome inhibitors are not chronic "
            "paediatric agents"
        ),
    ),
    (
        "HSP90 inhibitors (geldanamycin class)",
        "missense_unstable",
        "direction-of-effect fact",
        0.0,
        "n/a",
        "PMID:20516114",
        (
            "ruled out as harmful: mutant - not wild-type - BubR1 depends on HSP90, and "
            "geldanamycin collapses it. A chaperone potentiator is the untested inverse"
        ),
    ),
    (
        "CBP/p300 inhibition",
        "missense_unstable",
        "mechanism only",
        0.2,
        "n/a",
        "PMID:24825348",
        (
            "CBP is the acetyltransferase opposing SIRT2 on the BubR1 lysine whose acetylation "
            "drives the age-related decline, so inhibiting it is the implied lever. No CBP "
            "inhibitor has been shown to raise BubR1 in vivo, and the class is pleiotropic"
        ),
    ),
    (
        "senolytics (dasatinib + quercetin; navitoclax as the mechanistic analogue)",
        "missense_inactive",
        "genetic proof in the matching mouse",
        0.4,
        "n/a",
        "PMID:22048312",
        (
            "if the missense protein is present but broken, no protein-level lever exists and "
            "the target moves downstream to the senescent cells the aneuploidy produces. "
            "Clearing p16Ink4a-positive cells delayed ageing phenotypes in BubR1 H/H mice; "
            "dasatinib + quercetin is the nearest approved analogue. Genetic clearance, not a "
            "drug, was what was tested"
        ),
    ),
    (
        "rapalogs (sirolimus, everolimus)",
        "missense_inactive",
        "mechanism from the matching mouse",
        0.2,
        "n/a",
        "PMID:31738183",
        (
            "sarcopenia in BubR1 +/X753 carriers tracked mTORC1 hyperactivation, which makes a "
            "rapalog the implied lever for the muscle terms (HP:0003202, HP:0001508). No "
            "rapalog has been tested in any BubR1 model"
        ),
    ),
)


def model_rows(path: Path, *, route: str = "R1") -> list[Candidate]:
    """One candidate per compound in this route's readthrough table."""
    if not path.is_file():
        return []
    out: list[Candidate] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            drug = row["drug_name"]
            passed = row["control_passed"] == "true"
            negative = drug == "Untreated"
            verdict = (
                "the negative control: context must not predict the no-drug column, and it "
                "does not, which is what licenses the drug columns"
                if negative
                else (
                    "predicted for this stop context; the declared benchmark-panel control "
                    "passed on both held-out sets"
                    if passed
                    else "not interpretable as a number: the declared positive control failed"
                )
            )
            out.append(
                Candidate(
                    drug_name=drug,
                    route=route,
                    branch="any" if negative else "stop_allele",
                    evidence_kind=(
                        "negative control"
                        if negative
                        else "context-model prediction, measured dataset"
                    ),
                    evidence_strength=0.0 if negative else (0.6 if passed else 0.3),
                    positive_control_passed=str(passed).lower(),
                    source=f"{row['source']} (Toledano et al., Nat Genet 2024)",
                    notes=(
                        f"predicted {row['predicted_readthrough']} % of the no-PTC control at "
                        f"the {row['evidence_level']} level over {row['rows_behind_it']} "
                        f"measured contexts (held-out rho "
                        f"{row['control_spearman'] or 'n/a'}). {verdict}. "
                        f"{COMPOUND_NOTES.get(drug, '')}"
                    ),
                )
            )
    return out


def candidates(readthrough_table: Path, *, route: str = "R1") -> list[Candidate]:
    """The full candidate list: model rows first, then the literature rows."""
    rows = model_rows(readthrough_table, route=route)
    rows.extend(
        Candidate(
            drug_name=drug,
            route=route,
            branch=branch,
            evidence_kind=kind,
            evidence_strength=strength,
            positive_control_passed=control,
            source=source,
            notes=note,
        )
        for drug, branch, kind, strength, control, source, note in LITERATURE
    )
    return rows
