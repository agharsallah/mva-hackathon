"""Refresh the Track 2 hero visual and preserved ten-slide interactive deck.

Produces:
- ``figures/it5/r6-pitch-overview.svg`` (+ ``.provenance.json``): 2-panel explanatory figure
  contrasting the two BUB1B alleles, the buried pseudokinase core (RSA < 0.20) vs distal
  Lys668 SIRT2/NAD+ shielding, and the weeks 1–2 research assay decision card.
- ``submissions/track2/iteration-6/pitch-slides.html``: self-contained 16:9 widescreen
  ten-slide deck with embedded research SVGs, keyboard navigation (Arrow keys / Space), and
  toggleable teleprompter (Key 'T': Technical / Plain-English / Hidden for recording).
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from mva.drugs import provenance

ROOT = Path(__file__).resolve().parents[1]
FIG_OUT = ROOT / "figures/it5/r6-pitch-overview.svg"
HTML_OUT = ROOT / "submissions/track2/iteration-6/pitch-slides.html"
ENTRY = (
    "docs/iteration5/step-1/methodology/"
    "163-cross-iteration-synthesis-and-calibrated-decision-analysis.md"
)

_HERO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 540"
  font-family="Inter, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif">
<rect width="1200" height="540" fill="#f8fafc" rx="12"/>
<rect x="20" y="16" width="1160" height="52" rx="8" fill="#0f172a"/>
<text x="38" y="40" font-size="17" font-weight="700" fill="#ffffff">
  MVA Track 2 Unified Synthesis — From Two Broken BUB1B Copies to a 48-Hour Protocol
</text>
<text x="38" y="58" font-size="12" fill="#94a3b8">
  Why Copy #1 cannot rescue the child, why Copy #2 favors distal Lys668 NAD+/SIRT2
  shielding, and how one blot captures 69.1% of EVPI
</text>
<rect x="20" y="82" width="565" height="412" rx="10" fill="#ffffff"
  stroke="#cbd5e1" stroke-width="1.5"/>
<text x="36" y="108" font-size="15" font-weight="700" fill="#0f172a">
  A. The Cell's "Seatbelt Inspector" (BubR1) &amp; 3D Pocket Biophysics
</text>
<rect x="36" y="122" width="533" height="82" rx="8" fill="#fef2f2"
  stroke="#ef4444" stroke-width="1.5"/>
<text x="50" y="144" font-size="13" font-weight="700" fill="#991b1b">
  Copy #1: Premature Stop Sign (stop_gained, in trans) — TORN MANUAL
</text>
<text x="50" y="164" font-size="11.5" fill="#7f1d1d">
  • Triggers NMD mRNA decay &amp; truncates the C-terminal pseudokinase domain
</text>
<text x="50" y="182" font-size="11.5" fill="#7f1d1d">
  • Route R1 Stop-Context Score = 0.33 → readthrough adds &lt;1.5% vs 8.5–28.5% gap (EVPPI=0%)
</text>
<rect x="448" y="132" width="108" height="24" rx="5" fill="#dc2626"/>
<text x="502" y="148" text-anchor="middle" font-size="11" font-weight="700" fill="#ffffff">
  NOT THE LEVER
</text>
<rect x="36" y="216" width="533" height="262" rx="8" fill="#f5f3ff"
  stroke="#7c3aed" stroke-width="1.5"/>
<text x="50" y="238" font-size="13" font-weight="700" fill="#4c1d95">
  Copy #2: Single-Letter Typo in Pseudokinase Core (missense) — THE SOLE LEVER
</text>
<text x="50" y="256" font-size="11.5" fill="#5b21b6">
  • ThermoMPNN ΔΔG = +1.55 kcal/mol (87.3rd pct of 19,950 swaps) • Boltz-2 RMSD = 0.45 Å
</text>
<rect x="50" y="270" width="245" height="192" rx="7" fill="#fff1f2"
  stroke="#f43f5e" stroke-width="1.2"/>
<text x="62" y="292" font-size="12" font-weight="700" fill="#be123c">
  Buried Pseudokinase Core
</text>
<text x="62" y="310" font-size="11" fill="#881337">• 62/285 residues buried (RSA &lt; 0.20)</text>
<text x="62" y="328" font-size="11" fill="#881337">• 72.2% of core swaps ΔΔG ≥ +1.0</text>
<text x="62" y="346" font-size="11" fill="#881337">• Non-catalytic pseudokinase (cd14029)</text>
<text x="62" y="364" font-size="11" fill="#881337">• No open pocket for polar active-site</text>
<text x="62" y="380" font-size="11" fill="#881337">  chaperones (migalastat logP = -2.6)</text>
<rect x="62" y="424" width="220" height="26" rx="5" fill="#ffe4e6"/>
<text x="172" y="441" text-anchor="middle" font-size="10.5" font-weight="700" fill="#9f1239">
  Calibrate R2 Weight w_R2 = 0.25
</text>
<rect x="310" y="270" width="245" height="192" rx="7" fill="#ecfdf5"
  stroke="#10b981" stroke-width="1.5"/>
<text x="322" y="292" font-size="12" font-weight="700" fill="#047857">
  Distal Lys668 Deacetylation Shield
</text>
<text x="322" y="310" font-size="11" fill="#065f46">• Solvent-exposed regulatory Lys668</text>
<text x="322" y="328" font-size="11" fill="#065f46">• NAD+ + SIRT2 deacetylates Lys668</text>
<text x="322" y="346" font-size="11" fill="#065f46">• Blocks ubiquitin-proteasome decay</text>
<text x="322" y="364" font-size="11" fill="#065f46">• Doubles Bub1b^{H/H} mouse survival</text>
<text x="322" y="380" font-size="11" fill="#065f46">  in vivo (PMID 24825348)</text>
<rect x="322" y="424" width="220" height="26" rx="5" fill="#10b981"/>
<text x="432" y="441" text-anchor="middle" font-size="10.5" font-weight="700" fill="#ffffff">
  NMN / Nicotinamide / Niacin
</text>
<rect x="605" y="82" width="575" height="412" rx="10" fill="#ffffff"
  stroke="#cbd5e1" stroke-width="1.5"/>
<text x="621" y="108" font-size="15" font-weight="700" fill="#0f172a">
  B. Clinical Tumor Board Protocol — "Test Once Before You Treat"
</text>
<rect x="621" y="122" width="543" height="68" rx="8" fill="#fefce8"
  stroke="#eab308" stroke-width="1.8"/>
<text x="635" y="143" font-size="13" font-weight="700" fill="#854d0e">
  STEP 1 — Run 48-Hour Cycloheximide-Chase BubR1 Western Blot ($300, Patient vs Parent)
</text>
<text x="635" y="162" font-size="11.5" fill="#713f12">
  • 100% of uncertainty (EVPI = 0.1800) sits on Missense Unstable (55%) vs Inactive (45%)
</text>
<text x="635" y="178" font-size="11.5" fill="#713f12">
  • One 48h blot captures 69.1% of total decision value (EVSI = 0.1245) before dosing
</text>
<rect x="621" y="202" width="264" height="128" rx="8" fill="#ecfdf5"
  stroke="#10b981" stroke-width="1.5"/>
<text x="633" y="222" font-size="12" font-weight="700" fill="#047857">
  IF UNSTABLE (t½ &lt; WT, P=0.55)
</text>
<text x="633" y="241" font-size="11" font-weight="600" fill="#065f46">
  1. Nicotinamide (10–20 mg/kg/d PO)
</text>
<text x="633" y="257" font-size="11" font-weight="600" fill="#065f46">
     or Niacin / NMN (u=0.4800)
</text>
<text x="633" y="275" font-size="10.5" fill="#047857">
     3-iteration consensus NAD+/SIRT2 rescue
</text>
<text x="633" y="294" font-size="11" fill="#065f46">
  2. Backups: Migalastat / Gliclazide
</text>
<text x="633" y="310" font-size="10.5" fill="#047857">
     (+2.7x BubR1 in Gygi-10k; test on blot)
</text>
<rect x="900" y="202" width="264" height="128" rx="8" fill="#eff6ff"
  stroke="#2563eb" stroke-width="1.5"/>
<text x="912" y="222" font-size="12" font-weight="700" fill="#1d4ed8">
  IF INACTIVE (t½ ≈ WT, P=0.45)
</text>
<text x="912" y="241" font-size="11" font-weight="600" fill="#1e3a8a">
  1. Dasatinib (60–85 mg/m²/d PFOS)
</text>
<text x="912" y="257" font-size="10.5" fill="#1e40af">
     • Sole 2-generator survivor (twin|prism)
</text>
<text x="912" y="275" font-size="10.5" fill="#1e40af">
     • #1 pre-test expected utility (EU=0.2537)
</text>
<text x="912" y="293" font-size="10.5" fill="#1e40af">
     • Clears senescent muscle cells + 99.4th
</text>
<text x="912" y="309" font-size="10.5" fill="#1e40af">
       pct aneuploidy lethality (p=0.0096)
</text>
<rect x="621" y="340" width="264" height="140" rx="8" fill="#f0fdf4"
  stroke="#16a34a" stroke-width="1.3"/>
<text x="633" y="360" font-size="12" font-weight="700" fill="#15803d">
  TUMOUR ADJUNCT (Rhabdomyosarcoma)
</text>
<text x="633" y="379" font-size="11" font-weight="600" fill="#166534">
  • Simvastatin / Lovastatin (Rung 5)
</text>
<text x="633" y="396" font-size="10.5" fill="#166534">
    Oral liquid • NCT02390843 + PMID 41249736
</text>
<text x="633" y="416" font-size="10.5" font-weight="600" fill="#b45309">
  • Gate K3: 5-Gene Clinical PGx Panel first
</text>
<text x="633" y="432" font-size="10" fill="#92400e">
    (SLCO1B1*5, ABCG2, CYP2C9, G6PD, UGT1A1;
</text>
<text x="633" y="447" font-size="10" fill="#92400e">
    VCF covers only 20/1,223 = 1.6% PGx loci)
</text>
<rect x="900" y="340" width="264" height="140" rx="8" fill="#fef2f2"
  stroke="#dc2626" stroke-width="1.5"/>
<text x="912" y="360" font-size="12" font-weight="700" fill="#991b1b">
  FIRST, DO NO HARM (38 Flagged)
</text>
<text x="912" y="379" font-size="10.5" font-weight="700" fill="#7f1d1d">
  • DO-NOT K1: 33/34 Mps1/Aurora/PLK1
</text>
<text x="912" y="394" font-size="10" fill="#7f1d1d">
    inhibitors fail in aneuploidy (p=0.0096)
</text>
<text x="912" y="413" font-size="10.5" font-weight="700" fill="#7f1d1d">
  • DOUBLE-FLAG K2: Vincristine
</text>
<text x="912" y="428" font-size="10" fill="#7f1d1d">
    CYP3A5 *1/*3 + HP:0003202 muscle atrophy
</text>
<text x="912" y="447" font-size="10.5" font-weight="700" fill="#7f1d1d">
  • ANAESTHESIA: RYR1 VUS (avoid volatile)
</text>
<text x="24" y="518" font-size="11.5" fill="#475569">
  Legend: Green = actionable therapeutic rescue • Yellow = 48h diagnostic decision gate
  (EVSI = 69.1% of EVPI) • Blue = senolytic lead • Purple = raw input • Red = contraindicated
</text>
</svg>
"""


def build_hero_svg() -> str:
    """Return the 2-panel explanatory SVG string."""
    svg = _HERO_SVG
    for old, new in {
        "48-Hour": "Weeks 1–2",
        "48-hour": "weeks 1–2",
        "48h": "weeks 1–2",
        "10–20 mg/kg/d PO": "research hypothesis",
        "or Niacin / NMN (u=0.4800)": "or Niacin (u=.192); NMN (u=.480)",
        "before dosing": "before preclinical selection",
        "actionable therapeutic rescue": "research hypotheses",
        "Clinical Tumor Board": "Research Triage",
        "+1.47": "+0.22",
        "+1.44": "+0.20",
        "8,793": "875",
        "8793": "875",
        "38942016": "36593396",
        "empirical-Bayes": "robust residual",
    }.items():
        svg = svg.replace(old, new)
    return svg


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()
    FIG_OUT.parent.mkdir(parents=True, exist_ok=True)
    FIG_OUT.write_text(build_hero_svg(), encoding="utf-8")
    inputs = [
        ROOT / "ressources/track2/it5/unified/unified_summary.json",
        ROOT / "ressources/track2/it5/unified/structural_pocket_audit.tsv",
        ROOT / "ressources/track2/it5/unified/paediatric_pkpd_dosing.tsv",
    ]
    manifest = {
        **provenance.envelope(FIG_OUT.stem, "tools/render_track2_pitch_slides.py"),
        "inputs": [
            {"path": provenance.repo_relative(p), "sha256": provenance.digest(p)[0]} for p in inputs
        ],
        "entry": ENTRY,
        "patient_data": "none: mechanism classes, drug names, VOI metrics; no genomic coordinates",
    }
    provenance.write(manifest, FIG_OUT.with_suffix(".provenance.json"))
    # Preserve the final hand-enhanced presentation rather than replace it with
    # the older seven-slide builder (which loses the interactive lineage).
    html = HTML_OUT.read_text(encoding="utf-8")
    for old, new in {
        "8,793": "875",
        "8793": "875",
        "38942016": "36593396",
        "empirical-Bayes": "robust residual",
    }.items():
        html = html.replace(old, new)
    if len(html.splitlines()) < 1000:
        html = subprocess.check_output(
            ["git", "show", "HEAD:submissions/track2/iteration-6/pitch-slides.html"],
            cwd=ROOT,
            text=True,
        )
    for old, new in {
        "0.9122": "0.8738",
        "0.8308": "0.8226",
        "0.8742": "0.8738",
        "0.8208": "0.8226",
        "0.5125": "0.5350",
        "0.4875": "0.4650",
        "Sp=0.90": "Sp=0.85",
        "Sp = 0.90": "Sp = 0.85",
        "0.912": "0.874",
        "0.831": "0.823",
        "0.91": "0.87",
        "0.83": "0.82",
        "522-edge": "recorded",
        "522 lineage edges": "recorded lineage edges",
        "48-hour": "weeks 1–2",
        "48-Hour": "Weeks 1–2",
        "48h": "weeks 1–2",
        "+1.47": "+0.22",
        "+1.44": "+0.20",
        "69.1%": "69.1% nominal",
        "69.1 %": "69.1% nominal",
        "EVPI is 0.18 at every weight": (
            "Joint sensitivity captures half EVPI in 51.38% of 7,425 settings; "
            "EVPI is structurally 0.18 in the original route-only sweep"
        ),
    }.items():
        if old == "69.1%":
            import re

            html = re.sub(r"69\.1%(?! nominal)", new, html)
        else:
            html = html.replace(old, new)
    notice = (
        "<aside style='font-size:10px;padding:8px;background:#fff3cd;color:#222'>"
        "Research triage only: priors, utilities and assay Se=Sp=0.85 are assumptions, "
        "not validated benefit or diagnostic probabilities. P(low)=0.535; P(normal)=0.465; "
        "P(unstable|low)=0.874; P(inactive|normal)=0.823. "
        "EVPI=0.18 is structurally prior(inactive)×0.4; zero readthrough information value "
        "uses strict dosage feasibility prior zero, not context heuristic 0.10. "
        "Primary patient/parental fibroblasts; CHX 0,2,4,8h ±MG132; culture and turnaround "
        "weeks 1–2, not a guaranteed 48h clinical result. "
        "Embedded R4/R5 figures are historical model illustrations; any .90 specificity "
        "or .912/.831 posteriors in them are superseded by this .85-specificity model. "
        "No candidate is a prescription; approval metadata does not establish MVA efficacy."
        " Historical R2 image labels 1.47/1.44 are not raw BUB1B log2FC; "
        "canonical raw values are .22/.20."
        "</aside>"
    )
    update = (
        "<section class='slide' data-slide='8'><h1>Final audit: assumptions and portability</h1>"
        "<h2>Sensitivity is conditional, not confidence</h2>"
        "<p>Joint grid: 3,815/7,425 settings (51.38%) capture ≥50% EVPI. "
        "EVPI .012–.240; blot EVSI 0–.2352. Canonical 69.1% is not universal.</p>"
        "<h2>Third disease: partial real cached-public transfer</h2>"
        "<p>Fanconi/FANCA: 34 public HPO terms; Fanca rank 37/76,699 "
        "(symmetric), 102 (Phenodigm). Raw graph top-50 Jaccard .098901 vs MVA; "
        ".041667 vs Bloom. About 29s cached CPU; no live requests, no fixtures. "
        "No PRISM/LINCS, approval labelling, convergence, safety checks "
        "or therapeutic validation.</p>"
        "<h2>Evidence boundary</h2><p>Eight allele abundance labels; stability AUROC .60 "
        "[.133,1] failed calibration. No measured patient prior or validated assay. "
        "Raw HCT116 10µM 24h BUB1B log2FC: gliclazide +.22, migalastat +.20; "
        "one summary column each. Earlier 1.47/1.44 are not raw BUB1B changes. "
        "No independent candidate replication or validated label expansion found.</p>"
        + notice
        + "</section>"
    )
    # Keep the ten-slide presentation and its fragment/lineage controls intact.
    # The audit is an accessible endnote, not an extra slide with incompatible navigation.
    if "Final audit: assumptions and portability" not in html:
        html = html.replace(
            "</body>", update.replace("class='slide'", "class='audit-note'") + "</body>"
        )
    elif "Historical R2 image labels" not in html:
        html = html.replace("</body>", notice + "</body>")
    HTML_OUT.write_text(html, encoding="utf-8")
    print(f"wrote {FIG_OUT.relative_to(ROOT)}")
    print(f"wrote {HTML_OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
