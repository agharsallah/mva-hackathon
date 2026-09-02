"""The research record: what is being asked, what is claimed, and what the evidence says.

The warehouse answers *where did this byte come from*. This package answers the other
question, the one a report is actually made of: **what do we believe, how strongly, and on
what basis** — and it answers it in tables, so the report and the submission are generated
from the record rather than transcribed out of it.

The loop, and the module that owns each station:

``steps``
    Every research step declares **one goal**. Claims are filed under a step, so the
    record reads by question rather than by date. Steps are code, not rows — few, stable,
    and reviewable in a diff.
``hypothesis``
    A falsifiable claim, its prediction, and the observation that would kill it. Stored as
    append-only revisions, so a belief that moves leaves a trace.
``evidence``
    One observation, tagged supports/refutes/neutral, weighted, and — the load-bearing
    part — carrying the receipt it came from.
``dossier``
    One claim plus everything recorded about it, and the bridge that stamps a hypothesis
    id into a submission row so a scored row can be traced back to the claim behind it.
``export``
    The committed mirror in ``docs/<step>/``, so a reviewer with a clone and no database
    sees the same record. Refuses to write a genomic coordinate into git.
``record`` / ``report`` / ``views``
    The whole record in one object, rendered onto :mod:`mva.render` — the same shell and
    the same palette as the data-profile report.

Three rules are enforced by constructors rather than asked for in a template: no claim
without a refutation condition, no observation without a source, no confidence without a
stated reason. The weighing in :mod:`~mva.science.evidence` suggests a number and shows its
arithmetic; committing it takes a human.

The quick path::

    uv run mva-science steps
    uv run mva-science hypothesis-add --step step-1 --statement '…' \\
        --prediction '…' --refuted-by '…'
    uv run mva-science verdict H001        # prints the arithmetic, writes nothing
    uv run mva-science check && uv run mva-science export
    uv run mva-science report
"""

from .dossier import Dossier, assemble, assemble_all, evidence_from_pair, to_row
from .evidence import Direction, Evidence, Weighing, weigh
from .hypothesis import Hypothesis, Status
from .record import Record, SpentProbe
from .report import build_report, write_report
from .steps import STEPS, Step, by_slug, research_steps
from .views import SECTIONS, build_sections

__all__ = [
    "SECTIONS",
    "STEPS",
    "Direction",
    "Dossier",
    "Evidence",
    "Hypothesis",
    "Record",
    "SpentProbe",
    "Status",
    "Step",
    "Weighing",
    "assemble",
    "assemble_all",
    "build_report",
    "build_sections",
    "by_slug",
    "evidence_from_pair",
    "research_steps",
    "to_row",
    "weigh",
    "write_report",
]
