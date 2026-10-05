"""Runtime settings, read from ``.env`` or the environment.

A deliberately small loader rather than a dependency. It understands the subset of
``.env`` syntax that people actually write — ``KEY=value``, ``export KEY=value``, ``#``
comments, optional surrounding quotes — and nothing else, because anything more
elaborate belongs in a real config file rather than a secret store.

One rule shapes it: **the real environment wins over the file.** A token exported in a
shell, or injected by CI, must not be silently overridden by a stale ``.env`` someone
forgot to delete. The file is a convenience for local work, not the source of truth.
"""

import os
from functools import lru_cache
from pathlib import Path

#: Keys read from the environment, with their defaults. Every knob the HTTP service and
#: the data layer understand is listed here, so this dict is the one place to look for
#: "what can I configure".
DEFAULTS = {
    # Where the challenge data lives. `raw` holds the files exactly as published;
    # everything else under `data/` is derived and reproducible.
    "DATA_DIR": "data",
    "RAW_DIR": "data/raw",
    "PARQUET_DIR": "data/parquet",
    "MANIFEST_DIR": "data/manifests",
    # The HTTP service in `sepiq.viz`.
    "API_TOKEN": "",
    "API_CORS": "http://localhost:5173,http://127.0.0.1:5173",
    "API_CACHE": "build/api-cache",
    # Optional upstream a job-shaped verb is forwarded to (see `sepiq.viz.proxy`).
    "UPSTREAM_URL": "",
}

#: Looked for upward from the working directory, so a CLI works from a subdirectory.
ENV_FILENAME = ".env"

#: Names one env file explicitly instead of searching for it. Set it to a path to pin
#: that file; set it to the empty string to use no file at all. The test suite sets it
#: empty so a developer's own ``.env`` can never decide what a test observes.
ENV_FILE_OVERRIDE = "ENV_FILE"


def setting(key: str, start: Path | None = None) -> str:
    """One setting: real environment first, then the nearest ``.env``, then :data:`DEFAULTS`."""
    return os.environ.get(key) or env_file_values(start).get(key) or DEFAULTS.get(key, "")


def env_file_values(start: Path | None = None) -> dict[str, str]:
    """The nearest ``.env`` as a mapping — ``{}`` when there is no file.

    The parse is cached per (path, size, modification time), because these readers sit on
    request paths: an uncached :func:`setting` means a disk read per HTTP request. Edit
    the file and the fingerprint changes, so the next call re-reads it;
    :func:`clear_env_cache` exists for tests that write a ``.env`` twice inside one
    filesystem timestamp tick.
    """
    env_path = find_env(start)
    if env_path is None:
        return {}
    stat = env_path.stat()
    return dict(_parsed_env(str(env_path), stat.st_size, stat.st_mtime_ns))


@lru_cache(maxsize=8)
def _parsed_env(path: str, size: int, mtime_ns: int) -> tuple[tuple[str, str], ...]:
    """Parse one ``.env``, keyed by its fingerprint. Returns pairs so the cache is immutable."""
    del size, mtime_ns  # cache key only; the path is what gets read
    return tuple(parse_env(Path(path).read_text(encoding="utf-8")).items())


def clear_env_cache() -> None:
    """Forget every parsed ``.env``. For tests that rewrite the file under a live process."""
    _parsed_env.cache_clear()


def find_env(start: Path | None = None) -> Path | None:
    """Locate the env file: the pinned one if :data:`ENV_FILE_OVERRIDE` is set, else the search.

    Without the override, the nearest ``.env`` walking upward from ``start`` to the
    filesystem root. With it, exactly that path — and a missing one raises rather than
    falling back to a search, because a pinned file that silently does not exist is how a
    process ends up reading credentials nobody meant it to read. The empty string means
    "no file", which is how the test suite stays hermetic.
    """
    pinned = os.environ.get(ENV_FILE_OVERRIDE)
    if pinned is not None:
        if not pinned:
            return None
        candidate = Path(pinned).expanduser()
        if not candidate.is_file():
            raise FileNotFoundError(f"{ENV_FILE_OVERRIDE}={pinned} is not a file")
        return candidate
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
    for raw_line in text.splitlines():
        line = raw_line.strip()
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
