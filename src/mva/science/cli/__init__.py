"""``mva-science`` — the command line over the research record.

Same shape as ``mva-warehouse``: argparse subparsers, one handler per verb returning an
exit code. The verbs divide into three groups, and the division is the point — so each
group is now its own module:

===================  ====================================================================
:mod:`.read`         ``steps``, ``board``, ``show``, ``evidence-list``, ``verdict``.
                     None of them writes. ``verdict`` computes a suggested confidence and
                     prints the arithmetic; it commits nothing without ``--commit`` and a
                     stated reason.
:mod:`.write`        ``hypothesis-add``, ``hypothesis-revise``, ``evidence-add``,
                     ``probe-link``. Each appends; none updates.
:mod:`.publish`      ``check``, ``export``, ``report``. ``check`` is the gate: it refuses
                     to let a genomic coordinate or an unsourced observation reach the
                     repository.
:mod:`.parser`       the command-line surface: every verb, its flags, its help.
:mod:`.context`      the connection and the default report path, so the three handler
                     modules never import each other.
===================  ====================================================================

Tests replace the database through one seam — ``cli.context.attached`` — and the settings
through another, ``cli.context.settings``.
"""

import sys

from .parser import build as _parser

__all__ = ["main"]


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        _parser().print_help()
        return 1
    try:
        return handler(args)
    except (KeyError, RuntimeError) as problem:
        print(f"error: {problem}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
