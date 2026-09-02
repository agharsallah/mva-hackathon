"""``source-fetch``: pipe the delivery from the publisher (a gated Hugging Face dataset
repo) straight into the bucket, without landing it on this machine first.

Meant to run **on the server**, where the link to the publisher is far faster than a
domestic upload and the hop into the object store is local. Kept apart from
:mod:`.upload` because it talks to a third party (Hugging Face) instead of reading a
directory that is already on disk.
"""

import datetime
import os
from pathlib import Path

from .. import source
from ..settings import Postgres
from . import context


def do_fetch(args) -> int:
    """Pipe the delivery from the publisher into the bucket, without touching disk.

    By default the bytes are streamed: read from the publisher and written to the bucket in
    one pass, with no staging file. Nothing is hashed, because ``huggingface_hub`` and the
    CDN already validate the transfer and a second pass would mean landing 85 GB on disk
    purely to re-read it.

    ``--verify`` opts back in: the file is downloaded to ``--staging``, hashed, checked
    against the publisher's own SHA-256, uploaded, then deleted. Slower and needs disk for
    one file, but it is the stronger evidence if a transfer is ever disputed.
    """
    store = context.object_store()
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
    with context.attached(settings) as connection:
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
    key = f"{source.PREFIX}/{name}"
    tee = (args.tee / name) if args.tee else None
    try:
        result = source.stream_to_bucket(
            store, args.repo, name, key, token, context.progress("streaming", 0), tee
        )
    except Exception as error:
        context.clear()
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
    context.clear()
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
    local = source.fetch(args.repo, name, args.staging, args.token or os.environ.get("HF_TOKEN"))
    size = local.stat().st_size
    digest = source.checksum(local, context.progress("hashing", size))
    context.clear()
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
    result = source.upload(store, item, context.progress("uploading", size))
    context.clear()
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
