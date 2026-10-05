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

The directory lives under ``build/``, which is gitignored: a cache entry is a derived
artifact reproducible from the inputs, so it is never committed.
"""

import json
import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

#: Characters allowed in a cache key. Keys are built from query parameters, so they are
#: caller-influenced; rejecting anything else keeps a key from escaping the directory.
_ALLOWED = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")


class InvalidKeyError(ValueError):
    """Raised when a cache key contains anything but letters, digits, ``-`` and ``_``."""


def safe_key(*parts: object) -> str:
    """Join ``parts`` into one filesystem-safe cache key, or raise.

    Rejecting beats sanitising: a key that needs escaping to be safe means a parameter
    reached here unvalidated, and silently rewriting it would collide two distinct
    queries onto one cache entry.
    """
    key = "-".join(str(part) for part in parts if part not in (None, ""))
    if not key or not set(key) <= _ALLOWED:
        raise InvalidKeyError(f"not a usable cache key: {key!r}")
    return key


def now() -> str:
    """The current instant, as the ISO-8601 string that goes into ``cached_at``."""
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Built:
    """A payload plus the concrete provenance of *this* build.

    Returned by a builder that knows something about its own reply the payload itself
    cannot carry — the AlphaFold model URL and version behind a fold, the Ensembl release
    a gene record came from. Those facts belong in the envelope's ``source`` line, but the
    client contracts in ``app/src/api/types/`` are frozen and have no field for them, so
    they are stored **beside** the payload in the cache entry and rendered into ``source``
    by :func:`sepiq.viz.response.cached`. A cache hit therefore reports the provenance of
    the reply it is actually serving, not of a request that never happened.
    """

    data: Any
    provenance: dict


@dataclass(frozen=True)
class Cached:
    """A payload, the instant it was built, and what it was built from."""

    data: Any
    cached_at: str
    provenance: dict | None = None


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
        provenance = stored.get("provenance")
        return Cached(
            stored["data"],
            stored.get("cached_at") or now(),
            provenance if isinstance(provenance, dict) else None,
        )

    def write(self, key: str, data: Any) -> Cached:
        """Store ``data`` under ``key`` and return it with its build instant.

        A :class:`Built` is unwrapped: its payload is stored under ``data`` and its
        provenance beside it, so an entry written before this existed still reads back
        (``provenance`` simply absent) and no cache directory needs clearing.
        """
        if isinstance(data, Built):
            entry = Cached(data.data, now(), data.provenance)
        else:
            entry = Cached(data, now())
        self.directory.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(dir=self.directory, suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(
                    {
                        "cached_at": entry.cached_at,
                        "provenance": entry.provenance,
                        "data": entry.data,
                    },
                    stream,
                )
            Path(temporary).replace(self.path(key))
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
        return entry

    def get_or_build(self, key: str, build: Callable[[], Any], refresh: bool = False) -> Cached:
        """Return the cached payload, building and storing it when absent or refused."""
        if not refresh:
            hit = self.read(key)
            if hit is not None:
                return hit
        return self.write(key, build())


def default_directory() -> Path:
    """Where the cache lives: ``API_CACHE``, defaulting under gitignored ``build/``."""
    from ..settings import setting

    return Path(setting("API_CACHE") or "build/api-cache").expanduser()
