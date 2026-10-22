"""HTML pitch-deck builder for the 3-minute Track 2 Iteration 6 presentation.

Generates a self-contained 16:9 widescreen 7-slide HTML deck (`pitch-slides.html`)
that embeds the repository's research SVGs (`figures/it4/*.svg`, `figures/it5/*.svg`)
and includes a toggleable live teleprompter for both Version A (Technical) and
Version B (Plain-English / Non-Technical).
"""

from __future__ import annotations

import base64
from pathlib import Path

__all__ = ["build_slides_html"]


def _uri(root: Path, rel: str) -> str:
    b64 = base64.b64encode((root / rel).read_bytes()).decode("ascii")
    return f"data:image/svg+xml;base64,{b64}"


def _tp(tech: str, plain: str) -> str:
    return (
        '<div class="teleprompter"><div class="tp-mode"><span class="tp-label">'
        "SPEAKER SCRIPT — VERSION A (TECHNICAL)</span>"
        "<span>Press [T] Technical / Plain-English / Hide • [←/→] Slide</span></div>"
        f'<p class="tp-tech">{tech}</p>'
        f'<p class="tp-plain" style="display:none;">{plain}</p></div>'
    )


def _slide(
    num: int, time_str: str, title: str, crit: str, body_html: str, tech: str, plain: str
) -> str:
    act = " active" if num == 1 else ""
    return (
        f'<section class="slide{act}" data-slide="{num}">'
        '<div class="topbar"><div class="topbar-left">'
        f'<span class="slide-badge">SLIDE {num} / 7</span>'
        f'<span class="time-badge">{time_str}</span>'
        f'<span class="slide-title">{title}</span></div>'
        f'<span class="crit-badge">{crit}</span></div>'
        f"{body_html}" + _tp(tech, plain) + "</section>"
    )


def _kpi(color: str, val: str, lbl: str) -> str:
    return (
        f'<div class="kpi {color}"><div class="kpi-val">{val}</div>'
        f'<div class="kpi-lbl">{lbl}</div></div>'
    )


def build_slides_html(root: Path, css: str = "", js: str = "") -> str:
    """Return the complete 7-slide HTML presentation string."""
    u_hero = _uri(root, "figures/it5/r6-pitch-overview.svg")
    u_ddg = _uri(root, "figures/it4/step9-e1-distribution.svg")
    u_twin = _uri(root, "figures/it4/step9-e2-rank.svg")
    u_r1 = _uri(root, "figures/it5/r1-dosage.svg")
    u_upset = _uri(root, "figures/it4/step10-s2-upset.svg")
    u_r2 = _uri(root, "figures/it5/r2-hits.svg")
    u_r5 = _uri(root, "figures/it5/r5-cross-iteration.svg")
    u_r4 = _uri(root, "figures/it5/r4-decision-tree.svg")
    u_r3 = _uri(root, "figures/it5/r3-mva-exposures.svg")
    u_cov = _uri(root, "figures/it4/step9-e56-coverage.svg")
    u_blm = _uri(root, "figures/it4/step11-t1-stages.svg")
    u_s1 = _uri(root, "figures/it5/s1-transfer.svg")

    s1 = _slide(
        1,
        "0:00 – 0:25 (Tech) | 0:00 – 0:30 (Plain)",
        'The Child, the "Seatbelt Inspector" (BUB1B), and the 5-Instrument Mechanism',
        "Scientific Rigor (35%)",
        '<div class="kpi-row">'
        + _kpi("purple", "Rank 1 Confirmed (1.0)", "Track 1 Oracle: <b>BUB1B</b> in trans")
        + _kpi("amber", "ΔΔG = +1.55 kcal/mol", "87.3rd pct → <b>55% Unstable</b> vs <b>45%</b>")
        + _kpi("green", "Top 0.99% MGI Twin", "<b>Bub1b<sup>H/H</sup></b> matches 8 HPO (p=0.026)")
        + _kpi("blue", "RMSD = 0.45 Å", "Boltz-2 fold preserved if Copy #2 is stabilized")
        + '</div><div class="content-grid-2">'
        '<div class="panel"><h3><span>1. All-19,950-Substitution Stability Atlas '
        '(Entry 149)</span><span class="pill amber">ThermoMPNN</span></h3>'
        f'<div class="fig-box"><img src="{u_ddg}" alt="ThermoMPNN"/></div></div>'
        '<div class="panel"><h3><span>2. Cross-Species Phenotype Twin Across 76,699 '
        'MGI Mice (Entry 150)</span><span class="pill green">Bub1b H/H Twin</span></h3>'
        f'<div class="fig-box"><img src="{u_twin}" alt="MGI twin"/></div></div></div>',
        "\"In Track 1, the oracle confirmed at Rank 1 that this child's MVA and "
        "rhabdomyosarcoma are caused by two broken copies of BUB1B: one premature "
        "stop codon and one missense swap in the BubR1 pseudokinase domain. Before "
        "naming a single medicine, we read the disease mechanism from five independent "
        "instruments: nine variant-effect models, a Boltz-2 structure fold, an "
        "all-19,950-substitution ThermoMPNN stability atlas, and a cross-species match "
        "of the child's 8 clinical terms against all 76,699 mouse genotypes in MGI. "
        "The result is hypomorphic loss of function: the child's phenotype twin in the "
        "top 1% of all mouse models (p = 0.026) is the Bub1b H/H hypomorph, while the "
        "missense allele sits at the 87.3rd percentile of destabilizing folding energy "
        '(+1.55 kcal/mol), giving a 55% prior that the mutant is unstable vs 45% inactive."',
        '"Every time one of our cells divides, a guardian protein called BubR1 acts '
        "like a seatbelt inspector. In Track 1, we proved this child inherited two "
        "broken copies of BUB1B. Copy #1 has a premature stop sign halfway through, "
        "so the cell destroys it. That means the child's survival depends entirely on "
        "Copy #2, which has just a single-letter typo. By testing that typo across 3D "
        "protein-folding models and comparing the child's symptoms against 76,000 mouse "
        "models, we found the child's exact biological twin: a mouse with too little "
        "working BubR1 whose cells age prematurely. And our 3D map revealed the one "
        "crucial question: does that typo make BubR1 crumple and break down too fast "
        '(55% chance), or hold its shape without working (45% chance)?"',
    )

    s2 = _slide(
        2,
        "0:25 – 0:52 (Tech) | 0:30 – 0:52 (Plain)",
        "Why Stop-Skipping &amp; Naive AI Pipelines Fail — And What Survives Null Testing",
        "Scientific Rigor &amp; Controls (35%)",
        '<div class="content-grid-2">'
        '<div class="panel"><h3><span>Route R1 Allele Dosage &amp; 4-Generator '
        'Convergence (Entries 155, 158)</span><span class="pill blue">Null Tested</span></h3>'
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;flex:1;min-height:0;">'
        f'<div class="fig-box"><img src="{u_r1}" alt="Allele dosage"/></div>'
        f'<div class="fig-box"><img src="{u_upset}" alt="UpSet"/></div></div>'
        '<div style="font-size:10.8px;color:#334155;margin-top:5px;background:#f1f5f9;'
        'padding:5px 8px;border-radius:6px;">'
        "• <b>Copy #1 Readthrough:</b> Adds &lt;1.42 pts vs 6.5–28.5 pt gap (EVPPI=0%).<br/>"
        "• <b>4-Generator Null (p=0.263):</b> Only <b>dasatinib</b> converges across ≥2 "
        "generators (<code>twin|prism</code>, 99.4th pct aneuploidy, p=0.0096).</div></div>"
        '<div class="panel"><h3><span>Counterfactual Benchmark: Why 5 Standard Bio-AI '
        'Shortcuts Fail</span><span class="pill red">5 Executed Controls</span></h3>'
        '<table class="mini-table"><thead><tr><th>Naive AI Archetype</th>'
        "<th>Naive Output</th><th>Executed Repo Test</th><th>Outcome</th></tr></thead><tbody>"
        "<tr><td><b>A1. 1-Hop Target</b></td><td>Mps1/Aurora/PLK1 inhib</td>"
        '<td>PRISM 919-line sweep</td><td><span class="pill red">DO-NOT K1</span> '
        "33/34 worse in aneuploidy (p=0.0096)</td></tr>"
        "<tr><td><b>A2. Disease Protocol</b></td><td>Standard Vincristine</td>"
        '<td>PharmCAT + OnSIDES</td><td><span class="pill red">FLAG K2</span> '
        "<code>CYP3A5 *1/*3</code> + <code>HP:0003202</code> neurotoxicity</td></tr>"
        "<tr><td><b>A3. Nonsense Rule</b></td><td>Ataluren / Gentamicin</td>"
        '<td>Route R1 + EVPPI</td><td><span class="pill amber">FUTILE</span> '
        "&lt;1.5% rescue vs gap; nephro/ototoxic</td></tr>"
        "<tr><td><b>A4. Raw LINCS</b></td><td>Raw L1000 reversers</td>"
        '<td>12-hallmark E2F/G2M</td><td><span class="pill amber">CONFOUNDED</span> '
        "91.7% proliferation; 0/3,849 FDR&lt;0.05</td></tr>"
        "<tr><td><b>A5. Uncalibrated</b></td><td>1-rep HCT116 &gt; mouse</td>"
        '<td>20-step w_R2 sweep</td><td><span class="pill blue">CALIBRATED</span> '
        "Fixed by <code>w_R2 = 0.25</code> (Entry 163)</td></tr>"
        "</tbody></table></div></div>",
        '"Rather than trusting a single drug pipeline, we built three orthogonal discovery '
        "engines across 13 public databases and forced every one of them through "
        "pre-registered negative controls and permutation nulls. First, across four "
        "independent drug generators, only one FDA-approved drug converged across two "
        "independent sources: dasatinib, which clears senescent cells in the Bub1b H/H "
        "twin model and ranks at the 99.4th percentile for selectively killing "
        "high-aneuploidy cancer cells (p = 0.0096). Second, we audited stop-codon "
        "readthrough (Route R1) and found suboptimal sequence context (score = 0.33), "
        'explaining why readthrough alone cannot carry the clinical bet."',
        '"Because developing a brand-new drug takes a decade, we searched thousands of '
        "already-approved medicines from three angles — and checked every idea against "
        "strict controls so we wouldn't fool ourselves. First, we asked: can a drug "
        "force the cell to ignore the stop sign on Copy #1? Our sequence check showed "
        "that 'stop-skipping' drugs would restore less than 1.5% of normal protein, "
        "which isn't enough. And when we tested what protects tissues if Copy #2 cannot "
        "be rescued, one FDA-approved medicine stood out across both our mouse twin "
        'and 919 cancer lines: dasatinib, which clears damaged aging cells."',
    )

    s3 = _slide(
        3,
        "0:52 – 1:15 (Tech &amp; Plain)",
        "8,793-Compound Proteome Scan vs. 3D Pseudokinase Pocket Biophysics",
        "Innovation (25%) &amp; Rigor (35%)",
        '<div class="content-grid-2">'
        '<div class="panel"><h3><span>Route R2: Proliferation-Corrected &amp; Gygi-10k '
        'Proteome Scan (Entries 159, 160)</span><span class="pill blue">Proteomics</span></h3>'
        f'<div class="fig-box"><img src="{u_r2}" alt="Proteome hits"/></div>'
        '<div style="font-size:10.8px;color:#334155;margin-top:4px;">'
        "• <b>Gygi-10k (8,793 drugs):</b> <b>Gliclazide (+1.47 log₂FC, 2.8×)</b> &amp; "
        "<b>Migalastat (+1.44 log₂FC, 2.7×)</b> are the top clean oral BubR1 raisers.<br/>"
        "• <b>Proliferation-corrected (Mitchell 2023):</b> Blocking proteasomal degradation "
        "is the dominant mechanism raising BubR1 protein.</div></div>"
        '<div class="panel"><h3><span>3D Pseudokinase Pocket Plausibility Audit '
        "(1,178 Buried Core Swaps, Entry 163)</span>"
        '<span class="pill green">3D Biophysics</span></h3>'
        f'<div class="fig-box"><img src="{u_hero}" alt="Hero overview"/></div>'
        '<div style="font-size:10.8px;color:#334155;margin-top:4px;">'
        "• <b>62/285 pseudokinase residues</b> form a buried core (<code>RSA &lt; 0.20</code>, "
        "72.2% swaps ΔΔG ≥ +1.0) with no cleft for polar <code>migalastat</code> (logP=-2.6).<br/>"
        "• <b>Distal Lys668 is solvent-exposed:</b> <b>NAD+/SIRT2</b> (<code>NMN</code>, "
        "<code>nicotinamide</code>, <code>niacin</code>) shields BubR1 in vivo.</div></div></div>",
        '"Third, we scanned 8,793 chemical perturbations in the Gygi-10k HCT116 proteome '
        "atlas (Route R2) using empirical-Bayes shrinkage, uncovering two oral FDA-approved "
        "small molecules — gliclazide and migalastat — that raise endogenous BubR1 protein "
        "by +1.47 and +1.44 log2 fold-change (2.7x above baseline). Crucially, our 3D "
        "pseudokinase audit across 1,178 buried-core swaps (RSA < 0.20) shows why distal "
        "Lys668 deacetylation via NAD+/SIRT2 (NMN, nicotinamide, niacin) is biophysically "
        'superior to direct active-site docking into a buried pseudokinase core."',
        '"Second, we asked: what if Copy #2 is crumpling too fast? Both our mouse-twin '
        "studies and a scan of 8,793 compounds in human cells revealed two groups of safe, "
        "oral medicines that boost or stabilize BubR1 protein levels: vitamin B3 / NAD+ "
        "boosters (NMN, niacin, and nicotinamide), which flip a surface switch (Lys668) to "
        "shield BubR1 from decay and doubled healthy lifespan in the matching mouse model, "
        "and two oral pills — migalastat and gliclazide — that raised BubR1 protein levels "
        'more than two-and-a-half-fold in human cells."',
    )

    s4 = _slide(
        4,
        "1:15 – 1:42 (Tech &amp; Plain)",
        "Cross-Iteration Synthesis &amp; Route Calibration (Entry 163: 52 Candidates Unified)",
        "Innovation (25%) &amp; Rigor (35%)",
        '<div class="kpi-row">'
        + _kpi("blue", "w<sub>R2</sub> = 0.25 Calibrated", "1-rep HCT116 weighed below mouse")
        + _kpi("green", "EVPI = 0.1800 (100%)", "Invariant across all 20 weights; 100% on Missense")
        + _kpi("amber", "EVSI = 69.1% of EVPI", "One 48h <b>CHX Western blot</b> = 0.1245 / 0.1800")
        + _kpi("purple", "2 Exact Flip Points", "<code>w*=0.686</code> &amp; <code>w*=0.274</code>")
        + '</div><div class="panel" style="flex:1;margin:8px 0;">'
        "<h3><span>Cross-Iteration Candidate Comparison (Panel A) &amp; 20-Step Route-R2 "
        "Weight Sweep (Panel B) — <code>figures/it5/r5-cross-iteration.svg</code></span>"
        '<span class="pill green">Entry 163</span></h3>'
        f'<div class="fig-box"><img src="{u_r5}" alt="R5 calibration"/></div></div>',
        '"In Iteration 6 (Entry 163), we asked the critical synthesis question: how do we '
        "weigh a 1-replicate cell-line proteomics hit (Route R2) against multi-animal in "
        "vivo survival rescues in the actual Bub1b H/H mouse twin (Route R3)? When we sweep "
        "the Route-R2 evidence weight across 20 calibration steps (Panel B), two things "
        "happen: First, Expected Value of Perfect Information (EVPI = 0.1800) is 100% "
        "invariant across every weight — and 100% of that uncertainty (EVPPI = 0.1800) "
        "sits on one question: is the child's missense protein unstable or inactive? "
        "Second, a single cycloheximide-chase BubR1 Western blot captures 59% to 69.1% "
        'of the entire decision value (EVSI = 0.1245)."',
        '"In our final unified submission, we combined all 52 drug candidates from every '
        "stage of our work into a single clinical decision engine that weighs real "
        "whole-animal survival higher than single petri-dish experiments. Instead of "
        "handing doctors a static list and guessing, our math proves something remarkable: "
        "100% of the uncertainty about which drug is best comes down to that one question "
        "about Copy #2. Better yet, doctors don't have to guess: a single, standard "
        "48-hour lab test on the child's cells — a protein stability blot — captures "
        'nearly 70% of the entire decision value before giving a single dose."',
    )

    s5 = _slide(
        5,
        "1:42 – 2:05 (Tech &amp; Plain)",
        "Clinical Tumor Board Action Card &amp; Paediatric PK/PD Dosing Protocol",
        "Potential Impact (25%)",
        '<div class="content-grid-2">'
        '<div class="panel"><h3><span>Two-State Bayesian VOI Decision Tree '
        '(Entries 161, 163)</span><span class="pill amber">Test Once Before You Treat</span></h3>'
        f'<div class="fig-box"><img src="{u_r4}" alt="Decision tree"/></div></div>'
        '<div class="panel"><h3><span>Paediatric PK/PD Dosing, Liquid Formulations &amp; '
        "Gates (<code>paediatric_pkpd_dosing.tsv</code>)</span>"
        '<span class="pill green">Bedside Ready</span></h3>'
        '<table class="mini-table"><thead><tr><th>Branch &amp; Lead</th>'
        "<th>Paediatric Dose &amp; Formulation</th><th>Tissue PK &amp; Gate</th></tr></thead>"
        "<tbody>"
        '<tr><td><span class="pill green">Unstable (55%)</span><br/><b>Nicotinamide/Niacin</b></td>'
        "<td><b>10–20 mg/kg/d PO</b> BID<br/>Crushable tab / oral liquid</td>"
        "<td>Skeletal muscle + BBB NAD+/SIRT2.<br/><b>Gate:</b> CHX blot + AST/ALT</td></tr>"
        '<tr><td><span class="pill green">Unstable (55%)</span><br/><b>NMN</b> (Overall #1)</td>'
        "<td><b>~32–40 mg/kg/d HED</b><br/>Water-soluble oral powder</td>"
        "<td>Doubles <code>Bub1b<sup>H/H</sup></code> life.<br/><b>Gate:</b> CHX blot+IRB</td></tr>"
        '<tr><td><span class="pill blue">Inactive (45%)</span><br/><b>Dasatinib</b> (#1 Pre)</td>'
        "<td><b>60–85 mg/m²/d PO</b> (NCT00777036)<br/><b>PFOS 10 mg/mL suspension</b></td>"
        "<td>Muscle + CNS penetration.<br/><b>Gate:</b> CHX blot + ECG (QTc) &amp; CBC</td></tr>"
        '<tr><td><span class="pill amber">Tumour D4 (RMS)</span><br/><b>Simva / Lovastatin</b></td>'
        "<td><b>0.2–0.5 mg/kg/d PO</b> (NCT02390843)<br/><b>4 mg/mL strawberry liquid</b></td>"
        "<td>RMS apoptosis (PMID 41249736).<br/><b>Gate:</b> <b>SLCO1B1*5 PGx</b> + CK</td></tr>"
        '<tr><td><span class="pill blue">R2 Backups</span><br/><b>Migalastat / Gliclazide</b></td>'
        "<td><b>2–3 mg/kg QOD</b> / <b>0.5–1 mg/kg/d</b><br/>Dissolved cap / scored tab</td>"
        "<td>+2.7× BubR1 in HCT116.<br/><b>Gate:</b> 24h drug-pulse blot + CGM/eGFR</td></tr>"
        "</tbody></table></div></div>",
        '"Under our calibrated model (w_R2 = 0.25): Before running the blot — and if the '
        "blot shows stable-but-inactive BubR1 — dasatinib (60–85 mg/m²/day paediatric PFOS "
        "suspension, EU = 0.2537) is the #1 FDA-approved candidate. If the blot confirms "
        "unstable BubR1: the Bub1b H/H NAD+/SIRT2 rescue NMN (u = 0.4800) is the #1 overall "
        "compound, oral niacin and nicotinamide (10–20 mg/kg/day, u = 0.1920, supported "
        "across all three iterations) are the #1 FDA-approved drugs, and migalastat and "
        "gliclazide are the top chaperone and proteomic backups. For the presenting "
        'rhabdomyosarcoma, simvastatin and lovastatin (NCT02390843) lead our tumour adjuncts."',
        '"Here is how the care team acts on that 48-hour blot: If the lab test shows the '
        "protein melts away too fast, start with the NAD+ boosters (NMN, niacin, or "
        "nicotinamide in child-friendly liquid form) to stabilize BubR1 via its natural "
        "repair pathway, with migalastat or gliclazide as oral backups. If the lab test "
        "shows the protein is stable but inactive, switch to dasatinib oral suspension to "
        "clear damaged cells. And to help fight the child's muscle tumour directly, pair "
        'standard care with simvastatin or lovastatin liquid suspension."',
    )

    s6 = _slide(
        6,
        "2:05 – 2:40 (Tech &amp; Plain)",
        "First, Do No Harm — 2-Source Per-Child Safety &amp; PGx Callability Honesty",
        "Potential Impact (25%) &amp; Rigor (35%)",
        '<div class="kpi-row">'
        + _kpi("red", "33 / 34 Fail (p=0.0096)", "<b>Do-Not K1:</b> Mps1/Aurora/PLK1 worsen MVA")
        + _kpi("red", "Vincristine Dual-Flag", "<b>Flag K2:</b> CYP3A5 *1/*3 + HP:0003202")
        + _kpi("amber", "Only 1.6% (20 / 1,223)", "<b>Gate K3:</b> Order 5-gene clinical PGx panel")
        + _kpi("purple", "RYR1 p.Arg1679His", "<b>Anaesthesia Alert:</b> Avoid volatile agents")
        + '</div><div class="content-grid-2">'
        '<div class="panel"><h3><span>Published MVA Drug Exposures &amp; Contraindications '
        '(Entry 160)</span><span class="pill red">38 Avoid/Caution Rows</span></h3>'
        f'<div class="fig-box"><img src="{u_r3}" alt="MVA exposures"/></div></div>'
        '<div class="panel"><h3><span>PharmCAT Regional Callability Audit Across 20 '
        'Pharmacogenes (Entry 152)</span><span class="pill amber">1.6% VCF Coverage</span></h3>'
        f'<div class="fig-box"><img src="{u_cov}" alt="PharmCAT coverage"/></div></div></div>',
        "\"Every candidate was audited against the child's own genome and clinical terms. "
        "First, Do-Not K1: across 919 cancer lines, 33 of 34 Mps1/TTK and Aurora kinase "
        "inhibitors are less effective in aneuploid cells (p = 0.0096) and worsen "
        "chromosomal chaos — they are strictly contraindicated. Second, vincristine — a "
        "standard rhabdomyosarcoma backbone drug — is the only medicine flagged by both "
        "safety sources: a CYP3A5 *1/*3 genotype plus an exact drug-label match to the "
        "child's skeletal muscle atrophy (HP:0003202). Third, because the delivered "
        "variant-only VCF covers just 1.6% (20 of 1,223) of PharmCAT loci, we recommend "
        "ordering a 5-gene clinical PGx panel (SLCO1B1, ABCG2, CYP2C9, G6PD, UGT1A1) before "
        'any statin or adjunct therapy, plus anaesthesia precautions for an RYR1 variant."',
        '"For a fragile child, knowing what not to give is just as important as finding a '
        "treatment. First, a common hunch is to use cell-division-blocking cancer drugs. "
        "Our data across 919 cell lines proves the exact opposite: 33 out of 34 drugs in "
        "that class actually work worse in cells like this child's and make chromosome "
        "scrambling worse. Second, by cross-checking the child's DNA and muscle weakness "
        "against drug safety labels, we flagged vincristine — a routine childhood "
        "chemotherapy — as a double-warning risk for severe nerve and muscle toxicity. "
        "And because standard genetic files only cover 1.6% of drug-metabolism spots, we "
        'give the care team an exact 5-gene safety checklist plus an anaesthesia alert."',
    )

    s7 = _slide(
        7,
        "2:40 – 3:00 (Tech &amp; Plain)",
        "Zero-Edit Scalability — Re-Executed on Bloom Syndrome (BLM) in 53 Min for $0",
        "Scalability (15%) &amp; Open Science",
        '<div class="kpi-row">'
        + _kpi("green", "53 Minutes • $0 Cost", "Full run on <b>Bloom Syndrome (BLM)</b> (0 edits)")
        + _kpi("blue", "Top 1.15% MGI Twin", "Matches <b>Blm<sup>tm1Ches</sup></b> (Jaccard=0.095)")
        + _kpi("amber", "522 Provenance Edges", "SHA-256 <code>.provenance.json</code> + DuckDB")
        + _kpi("purple", "Zero Coordinates Leaked", "CI gate + React app (<code>/track2</code>)")
        + '</div><div class="content-grid-2">'
        '<div class="panel"><h3><span>Iteration 4 Generator Transfer to Bloom Syndrome '
        '(Entry 156)</span><span class="pill green">Zero Code Edits</span></h3>'
        f'<div class="fig-box"><img src="{u_blm}" alt="Bloom transfer"/></div></div>'
        '<div class="panel"><h3><span>Iteration 5 Route R1–R3 Case-Card Transfer &amp; '
        'Byte-Identity Check (Entry 162)</span><span class="pill blue">Case Cards</span></h3>'
        f'<div class="fig-box"><img src="{u_s1}" alt="Case card transfer"/></div></div></div>',
        '"Finally, this entire platform is built for any N-of-1 rare disease. We executed '
        "the full chain on a second chromosomal-instability disorder — Bloom syndrome "
        "(BLM) — in 53 minutes on a laptop for $0, matching Blm mice in the top 1.15% of "
        "MGI and generating a disease-specific candidate list (Jaccard = 0.095). Every "
        "script, provenance manifest, and negative result is open and reproducible in our "
        'repository. Thank you."',
        "\"Best of all, we didn't build a one-off script just for this hackathon. We built "
        "a reusable, open-source rare-disease engine. When we pointed it at a completely "
        "different genetic disorder — Bloom syndrome — without changing a single line of "
        "code, it ran in 53 minutes on a standard laptop for $0 and produced a tailored, "
        'safety-checked treatment roadmap. Thank you."',
    )

    body = "\n".join([s1, s2, s3, s4, s5, s6, s7])
    return (
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8"/>\n'
        "<title>MVA Hackathon 2026 — Track 2 Pitch Deck (7 Slides)</title>\n"
        f'<style>{css}</style>\n</head>\n<body>\n<div class="deck">\n{body}\n</div>\n'
        '<div class="controls-bar">'
        '<button onclick="prevSlide()">◀ Prev</button>'
        '<span id="slideIndicator">Slide 1 / 7</span>'
        '<button onclick="nextSlide()">Next ▶</button>'
        '<button onclick="toggleMode()" id="modeBtn">Script: Tech (T)</button>'
        "</div>\n"
        f"<script>{js}</script>\n</body>\n</html>\n"
    )
