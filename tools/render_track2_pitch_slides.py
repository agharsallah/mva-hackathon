"""Render the Track 2 3-minute pitch hero visual and 7-slide interactive/PDF deck.

Produces:
- ``figures/it5/r6-pitch-overview.svg`` (+ ``.provenance.json``): 2-panel explanatory figure
  contrasting the two BUB1B alleles, the buried pseudokinase core (RSA < 0.20) vs distal
  Lys668 SIRT2/NAD+ shielding, and the 48-hour CHX-chase blot clinical decision card.
- ``submissions/track2/iteration-6/pitch-slides.html``: self-contained 16:9 widescreen
  7-slide deck with embedded research SVGs, keyboard navigation (Arrow keys / Space), and
  toggleable teleprompter (Key 'T': Technical / Plain-English / Hidden for recording).
"""

from __future__ import annotations

from pathlib import Path

from mva.drugs import provenance
from mva.drugs.pitch_deck import build_slides_html

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


_DECK_CSS = (
    ":root{--green:#059669;--green-bg:#ecfdf5;--red:#dc2626;--red-bg:#fef2f2;--amber:#d97706;"
    "--amber-bg:#fefce8;--blue:#2563eb;--blue-bg:#eff6ff;--purple:#7c3aed;--purple-bg:#f5f3ff;}"
    "*{box-sizing:border-box;margin:0;padding:0;}"
    'body{font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;'
    "background:#090d16;color:#0f172a;overflow:hidden;}"
    ".deck{width:100vw;height:100vh;display:flex;align-items:center;justify-content:center;}"
    ".slide{display:none;width:1280px;height:720px;background:#f8fafc;border-radius:12px;"
    "box-shadow:0 25px 60px rgba(0,0,0,0.55);padding:18px 26px 14px 26px;"
    "flex-direction:column;justify-content:space-between;position:relative;overflow:hidden;}"
    ".slide.active{display:flex;}"
    ".topbar{display:flex;align-items:center;justify-content:space-between;background:#0f172a;"
    "color:#fff;padding:9px 16px;border-radius:8px;}"
    ".topbar-left{display:flex;align-items:center;gap:10px;}"
    ".slide-badge{background:#2563eb;color:#fff;font-weight:800;font-size:11.5px;"
    "padding:4px 10px;border-radius:999px;}"
    ".time-badge{background:#1e293b;color:#38bdf8;font-weight:700;font-size:11.5px;"
    "padding:4px 10px;border-radius:999px;border:1px solid #334155;}"
    ".crit-badge{background:#065f46;color:#a7f3d0;font-weight:700;font-size:11px;"
    "padding:4px 10px;border-radius:999px;}"
    ".slide-title{font-size:16px;font-weight:800;color:#ffffff;}"
    ".content-grid-2{display:grid;grid-template-columns:1.04fr 0.96fr;gap:14px;flex:1;"
    "margin:10px 0;min-height:0;}"
    ".panel{background:#ffffff;border:1.5px solid #cbd5e1;border-radius:10px;padding:10px 12px;"
    "display:flex;flex-direction:column;justify-content:space-between;min-height:0;}"
    ".panel h3{font-size:13px;font-weight:800;color:#0f172a;margin-bottom:5px;display:flex;"
    "align-items:center;justify-content:space-between;}"
    ".fig-box{flex:1;display:flex;align-items:center;justify-content:center;"
    "overflow:hidden;min-height:0;}"
    ".fig-box img{max-width:100%;max-height:100%;object-fit:contain;}"
    ".kpi-row{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:8px;}"
    ".kpi{border-radius:8px;padding:7px 10px;border:1.5px solid #cbd5e1;background:#fff;}"
    ".kpi.green{background:var(--green-bg);border-color:var(--green);}"
    ".kpi.red{background:var(--red-bg);border-color:var(--red);}"
    ".kpi.amber{background:var(--amber-bg);border-color:var(--amber);}"
    ".kpi.blue{background:var(--blue-bg);border-color:var(--blue);}"
    ".kpi.purple{background:var(--purple-bg);border-color:var(--purple);}"
    ".kpi-val{font-size:15px;font-weight:800;color:#0f172a;}"
    ".kpi-lbl{font-size:10.8px;color:#334155;margin-top:2px;line-height:1.25;}"
    ".mini-table{width:100%;border-collapse:collapse;font-size:10.8px;}"
    ".mini-table th{background:#0f172a;color:#fff;text-align:left;padding:5px 6px;font-weight:700;}"
    ".mini-table td{padding:5px 6px;border-bottom:1px solid #e2e8f0;"
    "vertical-align:top;line-height:1.28;}"
    ".pill{display:inline-block;padding:1px 6px;border-radius:4px;font-weight:700;font-size:9.8px;}"
    ".pill.green{background:#d1fae5;color:#065f46;}.pill.red{background:#fee2e2;color:#991b1b;}"
    ".pill.amber{background:#fef3c7;color:#92400e;}.pill.blue{background:#dbeafe;color:#1e40af;}"
    ".teleprompter{background:#0f172a;color:#f8fafc;border-radius:8px;padding:8px 13px;"
    "font-size:11.8px;line-height:1.38;border-left:5px solid #38bdf8;}"
    ".teleprompter.hidden{display:none;}"
    ".tp-mode{font-size:9.8px;font-weight:800;text-transform:uppercase;color:#38bdf8;"
    "margin-bottom:2px;display:flex;justify-content:space-between;}"
    ".controls-bar{position:fixed;bottom:8px;right:14px;background:rgba(15,23,42,0.92);"
    "color:#cbd5e1;padding:5px 10px;border-radius:999px;font-size:11px;display:flex;gap:8px;"
    "align-items:center;z-index:100;border:1px solid #334155;}"
    ".controls-bar button{background:#1e293b;color:#fff;border:1px solid #475569;border-radius:6px;"
    "padding:2px 8px;font-size:11px;cursor:pointer;font-weight:600;}"
    "@media print{@page{size:1280px 720px;margin:0;}body{background:#fff;overflow:visible;}"
    ".deck{display:block;width:auto;height:auto;}.slide{display:flex!important;"
    "page-break-after:always;box-shadow:none;border-radius:0;width:1280px;height:720px;}"
    ".controls-bar{display:none!important;}}"
)

_DECK_JS = (
    "let cur=0,mode=0;"
    "const slides=Array.from(document.querySelectorAll('.slide'));"
    "const ind=document.getElementById('slideIndicator');"
    "const modeBtn=document.getElementById('modeBtn');"
    "function showSlide(idx){cur=Math.max(0,Math.min(slides.length-1,idx));"
    "slides.forEach((s,i)=>s.classList.toggle('active',i===cur));"
    "ind.textContent=`Slide ${cur+1} / ${slides.length}`;}"
    "function nextSlide(){showSlide(cur+1);}function prevSlide(){showSlide(cur-1);}"
    "function toggleMode(){mode=(mode+1)%3;"
    "const tps=document.querySelectorAll('.teleprompter');"
    "const techs=document.querySelectorAll('.tp-tech');"
    "const plains=document.querySelectorAll('.tp-plain');"
    "const labels=document.querySelectorAll('.tp-label');"
    "if(mode===0){tps.forEach(el=>el.classList.remove('hidden'));"
    "techs.forEach(el=>el.style.display='block');plains.forEach(el=>el.style.display='none');"
    "labels.forEach(el=>el.textContent='SPEAKER SCRIPT — VERSION A (TECHNICAL)');"
    "modeBtn.textContent='Script: Tech (T)';}else if(mode===1){"
    "tps.forEach(el=>el.classList.remove('hidden'));"
    "techs.forEach(el=>el.style.display='none');plains.forEach(el=>el.style.display='block');"
    "labels.forEach(el=>el.textContent='SPEAKER SCRIPT — VERSION B (PLAIN-ENGLISH)');"
    "modeBtn.textContent='Script: Plain (T)';}else{"
    "tps.forEach(el=>el.classList.add('hidden'));modeBtn.textContent='Script: Hidden (T)';}}"
    "document.addEventListener('keydown',(e)=>{"
    "if(e.key==='ArrowRight'||e.key===' '||e.key==='PageDown'){e.preventDefault();nextSlide();}"
    "else if(e.key==='ArrowLeft'||e.key==='PageUp'){e.preventDefault();prevSlide();}"
    "else if(e.key==='t'||e.key==='T'){e.preventDefault();toggleMode();}});"
)


def build_hero_svg() -> str:
    """Return the 2-panel explanatory SVG string."""
    return _HERO_SVG


def main() -> int:
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
    HTML_OUT.write_text(build_slides_html(ROOT, css=_DECK_CSS, js=_DECK_JS), encoding="utf-8")
    print(f"wrote {FIG_OUT.relative_to(ROOT)}")
    print(f"wrote {HTML_OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
