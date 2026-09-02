"""The three verbs that work against the delivery directory on this machine:
``source-scan`` (inventory only), ``source-upload`` (hash, upload, verify, record) and
``source-status`` (compare disk against the ledger). All three read the same local
directory; ``source-upload`` is the only one of the three that writes anywhere.
"""

import time

from .. import source
from ..postgres import ALIAS, safe_identifier
from ..settings import Postgres
from . import context


def do_scan(args) -> int:
    """Inventory the delivery directory without uploading anything."""
    items = source.scan(args.directory)
    if not items:
        print(f"nothing found in {args.directory}")
        return 1
    width = max(len(i.path.name) for i in items)
    total = 0
    for item in items:
        total += item.size
        print(f"  {item.path.name:<{width}}  {item.kind:<9} {item.size / 1e9:>8.2f} GB")
    print(f"  {'':<{width}}  {'TOTAL':<9} {total / 1e9:>8.2f} GB across {len(items)} files")
    return 0


def do_upload(args) -> int:
    """Hash, upload unchanged, verify, and record — one file at a time."""
    store = context.object_store()
    if store.missing:
        print("missing object-store settings: " + ", ".join(store.missing))
        return 1
    settings = Postgres.from_env()

    items = source.scan(args.directory)
    if args.only:
        wanted = set(args.only)
        items = [i for i in items if i.path.name in wanted or i.kind in wanted]
    if not items:
        print("nothing selected")
        return 1

    print(f"versioning on {store.bucket}: {source.enable_versioning(store)}")
    print(f"{len(items)} file(s), {sum(i.size for i in items) / 1e9:.2f} GB\n")

    with context.attached(settings) as connection:
        source.ensure_ledger(connection, settings.schema)
        for item in items:
            existing = source.remote_state(store, item.key)

            print(f"  {item.path.name}")
            started = time.time()
            digest = source.checksum(item.path, context.progress("hashing", item.size))
            context.clear()
            hashed = source.SourceFile(item.path, item.size, item.modified, digest)
            print(f"    sha256   {digest}")

            if existing and existing.get("sha256") == digest and not args.force:
                print(
                    "    skipped  identical copy already in the bucket "
                    f"(version {existing.get('version_id', '')[:12] or 'n/a'})\n"
                )
                continue
            if existing:
                print(
                    "    note     an object already exists here with a DIFFERENT hash; "
                    "versioning keeps the old one"
                )

            result = source.upload(store, hashed, context.progress("uploading", item.size))
            context.clear()

            after = source.remote_state(store, hashed.key) or {}
            verified = after.get("size") == item.size and after.get("sha256") == digest
            elapsed = max(time.time() - started, 0.001)
            print(
                f"    uploaded {item.size / 1e9:.2f} GB in {elapsed / 60:.1f} min "
                f"({item.size / elapsed / 1e6:.1f} MB/s)"
            )
            print(f"    version  {result.get('version_id', '') or 'n/a'}")
            print(f"    verified {'yes' if verified else 'NO — size or hash mismatch'}\n")
            source.record(connection, settings.schema, hashed, result, verified)
    print(f"ledger updated: {settings.schema}.{source.LEDGER_TABLE}")
    return 0


def do_status(args) -> int:
    """Compare the delivery on disk with what the ledger says was uploaded."""
    settings = Postgres.from_env()
    items = {i.path.name: i for i in source.scan(args.directory)}
    with context.attached(settings, read_only=True) as connection:
        safe = safe_identifier(settings.schema)
        try:
            rows = connection.execute(
                f"SELECT file_name, max(uploaded_at), count(*), any_value(size_bytes), "
                f"bool_and(verified) FROM {ALIAS}.{safe}.{source.LEDGER_TABLE} "
                "GROUP BY file_name"
            ).fetchall()
        except Exception:
            print("no ledger yet — run `source-upload` first")
            return 1
    ledger = {r[0]: r for r in rows}
    width = max([len(n) for n in items] + [4])
    print(f"  {'file':<{width}}  {'uploads':>7}  {'state':<28} size match")
    for name, item in items.items():
        entry = ledger.get(name)
        if entry is None:
            print(f"  {name:<{width}}  {'-':>7}  {'NOT UPLOADED':<28} -")
            continue
        state = f"last {entry[1]:%Y-%m-%d %H:%M}" + ("" if entry[4] else "  UNVERIFIED")
        match = "yes" if entry[3] == item.size else "NO"
        print(f"  {name:<{width}}  {entry[2]:>7}  {state:<28} {match}")
    missing = [n for n in items if n not in ledger]
    print(f"\n{len(items) - len(missing)}/{len(items)} uploaded")
    return 0
