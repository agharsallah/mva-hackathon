"""Reading a Track 2 ``*.provenance.json``: the manifest, and the values an edge needs.

Split out of :mod:`mva.warehouse.track2_lineage` so that module holds one concern — turning
a set of tables into ``data_lineage`` edges — and this one holds the other: what a single
provenance manifest on disk actually says. Nothing here knows what an edge is.

Three of these functions exist because a public API is not a file. A file has a byte stream
to hash and a version to name; an API has neither, so :func:`rollup_digest` and
:func:`api_version` state the only reproducible things there are — a digest over the cached
replies that were read, and the window they were retrieved in. Neither invents a version to
fill a column.

No coordinate can reach here: a manifest names URLs, digests, row counts and table paths.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

__all__ = [
    "TOOL",
    "TRACK2_DIR",
    "TRACK2_SCHEMA",
    "Manifest",
    "api_host",
    "api_version",
    "card_version",
    "read_manifest",
    "rollup_digest",
]

#: The tool that produced the tables, for the ``tool`` column and as the manifest default.
TOOL = "mva-drugs snapshot"

#: The schema name written into every Track 2 edge. Not a real PostgreSQL schema — see
#: :mod:`mva.warehouse.track2_lineage`. Defined here, the lowest Track 2 lineage module, so
#: the recorders beside it can share it without importing each other.
TRACK2_SCHEMA = "track2"

#: Where the snapshot writes, relative to the repository root.
TRACK2_DIR = "ressources/track2"


@dataclass(frozen=True)
class Manifest:
    """One ``*.provenance.json`` beside one TSV, as the edge builder needs it."""

    name: str
    rows: int
    method: str
    inputs: list[dict[str, Any]]
    built_by: str = TOOL

    @property
    def tables(self) -> list[dict[str, Any]]:
        """Inputs that are other Track 2 **tables**: a ``path``, no ``url``, and a ``.tsv``.

        A manifest may also name a ``.json`` input — a card, a spec, a snapshot index. Those
        are not tables: a card gets its own ``card`` edge and a snapshot index is a roll-up
        of tables that already have edges of their own, so turning either into a ``table``
        edge would assert a table that does not exist.
        """
        return [
            entry
            for entry in self.inputs
            if str(entry.get("path") or "").endswith(".tsv") and not entry.get("url")
        ]

    @property
    def hosts(self) -> list[str]:
        """Every distinct API host this table read, in first-seen order."""
        seen: list[str] = []
        for entry in self.inputs:
            host = api_host(str(entry.get("url") or ""))
            if host and host not in seen:
                seen.append(host)
        return seen

    def for_host(self, host: str) -> list[dict[str, Any]]:
        return [entry for entry in self.inputs if api_host(str(entry.get("url") or "")) == host]


def api_host(url: str) -> str:
    """The host part of an API URL — ``api.platform.opentargets.org`` — or ``""``."""
    return urlparse(url).netloc


def read_manifest(directory: Path, table: str) -> Manifest | None:
    """One manifest, or ``None`` when the snapshot has not been run in this checkout.

    A missing manifest is not an error: recording lineage for the four tables that exist
    is a truer statement than failing over the fifth that does not.
    """
    path = directory / f"{table}.provenance.json"
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    outputs = loaded.get("outputs") or [{}]
    return Manifest(
        name=str(loaded.get("name") or table),
        rows=int(outputs[0].get("rows") or 0),
        method=str(loaded.get("method") or ""),
        inputs=list(loaded.get("inputs") or []),
        built_by=str(loaded.get("built_by") or TOOL),
    )


def card_version(directory: Path) -> str:
    """``v<n>`` for the card the snapshot ran against, or ``""`` when it cannot be read."""
    try:
        card = json.loads((directory / "mechanism.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    version = card.get("version")
    return f"v{version}" if version is not None else ""


def rollup_digest(entries: list[dict[str, Any]]) -> str:
    """sha256 over one host's input digests, sorted and concatenated.

    The manifests already roll each API's cached reply bodies up to one digest per input
    row; this rolls those up once more, per host, so the edge carries a value that is
    reproducible from the manifest and changes whenever any reply behind it changed.
    """
    digests = sorted(str(entry.get("sha256") or "") for entry in entries)
    joined = "".join(digests).encode("utf-8")
    return hashlib.sha256(joined).hexdigest()


def api_version(entries: list[dict[str, Any]]) -> str:
    """The release the API states, or the retrieval window of the replies used.

    None of these seven APIs states a release in its replies — the manifests say so in
    ``known_gap`` — so in practice this is the window. It is not a version and is not
    labelled as one anywhere: it is the only reproducible thing there is to record.
    """
    stated = sorted({str(entry["version"]) for entry in entries if entry.get("version")})
    if stated:
        return ", ".join(stated)
    starts = [str(entry.get("retrieved_from") or "") for entry in entries]
    ends = [str(entry.get("retrieved_at") or "") for entry in entries]
    first = min((value for value in starts if value), default="")
    last = max((value for value in ends if value), default="")
    if not first and not last:
        return ""
    return f"retrieved {first}..{last}"
