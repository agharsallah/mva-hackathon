"""Query files that live on the server, from a laptop, without downloading them.

The problem this solves: the data is too large to keep locally, but SSHing into the box to
run every query is not working remotely. The answer is **object storage plus range
requests**. Files sit in an S3-compatible store on the server; DuckDB's ``httpfs``
extension asks for byte ranges over HTTP, and Parquet's layout means it can work out which
ranges it needs from the file's footer.

The consequence is the point, and it is measured in ``methodology/013``: a ``count(*)``
over a five-million-row Parquet transfers **0.5%** of the file, and a filtered aggregate
whose row groups can be pruned transfers **0.2%**. Nothing is cached locally and nothing is
downloaded whole.

That efficiency is not automatic. It comes from row-group statistics, which only prune when
the data is **sorted by the column you filter on** — the same filter costs 24.6% of the
file unsorted and 0.6% sorted. :func:`sorted_copy` exists to make that cheap to do.

S3 is used purely as a protocol here. MinIO on the server speaks it; nothing goes to AWS.
"""

from dataclasses import dataclass
from pathlib import Path

#: Name DuckDB stores the credentials under for the session.
SECRET_NAME = "mva_object_store"


@dataclass(frozen=True)
class ObjectStore:
    """Where the object store is and how to authenticate to it."""

    endpoint: str = ""
    access_key: str = ""
    secret_key: str = ""
    bucket: str = "mva"
    use_ssl: bool = True
    region: str = "us-east-1"

    @property
    def missing(self) -> list[str]:
        """Settings that must be supplied and were not."""
        return [name for name, value in (("S3_ENDPOINT", self.endpoint),
                                         ("S3_ACCESS_KEY", self.access_key),
                                         ("S3_SECRET_KEY", self.secret_key))
                if not value]

    def url(self, key: str) -> str:
        """The ``s3://`` URL for one object."""
        return f"s3://{self.bucket}/{key.lstrip('/')}"

    def describe(self) -> str:
        """A one-line summary safe to print: the secret key is redacted."""
        scheme = "https" if self.use_ssl else "http"
        secret = "set" if self.secret_key else "MISSING"
        return (f"{scheme}://{self.endpoint}/{self.bucket} "
                f"(key: {self.access_key or 'MISSING'}, secret: {secret})")

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"ObjectStore({self.describe()})"


def connect(store: ObjectStore):
    """A DuckDB connection wired to the object store.

    ``url_style='path'`` is required for MinIO and every other self-hosted S3: the
    virtual-host style AWS uses would resolve ``bucket.your-server`` in DNS, which does not
    exist. Getting this wrong produces a name-resolution error that looks nothing like a
    configuration problem.
    """
    import duckdb

    if store.missing:
        raise RuntimeError("missing settings: " + ", ".join(store.missing) +
                           " — add them to .env (see .env.example)")
    connection = duckdb.connect()
    connection.execute("INSTALL httpfs; LOAD httpfs;")
    connection.execute(f"""
        CREATE OR REPLACE SECRET {SECRET_NAME} (
            TYPE s3,
            KEY_ID '{store.access_key}',
            SECRET '{store.secret_key}',
            ENDPOINT '{store.endpoint}',
            REGION '{store.region}',
            URL_STYLE 'path',
            USE_SSL {str(store.use_ssl).lower()}
        )
    """)
    return connection


def put(store: ObjectStore, local: Path, key: str) -> str:
    """Upload one Parquet by having DuckDB rewrite it straight into the bucket.

    Going through DuckDB rather than an S3 client keeps the dependency list at zero and
    means the file is validated as readable Parquet on the way up: a corrupt local file
    fails here rather than months later when someone queries it.
    """
    url = store.url(key)
    with connect(store) as connection:
        connection.execute(
            f"COPY (SELECT * FROM read_parquet(?)) TO '{url}' "
            "(FORMAT parquet, COMPRESSION zstd)", [str(local)])
    return url


def sorted_copy(store: ObjectStore, source_url: str, key: str,
                order_by: list[str], row_group_size: int = 100_000) -> str:
    """Write a copy ordered by ``order_by``, so row-group pruning can work.

    This is the single highest-leverage thing you can do to a remote Parquet. Row-group
    statistics only exclude a group when its min/max cannot match the predicate, which
    requires the filter column to be clustered. Measured on a five-million-row file: the
    same gene lookup moved 24.6% of the file unsorted and 0.6% sorted, 1.03 s to 0.03 s.
    """
    columns = ", ".join(f'"{name}"' for name in order_by)
    url = store.url(key)
    with connect(store) as connection:
        connection.execute(
            f"COPY (SELECT * FROM '{source_url}' ORDER BY {columns}) TO '{url}' "
            f"(FORMAT parquet, COMPRESSION zstd, ROW_GROUP_SIZE {row_group_size})")
    return url


class Unreachable(RuntimeError):
    """The object store did not answer, with a diagnosis attached."""


def diagnose(store: ObjectStore, error: Exception) -> str:
    """Turn a transport failure into something actionable.

    A raw ``IOException: Could not connect`` says nothing about *why*, and the three
    causes need completely different fixes. Each is checked here so the message names one.
    """
    host, _, port = store.endpoint.partition(":")
    lines = [f"cannot reach the object store at {store.endpoint}", ""]

    if host in ("localhost", "127.0.0.1"):
        lines += [
            "S3_ENDPOINT points at localhost — that is THIS machine, not the server.",
            "That value is only correct while an SSH tunnel is open. Either:",
            "",
            f"  open the tunnel:  ssh -N -L {port or 9012}:localhost:{port or 9012} "
            f"<user>@<server>",
            "  or point straight at the server:  S3_ENDPOINT=<server-hostname>:"
            f"{port or 9012}",
            "",
        ]
    else:
        lines += [
            "Check, on the server:",
            f"  <podman|docker> ps --filter name=minio        # is it running?",
            f"  <podman|docker> port <container>              # is {port or 9012} published?",
            f"  curl -sf http://localhost:{port or 9012}/minio/health/live && echo OK",
            "",
            "Then from here:",
            f"  curl -v --max-time 5 http://{store.endpoint}/minio/health/live",
            "  (a hang or timeout means a firewall; 'connection refused' means nothing "
            "is listening)",
            "",
        ]

    if store.use_ssl:
        lines.append("S3_USE_SSL=true but MinIO serves plain HTTP unless you put TLS in "
                     "front of it — try S3_USE_SSL=false over a tunnel.")
    lines.append(f"underlying error: {str(error).splitlines()[0][:160]}")
    return "\n".join(lines)


def listing(store: ObjectStore, prefix: str = "") -> list[str]:
    """Every object key under ``prefix``.

    ``glob`` returns one column, the full URL. An earlier version invented a second
    ``size`` column and swallowed the failure in a bare ``except``, which turned a
    connection error into an empty listing — the worst possible outcome, since it looks
    exactly like an empty bucket.
    """
    pattern = store.url(f"{prefix.strip('/')}/**") if prefix else store.url("**")
    try:
        with connect(store) as connection:
            rows = connection.execute("SELECT * FROM glob(?)", [pattern]).fetchall()
    except RuntimeError:
        raise
    except Exception as error:
        raise Unreachable(diagnose(store, error)) from error
    return [str(row[0]) for row in rows]


def console_url(store: ObjectStore) -> str:
    """Best guess at the MinIO console address, for a human to open in a browser."""
    host, _, port = store.endpoint.partition(":")
    # setup-object-store.sh publishes the console one above the API port.
    guess = f"{int(port) + 1}" if port.isdigit() else "9013"
    return f"http://{host}:{guess}"


def query(store: ObjectStore, sql: str):
    """Run one statement against the object store, materialising the result.

    Materialised for the same reason the Postgres path is: a lazy relation whose connection
    has closed is an error waiting to happen at the call site.
    """
    from .postgres import Result

    with connect(store) as connection:
        relation = connection.sql(sql)
        if relation is None:
            return Result((), [])
        return Result(tuple(relation.columns), relation.fetchall())
