"""``mva-science`` — the command line over the research record.

Same shape as ``mva-warehouse``: argparse subparsers, one handler per verb returning an
exit code, ``attached`` imported into this module's namespace so a test can replace it.

The verbs divide into three groups, and the division is the point:

**Write** — ``hypothesis-add``, ``hypothesis-revise``, ``evidence-add``, ``probe-link``.
Each one appends; none updates. Each refuses input the register should not hold.

**Read** — ``steps``, ``board``, ``show``, ``evidence-list``, ``verdict``. ``verdict``
computes a suggested confidence and prints the arithmetic; it writes nothing without an
explicit ``--commit`` and a stated reason.

**Publish** — ``check``, ``export``, ``report``. ``check`` is the gate: it refuses to let a
genomic coordinate or an unsourced observation reach the repository.
"""

import argparse
import sys
from pathlib import Path

from ..warehouse.postgres import attached, render_table
from ..warehouse.settings import Postgres
from . import evidence as evidence_module
from . import export as export_module
from . import hypothesis as hypothesis_module
from . import record as record_module
from . import steps as steps_module
from .dossier import assemble, assemble_all
from .evidence import Direction, Evidence
from .hypothesis import Hypothesis, Status
from .report import write_report

DEFAULT_REPORT = "figures/science-report.html"


def _settings() -> Postgres:
    """Resolved connection settings. Replaced wholesale in tests."""
    return Postgres.from_env()


# --------------------------------------------------------------------------------------
# Read
# --------------------------------------------------------------------------------------

def do_steps(args) -> int:
    """The step map: every goal, in dependency order."""
    for step in steps_module.STEPS:
        marker = {"done": "✔", "open": "▶", "planned": "·"}[step.status]
        print(f"{marker} {step.slug:8s} {step.title}")
        print(f"    goal: {step.goal}")
        print(f"    kind: {step.kind}   docs: {step.docs}/"
              + (f"   unblocks: {', '.join(step.unblocks)}" if step.unblocks else ""))
    return 0


def do_board(args) -> int:
    """Every claim, one latest revision each."""
    settings = _settings()
    with attached(settings, read_only=True) as connection:
        rows = hypothesis_module.board(connection, settings.schema, args.step)
    if not rows:
        print("no hypotheses recorded"
              + (f" for {args.step}" if args.step else ""))
        return 0
    print(render_table(hypothesis_module.BOARD_COLUMNS,
                       [hypothesis_module.as_row(row) for row in rows]))
    return 0


def do_show(args) -> int:
    """One claim in full: prediction, refutation condition, evidence, weighing, history."""
    settings = _settings()
    with attached(settings, read_only=True) as connection:
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
        print(render_table(evidence_module.LISTING_COLUMNS,
                           [evidence_module.as_row(row) for row in dossier.evidence]))
        print()
    for line in dossier.weighing.arithmetic():
        print(line)
    return 0


def do_evidence_list(args) -> int:
    settings = _settings()
    with attached(settings, read_only=True) as connection:
        rows = evidence_module.listing(connection, settings.schema, args.hypothesis)
    if not rows:
        print("no evidence recorded")
        return 0
    print(render_table(evidence_module.LISTING_COLUMNS,
                       [evidence_module.as_row(row) for row in rows]))
    return 0


def do_verdict(args) -> int:
    """Weigh the evidence and show the arithmetic. Writes only with ``--commit``."""
    settings = _settings()
    with attached(settings, read_only=not args.commit) as connection:
        dossier = assemble(connection, settings.schema, args.hypothesis)
        for line in dossier.weighing.arithmetic():
            print(line)

        if not args.commit:
            print("\nnothing written. Re-run with --commit --status <s> --reasoning '…' "
                  "to record this as a verdict.")
            return 0
        if not args.reasoning:
            print("error: --commit requires --reasoning: a confidence with no stated "
                  "basis is a number nobody can check", file=sys.stderr)
            return 1

        confidence = (dossier.weighing.confidence if args.confidence is None
                      else args.confidence)
        hypothesis_module.ensure_table(connection, settings.schema)
        revised = hypothesis_module.revise(
            connection, settings.schema, args.hypothesis,
            status=Status(args.status), confidence=confidence,
            reasoning=args.reasoning, author=args.by or "")
    print(f"\nrecorded {revised.hypothesis_id} revision {revised.revision}: "
          f"{revised.status.value} at {confidence:.2f}")
    return 0


# --------------------------------------------------------------------------------------
# Write
# --------------------------------------------------------------------------------------

def do_hypothesis_add(args) -> int:
    settings = _settings()
    try:
        claim = Hypothesis(
            step=args.step, statement=args.statement, prediction=args.prediction,
            refuted_by=args.refuted_by, gene=args.gene or "", path=args.path or "",
            author=args.by or "")
    except (ValueError, KeyError) as problem:
        print(f"error: {problem}", file=sys.stderr)
        return 1

    with attached(settings) as connection:
        hypothesis_module.ensure_table(connection, settings.schema)
        stored = hypothesis_module.propose(connection, settings.schema, claim)
    print(f"recorded {stored.hypothesis_id} under {stored.step}")
    return 0


def do_hypothesis_revise(args) -> int:
    settings = _settings()
    with attached(settings) as connection:
        hypothesis_module.ensure_table(connection, settings.schema)
        try:
            revised = hypothesis_module.revise(
                connection, settings.schema, args.hypothesis,
                status=Status(args.status), confidence=args.confidence,
                reasoning=args.reasoning, author=args.by or "")
        except (ValueError, KeyError) as problem:
            print(f"error: {problem}", file=sys.stderr)
            return 1
    print(f"recorded {revised.hypothesis_id} revision {revised.revision}: "
          f"{revised.status.value}")
    return 0


def do_evidence_add(args) -> int:
    settings = _settings()
    try:
        observation = Evidence(
            hypothesis_id=args.hypothesis, direction=Direction(args.direction),
            claim=args.claim, source_ref=args.source_ref, kind=args.kind,
            strength=args.strength, lineage_ref=args.lineage_ref or "",
            author=args.by or "")
    except ValueError as problem:
        print(f"error: {problem}", file=sys.stderr)
        return 1

    with attached(settings) as connection:
        evidence_module.ensure_table(connection, settings.schema)
        evidence_id = evidence_module.record(connection, settings.schema, observation)
    print(f"recorded evidence {evidence_id} against {observation.hypothesis_id}")
    return 0


def do_probe_link(args) -> int:
    """Tie a spent probe to the hypotheses it was fired to test.

    The ledger is append-only, so this does not edit the probe row. It records the tie as
    evidence — which is the honest shape anyway: what a reply *means* for a belief is a
    judgment, and judgments belong in the evidence ledger with a source, not silently
    inside the record of what was uploaded.
    """
    settings = _settings()
    rows = []
    with attached(settings) as connection:
        evidence_module.ensure_table(connection, settings.schema)
        for hypothesis_id in args.hypothesis:
            observation = Evidence(
                hypothesis_id=hypothesis_id, direction=Direction(args.direction),
                claim=args.claim, source_ref=f"probe:{args.probe}", kind="oracle",
                strength=args.strength, author=args.by or "")
            rows.append(evidence_module.record(connection, settings.schema, observation))
    print(f"recorded {len(rows)} oracle observation(s) from probe {args.probe}: "
          + ", ".join(str(row) for row in rows))
    return 0


# --------------------------------------------------------------------------------------
# Publish
# --------------------------------------------------------------------------------------

def do_check(args) -> int:
    """The gate. Refuses what must not reach the repository."""
    settings = _settings()
    with attached(settings, read_only=True) as connection:
        dossiers = assemble_all(connection, settings.schema)

    problems = [str(leak) for leak in export_module.scan(dossiers)]
    for dossier in dossiers:
        if dossier.hypothesis.status.is_settled and not dossier.evidence:
            problems.append(
                f"{dossier.hypothesis.hypothesis_id}: settled as "
                f"{dossier.hypothesis.status.value} with no evidence recorded")

    if problems:
        print("check failed:")
        for problem in problems:
            print(f"  {problem}")
        return 1
    print(f"check passed: {len(dossiers)} hypotheses, "
          f"{sum(len(d.evidence) for d in dossiers)} evidence rows, no coordinates")
    return 0


def do_export(args) -> int:
    settings = _settings()
    with attached(settings, read_only=True) as connection:
        dossiers = assemble_all(connection, settings.schema)
    try:
        written = export_module.write(dossiers, args.root)
    except ValueError as problem:
        print(f"error: {problem}", file=sys.stderr)
        return 1
    print(f"wrote {len(written)} files under {args.root}/")
    for path in written:
        print(f"  {path}")
    return 0


def do_report(args) -> int:
    if args.source:
        import json
        record = record_module.from_register(
            json.loads(Path(args.source).read_text(encoding="utf-8")),
            subject=args.source)
    else:
        settings = _settings()
        with attached(settings, read_only=True) as connection:
            record = record_module.read(
                connection, settings.schema,
                subject=settings.describe().get("database", "mva"))
    path = write_report(record, args.out)
    print(f"wrote {path} ({path.stat().st_size // 1024} KB) — "
          f"{len(record.dossiers)} hypotheses, {record.budget_spent}/"
          f"{record.budget_total} probes spent")
    return 0


# --------------------------------------------------------------------------------------
# Wiring
# --------------------------------------------------------------------------------------

def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mva-science",
        description="The research record: steps, hypotheses, evidence, verdicts.")
    subparsers = parser.add_subparsers()

    listing = subparsers.add_parser("steps", help="the step map and each step's goal")
    listing.set_defaults(handler=do_steps)

    board = subparsers.add_parser("board", help="every claim, one latest revision each")
    board.add_argument("--step", choices=steps_module.slugs(), default=None)
    board.set_defaults(handler=do_board)

    show = subparsers.add_parser("show", help="one claim in full, with its weighing")
    show.add_argument("hypothesis")
    show.set_defaults(handler=do_show)

    add = subparsers.add_parser(
        "hypothesis-add",
        help="propose a claim (needs a prediction and a refutation condition)")
    add.add_argument("--step", required=True,
                     choices=[s.slug for s in steps_module.research_steps()])
    add.add_argument("--statement", required=True, help="the falsifiable claim")
    add.add_argument("--prediction", required=True,
                     help="what must be observed if the claim is true")
    add.add_argument("--refuted-by", required=True, dest="refuted_by",
                     help="what observation would kill the claim")
    add.add_argument("--gene", default="", help="the gene, if the claim names one")
    add.add_argument("--path", default="", help="which solution path generated it")
    add.add_argument("--by", default="", help="who proposed it")
    add.set_defaults(handler=do_hypothesis_add)

    revise = subparsers.add_parser("hypothesis-revise",
                                   help="append a revision changing status or confidence")
    revise.add_argument("hypothesis")
    revise.add_argument("--status", required=True,
                        choices=[s.value for s in Status])
    revise.add_argument("--confidence", type=float, default=None)
    revise.add_argument("--reasoning", required=True, help="why, in one sentence")
    revise.add_argument("--by", default="")
    revise.set_defaults(handler=do_hypothesis_revise)

    evidence = subparsers.add_parser("evidence-add",
                                     help="record one observation against a claim")
    evidence.add_argument("--hypothesis", required=True)
    evidence.add_argument("--direction", required=True,
                          choices=[d.value for d in Direction])
    evidence.add_argument("--claim", required=True, help="what was observed, one sentence")
    evidence.add_argument("--source-ref", required=True, dest="source_ref",
                          help="the receipt: methodology entry, table, PMID, ClinVar id")
    evidence.add_argument("--kind", default="measurement", choices=evidence_module.KINDS)
    evidence.add_argument("--strength", type=float, default=0.5,
                          help="how hard it cuts, 0 to 1")
    evidence.add_argument("--lineage-ref", default="", dest="lineage_ref",
                          help="the data_lineage row the observation was computed from")
    evidence.add_argument("--by", default="")
    evidence.set_defaults(handler=do_evidence_add)

    evidence_list = subparsers.add_parser("evidence-list", help="the evidence ledger")
    evidence_list.add_argument("--hypothesis", default=None)
    evidence_list.set_defaults(handler=do_evidence_list)

    verdict = subparsers.add_parser(
        "verdict", help="weigh the evidence and show the arithmetic")
    verdict.add_argument("hypothesis")
    verdict.add_argument("--commit", action="store_true",
                         help="record the result as a new revision")
    verdict.add_argument("--status", default=Status.SUPPORTED.value,
                         choices=[s.value for s in Status])
    verdict.add_argument("--confidence", type=float, default=None,
                         help="override the suggested confidence")
    verdict.add_argument("--reasoning", default="", help="required with --commit")
    verdict.add_argument("--by", default="")
    verdict.set_defaults(handler=do_verdict)

    link = subparsers.add_parser(
        "probe-link", help="record what an oracle reply means for the claims it tested")
    link.add_argument("probe", help="the probe_id from the ledger")
    link.add_argument("--hypothesis", required=True, action="append",
                      help="repeatable: every claim the probe was fired to test")
    link.add_argument("--direction", required=True, choices=[d.value for d in Direction])
    link.add_argument("--claim", required=True, help="what the reply told us")
    link.add_argument("--strength", type=float, default=0.8)
    link.add_argument("--by", default="")
    link.set_defaults(handler=do_probe_link)

    check = subparsers.add_parser(
        "check", help="the publish gate: coordinates, and verdicts with no evidence")
    check.set_defaults(handler=do_check)

    export = subparsers.add_parser("export", help="write the committed mirror")
    export.add_argument("--root", default="docs", help="where the step folders live")
    export.set_defaults(handler=do_export)

    report = subparsers.add_parser("report", help="render the research record as HTML")
    report.add_argument("-o", "--out", default=DEFAULT_REPORT)
    report.add_argument("--from", dest="source", default=None,
                        help="render from an exported science-register.json instead of "
                             "the warehouse — needs no database")
    report.set_defaults(handler=do_report)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        _parser().print_help()
        return 1
    try:
        return handler(args)
    except RuntimeError as problem:
        print(f"error: {problem}", file=sys.stderr)
        return 1
    except KeyError as problem:
        print(f"error: {problem}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
