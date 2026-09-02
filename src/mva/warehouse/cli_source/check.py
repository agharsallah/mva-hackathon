"""``source-check``: survey the bucket, verify every hash against the **publisher's**
own value, and refresh the object inventory (:mod:`..lineage`).

Separate from :mod:`.upload` and :mod:`.fetch` because it inspects what already landed
rather than moving new bytes — the reference it checks against is external evidence
(the publisher's SHA-256), not our own upload record, so this is an audit, not a retry.
"""

from .. import lineage, source
from ..postgres import ALIAS, safe_identifier
from ..settings import Postgres
from . import context


def do_check(args) -> int:
    """Survey the bucket, verify every hash, and refresh the object inventory."""
    store = context.object_store()
    if store.missing:
        print("missing object-store settings: " + ", ".join(store.missing))
        return 1
    settings = Postgres.from_env()
    published = source.published_hashes()

    with context.attached(settings) as connection:
        lineage.ensure_tables(connection, settings.schema)
        recorded = dict(
            connection.execute(
                f"SELECT DISTINCT file_name, sha256 FROM {ALIAS}."
                f"{safe_identifier(settings.schema)}.{source.LEDGER_TABLE} "
                "WHERE sha256 <> ''"
            ).fetchall()
        )
        rows = lineage.survey(store, published, recorded)
        lineage.replace_objects(connection, settings.schema, store.bucket, rows)

    width = max(len(r["file_name"]) for r in rows)
    unverified = []
    for row in rows:
        mark = "ok" if row["hash_verified"] else ("no hash" if not row["sha256"] else "UNCHECKED")
        if not row["hash_verified"]:
            unverified.append(row["file_name"])
        lane = f"L{row['lane']} R{row['read_num']}" if row["lane"] else ""
        print(
            f"  {row['file_name']:<{width}}  {row['role']:<14} "
            f"{row['size_bytes'] / 1e9:>7.2f} GB  {lane:<6} {mark}"
        )

    total = sum(r["size_bytes"] for r in rows)
    print(f"\n  {len(rows)} objects, {total / 1e9:.2f} GB")
    print(f"  {len(rows) - len(unverified)} hash-verified against the publisher")
    if unverified:
        print(f"  not verified: {', '.join(unverified)}")
    print(f"\ninventory refreshed: {settings.schema}.{lineage.OBJECTS_TABLE}")
    return 0
