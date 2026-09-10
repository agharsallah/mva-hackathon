"""The argument parser: every verb, its flags, and its help text.

One module because it is one concern — the command-line surface — and because it is the
half of the CLI that has no behaviour to test beyond its own shape (see
``tests/test_cli_parsers.py``).
"""

import argparse

from .. import evidence as evidence_module
from .. import steps as steps_module
from ..evidence import Direction
from ..hypothesis import Status
from . import publish, read, write
from .context import DEFAULT_REPORT


def _read_verbs(subparsers: argparse._SubParsersAction) -> None:
    """The verbs that only read. See :mod:`.read`."""
    listing = subparsers.add_parser("steps", help="the step map and each step's goal")
    listing.set_defaults(handler=read.do_steps)

    board = subparsers.add_parser("board", help="every claim, one latest revision each")
    board.add_argument("--step", choices=steps_module.slugs(), default=None)
    board.set_defaults(handler=read.do_board)

    show = subparsers.add_parser("show", help="one claim in full, with its weighing")
    show.add_argument("hypothesis")
    show.set_defaults(handler=read.do_show)

    evidence_list = subparsers.add_parser("evidence-list", help="the evidence ledger")
    evidence_list.add_argument("--hypothesis", default=None)
    evidence_list.set_defaults(handler=read.do_evidence_list)

    verdict = subparsers.add_parser("verdict", help="weigh the evidence and show the arithmetic")
    verdict.add_argument("hypothesis")
    verdict.add_argument(
        "--commit", action="store_true", help="record the result as a new revision"
    )
    verdict.add_argument(
        "--status", default=Status.SUPPORTED.value, choices=[s.value for s in Status]
    )
    verdict.add_argument(
        "--confidence", type=float, default=None, help="override the suggested confidence"
    )
    verdict.add_argument("--reasoning", default="", help="required with --commit")
    verdict.add_argument("--by", default="")
    verdict.set_defaults(handler=read.do_verdict)


def _write_verbs(subparsers: argparse._SubParsersAction) -> None:
    """The verbs that append a revision or a row. See :mod:`.write`."""
    add = subparsers.add_parser(
        "hypothesis-add", help="propose a claim (needs a prediction and a refutation condition)"
    )
    add.add_argument(
        "--step", required=True, choices=[s.slug for s in steps_module.research_steps()]
    )
    add.add_argument("--statement", required=True, help="the falsifiable claim")
    add.add_argument(
        "--prediction", required=True, help="what must be observed if the claim is true"
    )
    add.add_argument(
        "--refuted-by",
        required=True,
        dest="refuted_by",
        help="what observation would kill the claim",
    )
    add.add_argument("--gene", default="", help="the gene, if the claim names one")
    add.add_argument("--path", default="", help="which solution path generated it")
    add.add_argument("--by", default="", help="who proposed it")
    add.set_defaults(handler=write.do_hypothesis_add)

    revise = subparsers.add_parser(
        "hypothesis-revise", help="append a revision changing status or confidence"
    )
    revise.add_argument("hypothesis")
    revise.add_argument("--status", required=True, choices=[s.value for s in Status])
    revise.add_argument("--confidence", type=float, default=None)
    revise.add_argument("--reasoning", required=True, help="why, in one sentence")
    revise.add_argument("--by", default="")
    revise.set_defaults(handler=write.do_hypothesis_revise)

    evidence = subparsers.add_parser("evidence-add", help="record one observation against a claim")
    evidence.add_argument("--hypothesis", required=True)
    evidence.add_argument("--direction", required=True, choices=[d.value for d in Direction])
    evidence.add_argument("--claim", required=True, help="what was observed, one sentence")
    evidence.add_argument(
        "--source-ref",
        required=True,
        dest="source_ref",
        help="the receipt: methodology entry, table, PMID, ClinVar id",
    )
    evidence.add_argument("--kind", default="measurement", choices=evidence_module.KINDS)
    evidence.add_argument("--strength", type=float, default=0.5, help="how hard it cuts, 0 to 1")
    evidence.add_argument(
        "--lineage-ref",
        default="",
        dest="lineage_ref",
        help="the data_lineage row the observation was computed from",
    )
    evidence.add_argument("--by", default="")
    evidence.set_defaults(handler=write.do_evidence_add)

    link = subparsers.add_parser(
        "probe-link", help="record what an oracle reply means for the claims it tested"
    )
    link.add_argument("probe", help="the probe_id from the ledger")
    link.add_argument(
        "--hypothesis",
        required=True,
        action="append",
        help="repeatable: every claim the probe was fired to test",
    )
    link.add_argument("--direction", required=True, choices=[d.value for d in Direction])
    link.add_argument("--claim", required=True, help="what the reply told us")
    link.add_argument("--strength", type=float, default=0.8)
    link.add_argument("--by", default="")
    link.set_defaults(handler=write.do_probe_link)


def _publish_verbs(subparsers: argparse._SubParsersAction) -> None:
    """The verbs that emit files the repository keeps. See :mod:`.publish`."""
    check = subparsers.add_parser(
        "check", help="the publish gate: coordinates, and verdicts with no evidence"
    )
    check.add_argument(
        "--blind",
        metavar="ITERATION",
        default="",
        help=(
            "also run the blind gate over docs/<ITERATION>/step-*/methodology/: every "
            "entry must declare its inputs and name no iteration-1 candidate table "
            "before the unblinding entry"
        ),
    )
    check.add_argument("--root", default="docs", help="where the step folders live")
    check.set_defaults(handler=publish.do_check)

    export = subparsers.add_parser("export", help="write the committed mirror")
    export.add_argument("--root", default="docs", help="where the step folders live")
    export.set_defaults(handler=publish.do_export)

    report = subparsers.add_parser("report", help="render the research record as HTML")
    report.add_argument("-o", "--out", default=DEFAULT_REPORT)
    report.add_argument(
        "--from",
        dest="source",
        default=None,
        help="render from an exported science-register.json instead of "
        "the warehouse — needs no database",
    )
    report.set_defaults(handler=publish.do_report)


def build() -> argparse.ArgumentParser:
    """The whole command-line surface. One registration function per verb group."""
    parser = argparse.ArgumentParser(
        prog="mva-science",
        description="The research record: steps, hypotheses, evidence, verdicts.",
    )
    subparsers = parser.add_subparsers()

    _read_verbs(subparsers)
    _write_verbs(subparsers)
    _publish_verbs(subparsers)
    return parser
