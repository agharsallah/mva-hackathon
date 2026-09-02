"""Command line for the exploration toolkit.

Four verbs, each answering one question without needing the others:

``report``
    Build the full interactive page from a profile directory.
``checks``
    Print the graded metrics to the terminal. Seconds, no browser, no output files — the
    command to run while a pipeline is being debugged.
``locus``
    Build the locus browser over a real VCF: variant track, phase groups, and the
    classified pair matrix for one region.
``export``
    Write every exhibit as its own file, for pasting a single figure into a document.

``locus`` is the only verb that reads patient records, and it writes wherever it is told
to — keep its output outside the repository.
"""

import argparse
import sys
from pathlib import Path

from . import install_template
from .checks import Verdict, run_checks
from .figure import Section
from .profile import CallsetProfile, ProfileLayout
from .report import LOCUS_BLURB, export_exhibits, render, write_report
from .views import build_sections
from .views import locus as locus_views

#: Terminal colours for the verdict column, and the plain fallback when piped to a file.
ANSI = {
    Verdict.PASS: "\033[32m",
    Verdict.WARN: "\033[33m",
    Verdict.FAIL: "\033[31m",
    Verdict.INFO: "\033[36m",
}
RESET = "\033[0m"


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns a process exit code."""
    install_template()
    parser = _parser()
    args = parser.parse_args(argv)
    if not getattr(args, "handler", None):
        parser.print_help()
        return 1
    return args.handler(args)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mva-explore",
        description="Explore and visualise a genomic callset profile.",
    )
    subparsers = parser.add_subparsers()

    report = subparsers.add_parser(
        "report", help="build the full interactive HTML report from a profile directory"
    )
    report.add_argument("directory", type=Path, help="a profile directory")
    report.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("figures/explore-report.html"),
        help="where to write the page (default: %(default)s)",
    )
    report.add_argument(
        "-t", "--title", default="Callset exploration", help="page title (default: %(default)s)"
    )
    report.set_defaults(handler=_report)

    checks = subparsers.add_parser(
        "checks", help="print the graded quality metrics to the terminal"
    )
    checks.add_argument("directory", type=Path, help="a profile directory")
    checks.add_argument("--strict", action="store_true", help="exit non-zero when any check fails")
    checks.set_defaults(handler=_checks)

    locus = subparsers.add_parser(
        "locus", help="build the locus browser over a real VCF (reads patient records)"
    )
    locus.add_argument("vcf", type=Path, help="a VCF, optionally bgzip-compressed")
    locus.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="where to write the page — keep this outside the repository",
    )
    locus.add_argument(
        "-l",
        "--label",
        default="locus",
        help="what to call the region in captions (default: %(default)s)",
    )
    locus.set_defaults(handler=_locus)

    export = subparsers.add_parser("export", help="write every exhibit as its own file")
    export.add_argument("directory", type=Path, help="a profile directory")
    export.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("figures/exhibits"),
        help="destination directory (default: %(default)s)",
    )
    export.add_argument(
        "--images",
        action="store_true",
        help="also write PNGs, if a static export engine is installed",
    )
    export.set_defaults(handler=_export)
    return parser


def _report(args) -> int:
    profile = _load(args.directory)
    if profile is None:
        return 1
    path = write_report(profile, args.output, args.title, subject=str(args.directory))
    sections = build_sections(profile)
    count = sum(len(s.exhibits) for s in sections)
    print(
        f"Wrote {path} — {count} exhibits across {len(sections)} sections "
        f"({path.stat().st_size / 1024:.0f} KB)."
    )
    return 0


def _checks(args) -> int:
    profile = _load(args.directory)
    if profile is None:
        return 1
    results = run_checks(profile)
    if not results:
        print("No gradeable metrics in this profile.", file=sys.stderr)
        return 1

    colour = sys.stdout.isatty()
    width = max(len(c.name) for c in results)
    print(f"\n{args.directory} — {len(results)} checks\n")
    for check in results:
        verdict = check.verdict.value.upper()
        if colour:
            verdict = f"{ANSI[check.verdict]}{verdict:<5}{RESET}"
        else:
            verdict = f"{verdict:<5}"
        print(
            f"  {verdict}  {check.name:<{width}}  {check.display:>18}   expected {check.expected}"
        )

    actionable = [c for c in results if c.is_actionable]
    if actionable:
        print("\nWorth acting on:")
        for check in actionable:
            print(f"  - {check.name}: {check.consequence or check.expected}")
    print()
    return 1 if args.strict and any(c.verdict is Verdict.FAIL for c in results) else 0


def _locus(args) -> int:
    from ..pipeline import read_calls

    if not args.vcf.exists():
        print(f"No such VCF: {args.vcf}", file=sys.stderr)
        return 1
    calls = read_calls(args.vcf)
    built = locus_views.exhibits(calls, args.label)
    if not built:
        print(f"{args.vcf} holds no calls to plot.", file=sys.stderr)
        return 1

    section = Section(
        "locus",
        f"Locus — {args.label}",
        "Every call in the region, its support, and which pairs can be "
        "placed on opposite copies of the chromosome.",
        built,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        render(
            [section],
            title=f"Locus browser — {args.label}",
            subject=str(args.vcf),
            blurb=LOCUS_BLURB,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {args.output} — {len(calls):,} calls, {len(built)} exhibits.")
    return 0


def _export(args) -> int:
    profile = _load(args.directory)
    if profile is None:
        return 1
    written = export_exhibits(build_sections(profile), args.output, images=args.images)
    print(f"Wrote {len(written)} files under {args.output}.")
    if args.images and not any(p.suffix == ".png" for p in written):
        print("No images written — install the optional `kaleido` engine for static export.")
    return 0


def _load(directory: Path) -> CallsetProfile | None:
    if not directory.is_dir():
        print(f"No such profile directory: {directory}", file=sys.stderr)
        return None
    profile = CallsetProfile.load(directory)
    if not profile.available:
        expected = ", ".join(sorted(vars(ProfileLayout()).values() or []))
        print(f"{directory} holds none of the expected artifacts.", file=sys.stderr)
        if expected:
            print(f"Expected any of: {expected}", file=sys.stderr)
        return None
    return profile


if __name__ == "__main__":
    raise SystemExit(main())
