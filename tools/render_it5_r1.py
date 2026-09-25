#!/usr/bin/env python3
"""Iteration 5, route R1, in four figures.

(a) ``r1-stop-anatomy`` - the transcript as an exon track: which exon carries the premature
    stop, how far it sits from the last exon-exon junction against the 50-55 nt rule that
    decides nonsense-mediated decay, and which protein domains the truncation loses.
(b) ``r1-control`` - the declared positive control, per compound: held-out rank correlation on
    the named benchmark panel and on a random 20 % of contexts, against the pass bar, with the
    dataset's own no-drug column as the negative control.
(c) ``r1-plus4`` - why this child's stop is a hard one: predicted readthrough for UGA by the +4
    base, per compound, with the child's base marked.
(d) ``r1-dosage`` - working BubR1 per scenario against the published genotypes, showing how
    little the stop allele can contribute.

Inputs: ``build/it5/r1/{stop_facts,controls}.json`` (gitignored) and the route's own tables.

    uv run python tools/render_it5_r1.py

Outputs ``figures/it5/r1-*.{svg,html}`` and one ``.provenance.json`` each.
"""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import plotly.graph_objects as go

from mva.drugs import provenance
from mva.drugs.readthrough import ReadthroughModel
from mva.drugs.readthrough_dataset import TOLEDANO_2024, load_wide
from mva.render.theme import BAD, DECISION, GOOD, MACHINE, MUTED, RAW, install_template

ENTRY = "docs/iteration5/step-1/work/r1-entry.md"
BUILD = Path("build/it5/r1")
TABLES = Path("ressources/track2/it5")
OUT = Path("figures/it5")


def _write(
    fig: go.Figure, name: str, size: tuple[int, int], inputs: list[Path], legend: str
) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    svg = OUT / f"{name}.svg"
    fig.write_image(svg, format="svg", width=size[0], height=size[1])
    fig.write_html(svg.with_suffix(".html"), include_plotlyjs="cdn", full_html=True)
    manifest = {
        "name": name,
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "built_by": "tools/render_it5_r1.py",
        "code_version": provenance.code_version(),
        "inputs": [
            {"path": p.as_posix(), "sha256": provenance.digest(p)[0]} for p in inputs if p.is_file()
        ],
        "entry": ENTRY,
        "legend": legend,
        "patient_data": (
            "none. Exon indices, counts, fractions, codon identities and public measurements; "
            "no genomic position and no run of patient sequence appears"
        ),
    }
    svg.with_suffix(".provenance.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {svg}\n  {legend}\n")


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def _facts() -> dict[str, Any]:
    return json.loads((BUILD / "stop_facts.json").read_text(encoding="utf-8"))


def stop_anatomy() -> None:
    """The exon track, the NMD rule, and the domains the truncation takes with it."""
    facts = _facts()
    exons, stop_exon = facts["exons_total"], facts["nmd"]["exon_index"]
    length, kept = facts["protein_length_aa"], facts["truncation"]["residues_kept"]
    fig = go.Figure()
    for index in range(1, exons + 1):
        after_stop = index > stop_exon
        fig.add_shape(
            type="rect",
            x0=index - 0.42,
            x1=index + 0.42,
            y0=0.6,
            y1=1.4,
            line={"color": MUTED.line, "width": 1},
            fillcolor=BAD.fill
            if after_stop
            else (DECISION.fill if index == stop_exon else RAW.fill),
        )
    fig.add_annotation(
        x=stop_exon,
        y=1.85,
        text=f"premature stop ({facts['stop']['rna_stop']}, +4 {facts['stop']['plus4'].upper()})"
        f"<br>exon {stop_exon} of {exons}",
        showarrow=True,
        arrowhead=2,
        ay=-30,
        font={"size": 12, "color": BAD.line},
    )
    fig.add_annotation(
        x=exons - 0.5,
        y=0.45,
        text=f"last exon-exon junction<br>{facts['nmd']['nt_to_last_junction']} nt downstream "
        f"of the stop, {facts['nmd']['junctions_downstream']} junctions after it",
        showarrow=True,
        arrowhead=2,
        ay=55,
        font={"size": 11, "color": MACHINE.line},
    )
    fig.add_annotation(
        x=(1 + exons) / 2,
        y=-0.85,
        text=(
            f"<b>NMD-competent</b>: the stop is more than {facts['nmd']['rule_nt']} nt upstream "
            f"of the last junction, so the message is destroyed<br>"
            f"<b>{kept} of {length} residues</b> would survive translation "
            f"({100 * facts['truncation']['fraction_lost']:.1f} % of the protein lost), "
            f"including all of: {', '.join(facts['truncation']['domains_lost'])}"
        ),
        showarrow=False,
        font={"size": 12},
    )
    fig.update_xaxes(
        title="exon (transcript order)", range=[0.2, exons + 0.8], dtick=2, showgrid=False
    )
    fig.update_yaxes(visible=False, range=[-1.4, 2.3])
    fig.update_layout(
        title="The stop allele's anatomy: exon, decay verdict, and what is lost",
        height=380,
        margin={"t": 60, "b": 110},
    )
    _write(
        fig,
        "r1-stop-anatomy",
        (1000, 380),
        [BUILD / "stop_facts.json"],
        "purple = coding exons before the stop; yellow = the exon carrying the stop (the "
        "decision point for the 50-55 nt rule); red = the exons the truncated protein never "
        "reaches; blue text = the junction the rule is measured against",
    )


def control() -> None:
    """Held-out rank correlation per compound, on both declared controls."""
    recorded = json.loads((BUILD / "controls.json").read_text(encoding="utf-8"))
    bar = recorded["bar"]["min_spearman"]
    drugs = sorted(
        recorded["controls"]["panel"]["drugs"],
        key=lambda d: -(recorded["controls"]["panel"]["drugs"][d]["spearman"] or 0),
    )
    fig = go.Figure()
    for name, hue, label in (
        ("panel", MACHINE, "named benchmark panel (14 contexts)"),
        ("random20", GOOD, "random 20 % of contexts"),
    ):
        cells = recorded["controls"][name]["drugs"]
        fig.add_bar(
            x=drugs,
            y=[cells[d]["spearman"] for d in drugs],
            name=label,
            marker_color=hue.fill,
            marker_line={"color": hue.line, "width": 1},
            text=[f"{cells[d]['spearman']:.2f}" for d in drugs],
            textposition="outside",
        )
    fig.add_hline(
        y=bar,
        line={"color": DECISION.line, "dash": "dash"},
        annotation_text=f"pass bar, declared before the run: rho = {bar}",
        annotation_position="top left",
    )
    fig.add_annotation(
        x="Untreated",
        y=0.06,
        text="negative control:<br>no drug, no signal",
        showarrow=True,
        arrowhead=2,
        ay=-55,
        font={"size": 11, "color": BAD.line},
    )
    fig.update_yaxes(title="Spearman rho, predicted vs measured on held-out contexts", range=[0, 1])
    fig.update_layout(
        title="The positive control: does stop context predict readthrough for this compound?",
        height=460,
        barmode="group",
        legend={"orientation": "h", "y": 1.12},
    )
    _write(
        fig,
        "r1-control",
        (980, 460),
        [BUILD / "controls.json"],
        "blue = the named benchmark panel, the declared primary control; green = the random "
        "held-out fifth; yellow dashed = the pass bar fixed before the run; the red note marks "
        "the dataset's own no-drug column, which must fail and does",
    )


def plus4(measurements: Path) -> None:
    """Predicted UGA readthrough by the +4 base, per compound, with this child's base marked."""
    facts = _facts()
    model = ReadthroughModel(load_wide(measurements, TOLEDANO_2024))
    child = facts["stop"]["plus4"].upper().replace("T", "U")
    bases = ("C", "U", "A", "G")
    drugs = [d for d in model.drugs if d != "Untreated"]
    fig = go.Figure()
    for base in bases:
        values = [model.predict(drug, "UGA", base).value or 0.0 for drug in drugs]
        hue = BAD if base == child else MACHINE
        fig.add_bar(
            x=drugs,
            y=values,
            name=f"+4 {base}" + ("  (this child)" if base == child else ""),
            marker_color=hue.line if base == child else hue.fill,
            marker_line={"color": hue.line, "width": 1},
        )
    floor = model.predict("Untreated", "UGA", child).value or 0.0
    fig.add_hline(
        y=floor,
        line={"color": MUTED.line, "dash": "dot"},
        annotation_text=f"assay floor (no drug): {floor:.2f} %",
    )
    fig.update_yaxes(title="predicted readthrough, % of the no-PTC control")
    fig.update_layout(
        title="The +4 base decides which compound is worth anything for this stop",
        height=460,
        barmode="group",
        legend={"orientation": "h", "y": 1.12},
    )
    _write(
        fig,
        "r1-plus4",
        (980, 460),
        [measurements],
        "red = the +4 base this child's stop actually has; blue = the three bases it does not; "
        "grey dotted = the assay's no-drug floor, below which a prediction is noise",
    )


def dosage() -> None:
    """Working BubR1 per scenario, against the published genotypes that bracket it."""
    rows = _rows(TABLES / "allele_dosage.tsv")
    rows = [r for r in rows if r["scenario"] != "wild type"]
    labels = [r["scenario"] for r in rows][::-1]
    totals = [float(r["total_pct_of_wild_type"]) for r in rows][::-1]
    treated = [r["drug"] != "none" for r in rows][::-1]
    fig = go.Figure()
    fig.add_bar(
        x=totals,
        y=labels,
        orientation="h",
        marker_color=[GOOD.fill if t else MACHINE.fill for t in treated],
        marker_line={"color": MUTED.line, "width": 1},
        text=[f"{v:.2f} %" for v in totals],
        textposition="outside",
    )
    for value, text, hue in (
        (13.0, "segregation fidelity near normal (~13 %)", GOOD),
        (10.0, "mouse hypomorph H/H (~10 %)", DECISION),
        (6.0, "majority mis-segregation (~6 %)", BAD),
        (4.5, "mouse -/H, neonatal death (~4.5 %)", BAD),
    ):
        fig.add_vline(
            x=value,
            line={"color": hue.line, "dash": "dash", "width": 1},
            annotation_text=text,
            annotation_textangle=-90,
            annotation_font={"size": 9},
        )
    fig.update_xaxes(title="working BubR1, % of the wild-type diploid level", range=[0, 55])
    fig.update_layout(
        title="What each lever is worth: readthrough moves the total by fractions of a point",
        height=520,
        margin={"l": 380},
    )
    _write(
        fig,
        "r1-dosage",
        (1120, 520),
        [TABLES / "allele_dosage.tsv"],
        "green bars = scenarios with a treatment; blue bars = untreated states; dashed lines = "
        "published genotypes and cell measurements used as yardsticks (green = safe side, "
        "yellow = the viable hypomorph, red = the failing side)",
    )


def main() -> None:
    install_template()
    measurements = BUILD / "toledano_ptc.tsv"
    stop_anatomy()
    control()
    if measurements.is_file():
        plus4(measurements)
    else:
        print(f"skipped r1-plus4: {measurements} missing (run it5_readthrough.py dataset)")
    dosage()


if __name__ == "__main__":
    main()
