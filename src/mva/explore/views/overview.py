"""The first screen — headline numbers, graded checks, and where the file came from.

Every established QC tool opens the same way: a row of numbers big enough to read from a
doorway, then a table saying which of them are acceptable. MultiQC calls it the general
statistics table. This is that, with two additions the rest of this toolkit depends on.

The first is that every check states the reasoning behind its band, not just the band, so a
reader with no sequencing background can decide whether to accept the verdict rather than
having to trust it. The second is a provenance block: which reference genome the file was
built against, which caller wrote it, how the chromosomes are named. Those three facts
cause more silent wrong answers in genomics than any statistic, because a coordinate copied
between two incompatible conventions looks perfectly valid and matches nothing.
"""

from ..checks import Check, Verdict, run_checks
from ..figure import Exhibit
from ..profile import CallsetProfile
from ..theme import MACHINE, MUTED, legend_line


def exhibits(profile: CallsetProfile) -> list[Exhibit]:
    """The overview exhibits the profile can actually fill.

    An empty tile row and a check table with no rows are worse than no section at all:
    they read as "nothing is wrong" when they mean "nothing was measured". Each exhibit is
    therefore built only when it has something to say.
    """
    out = []
    tiles = headline(profile)
    if tiles.html:
        out.append(tiles)
    if run_checks(profile):
        out.append(quality_table(profile))
    if profile.header and profile.header.contigs:
        out.append(provenance(profile))
    return out


def headline(profile: CallsetProfile) -> Exhibit:
    """The handful of numbers that describe the whole dataset."""
    graded = {c.name: c for c in run_checks(profile)}
    tiles: list[tuple[str, str, str]] = []

    if profile.total_records:
        tiles.append((f"{profile.total_records:,}", "variants called",
                      "every difference from the reference genome"))
    if "PASS fraction" in graded:
        tiles.append((graded["PASS fraction"].display, "passed the caller's filters",
                      "the rest are a search space, not garbage"))
    if "Estimated raw coverage" in graded:
        tiles.append((graded["Estimated raw coverage"].display, "raw coverage",
                      "times each position was read independently"))
    if profile.total_gigabases:
        tiles.append((f"{profile.total_gigabases:,.0f} Gb", "bases sequenced",
                      f"across {len(profile.reads)} files"))
    if "Transition/transversion ratio" in graded:
        tiles.append((graded["Transition/transversion ratio"].display, "transition/transversion",
                      "about 2.0 means the calls are mostly real"))
    if profile.panel:
        total = sum(g.variants for g in profile.panel)
        tiles.append((f"{total:,}", f"calls in {len(profile.panel)} candidate genes",
                      "where the search starts"))

    if not tiles:
        return Exhibit(slug="headline", title="", caption="", legend="")

    cards = "".join(
        f'<div class="tile"><span class="tile-value">{value}</span>'
        f'<span class="tile-label">{label}</span>'
        f'<span class="tile-hint">{hint}</span></div>'
        for value, label, hint in tiles
    )
    return Exhibit(
        slug="headline",
        title="The dataset in six numbers",
        caption=(
            "What was sequenced, how much of it survived quality control, and how much of "
            "it lands in genes already suspected of causing this condition."
        ),
        legend=legend_line(MACHINE, extra="each tile is a measured value from the profile "
                                          "run, not an estimate"),
        html=f'<div class="tiles">{cards}</div>',
    )


def quality_table(profile: CallsetProfile) -> Exhibit:
    """Every graded metric, with its expected band and the reasoning behind it."""
    checks = run_checks(profile)
    rows = "".join(_row(c) for c in checks)
    actionable = [c for c in checks if c.is_actionable]

    table = (
        '<div class="table-wrap"><table class="checks">'
        "<thead><tr><th>Check</th><th>Measured</th><th>Expected</th>"
        "<th>Verdict</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></div>"
    )
    summary = ""
    if actionable:
        items = "".join(
            f"<li><strong>{c.name}</strong> — {c.consequence or c.expected}</li>"
            for c in actionable
        )
        summary = f'<div class="callout"><p>Worth acting on:</p><ul>{items}</ul></div>'

    return Exhibit(
        slug="quality-checks",
        title="Quality checks",
        caption=(
            "Each number graded against the range a healthy germline whole genome is "
            "expected to fall in. Expand any row for why that range is the right one — the "
            "bands are community conventions and are meant to be argued with, while the "
            "measured values come from executed runs. A yellow verdict is a prompt to look, "
            "never a finding on its own."
        ),
        legend=legend_line(*[v.hue for v in (Verdict.PASS, Verdict.WARN, Verdict.FAIL)],
                           extra="grey is reported without grading"),
        html=table + summary,
    )


def provenance(profile: CallsetProfile) -> Exhibit:
    """Which reference, which caller, which chromosome naming convention.

    The chromosome naming line is the one to read twice. A callset built against a
    ``no_chr`` reference names chromosome 15 as ``15``; most downstream formats and every
    submission template name it ``chr15``. Both are valid, neither is convertible by
    accident, and a tool comparing them by string finds no matches at all while reporting
    no error.
    """
    header = profile.header
    contig_names = [name for name, _ in header.contigs]
    prefixed = sum(1 for n in contig_names if n.startswith("chr"))
    convention = ("chr-prefixed (chr15)" if prefixed > len(contig_names) / 2
                  else "bare (15, no chr prefix)")

    facts = [
        ("Sample column", header.sample or "not declared"),
        ("Reference genome", "<br>".join(header.references) or "not declared"),
        ("Written by", ", ".join(header.sources) or "not declared"),
        ("Contigs declared", f"{len(header.contigs):,}"),
        ("Chromosome naming", f"<strong>{convention}</strong>"),
        ("Annotation fields", ", ".join(
            f"{kind} ×{len(items)}" for kind, items in sorted(header.fields.items()))),
    ]
    rows = "".join(f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in facts)

    return Exhibit(
        slug="provenance",
        title="Where this file came from",
        caption=(
            "A variant file is a set of coordinates, and a coordinate only means something "
            "against the reference genome it was measured on. These six facts decide "
            "whether a position from this file can be compared to a position from anywhere "
            "else — and a mismatch produces silence, not an error."
        ),
        legend=legend_line(MUTED, extra="every value is copied verbatim from the file's own "
                                        "header"),
        html=f'<div class="table-wrap"><table class="facts"><tbody>{rows}</tbody></table></div>',
    )


def _row(check: Check) -> str:
    hue = check.verdict.hue
    badge = (f'<span class="badge" style="background:{hue.fill};'
             f'border-color:{hue.line};color:{hue.line}">{check.verdict.value}</span>')
    reasoning = check.basis + (f" <em>{check.consequence}</em>" if check.consequence else "")
    return (
        f"<tr><td><details><summary>{check.name}</summary>"
        f'<p class="reasoning">{reasoning}</p></details></td>'
        f'<td class="numeric">{check.display}</td>'
        f"<td>{check.expected}</td><td>{badge}</td></tr>"
    )
