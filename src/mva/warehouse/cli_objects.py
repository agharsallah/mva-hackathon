"""The ``s3-*`` verbs: work with the bulk files without downloading them.

These target the object store on the server rather than PostgreSQL. The distinction is not
arbitrary: Postgres holds the tables people query interactively and edit, while the object
store holds the large immutable files — raw layers, read Parquet — that are scanned and
never updated.

``s3-query`` is the one that matters day to day. It runs SQL against a file that never
leaves the server, transferring only the byte ranges the query needs.
"""

from pathlib import Path

from . import objects
from .settings import object_store


def _store(args):
    """Resolve object-store settings, letting ``--bucket`` override the environment."""
    from dataclasses import replace

    store = object_store()
    return replace(store, bucket=args.bucket) if getattr(args, "bucket", None) else store


def do_check(args) -> int:
    """Show the resolved settings, then prove the store answers."""
    store = _store(args)
    print(f"target: {store.describe()}")
    if store.missing:
        print("\nmissing: " + ", ".join(store.missing))
        print("Run tools/setup-object-store.sh on the server, then paste its block into .env.")
        return 1

    try:
        entries = objects.listing(store)
    except objects.UnreachableError as error:
        print(f"\n{error}")
        return 1
    print(f"\nconnected. {len(entries)} object(s) in {store.bucket}:")
    for key in entries[:20]:
        print(f"  {key}")
    if len(entries) > 20:
        print(f"  … and {len(entries) - 20} more")
    print(f"\nconsole (browser): {objects.console_url(store)}")
    return 0


def do_put(args) -> int:
    """Upload one Parquet into the bucket."""
    store = _store(args)
    key = args.key or Path(args.file).name
    size = Path(args.file).stat().st_size
    print(f"uploading {args.file} ({size / 1e6:.0f} MB) -> {store.url(key)}")
    print("landed:", objects.put(store, Path(args.file), key))
    return 0


def do_ls(args) -> int:
    """List what is in the bucket."""
    store = _store(args)
    entries = objects.listing(store, args.prefix or "")
    for key in entries:
        print(f"  {key}")
    print(f"{len(entries)} object(s)")
    return 0


def do_query(args) -> int:
    """Run one statement against the object store."""
    print(objects.query(_store(args), args.sql))
    return 0


def do_sort(args) -> int:
    """Rewrite an object clustered by the columns you filter on.

    Worth doing to anything that will be filtered repeatedly: row-group statistics can only
    skip a group when the filter column is clustered, and the difference is large — a gene
    lookup measured at 24.6% of the file unsorted and 0.6% sorted.
    """
    store = _store(args)
    print(f"rewriting {args.source} ordered by {', '.join(args.by)}")
    print("landed:", objects.sorted_copy(store, store.url(args.source), args.key, args.by))
    return 0


def register(subparsers) -> None:
    """Attach the ``s3-*`` verbs to the top-level parser."""

    def add(name, handler, help_text):
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument("--bucket", help="override S3_BUCKET")
        sub.set_defaults(handler=handler)
        return sub

    add("s3-check", do_check, "show object-store settings and list the bucket")

    put = add("s3-put", do_put, "upload a Parquet into the bucket")
    put.add_argument("file", type=Path)
    put.add_argument("--key", help="destination name (default: the filename)")

    ls = add("s3-ls", do_ls, "list objects in the bucket")
    ls.add_argument("prefix", nargs="?", default="")

    query = add(
        "s3-query", do_query, "run SQL against the store, downloading only the byte ranges needed"
    )
    query.add_argument("sql", help="use s3://bucket/key.parquet in the FROM clause")

    sort = add("s3-sort", do_sort, "rewrite an object clustered for fast filtering")
    sort.add_argument("source", help="existing key in the bucket")
    sort.add_argument("--key", required=True, help="destination key")
    sort.add_argument("--by", nargs="+", required=True, help="columns to order by")
