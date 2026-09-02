"""The ``source-*`` verbs: put the delivery into the landing zone, unchanged.

These are deliberately separate from every other family in the tool. The rest of
``mva-warehouse`` moves *derived* data — things that can be rebuilt if they are wrong.
These move the delivery itself, which cannot be rebuilt, so they hash before sending,
verify after, record what happened, and never overwrite.
"""

import sys
import time
from pathlib import Path

from . import source
from .postgres import ALIAS, attached, safe_identifier
from .settings import Postgres, object_store, setting

#: Delivery directory, staging scratch directory, and the (gated) dataset the delivery
#: came from. All three resolve as real environment > ``.env`` > ``settings.DEFAULTS``.
DEFAULT_SOURCE = Path(setting("MVA_SOURCE_DIR"))
DEFAULT_STAGING = Path(setting("MVA_STAGING_DIR"))
DEFAULT_REPO = setting("MVA_HF_REPO")


#: Width used to blank the progress line. Anything shorter leaves fragments of a longer
#: previous line on screen, which is how a tidy status display turns into noise.
LINE = 96


#: In-place progress needs a terminal. Piped to a log — which is how an hours-long
#: transfer should actually be run — carriage returns and blanking spaces become noise
#: that buries the real output, so the whole progress line is simply suppressed.
def _interactive() -> bool:
    return sys.stdout.isatty()


def _clear() -> None:
    """Blank the in-place progress line and return the cursor to its start."""
    if not _interactive():
        return
    sys.stdout.write("\r" + " " * LINE + "\r")
    sys.stdout.flush()


def _progress(label: str, total: int):
    """A callback printing one rewritten line, so a long upload visibly moves.

    Rate is computed over the whole transfer rather than the last chunk: an instantaneous
    figure on a multipart upload swings wildly enough to be useless for deciding whether
    to wait or cancel.
    """
    state = {"done": 0, "last": 0.0, "start": time.time()}
    if not _interactive():
        return lambda chunk: None

    def report(chunk: int) -> None:
        state["done"] += chunk
        now = time.time()
        if now - state["last"] < 0.5 and state["done"] < total:
            return
        state["last"] = now
        pct = 100.0 * state["done"] / total if total else 100.0
        rate = state["done"] / max(now - state["start"], 0.001) / 1e6
        eta = (total - state["done"]) / (rate * 1e6) if rate > 0 else 0
        _clear()
        sys.stdout.write(
            f"    {label:<30} {pct:5.1f}%  {state['done'] / 1e9:5.2f}/{total / 1e9:.2f} GB"
            f"  {rate:5.1f} MB/s  eta {eta / 60:4.1f}m"
        )
        sys.stdout.flush()

    return report


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
    store = object_store()
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

    with attached(settings) as connection:
        source.ensure_ledger(connection, settings.schema)
        for item in items:
            existing = source.remote_state(store, item.key)

            print(f"  {item.path.name}")
            started = time.time()
            digest = source.checksum(item.path, _progress("hashing", item.size))
            _clear()
            item = source.SourceFile(item.path, item.size, item.modified, digest)
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

            result = source.upload(store, item, _progress("uploading", item.size))
            _clear()

            after = source.remote_state(store, item.key) or {}
            verified = after.get("size") == item.size and after.get("sha256") == digest
            elapsed = max(time.time() - started, 0.001)
            print(
                f"    uploaded {item.size / 1e9:.2f} GB in {elapsed / 60:.1f} min "
                f"({item.size / elapsed / 1e6:.1f} MB/s)"
            )
            print(f"    version  {result.get('version_id', '') or 'n/a'}")
            print(f"    verified {'yes' if verified else 'NO — size or hash mismatch'}\n")
            source.record(connection, settings.schema, item, result, verified)
    print(f"ledger updated: {settings.schema}.{source.LEDGER_TABLE}")
    return 0


def do_status(args) -> int:
    """Compare the delivery on disk with what the ledger says was uploaded."""
    settings = Postgres.from_env()
    items = {i.path.name: i for i in source.scan(args.directory)}
    with attached(settings, read_only=True) as connection:
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


def register(subparsers) -> None:
    """Attach the ``source-*`` verbs to the top-level parser."""

    def add(name, handler, help_text):
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument(
            "--directory",
            type=Path,
            default=DEFAULT_SOURCE,
            help=f"the delivery directory (default: {DEFAULT_SOURCE})",
        )
        sub.set_defaults(handler=handler)
        return sub

    add("source-scan", do_scan, "inventory the delivery without uploading")
    upload = add(
        "source-upload", do_upload, "hash, upload unchanged, verify, and record in the ledger"
    )
    upload.add_argument(
        "--only", nargs="*", help="file names or kinds (fastq, vcf, index, document)"
    )
    upload.add_argument(
        "--force",
        action="store_true",
        help="re-upload even when an identical copy is already there",
    )
    add("source-status", do_status, "compare the delivery on disk with the ledger")
    add("source-check", do_check, "survey the bucket, verify hashes, refresh the object inventory")

    fetch = subparsers.add_parser(
        "source-fetch",
        help="RUN ON THE SERVER: download from the publisher straight into the bucket",
    )
    fetch.add_argument("--repo", default=DEFAULT_REPO, help="Hugging Face dataset repo")
    fetch.add_argument("--only", nargs="*", help="file names (default: all published)")
    fetch.add_argument("--token", help="Hugging Face token; else $HF_TOKEN")
    fetch.add_argument(
        "--staging",
        type=Path,
        default=DEFAULT_STAGING,
        help="scratch directory, used only with --verify",
    )
    fetch.add_argument(
        "--keep",
        action="store_true",
        help="with --verify, keep the downloaded copy instead of deleting",
    )
    fetch.add_argument(
        "--tee",
        type=Path,
        help="also write each streamed file here, so a failed upload does "
        "not throw the download away",
    )
    fetch.add_argument(
        "--verify",
        action="store_true",
        help="download to disk and check the publisher's SHA-256 first "
        "(slower, needs disk for one file)",
    )
    fetch.set_defaults(handler=do_fetch)


def do_fetch(args) -> int:
    """Pipe the delivery from the publisher into the bucket, without touching disk.

    Meant to run **on the server**, where the link to the publisher is far faster than a
    domestic upload and the hop into MinIO is local.

    By default the bytes are streamed: read from the publisher and written to the bucket in
    one pass, with no staging file. Nothing is hashed, because ``huggingface_hub`` and the
    CDN already validate the transfer and a second pass would mean landing 85 GB on disk
    purely to re-read it.

    ``--verify`` opts back in: the file is downloaded to ``--staging``, hashed, checked
    against the publisher's own SHA-256, uploaded, then deleted. Slower and needs disk for
    one file, but it is the stronger evidence if a transfer is ever disputed.
    """
    import os

    store = object_store()
    if store.missing:
        print("missing object-store settings: " + ", ".join(store.missing))
        return 1
    token = args.token or os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if not token:
        print(
            "no Hugging Face token. The dataset is gated, so one is required:\n"
            "    export HF_TOKEN=hf_...            (or pass --token)\n"
            "The token's account must have been granted access to the dataset."
        )
        return 1

    expected = source.published_hashes()
    names = args.only or sorted(expected)
    if not names:
        print("nothing to fetch — no published hash table and no --only given")
        return 1

    settings = Postgres.from_env()
    print(f"repo       {args.repo}")
    mode = (
        "download, verify, upload"
        if args.verify
        else (f"streamed, teed to {args.tee}" if args.tee else "streamed — no disk")
    )
    print(f"mode       {mode}")
    print(f"versioning on {store.bucket}: {source.enable_versioning(store)}\n")

    failures = 0
    with attached(settings) as connection:
        source.ensure_ledger(connection, settings.schema)
        for name in names:
            print(f"  {name}")
            try:
                if args.verify:
                    ok = _fetch_verified(
                        args, store, connection, settings, name, expected.get(name, "")
                    )
                else:
                    ok = _fetch_streamed(args, store, connection, settings, name, token)
            except Exception as error:
                print(f"    FAILED: {str(error).splitlines()[0][:140]}\n")
                ok = False
            failures += 0 if ok else 1

    print(f"done. {len(names) - failures}/{len(names)} succeeded.")
    return 1 if failures else 0


def _fetch_streamed(args, store, connection, settings, name: str, token: str) -> bool:
    """Publisher -> bucket in one pass, no staging file."""
    import datetime

    key = f"{source.PREFIX}/{name}"
    tee = (args.tee / name) if args.tee else None
    try:
        result = source.stream_to_bucket(
            store, args.repo, name, key, token, _progress("streaming", 0), tee
        )
    except Exception as error:
        _clear()
        print(f"    UPLOAD FAILED: {str(error).splitlines()[0][:120]}")
        if tee and tee.exists():
            print(f"    kept     {tee} ({tee.stat().st_size / 1e9:.2f} GB downloaded)")
            print("             the download is not lost; finish it with:")
            print(
                f"             mva-warehouse source-upload --directory {tee.parent} --only {name}"
            )
        else:
            print("    the download was discarded with the failed upload. Re-run with --tee DIR")
            print("    to keep the bytes on disk next time.")
        print()
        return False
    _clear()
    declared = result.get("declared_size", 0)
    landed = result.get("size", 0)
    # The only integrity check that costs nothing: the store must hold as many bytes as
    # the publisher said it was sending. A truncated stream shows up here.
    consistent = bool(landed) and (not declared or landed == declared)
    print(
        f"    size     {landed / 1e9:.2f} GB"
        + ("" if consistent else f"  MISMATCH — publisher declared {declared:,}")
    )
    print(f"    version  {result.get('version_id', '') or 'n/a'}")
    item = source.SourceFile(Path(name), landed, datetime.datetime.now(datetime.UTC), "")
    source.record(connection, settings.schema, item, result, consistent)
    print()
    return consistent


def _fetch_verified(args, store, connection, settings, name: str, want: str) -> bool:
    """Download to disk, hash, compare with the publisher, upload, then delete."""
    import datetime

    local = source.fetch(
        args.repo, name, args.staging, args.token or __import__("os").environ.get("HF_TOKEN")
    )
    size = local.stat().st_size
    digest = source.checksum(local, _progress("hashing", size))
    _clear()
    if want and digest != want:
        # The publisher's own hash disagreeing means these are not the delivery.
        # Uploading them would poison the source of truth.
        print("    HASH MISMATCH — not uploading")
        print(f"      published  {want}")
        print(f"      downloaded {digest}\n")
        local.unlink(missing_ok=True)
        return False
    print(f"    sha256   {digest}{'  (matches publisher)' if want else ''}")

    item = source.SourceFile(
        local, size, datetime.datetime.fromtimestamp(local.stat().st_mtime, tz=datetime.UTC), digest
    )
    result = source.upload(store, item, _progress("uploading", size))
    _clear()
    after = source.remote_state(store, item.key) or {}
    verified = after.get("size") == size and after.get("sha256") == digest
    print(f"    version  {result.get('version_id', '') or 'n/a'}")
    print(f"    verified {'yes' if verified else 'NO — size or hash mismatch'}")
    source.record(connection, settings.schema, item, result, verified)
    # Only ever delete a download that made it to the bucket intact. Removing it after a
    # failed upload would mean re-fetching gigabytes to retry something that had already
    # arrived once.
    if verified and not args.keep:
        local.unlink(missing_ok=True)
        print("    removed local copy")
    elif not verified:
        print(f"    kept     {local} — retry with:")
        print(
            f"             mva-warehouse source-upload --directory {local.parent} "
            f"--only {local.name}"
        )
    print()
    return verified


def do_check(args) -> int:
    """Survey the bucket, verify every hash, and refresh the object inventory.

    The reference hash is the **publisher's**, not our own upload record, so this compares
    against an external authority rather than re-confirming an earlier claim of ours.
    """
    from . import lineage

    store = object_store()
    if store.missing:
        print("missing object-store settings: " + ", ".join(store.missing))
        return 1
    settings = Postgres.from_env()
    published = source.published_hashes()

    with attached(settings) as connection:
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
