"""The publish verbs: ``check``, ``export``, ``report``.

``check`` is the gate. It refuses to let a genomic coordinate or an unsourced observation
reach the repository, and ``export`` runs the same scan again before writing anything —
all-or-nothing, not best-effort per file.
"""

import sys
from pathlib import Path

from .. import blind as blind_module
from .. import export as export_module
from .. import record as record_module
from ..dossier import assemble_all
from ..report import write_report
from . import context


def do_check(args) -> int:
    """The gate. Refuses what must not reach the repository."""
    settings = context.settings()
    with context.attached(settings, read_only=True) as connection:
        dossiers = assemble_all(connection, settings.schema)

    problems = [str(leak) for leak in export_module.scan(dossiers)]
    problems.extend(
        f"{dossier.hypothesis.hypothesis_id}: settled as "
        f"{dossier.hypothesis.status.value} with no evidence recorded"
        for dossier in dossiers
        if dossier.hypothesis.status.is_settled and not dossier.evidence
    )

    blind_report = None
    if getattr(args, "blind", ""):
        blind_report = blind_module.check(Path(args.root), args.blind)
        problems.extend(blind_report.problems)

    if problems:
        print("check failed:")
        for problem in problems:
            print(f"  {problem}")
        return 1
    print(
        f"check passed: {len(dossiers)} hypotheses, "
        f"{sum(len(d.evidence) for d in dossiers)} evidence rows, no coordinates"
    )
    if blind_report is not None:
        state = "still blind" if blind_report.blind else f"unblinded by {blind_report.unblinded_by}"
        print(
            f"blind gate passed: {len(blind_report.entries)} {blind_report.iteration} "
            f"entries, every one declaring its inputs — {state}"
        )
    return 0


def do_export(args) -> int:
    settings = context.settings()
    with context.attached(settings, read_only=True) as connection:
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
            json.loads(Path(args.source).read_text(encoding="utf-8")), subject=args.source
        )
    else:
        settings = context.settings()
        with context.attached(settings, read_only=True) as connection:
            record = record_module.read(connection, settings.schema, subject=settings.database)
    path = write_report(record, args.out)
    print(
        f"wrote {path} ({path.stat().st_size // 1024} KB) — "
        f"{len(record.dossiers)} hypotheses, {record.budget_spent}/"
        f"{record.budget_total} probes spent"
    )
    return 0
