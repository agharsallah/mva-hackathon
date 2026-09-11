"""Where the read store lives and how to open it — shared by the CLI and the API.

Both front ends resolve the same two things before any query: the store *root* (an
``s3://`` prefix by default, a staging directory during a build) and a DuckDB
connection able to read it (carrying the object-store secret when the root is remote).
Kept in one module so the two front ends can never disagree about either.
"""

from ..warehouse.settings import object_store
from . import schema


def s3_root(cfg=None) -> str:
    """The store's object-store prefix, e.g. ``s3://mva/reads``."""
    cfg = cfg or object_store()
    return f"s3://{cfg.bucket}/{schema.PREFIX}"


def resolve_root(root: str | None = None) -> str:
    """The root to query: the caller's choice, else the object store."""
    return root or s3_root()


def storage_options(root: str) -> dict[str, str] | None:
    """Object-store credentials in the spelling Polars/object_store expects.

    DuckDB takes the secret through a `CREATE SECRET` in :func:`connection`; Polars takes
    it as a dict on every scan. Same credentials, two dialects — written once here so a
    rotated key cannot reach one reader and miss the other. ``None`` for a local root.
    """
    if not root.startswith("s3://"):
        return None
    store = object_store()
    scheme = "https" if store.use_ssl else "http"
    return {
        "aws_access_key_id": store.access_key,
        "aws_secret_access_key": store.secret_key,
        "aws_endpoint_url": f"{scheme}://{store.endpoint}",
        "aws_region": store.region,
        "aws_allow_http": str(not store.use_ssl).lower(),
    }


def connection(root: str):
    """A DuckDB connection able to read ``root`` — with the store secret when remote."""
    if root.startswith("s3://"):
        from ..warehouse.objects import connect

        return connect(object_store())
    import duckdb

    return duckdb.connect()
