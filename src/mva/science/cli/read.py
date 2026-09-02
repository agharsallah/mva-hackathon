"""The read verbs: ``steps``, ``board``, ``show``, ``evidence-list``, ``verdict``.

None of these writes. ``verdict`` is the exception that proves the rule — it computes a
suggested confidence and prints the arithmetic behind it, and writes nothing without an
explicit ``--commit`` and a stated reason.
"""

import sys

from .. import evidence as evidence_module
from .. import hypothesis as hypothesis_module
from .. import steps as steps_module
from ..dossier import assemble
from ..hypothesis import Status
from . import context


def do_steps(args) -> int:
    """The step map: every goal, in dependency order."""
    for step in steps_module.STEPS:
        marker = {"done": "✔", "open": "▶", "planned": "·"}[step.status]
        print(f"{marker} {step.slug:8s} {step.title}")
        print(f"    goal: {step.goal}")
        print(
            f"    kind: {step.kind}   docs: {step.docs}/"
            + (f"   unblocks: {', '.join(step.unblocks)}" if step.unblocks else "")
        )
    return 0


def do_board(args) -> int:
    """Every claim, one latest revision each."""
    settings = context.settings()
    with context.attached(settings, read_only=True) as connection:
        rows = hypothesis_module.board(connection, settings.schema, args.step)
    if not rows:
        print("no hypotheses recorded" + (f" for {args.step}" if args.step else ""))
        return 0
    print(
        context.render_table(
            hypothesis_module.BOARD_COLUMNS, [hypothesis_module.as_row(row) for row in rows]
        )
    )
    return 0


def do_show(args) -> int:
    """One claim in full: prediction, refutation condition, evidence, weighing, history."""
    settings = context.settings()
    with context.attached(settings, read_only=True) as connection:
        dossier = assemble(connection, settings.schema, args.hypothesis)
    h = dossier.hypothesis
    print(f"{h.hypothesis_id}  [{h.status.value}]  revision {h.revision}")
    print(f"  step        {h.step} — {dossier.step.goal}")
    print(f"  claim       {h.statement}")
    print(f"  prediction  {h.prediction}")
    print(f"  refuted by  {h.refuted_by}")
    if h.gene:
        print(f"  gene        {h.gene}")
    if h.reasoning:
        print(f"  reasoning   {h.reasoning}")
    print()
    if dossier.evidence:
        print(
            context.render_table(
                evidence_module.LISTING_COLUMNS,
                [evidence_module.as_row(row) for row in dossier.evidence],
            )
        )
        print()
    for line in dossier.weighing.arithmetic():
        print(line)
    return 0


def do_evidence_list(args) -> int:
    settings = context.settings()
    with context.attached(settings, read_only=True) as connection:
        rows = evidence_module.listing(connection, settings.schema, args.hypothesis)
    if not rows:
        print("no evidence recorded")
        return 0
    print(
        context.render_table(
            evidence_module.LISTING_COLUMNS, [evidence_module.as_row(row) for row in rows]
        )
    )
    return 0


def do_verdict(args) -> int:
    """Weigh the evidence and show the arithmetic. Writes only with ``--commit``."""
    settings = context.settings()
    with context.attached(settings, read_only=not args.commit) as connection:
        dossier = assemble(connection, settings.schema, args.hypothesis)
        for line in dossier.weighing.arithmetic():
            print(line)

        if not args.commit:
            print(
                "\nnothing written. Re-run with --commit --status <s> --reasoning '…' "
                "to record this as a verdict."
            )
            return 0
        if not args.reasoning:
            print(
                "error: --commit requires --reasoning: a confidence with no stated "
                "basis is a number nobody can check",
                file=sys.stderr,
            )
            return 1

        confidence = dossier.weighing.confidence if args.confidence is None else args.confidence
        hypothesis_module.ensure_table(connection, settings.schema)
        revised = hypothesis_module.revise(
            connection,
            settings.schema,
            args.hypothesis,
            status=Status(args.status),
            confidence=confidence,
            reasoning=args.reasoning,
            author=args.by or "",
        )
    print(
        f"\nrecorded {revised.hypothesis_id} revision {revised.revision}: "
        f"{revised.status.value} at {confidence:.2f}"
    )
    return 0
