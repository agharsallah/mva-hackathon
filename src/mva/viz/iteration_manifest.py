"""The provenance manifest beside a data file, read whatever shape it was written in.

A file that no warehouse edge describes carries its lineage in a ``*.provenance.json``
committed next to it (dictionary: *Provenance manifest*). About 160 exist, written by a
dozen tools over three weeks, and they do not share one schema: the producer is
``built_by`` or ``tool`` or ``generator``; the instant is ``built_at``, ``generated_at``
or ``retrieved_at``; the row count sits at the top level or inside ``outputs``. This
module reads every one of those spellings into one :class:`Manifest`, so the catalogue
can say "this file has lineage" without caring which tool wrote it.

**Which manifest belongs to a file** is decided by name first — ``shortlist.tsv`` →
``shortlist.provenance.json`` or ``shortlist.tsv.provenance.json`` — then by any
``*provenance*.json`` in the same directory whose ``outputs`` list the file
(``hpo_provenance.json`` lists ``hpo_gene_scores.tsv``). A directory-wide
``_provenance.json`` is the last resort.

**A self-described file is its own manifest.** ``mechanism.json`` carries a ``_standing``
line and a ``history`` of versions with the entries each came from; a tool-written JSON
result that stamps its own ``code_version`` and build instant says who made it and when.
Either is a provenance record committed with the bytes, so it is read as one. A file matched by none
of these rules has no manifest, and says so.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

SUFFIX = ".provenance.json"

#: Producer and instant keys, in the order they are preferred when a manifest has several.
PRODUCER_KEYS = ("built_by", "tool", "generator", "script")
INSTANT_KEYS = ("built_at", "generated_at", "retrieved_at", "created_at")

#: Directory-wide manifests, tried after the per-file names.
DIRECTORY_NAMES = ("_provenance.json", "provenance.json")


@dataclass(frozen=True)
class Manifest:
    """What one manifest says about one file."""

    path: str
    built_by: str = ""
    built_at: str = ""
    rows: int | None = None
    sha256: str = ""
    version: str = ""
    inputs: list[dict[str, str]] = field(default_factory=list)
    #: The manifest's whole text, so a caller can look for an entry number in it.
    text: str = ""


def _first(data: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _output_names(data: Any) -> dict[str, dict[str, Any]]:
    """``outputs`` by file name, in either shape: a list of rows, or ``{file: rows}``."""
    outputs = data.get("outputs") if isinstance(data, dict) else None
    if isinstance(outputs, dict):
        return {Path(str(name)).name: {"rows": rows} for name, rows in outputs.items()}
    return {
        Path(str(row["path"])).name: row
        for row in outputs or []
        if isinstance(row, dict) and row.get("path")
    }


def _output_for(data: dict[str, Any], relative: str) -> dict[str, Any]:
    """The ``outputs`` row describing ``relative``, or the manifest's top level."""
    return _output_names(data).get(Path(relative).name, data)


def _inputs(data: dict[str, Any]) -> list[dict[str, str]]:
    """Upstream inputs: the ``inputs`` list, else a top-level ``source``/``url``."""
    found = []
    for item in data.get("inputs") or []:
        if isinstance(item, dict):
            ref = _first(item, ("path", "url", "name", "ref"))
            if ref:
                found.append({"ref": ref, "sha256": str(item.get("sha256") or "")})
        elif isinstance(item, str):
            found.append({"ref": item, "sha256": ""})
    if not found:
        ref = _first(data, ("source_url", "url", "source"))
        if ref:
            found.append({"ref": ref, "sha256": str(data.get("source_sha256") or "")})
    return found


def _rows(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def parse(path: Path, relative_file: str, root: Path) -> Manifest | None:
    """One manifest file, read for one data file; ``None`` if it is not valid JSON."""
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    output = _output_for(data, relative_file)
    if path.name == Path(relative_file).name and not path.name.endswith(SUFFIX):
        return _card(path, data, text, root)
    return Manifest(
        path=path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path),
        built_by=_first(data, PRODUCER_KEYS),
        built_at=_first(data, INSTANT_KEYS),
        rows=_rows(output.get("rows")),
        sha256=str(output.get("sha256") or ""),
        version=_first(data, ("version", "release", "code_version")),
        inputs=_inputs(data),
        text=text,
    )


def _stamp(data: dict[str, Any]) -> tuple[str, str]:
    """``(producer, instant)`` a JSON file states about itself, or ``('', '')``.

    Two shapes count. A hand-authored card or spec carries a ``_standing`` line (and often a
    ``history`` of versions); a tool-written result stamps its own ``code_version`` beside a
    build instant. Anything less is not provenance.
    """
    history = [h for h in data.get("history") or [] if isinstance(h, dict)]
    if "_standing" in data:
        last = str(history[-1].get("date") or "") if history else ""
        return "hand-authored (standing line in file)", last
    instant = _first(data, (*INSTANT_KEYS, "computed_at"))
    if data.get("code_version") and instant:
        return f"self-stamped at commit {data['code_version']}", instant
    return "", ""


def _card(path: Path, data: dict[str, Any], text: str, root: Path) -> Manifest:
    """A self-described file: what it stamps about itself, and its own version."""
    producer, instant = _stamp(data)
    return Manifest(
        path=path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path),
        built_by=producer,
        built_at=instant,
        version=str(data.get("version") or ""),
        text=text,
    )


@cache
def _directory_outputs(directory: Path) -> dict[str, Path]:
    """File name → the ``*provenance*.json`` in ``directory`` that lists it as an output.

    Outputs only: a manifest that names a file among its *inputs* (the shortlist's manifest
    names the mechanism card) describes something else, not that file.
    """
    listed: dict[str, Path] = {}
    for manifest in sorted(directory.glob("*provenance*.json")):
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for name in _output_names(data):
            listed.setdefault(name, manifest)
    return listed


def _self_described(file: Path) -> bool:
    """A JSON file that carries its own provenance: see :func:`_stamp`."""
    if file.suffix != ".json" or not file.is_file():
        return False
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(data, dict) and bool(_stamp(data)[0])


def locate(root: Path, relative: str) -> Path | None:
    """The manifest describing ``relative`` (a repo path), or ``None``."""
    file = root / relative
    directory = file.parent
    if not directory.is_dir():
        return None
    for name in (f"{file.stem}{SUFFIX}", f"{file.name}{SUFFIX}"):
        candidate = directory / name
        if candidate.is_file():
            return candidate
    listed = _directory_outputs(directory).get(file.name)
    if listed is not None:
        return listed
    if _self_described(file):
        return file
    for name in DIRECTORY_NAMES:
        candidate = directory / name
        if candidate.is_file():
            return candidate
    return None


def read(root: Path, relative: str) -> Manifest | None:
    """The parsed manifest for one repo-relative data file, or ``None``."""
    found = locate(root, relative)
    return parse(found, relative, root) if found else None


def clear() -> None:
    """Forget the per-directory output index (tests, and a rebuild after new manifests)."""
    _directory_outputs.cache_clear()
