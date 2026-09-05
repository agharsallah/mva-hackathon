"""One provenance manifest per table this package writes.

The repository's rule is that every committed dataset carries a manifest saying what was
read, from where, at which version, by which tool at which commit, and what came out with
which digest. ``ressources/reference/coding_regions.provenance.json`` is the reference
shape and this module reproduces it for the Track 2 tables.

Two things are deliberately different, and both are stated in the manifests themselves:

* **Inputs are APIs, not files.** A public API has no byte stream to hash, so an input row
  names the endpoint, the version the API states about itself (or ``null`` — never a
  guessed one), the ``retrieved_at`` window of the replies used, how many requests were
  made, and a **roll-up digest**: the sha256 of the sorted per-reply body digests. Same
  replies in, same value out. Listing a thousand cached bodies individually would not be a
  manifest, and picking one of them would be a fiction.
* **The primitives are re-implemented here, not imported.** :mod:`mva.viz.refprovenance`
  owns the same three functions, but the package layering forbids anything outside
  ``mva.viz`` from importing it and ``mva.drugs`` sits well below the web layer. The
  digest is the same algorithm over the same chunk size, so a value written here and one
  written there are comparable.

Nothing here can write a genomic position: a manifest holds URLs, versions, digests and
counts, and the tables it describes name genes and drugs.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = [
    "CHUNK",
    "api_input",
    "code_version",
    "digest",
    "envelope",
    "now",
    "output",
    "repo_relative",
    "write",
]

#: Bytes per read when digesting a file. Matches :mod:`mva.viz.refprovenance`.
CHUNK = 1 << 20

PATIENT_DATA = (
    "none. Public API replies only - gene symbols, drug names, trial ids and citations. "
    "Nothing here was derived from the callset, and no genomic position appears in any "
    "row by construction."
)


def digest(path: Path) -> tuple[str, int]:
    """``(sha256 hex, byte count)`` for one file."""
    sha = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(CHUNK):
            sha.update(chunk)
            size += len(chunk)
    return sha.hexdigest(), size


def code_version() -> str:
    """The short commit the build ran at, or ``"unknown"``. Never a guess."""
    try:
        done = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return done.stdout.strip() or "unknown"


def now() -> str:
    """The build instant as the ISO-8601 UTC string every manifest's ``built_at`` uses."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def repo_relative(path: Path) -> str:
    """``ressources/track2/targets.tsv``, not one laptop's absolute path."""
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def envelope(name: str, built_by: str) -> dict[str, Any]:
    """The five fields every manifest in this repository opens with."""
    return {
        "name": name,
        "built_at": now(),
        "built_by": built_by,
        "code_version": code_version(),
        "code_version_note": (
            "the commit at build time, which precedes the commit that lands this file"
        ),
    }


def api_input(
    name: str,
    url: str,
    *,
    role: str,
    version: str | None = None,
    fetcher: Any = None,
    queries: list[str] | None = None,
) -> dict[str, Any]:
    """One upstream API as a manifest input row.

    ``fetcher`` is a :class:`~mva.drugs.cache.Fetcher`; its ``digest`` and ``window`` carry
    the roll-up digest and the ``retrieved_at`` range of every reply the build used. A
    ``version`` is written only when the API states one about itself.
    """
    window = getattr(fetcher, "window", None) if fetcher is not None else None
    replies = len(getattr(fetcher, "replies", [])) if fetcher is not None else 0
    entry: dict[str, Any] = {
        "name": name,
        "url": url,
        "version": version,
        "role": role,
        "retrieved_at": window[1] if window else None,
        "retrieved_from": window[0] if window else None,
        "requests": replies,
        "live_calls": getattr(fetcher, "live_calls", 0) if fetcher is not None else 0,
        "sha256": getattr(fetcher, "digest", None) if fetcher is not None else None,
        "sha256_scope": (
            "roll-up: sha256 over the sorted sha256 digests of every cached reply body "
            "this build read from this API. A public API has no single byte stream to "
            "hash; this value is reproducible from the cache and changes when any reply "
            "changes."
        ),
    }
    if queries:
        entry["queries"] = queries
    if version is None:
        entry["known_gap"] = (
            "this API states no release or version in its replies, so the field is null "
            "rather than a date copied from the run."
        )
    return entry


def output(path: Path, rows: int) -> dict[str, Any]:
    """One output file as ``{path, sha256, bytes, rows}``."""
    sha, size = digest(path)
    return {"path": repo_relative(path), "sha256": sha, "bytes": size, "rows": rows}


def write(manifest: dict[str, Any], path: Path) -> Path:
    """Write one manifest as pretty JSON with a trailing newline. Returns ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return path
