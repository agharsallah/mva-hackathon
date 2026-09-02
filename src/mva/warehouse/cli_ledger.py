"""The ``lineage-*`` and ``probe-*`` verbs: the two ledgers nobody can reconstruct later.

Both answer questions that only have an answer if somebody wrote it down at the time.
``lineage-*`` answers "which bytes produced this table"; ``probe-*`` answers "which of our
eighteen oracle submissions is this, who spent it, and what came back".

They share a module because they share a shape: an append-only table in the ingest schema,
a verb that adds a row, and a verb that reads the table back. Neither ever updates or
deletes — a correction is a newer row that says what it supersedes.
"""

from pathlib import Path

from . import lineage, probes
from .postgres import attached, render_table
from .settings import Postgres, object_store


def _settings() -> Postgres:
    return Postgres.from_env()


def do_lineage_repair(args) -> int:
    """Repoint local-path lineage edges at the verified object in the store.

    Append, not update: :mod:`mva.warehouse.lineage` is append-only by design ("lineage that
    can be edited is not evidence"), so the correction is a *newer* edge whose ``notes``
    name the timestamp of the row it supersedes. The old edge stays as the record of what
    was originally claimed.
    """
    settings = _settings()
    bucket = args.bucket or object_store().bucket
    with attached(settings) as connection:
        lineage.ensure_tables(connection, settings.schema)
        appended = lineage.repoint(connection, settings.schema, bucket)
    if not appended:
        print("nothing to repair — every lineage edge already names an object in the store")
        return 0
    for item in appended:
        print(f"  {item['target']}")
        print(f"    was      {item['was']}")
        print(f"    now      {item['now']}")
        print(f"    sha256   {item['sha256']}")
        print(f"    version  {item['version_id']}")
    print(
        f"\n{len(appended)} superseding edge(s) appended to "
        f"{settings.schema}.{lineage.LINEAGE_TABLE}"
    )
    return 0


def do_lineage_backfill(args) -> int:
    """Give every already-logged derivation run the lineage edge it never got."""
    settings = _settings()
    with attached(settings) as connection:
        lineage.ensure_tables(connection, settings.schema)
        appended = lineage.backfill_derivations(connection, settings.schema, settings.result_schema)
    if not appended:
        print("nothing to backfill — every logged derivation run already has an edge")
        return 0
    for item in appended:
        print(
            f"  {item['target']:<28} {item['rows']:>5} rows  <- {item['sources']}"
            f"   (run {item['run']})"
        )
    print(
        f"\n{len(appended)} derivation edge(s) appended to "
        f"{settings.schema}.{lineage.LINEAGE_TABLE}"
    )
    return 0


LINEAGE_COLUMNS = (
    "produced_at",
    "target_schema",
    "target_table",
    "target_rows",
    "source_kind",
    "source_ref",
    "source_version",
    "source_sha256",
    "tool",
    "notes",
    "is_current",
)


def do_lineage_list(args) -> int:
    """Show the edge list, newest edge per target first, superseded rows included."""
    settings = _settings()
    with attached(settings, read_only=True) as connection:
        rows = lineage.edges(connection, settings.schema)
    if args.current:
        rows = [row for row in rows if row[-1]]
    trimmed = [
        (
            *row[:5],
            row[5][:48],
            (row[6] or "")[:12],
            (row[7] or "")[:12],
            row[8],
            (row[9] or "")[:40],
            row[10],
        )
        for row in rows
    ]
    print(render_table(LINEAGE_COLUMNS, trimmed))
    return 0


def do_probe_log(args) -> int:
    """Record one spent oracle submission. Refuses nothing — a probe is spent either way."""
    settings = _settings()
    payload = args.payload or ""
    n_rows = args.rows
    if args.payload_file:
        path = Path(args.payload_file)
        payload = path.read_text(encoding="utf-8")
        if n_rows is None:
            n_rows = max(len(payload.strip().splitlines()) - 1, 0)
    probe = probes.Probe(
        track=args.track,
        probe_type=args.type,
        submitted_by=args.by,
        submission_ref=args.ref or (str(args.payload_file) if args.payload_file else ""),
        payload=payload,
        n_rows=n_rows or 0,
        response=args.response or "",
        score=args.score,
        rationale=args.rationale or "",
    )
    with attached(settings) as connection:
        probes.ensure_table(connection, settings.schema)
        probe_id = probes.log(connection, settings.schema, probe)
        left = probes.budget(connection, settings.schema)
    print(f"logged probe {probe_id} into {settings.schema}.{probes.PROBE_TABLE}")
    print(f"budget: {left}")
    return 0


def do_probe_list(args) -> int:
    """Show the ledger and what is left of the allowance."""
    settings = _settings()
    with attached(settings) as connection:
        probes.ensure_table(connection, settings.schema)
        rows = probes.listing(connection, settings.schema, args.limit or 0)
        left = probes.budget(connection, settings.schema)
    print(render_table(probes.LISTING_COLUMNS, rows))
    print(f"\nbudget: {left}")
    return 0


def do_probe_budget(args) -> int:
    """The one-line answer: how many of the eighteen are left."""
    settings = _settings()
    with attached(settings) as connection:
        probes.ensure_table(connection, settings.schema)
        left = probes.budget(connection, settings.schema, args.track)
    scope = f"track {args.track}" if args.track else "all tracks"
    print(f"{scope}: {left}")
    return 0


def register(subparsers) -> None:
    """Attach the ``lineage-*`` and ``probe-*`` verbs to the top-level parser."""
    repair = subparsers.add_parser(
        "lineage-repair", help="append superseding edges for inputs still recorded as local paths"
    )
    repair.add_argument("--bucket", help="object-store bucket (default: S3_BUCKET)")
    repair.set_defaults(handler=do_lineage_repair)

    backfill = subparsers.add_parser(
        "lineage-backfill", help="append a lineage edge for every already-logged derivation run"
    )
    backfill.set_defaults(handler=do_lineage_backfill)

    listing = subparsers.add_parser(
        "lineage-list", help="show the lineage edge list, superseded rows included"
    )
    listing.add_argument(
        "--current", action="store_true", help="only the newest edge per target table"
    )
    listing.set_defaults(handler=do_lineage_list)

    log = subparsers.add_parser(
        "probe-log", help="record one spent oracle submission in the probe ledger"
    )
    log.add_argument("--track", default="1", help="hackathon track (default: 1)")
    log.add_argument(
        "--type",
        default="other",
        choices=list(probes.PROBE_TYPES),
        help="probe kind from the oracle protocol",
    )
    log.add_argument("--by", required=True, help="who spent this submission")
    log.add_argument("--ref", help="where the submitted file lives (path or s3:// key)")
    log.add_argument("--payload", help="the submitted content, inline")
    log.add_argument(
        "--payload-file",
        dest="payload_file",
        type=Path,
        help="read the submitted content from this CSV",
    )
    log.add_argument("--rows", type=int, help="rows submitted (default: counted from CSV)")
    log.add_argument("--response", help="what the scorer replied, verbatim")
    log.add_argument("--score", type=float, help="rank_points, if the reply carried one")
    log.add_argument("--rationale", help="why this probe, and what it was meant to decide")
    log.set_defaults(handler=do_probe_log)

    plist = subparsers.add_parser("probe-list", help="show the probe ledger and the budget")
    plist.add_argument("--limit", type=int, help="show at most this many rows")
    plist.set_defaults(handler=do_probe_list)

    pbudget = subparsers.add_parser(
        "probe-budget", help=f"how many of the {probes.BUDGET} oracle submissions are left"
    )
    pbudget.add_argument("--track", help="count only this track")
    pbudget.set_defaults(handler=do_probe_budget)
