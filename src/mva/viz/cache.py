"""A disk cache for responses that cost seconds to compute.

Why a cache at all: the endpoints behind it are not slow because the code is bad, they
are slow because of physics. A per-shard read aggregate transfers ~250 MB over a
6.4 MiB/s link; a locus query scans five million unindexed text rows. Neither belongs on
the critical path of a chart that re-renders when someone drags a slider.

Two properties make it safe rather than merely fast:

* **The cache is the answer, not a copy of it.** A hit returns the stored payload
  *and* the instant it was built, and the API surfaces that instant as ``cached_at`` —
  so a stale number is visible in the UI instead of silently pretending to be live.
* **A miss is never a partial write.** The payload goes to a temporary file and is
  renamed into place, so a killed process leaves either the old entry or none.

The directory lives under ``build/``, which is gitignored, and that is load-bearing:
the locus cache holds **real patient positions**, which must never enter the repository.
"""

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

#: Characters allowed in a cache key. Keys are built from query parameters, so they are
#: caller-influenced; rejecting anything else keeps a key from escaping the directory.
_ALLOWED = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")


class InvalidKey(ValueError):
    """Raised when a cache key contains anything but letters, digits, ``-`` and ``_``."""


def safe_key(*parts: object) -> str:
    """Join ``parts`` into one filesystem-safe cache key, or raise.

    Rejecting beats sanitising: a key that needs escaping to be safe means a parameter
    reached here unvalidated, and silently rewriting it would collide two distinct
    queries onto one cache entry.
    """
    key = "-".join(str(part) for part in parts if part not in (None, ""))
    if not key or not set(key) <= _ALLOWED:
        raise InvalidKey(f"not a usable cache key: {key!r}")
    return key


def now() -> str:
    """The current instant, as the ISO-8601 string that goes into ``cached_at``."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Cached:
    """A payload and the instant it was built."""

    data: Any
    cached_at: str


@dataclass(frozen=True)
class Cache:
    """A directory of JSON entries, keyed by name."""

    directory: Path

    def path(self, key: str) -> Path:
        return self.directory / f"{safe_key(key)}.json"

    def read(self, key: str) -> Cached | None:
        """The entry for ``key``, or ``None`` when absent or unreadable.

        A corrupt entry is treated as a miss rather than an error: the cache is
        derived data, and the correct response to a truncated file is to rebuild it.
        """
        path = self.path(key)
        try:
            stored = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(stored, dict) or "data" not in stored:
            return None
        return Cached(stored["data"], stored.get("cached_at") or now())

    def write(self, key: str, data: Any) -> Cached:
        """Store ``data`` under ``key`` and return it with its build instant."""
        entry = Cached(data, now())
        self.directory.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(dir=self.directory, suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump({"cached_at": entry.cached_at, "data": entry.data}, stream)
            os.replace(temporary, self.path(key))
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
        return entry

    def get_or_build(self, key: str, build: Callable[[], Any],
                     refresh: bool = False) -> Cached:
        """Return the cached payload, building and storing it when absent or refused."""
        if not refresh:
            hit = self.read(key)
            if hit is not None:
                return hit
        return self.write(key, build())


def default_directory() -> Path:
    """Where the cache lives: ``MVA_VIZ_CACHE``, defaulting under gitignored ``build/``."""
    from ..warehouse.settings import setting

    return Path(setting("MVA_VIZ_CACHE") or "build/viz-cache").expanduser()
