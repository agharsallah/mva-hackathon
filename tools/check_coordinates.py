#!/usr/bin/env python3
"""Fail when a patient genomic coordinate appears in a file the repository would publish.

The Data Transfer Agreement and CLAUDE.md say the same thing: never write a genomic
position of the proband into a hypothesis, an evidence claim, a doc, or any exported file.
``mva-science check`` guards the register; nothing guarded the rest of the tree, and one
methodology entry pasted a submission row with both candidate coordinates in it. This is
the gate that would have caught it.

Four rules, each cheap and explicit:

1. **Submission rows.** A line shaped like a Track-1 CSV data row
   (``PROBAND01,chr<x>,<pos>,...``) is a leak wherever it stands.
2. **Spec positions.** When the gitignored submission spec exists
   (``build/submission/spec.json``), every position it names is searched for as a bare
   number. This is the strongest rule and the only one that knows the real coordinates;
   it therefore only runs on a machine that holds the spec.
3. **Candidate-gene span.** Any 8-digit number strictly inside the candidate gene's public
   genomic span, when it stands next to that gene's chromosome (``chr15:``, ``15 ``,
   ``,chr15,``). The span is public knowledge and its two endpoints are exempt; a number
   inside it is a variant position by construction. Synthetic examples are listed, with
   their reason, in ``tools/coordinate_allowlist.txt``.
4. **DNA literals.** A run of ``MIN_DNA_RUN`` or more ``[ACGTN]`` characters. A position
   names a place in a public coordinate system; a *sequence* is the patient's genome
   itself, and rules 1-3 cannot see it. Iteration 2 turned 42 Mb of reference into 31-mers
   and swept a billion reads with them, so this is the first step where patient sequence
   can plausibly reach a tracked file. Reference sequence is not exempt by being
   reference: it is exempt by being **verified** absent of patient information, one entry
   at a time, in the same allowlist.

Scans every tracked and untracked-but-not-ignored text file, except the trees named in
``SKIP_PREFIXES`` (public reference tables and the organisers' template are coordinates by
design, not leaks).

Usage::

    uv run python tools/check_coordinates.py            # the gate
    uv run python tools/check_coordinates.py --quiet    # only the failures
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

#: Text files worth scanning. Binary formats (PNG, PDF, xlsx) cannot be grepped honestly.
TEXT_SUFFIXES = {
    ".md", ".json", ".py", ".ts", ".tsx", ".mjs", ".js", ".html", ".csv", ".tsv",
    ".txt", ".svg", ".toml", ".yaml", ".yml", ".sql", ".sh",
}  # fmt: skip

#: Trees that legitimately hold coordinates that are not the proband's: the organisers'
#: repository (made-up template rows), public reference tables under ``ressources/`` (ClinVar,
#: gene models — every row is a public coordinate, each file has a provenance manifest), and
#: ``archive/`` (superseded drafts, never edited; a leak there is handled by history, not here).
SKIP_PREFIXES = ("ressources/", "archive/")
SKIP_SUFFIXES = (".svg",)

#: The candidate gene's public span on GRCh38, as the panel BED states it (with padding).
DEFAULT_SPAN = ("15", 40140984, 40241137)

#: A Track-1 CSV data row whose first position has 7 or more digits. Synthetic rows in the
#: docs use short positions (``12345``, ``100000``) precisely so they can never be real.
SUBMISSION_ROW = re.compile(r"^\s*PROBAND\d+,chr\w+,\d{7,},")

#: Shortest run of bases treated as a DNA literal. 25 is below the k=31 the bait uses, so a
#: single bait k-mer cannot slip through, and far above the longest DNA-alphabet token that
#: occurs by accident (``CAG``, ``ATAC``, a ``TATA`` box, a column named ``cat``). Runs are
#: matched case-insensitively: a soft-masked reference writes them lowercase.
MIN_DNA_RUN = 25

#: A bare run of bases, not embedded in a longer alphanumeric token (which would make it an
#: identifier, a hash or a base64 blob rather than sequence).
DNA_RUN = re.compile(rf"(?<![A-Za-z0-9])[ACGTNacgtn]{{{MIN_DNA_RUN},}}(?![A-Za-z0-9])")


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    rule: str
    excerpt: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.rule}: {self.excerpt}"


def candidate_files(root: Path) -> list[Path]:
    """Every tracked or untracked-but-not-ignored text file under ``root``."""
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    files = []
    for rel in out.splitlines():
        if rel.startswith(SKIP_PREFIXES) or rel.endswith(SKIP_SUFFIXES):
            continue
        if Path(rel).suffix not in TEXT_SUFFIXES:
            continue
        path = root / rel
        if path.is_file():
            files.append(path)
    return files


def spec_positions(spec_path: Path) -> set[str]:
    """The positions the submission spec names, as strings; empty when the spec is absent."""
    if not spec_path.is_file():
        return set()
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    return {str(int(a["pos"])) for a in spec.get("alleles", {}).values()}


def load_allowlist(path: Path) -> set[str]:
    """Things known not to be the proband's: one per line, ``<token>  # reason``.

    A token is a position (rule 3) or a DNA literal (rule 4); both are compared as exact
    strings, so one file stays the single owner of "verified not patient data". DNA
    literals are stored uppercase and compared uppercased.
    """
    if not path.is_file():
        return set()
    allowed = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        token = line.split("#", 1)[0].strip()
        if token:
            allowed.add(token.upper() if token[:1].isalpha() else token)
    return allowed


def span_pattern(span: tuple[str, int, int]) -> re.Pattern[str]:
    chrom = re.escape(span[0])
    # the chromosome, then a separator, then an 8-digit position
    return re.compile(rf"(?<![\w.])(?:chr)?{chrom}[\s:,_-]+(\d{{8}})(?!\d)")


def scan_text(
    text: str,
    *,
    rel: str,
    positions: set[str],
    span: tuple[str, int, int],
    allowed: set[str],
) -> list[Finding]:
    findings: list[Finding] = []
    pattern = span_pattern(span)
    for number, line in enumerate(text.splitlines(), start=1):
        excerpt = line.strip()[:120]
        if SUBMISSION_ROW.match(line):
            findings.append(Finding(rel, number, "submission row", excerpt))
            continue
        for run in DNA_RUN.finditer(line):
            if run.group().upper() not in allowed:
                findings.append(
                    Finding(rel, number, f"DNA literal ({len(run.group())} bp)", excerpt)
                )
                break
        for pos in positions:
            if re.search(rf"(?<!\d){pos}(?!\d)", line):
                findings.append(Finding(rel, number, "spec position", excerpt))
                break
        else:
            for match in pattern.finditer(line):
                pos = match.group(1)
                inside = span[1] < int(pos) < span[2]  # the endpoints name the span itself
                if inside and pos not in allowed:
                    findings.append(Finding(rel, number, "inside candidate-gene span", excerpt))
                    break
    return findings


def scan(root: Path, spec_path: Path, allowlist: Path, span: tuple[str, int, int]) -> list[Finding]:
    positions = spec_positions(spec_path)
    allowed = load_allowlist(allowlist)
    findings: list[Finding] = []
    for path in candidate_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rel = path.relative_to(root).as_posix()
        findings.extend(scan_text(text, rel=rel, positions=positions, span=span, allowed=allowed))
    return findings


def parse_span(value: str) -> tuple[str, int, int]:
    chrom, rest = value.split(":", 1)
    lo, hi = (int(x.replace(",", "")) for x in rest.split("-", 1))
    return (chrom.removeprefix("chr"), lo, hi)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--spec", type=Path, default=Path("build/submission/spec.json"))
    parser.add_argument("--allowlist", type=Path, default=Path("tools/coordinate_allowlist.txt"))
    parser.add_argument(
        "--span",
        type=parse_span,
        default=DEFAULT_SPAN,
        help="candidate gene span, e.g. 15:40000000-40300000",
    )
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    spec = args.spec if args.spec.is_absolute() else root / args.spec
    allowlist = args.allowlist if args.allowlist.is_absolute() else root / args.allowlist
    findings = scan(root, spec, allowlist, args.span)

    if not args.quiet:
        known = "known" if spec.is_file() else "not on this machine"
        span = f"{args.span[0]}:{args.span[1]}-{args.span[2]}"
        print(f"coordinate gate: spec positions {known}; span {span}")
    for finding in findings:
        print(finding)
    if findings:
        print(
            f"coordinate gate: {len(findings)} leak(s) — redact before committing", file=sys.stderr
        )
        return 1
    if not args.quiet:
        print("coordinate gate: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
