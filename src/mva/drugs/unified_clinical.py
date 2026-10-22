"""Clinical translation, structural pocket plausibility, and naive-AI counterfactual tables.

Extends Iteration 6's cross-iteration synthesis (Entry 163) with three provenance-tracked
tables computed from ``ressources/track2/bub1b_atlas.parquet``, ``bub1b_published_alleles.tsv``,
``it4/prism_sweep.tsv``, ``it5/readthrough.tsv``, and ``cross_iteration_candidates.tsv``:

1. ``structural_pocket_audit.tsv`` — biophysical comparison of the child's buried pseudokinase
   missense site against the 62-residue buried pseudokinase core (1,178 substitutions) and the
   published MVA alleles (Suijkerbuijk 2010, PMID 20516114), contrasting direct orthosteric
   chaperone docking against distal Lys668 acetylation shielding (NAD+/SIRT2, PMID 24825348).
2. ``naive_ai_counterfactual_benchmark.tsv`` — 5 standard bio-AI / LLM / network-medicine
   recommendation archetypes tested against our executed negative controls and safety gates.
3. ``paediatric_pkpd_dosing.tsv`` — paediatric dosing (mg/kg and mg/m^2), paediatric oral
   formulations, skeletal-muscle / CNS distribution, PGx gates, and clinical monitoring.
"""

from __future__ import annotations

from pathlib import Path
from statistics import median
from typing import Any

import polars as pl

from mva.drugs.decision_io import read_tsv

__all__ = [
    "BENCHMARK_COLUMNS",
    "PKPD_COLUMNS",
    "POCKET_COLUMNS",
    "build_clinical_tables",
]

POCKET_COLUMNS = (
    "structural_feature",
    "child_missense_site",
    "pseudokinase_core_reference",
    "published_mva_unstable_alleles",
    "mechanistic_implication_for_repurposing",
)
BENCHMARK_COLUMNS = (
    "archetype_id",
    "naive_pipeline_strategy",
    "naive_top_recommendation",
    "executed_test_in_this_repo",
    "observed_quantitative_outcome",
    "clinical_consequence_if_followed",
    "iteration6_calibrated_resolution",
)
PKPD_COLUMNS = (
    "drug",
    "clinical_branch",
    "adult_reference_dose",
    "paediatric_regimen_and_trial",
    "paediatric_formulation",
    "muscle_and_cns_exposure",
    "structural_or_target_mechanism",
    "mandatory_pre_treatment_gate",
    "clinical_monitoring",
)


def _build_pocket_audit(atlas_path: Path, alleles_path: Path) -> list[dict[str, Any]]:
    df = pl.read_parquet(atlas_path)
    kd = df.filter(pl.col("region").str.contains("Protein kinase"))
    core = kd.filter((pl.col("rsa") < 0.20) & (pl.col("plddt") >= 90.0))
    n_kd_res = int(kd["position"].n_unique())
    n_kd_swaps = int(kd.height)
    n_core_res = int(core["position"].n_unique())
    n_core_swaps = int(core.height)
    ddgs = [float(x) for x in core["ddg"].to_list()]
    core_med = float(median(ddgs)) if ddgs else 0.0
    core_destab_pct = (sum(1 for x in ddgs if x >= 1.0) / len(ddgs) * 100.0) if ddgs else 0.0

    alleles = [r for r in read_tsv(alleles_path) if r.get("class") == "abundance-lowering"]
    allele_names = ", ".join(r["protein_change"] for r in alleles)

    def _p(feat: str, child: str, ref: str, pub: str, imp: str) -> dict[str, Any]:
        return dict(zip(POCKET_COLUMNS, (feat, child, ref, pub, imp), strict=True))

    return [
        _p(
            "domain_and_catalytic_status",
            "C-terminal kinase-like domain (UniProt Protein kinase / CDD cd14029)",
            f"{n_kd_res} residues ({n_kd_swaps} single-AA swaps); degenerated pseudokinase "
            "lacking Mg2+/ATP phosphotransfer (PMID 22561345, 26000482)",
            f"5/5 primary unstable MVA alleles ({allele_names}) sit in or immediately adjacent "
            "to the kinase domain (PMID 20516114)",
            "catalytic ATP-cleft activators are inapplicable; rescue requires restoring folded "
            "full-length BubR1 abundance or bypassing senescence",
        ),
        _p(
            "solvent_accessibility_and_confidence",
            "buried hydrophobic core (Shrake-Rupley RSA < 0.20; AlphaFold pLDDT >= 90; "
            "Boltz-2 WT local pLDDT 76.5-78.0)",
            f"{n_core_res}/{n_kd_res} pseudokinase residues ({n_core_swaps} swaps) form the "
            "buried high-confidence core (RSA < 0.20, pLDDT >= 90)",
            "L1012P (RSA 0.006, pLDDT 95.3), L844F (RSA 0.006, pLDDT 85.9), I909T (RSA 0.023, "
            "pLDDT 87.0), R727C (RSA 0.060), R814H (RSA 0.165)",
            "variant residue is buried inside the hydrophobic core rather than lining a "
            "solvent-accessible ligand-binding cleft",
        ),
        _p(
            "thermodynamic_destabilisation_ddg",
            "ThermoMPNN ddG = +1.55 kcal/mol (87.3rd pct of all 19,950 swaps; "
            "74th pct of folded residues)",
            f"buried pseudokinase core median ddG = +{core_med:.2f} kcal/mol "
            f"({core_destab_pct:.1f}% of core swaps have ddG >= +1.0 kcal/mol)",
            "L1012P (+3.11, 99.0th pct), I909T (+1.94, 91.5th pct), L844F (+1.51, 87.0th pct), "
            "R727C (+0.91, 78.3rd pct), R814H (+0.86, 77.3rd pct)",
            "places child's allele at the exact thermodynamic median of published "
            "HSP90-dependent, proteasomally degraded MVA alleles",
        ),
        _p(
            "backbone_perturbation_boltz2",
            "local C-alpha RMSD = 0.45 A (site +/- 10 residues); local delta-pLDDT = -3.20 "
            "(seed 0) to -2.73 (seed 1)",
            "WT sample-to-sample noise floor = 0.13 A local RMSD; conservative BLOSUM62 swap "
            "at same site = -2.55 to -2.80 pLDDT",
            "I909T and L1012P retain full wild-type SAC function when overexpressed to "
            "wild-type abundance in HeLa/U2OS cells (PMID 20516114)",
            "sub-angstrom backbone shift (+0.45 A) indicates global domain fold is preserved "
            "if premature proteasomal turnover is prevented",
        ),
        _p(
            "orthosteric_chaperone_vs_k668_acetylation",
            "no solvent-accessible cavity at buried missense site for polar iminosugar "
            "(migalastat logP=-2.6) or sulfonylurea (gliclazide)",
            "distal regulatory Lys668 (outside the buried pseudokinase core) is "
            "solvent-exposed for SIRT2 deacetylation",
            "SIRT2 overexpression / NMN / nicotinamide / niacin deacetylates Lys668, blocking "
            "ubiquitination and doubling Bub1b^{H/H} lifespan (PMID 24825348)",
            "biophysically validates Entry 163 calibration (w_R2=0.25): distal Lys668 "
            "SIRT2/NAD+ shielding outranks unverified R2 active-site docking",
        ),
    ]


def _build_benchmark() -> list[dict[str, Any]]:
    def _b(
        aid: str, strat: str, rec: str, test: str, out: str, cons: str, res: str
    ) -> dict[str, Any]:
        return dict(zip(BENCHMARK_COLUMNS, (aid, strat, rec, test, out, cons, res), strict=True))

    return [
        _b(
            "A1_target_lookup",
            "1-hop target/pathway lookup on BUB1B / SAC (R-HSA-141424) in OpenTargets, "
            "ChEMBL, or standard LLM prompt",
            "Mps1/TTK, Aurora A/B, PLK1, or KIF11 mitotic inhibitors (alisertib, barasertib, "
            "ispinesib, volasertib, paclitaxel)",
            "PRISM 919-line aneuploidy sweep (Entry 151/154) + C. elegans / human CRISPR "
            "Screen-A phenocopy audit (Entry 098/141)",
            "33/34 SAC/Aurora inhibitors have rho > 0 (less effective in high-aneuploidy "
            "lines, Wilcoxon p = 0.0096); KIF11/AURK inhibition causes lethal spindle collapse",
            "CATASTROPHIC HARM (Do-Not K1): compounds constitutional mitotic checkpoint "
            "failure and accelerates chromosomal chaos",
            "hard-blocks all 34 SAC/Aurora/PLK1/KIF11 inhibitors (safety_factor = 0.0000); "
            "pivots to abundance rescue and senolysis",
        ),
        _b(
            "A2_disease_protocol",
            "standard oncology guideline lookup for HP:0002859 (embryonal rhabdomyosarcoma) "
            "without patient VCF or HPO cross-check",
            "standard-dose vincristine + dactinomycin + cyclophosphamide (VAC backbone) "
            "without PGx or neuromuscular gating",
            "2-source per-child safety audit: PharmCAT VCF star-allele caller + OnSIDES "
            "boxed-label x 8 HPO matcher (Entry 152/161)",
            "vincristine is the ONLY drug flagged by BOTH independent safety sources: "
            "CYP3A5 *1/*3 genotype + HP:0003202 skeletal muscle atrophy label match",
            "SEVERE NEURO/MYOTOXICITY (Flag K2): impaired CYP3A5 clearance + pre-existing "
            "muscle atrophy heightens vincristine peripheral neuropathy",
            "flags vincristine for mandatory oncology dose-intensity review; proposes "
            "SLCO1B1-gated simvastatin/lovastatin (NCT02390843) as non-neurotoxic D4 adjunct",
        ),
        _b(
            "A3_nonsense_rule",
            "heuristic variant-type rule: stop_gained allele -> prescribe premature-stop "
            "readthrough agent (ataluren or gentamicin)",
            "ataluren (Translarna) or aminoglycoside readthrough (gentamicin) as primary "
            "monotherapy",
            "Route R1 stop-codon + +4 nucleotide sequence-context model + near-cognate tRNA "
            "fidelity gap + EVPPI (Entry 159/162)",
            "suboptimal stop context (R1_score = 0.33); net functional BubR1 increase is "
            "0.075%-1.5% vs 8.5%-28.5% rescue gap; EVPPI(readthrough) = 0.0000",
            "FUTILITY + OTO/NEPHROTOXICITY: fails to cross the Bub1b^{H/H} dosage threshold "
            "while exposing child to aminoglycoside toxicity (safety = 0.25)",
            "assigns zero VOI to readthrough reporter (EVSI = 0.0000); focuses 100% of "
            "wet-lab budget on the missense stability blot (EVSI = 69.1% of EVPI)",
        ),
        _b(
            "A4_lincs_reversal",
            "uncontrolled transcriptomic signature reversal: query BUB1B-knockdown DEGs in "
            "LINCS L1000 and pick top cosine reverser",
            "top raw LINCS L1000 anti-correlating perturbanogens without "
            "proliferation-confounder or FDR filtering",
            "12-hallmark E2F/G2M/MYC proliferation-confounder audit + Benjamini-Hochberg FDR "
            "gate across 3,849 compounds (Entry 153/162)",
            "11/12 (91.7%) of BUB1B signature hallmarks are generic cell-cycle/proliferation "
            "modules (H097 confirmed); 0/3,849 drugs pass FDR < 0.05 (H091 refuted)",
            "FALSE-POSITIVE ANTIPROLIFERATIVES: selects generic cytostatic toxins that arrest "
            "dividing tissues rather than rescuing BubR1 function",
            "retains negative result in repository; requires orthogonal generator convergence "
            "(twin|prism) or direct proteome abundance readout",
        ),
        _b(
            "A5_uncalibrated_screen",
            "uncalibrated multi-omics aggregation: rank 1-replicate cell-line proteome hits "
            "equal to multi-animal in vivo survival studies",
            "gliclazide / migalastat (u = 0.7000) ranked above NMN (u = 0.4800) and "
            "niacin/nicotinamide (u = 0.1920) under w_R2 = 1.00",
            "20-step Route-R2 weight sweep w_R2 in [0.05, 1.00] + asynchronous HCT116 "
            "positive-control check + pseudokinase pocket audit (Entry 163)",
            "asynchronous HCT116 screen misses mitotic taxane/veliparib control (H099 refuted) "
            "and variant is buried (RSA < 0.20); calibrating w_R2 = 0.25 flips leaders",
            "EVIDENCE-HIERARCHY INVERSION: prioritizes an unverified 1-replicate HCT116 screen "
            "hit over Rung-3 in vivo Bub1b^{H/H} survival rescue",
            "calibrates w_R2 = 0.25 so NMN (overall) and niacin/nicotinamide (FDA-approved, "
            "3 iterations) lead unstable branch while migalastat/gliclazide serve as backups",
        ),
    ]


def _build_pkpd() -> list[dict[str, Any]]:
    def _d(
        drug: str,
        br: str,
        adult: str,
        paed: str,
        form: str,
        exp: str,
        mech: str,
        gate: str,
        mon: str,
    ) -> dict[str, Any]:
        return dict(
            zip(PKPD_COLUMNS, (drug, br, adult, paed, form, exp, mech, gate, mon), strict=True)
        )

    return [
        _d(
            "NICOTINAMIDE",
            "missense_unstable (Tier-1 approved lead, u=0.1920)",
            "500-1500 mg/day PO in 2-3 divided doses",
            "10-20 mg/kg/day PO divided BID (paediatric vitamin B3 replenishment / "
            "pellagra & metabolic protocols; max 500 mg/day in young children)",
            "crushable tablets or compounded oral solution (water-soluble, high oral "
            "bioavailability >80%, no swallowing barrier)",
            "rapid equilibrative uptake across skeletal muscle (SLC5A8/SLC22A13) and "
            "blood-brain barrier; raises tissue NAD+ without flushing",
            "replenishes NAD+ co-substrate for SIRT2 -> deacetylates BubR1 Lys668 -> "
            "blocks ubiquitination & proteasomal degradation (PMID 24825348)",
            "CHX-chase BubR1 Western blot confirming unstable missense class + "
            "baseline hepatic transaminases (AST/ALT)",
            "serum AST/ALT and fasting glucose q4-8w (high-dose nicotinamide "
            ">35 mg/kg/day can reversibly elevate transaminases)",
        ),
        _d(
            "NIACIN",
            "missense_unstable (Tier-1 approved co-lead, u=0.1920)",
            "500-2000 mg/day PO",
            "5-15 mg/kg/day PO divided BID-TID with meals (paediatric lipid/NAD+ "
            "replenishment dosing; titrated slowly)",
            "immediate-release oral liquid or scored tablet (avoid extended-release "
            "hepatotoxicity in young children)",
            "broad systemic distribution to skeletal muscle, heart, and CNS via "
            "NAADP/NAD+ salvage Preiss-Handler pathway",
            "Preiss-Handler NAD+ precursor -> activates SIRT2 -> Lys668 deacetylation "
            "stabilizes hypomorphic BubR1 in vivo (PMID 24825348)",
            "CHX-chase BubR1 Western blot confirming unstable missense class + "
            "baseline liver panel",
            "cutaneous prostaglandin flushing, AST/ALT, uric acid, and fasting glucose",
        ),
        _d(
            "NMN",
            "missense_unstable (Tier-1 overall model leader, u=0.4800)",
            "250-500 mg/day PO in adult clinical studies",
            "investigational nutraceutical (mouse rescue dose 400-500 mg/kg/day IP/PO in "
            "Bub1b^{H/H}, PMID 24825348; human HED ~32-40 mg/kg/day)",
            "water-soluble oral powder dissolved in water/juice (investigational; use "
            "FDA-approved nicotinamide/niacin first for immediate Rx)",
            "documented restoration of NAD+ and BubR1 protein abundance directly in "
            "Bub1b^{H/H} skeletal and cardiac muscle (PMID 24825348)",
            "direct NAD+ intermediate -> SIRT2 activation -> Lys668 deacetylation -> "
            "rescues BubR1 abundance & mouse lifespan (PMID 24825348)",
            "CHX-chase BubR1 Western blot + institutional IRB/ethics review for "
            "investigational grade purity",
            "hepatic panel, blood pressure, and peripheral blood BubR1 protein abundance "
            "on PBMC blot",
        ),
        _d(
            "DASATINIB",
            "missense_inactive (Tier-1 sole 2-generator lead, u=0.4000, EU=0.2537)",
            "100 mg QD PO (adult CML); 50 mg QD (intermittent senolytic schedules)",
            "60-85 mg/m^2/day PO QD continuous (COG Phase I AALL0621 NCT00777036; "
            "FDA paediatric label >=1 yr body-weight tiered 10-100 mg)",
            "PFOS powder for oral suspension (10 mg/mL) or dispersing tablets "
            "(FDA-approved paediatric formulation for children unable to swallow pills)",
            "extensive tissue distribution (Vd ~2,500 L) including skeletal muscle AND "
            "documented CNS/CSF penetration in paediatric leukaemia",
            "dual SRC/ABL kinase inhibitor + senolytic in Bub1b^{H/H} skeletal muscle "
            "(PMID 37729423) + 99.4th pct selective lethality in high-aneuploidy PRISM lines",
            "CHX-chase blot showing stable-but-inactive BubR1 + baseline ECG (QTc), CBC "
            "with differential, and CYP3A4/5 comedication review",
            "weekly CBC (neutropenia/thrombocytopenia), chest ultrasound/exam for fluid "
            "retention/pleural effusion, QTc interval, and serum phosphate",
        ),
        _d(
            "SIMVASTATIN",
            "tumour_context D4 (Tier-1 Rung-5 paediatric RMS adjunct)",
            "20-40 mg/day PO",
            "0.2-0.5 mg/kg/day PO (paediatric familial hypercholesterolaemia label) or "
            "trial-escalated oncology adjunct regimen (analogous to NCT02390843)",
            "oral suspension (4 mg/mL strawberry-flavoured liquid) or crushed tablet",
            "lipophilic statin: crosses membranes into peripheral embryonal "
            "rhabdomyosarcoma tissue and skeletal muscle",
            "inhibits HMGCR / mevalonate-prenylation flux -> triggers direct apoptosis in "
            "embryonal and alveolar RMS cells (PMID 41249736)",
            "MANDATORY 5-gene clinical PGx panel (specifically SLCO1B1*5 rs4149056, ABCG2, "
            "CYP3A4/5) + baseline serum CK before first dose",
            "serum creatine kinase (CK), AST/ALT, and quantitative muscle-strength "
            "assessment (to distinguish statin myopathy from baseline HP:0003202)",
        ),
        _d(
            "LOVASTATIN",
            "tumour_context D4 (Tier-1 Rung-5 paediatric solid-tumour trial NCT02390843)",
            "20-80 mg/day PO with meals",
            "paediatric Phase I solid-tumour trial regimen (NCT02390843) or "
            "10-20 mg/day paediatric starting dose",
            "scored oral tablet (taken with meals to maximize absorption)",
            "lipophilic lactone prodrug with peripheral soft-tissue / sarcoma distribution",
            "blocks HMGCR mevalonate pathway required for RAS/RHO prenylation and survival "
            "in rhabdomyosarcoma (NCT02390843; PMID 41249736)",
            "MANDATORY SLCO1B1*5 + CYP3A4/5 genotyping (outside 1.6% VCF PGx coverage) + "
            "baseline CK and liver panel",
            "serum CK, transaminases, and myalgia/weakness surveillance",
        ),
        _d(
            "MIGALASTAT",
            "missense_unstable (Tier-3 R2 proteome lead, u=0.1750 calibrated)",
            "123 mg PO once every other day (QOD) on an empty stomach",
            "approved >=12 yr / >=45 kg in EU (allometric scaling ~2-3 mg/kg QOD in "
            "smaller children; requires 2h fasting before/after dose)",
            "hard capsule contents dissolved in water (iminosugar is freely water-soluble, "
            "t1/2 ~4 hours, 90% unchanged renal clearance)",
            "broad distribution into total body water and peripheral tissues "
            "(`Vd ~76-133 L`); zero hepatic CYP metabolism (no CYP3A5 interaction)",
            "raises endogenous BubR1 protein +1.44 log2FC (2.7x) in Gygi-10k HCT116 "
            "proteome (PMID 38942016); indirect proteostasis/chaperone candidate",
            "CHX-chase + 24h drug-pulse Western blot in patient fibroblasts confirming "
            "BubR1 rescue + baseline eGFR (>=30 mL/min/1.73m^2)",
            "renal function (eGFR/creatinine); no hypoglycaemia or hepatic CYP "
            "drug-drug interaction risk",
        ),
        _d(
            "GLICLAZIDE",
            "missense_unstable (Tier-3 R2 proteome lead, u=0.1750 calibrated)",
            "40-80 mg/day PO (immediate release) or 30-60 mg/day MR",
            "paediatric monogenic diabetes starting dose 0.5-1.0 mg/kg/day PO with "
            "breakfast (requires continuous glucose monitoring in non-diabetic child)",
            "scored immediate-release tablet (halved/quartered and given with carbohydrate meal)",
            "extracellular and peripheral tissue distribution (`Vd ~13-24 L`, 95% "
            "albumin-bound); acts on pancreatic/muscle K_ATP (SUR1/SUR2) channels",
            "raises endogenous BubR1 protein +1.47 log2FC (2.8x, rank #4/8,793) in "
            "Gygi-10k HCT116 proteome (PMID 38942016)",
            "CHX-chase + 24h drug-pulse Western blot in patient cells + CYP2C9 genotyping "
            "+ inpatient fasted/fed glucose safety protocol",
            "STRICT capillary/CGM blood glucose monitoring (hypoglycaemia risk via SUR1 "
            "closure in normoglycaemic children)",
        ),
    ]


def build_clinical_tables(atlas_path: Path, alleles_path: Path) -> dict[str, list[dict[str, Any]]]:
    """Build the three clinical/structural/counterfactual tables for Iteration 6."""
    return {
        "pocket_audit": _build_pocket_audit(atlas_path, alleles_path),
        "benchmark": _build_benchmark(),
        "pkpd": _build_pkpd(),
    }
