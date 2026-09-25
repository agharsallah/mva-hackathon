"""Lineage edges for iteration 5's Track 2 tables (``ressources/track2/it5``).

Iteration 5's route drivers write the same manifest shapes iteration 4's did, so every
manifest is read by :func:`~mva.warehouse.track2_lineage_it4.manifest_edges` and its target is
named the same way (``it5.readthrough``, ``it5.proteome_hits``). Two rules are added:

* **Filed entries only.** A table is recorded once the methodology entry that built it is
  filed: the manifest's ``entry`` must start with a path under a ``methodology/`` folder that
  exists. A table whose entry is still a draft is left out until it is filed, because the
  ledger is append-only and a draft's digests still move.
* **The clinical document by file name.** A manifest whose ``sources.clinical`` names the
  clinical document by its file name, not its full path, still gets its ``clinical`` edge.

**The transfer case.** ``ressources/track2/it5/transfer/`` holds the same three routes run on a
*second* disease (Bloom syndrome, ``BLM``), so the folder is walked recursively and its tables
are named from their path — ``it5.transfer.r1.readthrough`` — and can never be confused with the
first case's ``it5.readthrough``. Those manifests declare ``sources.clinical: "none"``: the
transfer case is published literature only, with no patient and no HPO term, so no ``clinical``
edge is written for them.
"""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any

from .submission_lineage import CLINICAL_FILE, CLINICAL_VERSION, sha256_of
from .track2_lineage_it4 import manifest_edges
from .track2_manifests import TRACK2_DIR

__all__ = ["IT5_DIR", "filed_entry", "it5_edges"]

#: Iteration 5's tables: one flat folder, one manifest per table.
IT5_DIR = f"{TRACK2_DIR}/it5"
CLINICAL_NAME = PurePosixPath(CLINICAL_FILE).name
CLINICAL_NOTE = "the proband's HPO terms, named by the manifest's sources.clinical"


def filed_entry(loaded: dict[str, Any], root: Path) -> str:
    """The filed methodology entry a manifest names, else ``""`` (a draft or a placeholder)."""
    words = str(loaded.get("entry") or "").split()
    path = words[0] if words else ""
    return path if "/methodology/" in path and (root / path).is_file() else ""


def _clinical_edges(found: list[dict[str, object]], root: Path) -> list[dict[str, object]]:
    """One ``clinical`` edge per target that does not have one yet."""
    have = {e["target_table"] for e in found if e["source_kind"] == "clinical"}
    added: list[dict[str, object]] = []
    for edge in found:
        target = edge["target_table"]
        if target in have:
            continue
        have.add(target)
        notes = "; ".join(p for p in (str(edge["notes"]).split("; ")[0], CLINICAL_NOTE) if p)
        added.append(
            {
                **edge,
                "source_kind": "clinical",
                "source_ref": CLINICAL_FILE,
                "source_version": CLINICAL_VERSION,
                "source_sha256": sha256_of(root / CLINICAL_FILE),
                "notes": notes,
            }
        )
    return added


def it5_edges(root: Path) -> list[dict[str, object]]:
    """Every edge iteration 5's filed tables imply. Pure: reads disk only."""
    edges: list[dict[str, object]] = []
    for manifest in sorted((root / IT5_DIR).rglob("*.provenance.json")):
        try:
            loaded = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not filed_entry(loaded, root):
            continue
        found = manifest_edges(manifest, root)
        clinical = str((loaded.get("sources") or {}).get("clinical") or "")
        if CLINICAL_NAME in clinical:
            found += _clinical_edges(found, root)
        edges += found
    return edges
