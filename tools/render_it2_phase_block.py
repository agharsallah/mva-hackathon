#!/usr/bin/env python3
"""The lead gene's phasing, drawn: exons on a rule, heterozygous sites, and the gaps.

**What phasing is, in one paragraph.** Two different broken copies of the same gene, one
inherited from each parent, is a *compound heterozygote* — and it is the thing this case is
looking for. A caller that reports two heterozygous alleles in a gene cannot say whether
they sit on the same copy (one broken copy, one intact — not a diagnosis) or on opposite
copies (both copies broken — a diagnosis). Read-backed phasing (**WhatsHap**) answers that
only where a single read or fragment spans both sites. Where no fragment bridges them, the
answer is not "same copy" or "opposite copies": it is **unknown**, and that gap is the
result H019 was written about.

So the exhibit draws the gap rather than describing it: a **phase block** is a run of sites
WhatsHap could connect, and the red stretches between blocks are where the chain breaks.

**Every number on this figure is an offset**, in bases, from the start of the gene's baited
window — never a position in GRCh38. The window, the exons, the sites and the blocks all
come from ``analysis.json``'s ``phase_track`` block, which
``tools/export_it2_step2_analysis.py`` computes as offsets inside the database.

Usage::

    uv run python tools/render_it2_phase_block.py
    uv run python tools/render_it2_phase_block.py --analysis build/it2/step-2/analysis.json
"""

from __future__ import annotations

import argparse
import json
import sys
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mva.render import theme
from mva.render.figure import Exhibit

DEFAULT_ANALYSIS = Path("build/it2/step-2/analysis.json")
DEFAULT_OUT = Path("figures/track1/iteration2/step-2")

#: Drawing box. Fixed rather than responsive: the SVG is embedded in a report page and in
#: the dashboard, and a fixed viewBox scales cleanly in both.
WIDTH, HEIGHT = 1100, 300
LEFT, RIGHT = 150, 40

#: Baseline of each lane, top to bottom.
LANE_EXONS, LANE_SITES, LANE_BLOCKS = 74, 138, 196
LANE_HEIGHT = 22

#: An exon narrower than this many pixels is still drawn this wide, so a 50 bp first exon
#: does not vanish from a 160 kb rule. The figure is about *where*, not about exon size.
MIN_MARK_PX = 2.0


def _scale(span: int):
    usable = WIDTH - LEFT - RIGHT

    def at(offset: float) -> float:
        return LEFT + usable * (offset / span if span else 0.0)

    return at, usable


def _rect(x: float, y: float, w: float, h: float, hue: theme.Hue, title: str) -> str:
    return (
        f'<rect x="{x:.1f}" y="{y}" width="{max(w, MIN_MARK_PX):.1f}" height="{h}" '
        f'fill="{hue.fill}" stroke="{hue.line}" stroke-width="1" rx="1">'
        f"<title>{escape(title)}</title></rect>"
    )


def _label(x: float, y: float, text: str, size: int = 12, anchor: str = "end") -> str:
    return (
        f'<text x="{x:.1f}" y="{y}" font-family="{theme.FONT}" font-size="{size}" '
        f'fill="{theme.SUBTLE_INK}" text-anchor="{anchor}">{escape(text)}</text>'
    )


def _gaps(blocks: list[dict], lo: int, hi: int) -> list[tuple[int, int]]:
    """The stretches inside ``[lo, hi)`` that no phase block covers.

    Computed from the blocks rather than read from a table, because "unphased" is defined
    as the complement of what WhatsHap connected and nothing writes that complement down.
    """
    covered = sorted(
        (max(lo, b["at"]), min(hi, b["at"] + b["width"]))
        for b in blocks
        if b["at"] < hi and b["at"] + b["width"] > lo
    )
    out: list[tuple[int, int]] = []
    cursor = lo
    for start, end in covered:
        if start > cursor:
            out.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < hi:
        out.append((cursor, hi))
    return out


def build_svg(track: dict) -> str:
    """The whole exhibit as one standalone SVG string."""
    span = int(track["span"])
    at, usable = _scale(span)
    coding = track["coding"]
    c_lo, c_hi = int(coding["at"]), int(coding["at"] + coding["width"])
    gaps = _gaps(track["blocks"], c_lo, c_hi)
    widest = max(gaps, key=lambda g: g[1] - g[0], default=(0, 0))

    opening = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" '
        f'width="{WIDTH}" height="{HEIGHT}" role="img">'
    )
    title = (
        f'<text x="{LEFT}" y="30" font-family="{theme.FONT}" font-size="16" '
        f'fill="{theme.INK}">{escape(track["gene"])} — what the reads could and could not '
        f"phase</text>"
    )
    parts = [
        opening,
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="{theme.PAPER}"/>',
        title,
    ]

    # The coding span, shaded behind every lane, so the eye can tell gene body from padding.
    parts.append(
        f'<rect x="{at(c_lo):.1f}" y="{LANE_EXONS - 14}" width="{at(c_hi) - at(c_lo):.1f}" '
        f'height="{LANE_BLOCKS + LANE_HEIGHT + 6 - LANE_EXONS + 14}" fill="#f7f9fc" '
        f'stroke="{theme.GRID}" stroke-dasharray="3 3"/>'
    )
    parts.append(
        _label(
            (at(c_lo) + at(c_hi)) / 2,
            LANE_EXONS - 20,
            "coding span",
            size=11,
            anchor="middle",
        )
    )

    # Lane 1 — the exons, on their rule.
    parts.append(
        f'<line x1="{LEFT}" y1="{LANE_EXONS + LANE_HEIGHT / 2}" x2="{WIDTH - RIGHT}" '
        f'y2="{LANE_EXONS + LANE_HEIGHT / 2}" stroke="{theme.MUTED.line}" stroke-width="1"/>'
    )
    for index, exon in enumerate(track["exons"], start=1):
        parts.append(
            _rect(
                at(exon["at"]),
                LANE_EXONS,
                at(exon["at"] + exon["width"]) - at(exon["at"]),
                LANE_HEIGHT,
                theme.GOOD,
                f"coding exon {index} of {len(track['exons'])}, {exon['width']} bp",
            )
        )
    parts.append(_label(LEFT - 12, LANE_EXONS + 16, f"coding exons ({len(track['exons'])})"))

    # Lane 2 — every heterozygous site the two callers agreed was heterozygous.
    for site in track["het_sites"]:
        x = at(site)
        parts.append(
            f'<line x1="{x:.1f}" y1="{LANE_SITES}" x2="{x:.1f}" '
            f'y2="{LANE_SITES + LANE_HEIGHT}" stroke="{theme.RAW.line}" stroke-width="1.2">'
            f"<title>heterozygous site at +{site:,} bp</title></line>"
        )
    parts.append(
        _label(LEFT - 12, LANE_SITES + 16, f"heterozygous sites ({len(track['het_sites'])})")
    )

    # Lane 3 — the blocks WhatsHap connected, and the stretches it could not.
    for lo, hi in gaps:
        parts.append(
            _rect(
                at(lo),
                LANE_BLOCKS,
                at(hi) - at(lo),
                LANE_HEIGHT,
                theme.BAD,
                f"unphased: {hi - lo:,} bp with no block spanning it",
            )
        )
    parts.extend(
        _rect(
            at(block["at"]),
            LANE_BLOCKS,
            at(block["at"] + block["width"]) - at(block["at"]),
            LANE_HEIGHT,
            theme.MACHINE,
            f"phase block, {block['width']:,} bp, {block['variants']} variants",
        )
        for block in track["blocks"]
    )
    parts.append(_label(LEFT - 12, LANE_BLOCKS + 16, f"phase blocks ({len(track['blocks'])})"))
    if widest[1] > widest[0]:
        mid = (at(widest[0]) + at(widest[1])) / 2
        parts.append(
            _label(
                mid,
                LANE_BLOCKS + LANE_HEIGHT + 15,
                f"widest unphased stretch inside the gene: {widest[1] - widest[0]:,} bp",
                size=11,
                anchor="middle",
            )
        )

    # The rule's own ticks, in offsets from the window start.
    axis_y = HEIGHT - 22
    parts.append(
        f'<line x1="{LEFT}" y1="{axis_y}" x2="{WIDTH - RIGHT}" y2="{axis_y}" '
        f'stroke="{theme.GRID}"/>'
    )
    for fraction in (0.0, 0.25, 0.5, 0.75, 1.0):
        x = LEFT + usable * fraction
        offset = int(span * fraction)
        parts.append(
            f'<line x1="{x:.1f}" y1="{axis_y}" x2="{x:.1f}" y2="{axis_y + 4}" '
            f'stroke="{theme.GRID}"/>'
        )
        parts.append(_label(x, axis_y + 17, f"+{offset:,}", size=10, anchor="middle"))
    parts.append(_label(LEFT - 12, axis_y + 17, "offset (bp)", size=10))
    parts.append(
        _label(
            WIDTH - RIGHT,
            axis_y - 6,
            "distance from the start of the baited window — never a genomic position",
            size=10,
            anchor="end",
        )
    )
    parts.append("</svg>")
    return "".join(parts)


def phase_exhibit(track: dict) -> Exhibit:
    """The SVG plus the caption and legend the repository requires it to carry."""
    coding = track["coding"]
    gaps = _gaps(track["blocks"], int(coding["at"]), int(coding["at"] + coding["width"]))
    widest = max((hi - lo for lo, hi in gaps), default=0)
    inside = [
        block
        for block in track["blocks"]
        if block["at"] < coding["at"] + coding["width"]
        and block["at"] + block["width"] > coding["at"]
    ]
    return Exhibit(
        slug=f"phase-{track['gene'].lower()}",
        title=f"{track['gene']} — where the reads could join two alleles, and where they could not",
        caption=(
            f"{len(track['het_sites'])} heterozygous sites across the baited window, "
            f"{len(track['blocks'])} read-backed phase blocks, {len(inside)} of them "
            f"touching the coding span. The widest stretch inside the gene that **no** "
            f"block spans is {widest:,} bp — two heterozygous alleles either side of it "
            "cannot be assigned to the same copy or to opposite copies by these reads. "
            "That is the gap H019 predicted the step would either close or name; it named "
            "it. Positions are offsets from the window's own start."
        ),
        legend=theme.legend_line(
            theme.GOOD,
            theme.RAW,
            theme.MACHINE,
            theme.BAD,
            extra=(
                "**green** = coding exons on the rule, **purple ticks** = heterozygous "
                "sites, **blue** = a phase block, **red** = an unphased stretch inside the "
                "coding span, **grey dashed box** = the coding span inside the padded "
                "baited window."
            ),
        ),
        html=build_svg(track),
        height=HEIGHT,
        notes=[
            (
                "Short-read phasing reaches only as far as one fragment. A gap here is a "
                "limit of the instrument, not evidence that the two alleles sit on the "
                "same copy — the distinction step 6 has to carry."
            ),
        ],
    )


def load_track(analysis: Path) -> dict | None:
    if not analysis.exists():
        return None
    rows = json.loads(analysis.read_text(encoding="utf-8")).get("phase_track") or []
    track = rows[0] if rows else None
    return track if track and track.get("found") else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--analysis", type=Path, default=DEFAULT_ANALYSIS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    track = load_track(args.analysis)
    if track is None:
        print(f"no phase_track in {args.analysis} — run tools/export_it2_step2_analysis.py")
        return 1
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"phase-{track['gene'].lower()}.svg"
    path.write_text(build_svg(track), encoding="utf-8")
    print(f"  {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
