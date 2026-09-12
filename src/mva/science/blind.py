"""The blind gate: what an iteration-2 methodology entry is allowed to have read.

Iteration 2 re-derives the case from the raw reads, the VCF and the eight HPO terms as if
no candidate were known. The candidate gene is written all over this repository, so the
blinding cannot be a secret — it is a **procedural rule**, and this module is the machine
that checks it. Every iteration-2 entry carries an ``## Inputs`` table naming what it
read; the gate refuses an entry that names an iteration-1 candidate table before the
unblinding entry exists.

Two things follow from that design, and both are deliberate:

* **The gate reads the entries, not the code.** What an analysis actually read is a claim
  its author makes in prose; the gate holds the author to it. It cannot detect a lie, and
  it is not meant to — it makes the blinding auditable by a reviewer who reads the same
  table.
* **It returns rows, not printed text.** The step-6 blinding checklist and the ``/steps``
  page both render this; the plan asks for a checklist *generated* from the gate, never
  typed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

#: The heading every entry of a blind iteration must carry.
INPUTS_HEADING = "## Inputs"

#: The line that ends the blinding, written in the entry that performs the comparison.
UNBLINDS_MARKER = re.compile(r"^\*\*Unblinds:\*\*\s*yes\b", re.MULTILINE | re.IGNORECASE)

#: What an entry may not name while the iteration is blind, and why. Public catalogues are
#: absent on purpose: ClinVar genome-wide and the HPO corpus carry no information about
#: *this* child, so reading them is not unblinding.
FORBIDDEN_INPUTS: dict[str, str] = {
    "results.gene_biallelic": "iteration 1's biallelic candidate table names the pair",
    "results.coding_candidates": "iteration 1's filtered candidate table names the pair",
    "decode-table": "iteration 1's decode table names the pair and the oracle reply",
}

#: Entry filenames that are records *about* the gate rather than analyses under it.
_SKIP = ("README.md",)

#: Passages that **name** a forbidden input in order to declare it was *not* read.
#:
#: The gate matches identifiers, so a sentence saying "we did not read X" trips the same
#: rule as one saying "we read X" — and ``methodology/`` is append-only, so the sentence
#: cannot be rewritten once filed. This is the same escape hatch
#: ``tools/coordinate_allowlist.txt`` gives the coordinate gate, built the same way: an
#: exact quotation plus a reason, so a reviewer can check the claim instead of trusting
#: it, and any later edit to the entry invalidates the exemption rather than widening it.
#:
#: Keyed by ``(entry filename, exact passage)``. A forbidden name is still a violation
#: wherever it appears **outside** these passages.
_O88_DISCLAIMER = (
    "**No iteration-1 candidate table was read.** `results.gene_biallelic`,\n"
    "`results.coding_candidates` and the decode table are untouched; the comparison "
    "they exist\nfor is step 6's."
)

NOT_READ_DECLARATIONS: dict[tuple[str, str], str] = {
    ("088-the-alleles-the-reads-carry.md", _O88_DISCLAIMER): (
        "the entry's own statement that it read neither table — the disclaimer, not a dependency"
    ),
}


def _uncovered(text: str, entry: str, named: str) -> bool:
    """Whether ``named`` appears anywhere outside this entry's non-read declarations."""
    remaining = text
    for filename, passage in NOT_READ_DECLARATIONS:
        if filename == entry and passage in remaining:
            remaining = remaining.replace(passage, "")
    return named in remaining


@dataclass(frozen=True)
class Violation:
    """One forbidden input named by one entry."""

    entry: Path
    named: str
    reason: str

    def __str__(self) -> str:
        return f"{self.entry}: names {self.named} — {self.reason}"


@dataclass(frozen=True)
class Entry:
    """One methodology entry as the gate sees it."""

    path: Path
    step: str
    declares_inputs: bool
    inputs: tuple[str, ...] = ()
    unblinds: bool = False
    violations: tuple[Violation, ...] = ()

    @property
    def ok(self) -> bool:
        return self.declares_inputs and not self.violations


@dataclass(frozen=True)
class Report:
    """The gate's verdict over one iteration — the checklist, in rows."""

    iteration: str
    entries: tuple[Entry, ...] = ()
    unblinded_by: Path | None = None
    problems: tuple[str, ...] = field(default=())

    @property
    def ok(self) -> bool:
        return not self.problems

    @property
    def blind(self) -> bool:
        """Whether the iteration is still blind — nothing has unblinded it yet."""
        return self.unblinded_by is None


def _inputs_block(text: str) -> str | None:
    """The body of the ``## Inputs`` section, or ``None`` when the entry has none."""
    start = text.find(INPUTS_HEADING)
    if start < 0:
        return None
    body = text[start + len(INPUTS_HEADING) :]
    end = body.find("\n## ")
    return body if end < 0 else body[:end]


def _named_inputs(block: str) -> tuple[str, ...]:
    """The non-empty lines of the inputs block, as rows a reader can be shown."""
    return tuple(
        line.strip().strip("|").strip()
        for line in block.splitlines()
        if line.strip() and not set(line.strip()) <= set("|-: ")
    )


def read_entry(path: Path, step: str) -> Entry:
    """Check one entry against the gate."""
    text = path.read_text(encoding="utf-8")
    block = _inputs_block(text)
    violations = tuple(
        Violation(path, named, reason)
        for named, reason in FORBIDDEN_INPUTS.items()
        if _uncovered(text, path.name, named)
    )
    return Entry(
        path=path,
        step=step,
        declares_inputs=block is not None,
        inputs=_named_inputs(block) if block else (),
        unblinds=bool(UNBLINDS_MARKER.search(text)),
        violations=violations,
    )


def entries_of(root: Path, iteration: str) -> list[tuple[Path, str]]:
    """``(entry, step slug)`` for every methodology entry of one iteration, in order."""
    found: list[tuple[Path, str]] = []
    base = root / iteration
    if not base.is_dir():
        return found
    for step_dir in sorted(base.glob("step-*")):
        found.extend(
            (entry, step_dir.name)
            for entry in sorted((step_dir / "methodology").glob("*.md"))
            if entry.name not in _SKIP
        )
    return found


def check(root: Path, iteration: str) -> Report:
    """Read every entry of ``iteration`` and say whether the blinding holds.

    An entry may name a forbidden input only from the unblinding entry onwards; entries
    are ordered by their (globally monotonic) number, so "onwards" is well defined.
    """
    checked = tuple(read_entry(path, step) for path, step in entries_of(root, iteration))
    unblinded_by = next((e.path for e in checked if e.unblinds), None)
    seen_unblinding = False
    problems: list[str] = []
    for entry in checked:
        if not entry.declares_inputs:
            problems.append(
                f"{entry.path}: no '{INPUTS_HEADING}' section — a blind iteration's entry "
                "must state what it read, so a reviewer can check it read nothing it "
                "should not have"
            )
        # The unblinding entry is the one that performs the comparison, so it and every
        # entry after it may name the iteration-1 tables.
        seen_unblinding = seen_unblinding or entry.unblinds
        if not seen_unblinding:
            problems.extend(str(v) for v in entry.violations)
    return Report(
        iteration=iteration,
        entries=checked,
        unblinded_by=unblinded_by,
        problems=tuple(problems),
    )
