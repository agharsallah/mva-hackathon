"""Provenance manifests for the route-R2 proteome tables: one writer, many files.

Separated from the driver so the driver stays a thin command surface: the driver knows the
files and the plan, this module knows the manifest shape the repository asks every table
to carry (inputs with their URL and sha256, parameters, sources, limitations, outputs).
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from mva.drugs import provenance

__all__ = ["file_input", "write_manifests"]


def file_input(path: Path, role: str, urls: Mapping[Path, str]) -> dict[str, Any]:
    """One local input file as a manifest row: path, upstream URL, digest, size."""
    sha, size = provenance.digest(path)
    return {
        "file": path.as_posix(),
        "url": urls.get(path),
        "role": role,
        "sha256": sha,
        "bytes": size,
    }


def write_manifests(
    *,
    out: Path,
    entry: str,
    inputs: list[dict[str, Any]],
    parameters: dict[str, Any],
    sources: dict[str, str],
    framing: str,
    limits: str,
    tables: list[tuple[str, int, dict[str, str]]],
    validation: dict[str, Any],
) -> None:
    """Write one manifest per table, sharing the inputs, parameters and caveats."""
    common = {
        "entry": entry,
        "tool": "tools/it5_proteome.py run",
        "inputs": inputs,
        "parameters": parameters,
        "sources": sources,
        "clinical_framing": framing,
        "limitations": limits,
    }
    for name, rows, columns in tables:
        path = out / f"{name}.tsv"
        manifest = provenance.envelope(name, built_by="tools/it5_proteome.py run")
        manifest.update(common)
        manifest["columns"] = columns
        manifest["rows"] = rows
        manifest["outputs"] = [provenance.output(path, rows)]
        manifest["validation"] = validation
        provenance.write(manifest, path.with_suffix(".provenance.json"))
