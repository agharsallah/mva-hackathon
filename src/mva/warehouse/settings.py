"""Connection settings, read from ``.env`` or the environment.

A deliberately small loader rather than a dependency. It understands the subset of
``.env`` syntax that people actually write — ``KEY=value``, ``export KEY=value``,
``#`` comments, optional surrounding quotes — and nothing else, because anything more
elaborate belongs in a real config file rather than a secret store.

Two rules shape everything here.

**The real environment wins over the file.** ``PGPASSWORD`` exported in a shell, or
injected by CI, must not be silently overridden by a stale ``.env`` someone forgot to
delete. The file is a convenience for local work, not the source of truth.

**The password is never rendered.** :meth:`Postgres.describe` and every ``__repr__`` on
this class redact it, so a settings object can be printed in a log or a traceback without
leaking the credential. The only method that emits it is :meth:`dsn`, which exists to be
handed to DuckDB and is never printed.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

#: Keys read from the environment, with their defaults. ``PGPASSWORD`` has no default
#: on purpose: a blank password should fail loudly rather than attempt a connection.
DEFAULTS = {
    "PGHOST": "localhost",
    "PGPORT": "5432",
    "PGDATABASE": "mva",
    "PGUSER": "mva",
    "PGPASSWORD": "",
    "PGSCHEMA": "warehouse",
    "PGRESULTSCHEMA": "results",
    "S3_ENDPOINT": "",
    "S3_ACCESS_KEY": "",
    "S3_SECRET_KEY": "",
    "S3_BUCKET": "mva",
    "S3_USE_SSL": "true",
    "MVA_SOURCE_DIR": str(Path.home() / "ubuntu" / "data"),
    "MVA_STAGING_DIR": str(Path.home() / "mva-staging"),
    "MVA_HF_REPO": "SageBio/mva-hackathon-2026-data",
    "MVA_API_TOKEN": "",
    "MVA_API_JOB_WORKERS": "2",
    "MVA_READS_API_URL": "http://127.0.0.1:8765",
    "MVA_VIZ_CORS": "http://localhost:5173,http://127.0.0.1:5173",
    "MVA_VIZ_CACHE": "build/viz-cache",
}

#: Looked for upward from the working directory, so the CLI works from a subdirectory.
ENV_FILENAME = ".env"


def setting(key: str, start: Path | None = None) -> str:
    """One setting, resolved by the same precedence as everything else here.

    Real environment first, then the nearest ``.env``, then :data:`DEFAULTS`. Use it for
    the plain-string knobs — a directory, a repository name — that do not belong to the
    Postgres or object-store settings objects.
    """
    env_path = find_env(start)
    from_file = parse_env(env_path.read_text(encoding="utf-8")) if env_path else {}
    return os.environ.get(key) or from_file.get(key) or DEFAULTS.get(key, "")


def find_env(start: Path | None = None) -> Path | None:
    """Locate the nearest ``.env``, walking upward from ``start`` to the filesystem root."""
    current = (start or Path.cwd()).resolve()
    for directory in (current, *current.parents):
        candidate = directory / ENV_FILENAME
        if candidate.is_file():
            return candidate
    return None


def parse_env(text: str) -> dict[str, str]:
    """Parse ``.env`` text into a mapping.

    Blank lines and ``#`` comments are skipped, a leading ``export`` is tolerated, and one
    matching pair of surrounding quotes is stripped. A line without ``=`` is ignored rather
    than raising — a half-written file should not stop the tool from reporting *which*
    settings it is missing.
    """
    values: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        line = line.removeprefix("export ").lstrip()
        key, separator, value = line.partition("=")
        if not separator:
            continue
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key:
            values[key] = value
    return values


@dataclass(frozen=True)
class Postgres:
    """Where the hosted database is, and which schemas the pipeline may write.

    ``schema`` holds ingested source tables; ``result_schema`` holds what the pipeline
    derives. They are separate so that re-ingesting can drop and rebuild one without
    touching the other.
    """

    host: str = "localhost"
    port: str = "5432"
    database: str = "mva"
    user: str = "mva"
    password: str = field(default="", repr=False)
    schema: str = "warehouse"
    result_schema: str = "results"

    @classmethod
    def from_env(cls, start: Path | None = None) -> "Postgres":
        """Build settings from the nearest ``.env``, with the real environment winning."""
        env_path = find_env(start)
        from_file = parse_env(env_path.read_text(encoding="utf-8")) if env_path else {}
        resolved = {
            key: os.environ.get(key) or from_file.get(key) or default
            for key, default in DEFAULTS.items()
        }
        return cls(
            host=resolved["PGHOST"], port=resolved["PGPORT"],
            database=resolved["PGDATABASE"], user=resolved["PGUSER"],
            password=resolved["PGPASSWORD"], schema=resolved["PGSCHEMA"],
            result_schema=resolved["PGRESULTSCHEMA"],
        )

    @property
    def missing(self) -> list[str]:
        """Settings that must be supplied and were not. Empty means ready to connect."""
        return [key for key, value in (("PGHOST", self.host), ("PGDATABASE", self.database),
                                       ("PGUSER", self.user), ("PGPASSWORD", self.password))
                if not value]

    def dsn(self) -> str:
        """A libpq connection string for DuckDB's ``ATTACH``. Contains the password."""
        return (f"host={self.host} port={self.port} dbname={self.database} "
                f"user={self.user} password={self.password}")

    def describe(self) -> str:
        """A one-line summary safe to print: the password is redacted."""
        secret = "set" if self.password else "MISSING"
        return (f"{self.user}@{self.host}:{self.port}/{self.database} "
                f"(password: {secret}, schemas: {self.schema} + {self.result_schema})")

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"Postgres({self.describe()})"


def object_store(start: Path | None = None):
    """Build :class:`~mva.warehouse.objects.ObjectStore` settings from the same sources.

    Kept here rather than in :mod:`mva.warehouse.objects` so that every credential this
    tool reads is resolved by one loader with one precedence rule, and there is a single
    place to look when something is picked up from the wrong file.
    """
    from .objects import ObjectStore

    env_path = find_env(start)
    from_file = parse_env(env_path.read_text(encoding="utf-8")) if env_path else {}
    value = lambda key: os.environ.get(key) or from_file.get(key) or DEFAULTS[key]
    return ObjectStore(
        endpoint=value("S3_ENDPOINT"),
        access_key=value("S3_ACCESS_KEY"),
        secret_key=value("S3_SECRET_KEY"),
        bucket=value("S3_BUCKET"),
        use_ssl=value("S3_USE_SSL").strip().lower() not in ("false", "0", "no"),
    )
