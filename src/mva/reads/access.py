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


def connection(root: str):
    """A DuckDB connection able to read ``root`` — with the store secret when remote."""
    if root.startswith("s3://"):
        from ..warehouse.objects import connect

        return connect(object_store())
    import duckdb

    return duckdb.connect()
