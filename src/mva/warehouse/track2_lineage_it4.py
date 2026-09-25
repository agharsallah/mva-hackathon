"""Lineage edges for iteration 4's Track 2 tables: steps 9 and 10, and the step-11 transfer.

:mod:`mva.warehouse.track2_lineage` records the snapshot and step-7 tables, whose manifests
all come from one writer. Iteration 4's tables came from four more — ``tools/converge.py``,
``tools/screen_sweep.py`` and ``tools/screen_replication.py``, ``tools/signature_reversal.py``,
``tools/patient_safety.py`` — plus two hand-curated tables, and their manifests do not share
one shape. This module reads all four shapes and turns each **output table** into edges:

* **run** manifests (``name``, ``built_by``, ``inputs``, ``outputs[]``): one target per
  ``.tsv``/``.parquet`` output, its rows from that output. A generator writes two — its list
  and its ``.universe`` — so both are targets, with the same inputs.
* **curated** manifests (a top-level ``sha256``, no ``outputs``): the target is the sibling
  table; its rows are counted on disk, and only when the file still has that digest.
* **safety** manifests (``tool``, ``rows``, ``inputs[].file``): the sibling table, ``rows``.
* **twin** manifests (``outputs`` a ``{file name: description}`` map): each ``.tsv`` named,
  rows counted on disk (the manifest records no digest to check them against).

Each input becomes one edge, by what the manifest says it is — never by guessing:

* a path to a table under ``ressources/track2`` → ``table``, named as its own target is;
* a URL read as cached replies (``retrieved_at``, no ``bytes``) → ``api``, one per host, the
  digest rolled up exactly as :mod:`~mva.warehouse.track2_lineage` does (and ``""`` when the
  manifest recorded no digest for that host — a hash of nothing is not a digest);
* a downloaded or local file → ``file``: the URL when there is one (the local copy is named in
  ``notes``), else the path; ``source_version`` is the release the manifest states;
* ``pgx_summary.json`` of the proband → ``derived``: it is PharmCAT's reading of the child's
  WGS callset. The edge names the file and its digest; the file holds actionability words and
  counts, and nothing here opens it. No coordinate can reach an edge from it;
* the clinical document, when the manifest's ``sources.clinical`` names it → ``clinical``.

Skipped: a ``*.provenance.json`` input (the table it describes has its own edge) and a
citation with neither a path, a URL nor a digest (a PMID that fixed a mapping choice is
evidence in the methodology entry, not a data input).

Targets are named from their path under ``ressources/track2``: ``it4.generators.walk``,
``it4.candidates``, and the step-9 tables at the top level by name (``bub1b_atlas``). A
step-11 transfer case under ``transfer-it4/<CASE>/`` is found by glob and recorded as
``transfer.<CASE>.<table>``, with the case file as its ``card`` edge and no ``submission``,
``clinical`` or ``derived`` edge: it is public annotation, not the child's record. A case name
used by both transfer folders would share names; none does.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path, PurePosixPath
from typing import Any

from .submission_lineage import CLINICAL_FILE, CLINICAL_VERSION, sha256_of
from .track2_manifests import TOOL, TRACK2_DIR, TRACK2_SCHEMA, api_host, api_version, rollup_digest

__all__ = [
    "IT4_DIR",
    "STEP9_TABLES",
    "TRANSFER_IT4_DIR",
    "it4_edges",
    "manifest_edges",
    "target_name",
]

#: Iteration 4 step 10's tables: the four generators, the sweep, the reversal, the join.
IT4_DIR = f"{TRACK2_DIR}/it4"

#: Iteration 4 step 9's tables, written at the Track 2 root beside the snapshot's.
STEP9_TABLES = (
    "bub1b_atlas",
    "bub1b_published_alleles",
    "model_interventions",
    "prism_replication",
    "hpo_to_adverse_terms",
    "candidate_safety",
)

#: Step 11's second case, one folder per case; its relabel record is not a table.
TRANSFER_IT4_DIR = f"{TRACK2_DIR}/transfer-it4"
TRANSFER_RECORD = "transfer.provenance.json"
CASE_FILE = "case.json"

#: PharmCAT's summary of the child's callset: the only patient-derived input these read.
PATIENT_DERIVED = "pgx_summary.json"
PATIENT_NOTE = (
    "patient-derived: PharmCAT phenotypes from the child's WGS callset "
    "(tools/patient_safety.py pharmcat); actionability words and counts, no diplotype, "
    "no position"
)

TABLE_SUFFIXES = (".tsv", ".parquet")
#: A URL ending in one of these is a download (a file), not a query to an API.
DOWNLOAD_SUFFIXES = {".zip", ".gz", ".csv", ".tsv", ".txt", ".parquet", ".pdb", ".xml"}
#: Where a transform is stated, in the order the four writers use the keys.
TRANSFORM_KEYS = ("method", "generator_rule", "list_rule", "test")


def target_name(path: str) -> str:
    """``ressources/track2/it4/generators/walk.universe.tsv`` → ``it4.generators.walk.universe``.

    A transfer case's ``transfer-it4/BLM/candidates.tsv`` becomes ``transfer.BLM.candidates``.
    """
    parts = path.split(f"{TRACK2_DIR}/", 1)[-1].split("/")
    if parts[0] == TRANSFER_IT4_DIR.rsplit("/", 1)[-1] and len(parts) > 2:
        parts = ["transfer", *parts[1:]]
    stem = "/".join(parts)
    for suffix in TABLE_SUFFIXES:
        stem = stem.removesuffix(suffix)
    return stem.replace("/", ".")


def _is_table(path: str) -> bool:
    return path.startswith(f"{TRACK2_DIR}/") and path.endswith(TABLE_SUFFIXES)


def _entry_path(entry: dict[str, Any]) -> str:
    """The input's repository path: ``path``, ``file``, or a ``name`` that is itself a path."""
    for key in ("path", "file"):
        if entry.get(key):
            return str(entry[key])
    name = str(entry.get("name") or "")
    return name if name.startswith(("ressources/", "build/")) else ""


def _is_api(entry: dict[str, Any]) -> bool:
    """Cached replies from a service, as opposed to one downloaded file."""
    url = str(entry.get("url") or "")
    if not url or entry.get("bytes") or entry.get("release"):
        return False
    return PurePosixPath(url.split("?", 1)[0]).suffix not in DOWNLOAD_SUFFIXES


def _count_rows(path: Path, expected_sha256: str) -> int:
    """Data rows of a TSV on disk, when it is the file the manifest describes; else 0."""
    if path.suffix != ".tsv" or not path.is_file():
        return 0
    if expected_sha256 and sha256_of(path) != expected_sha256:
        return 0
    with path.open(encoding="utf-8", newline="") as handle:
        return max(sum(1 for _ in csv.reader(handle, delimiter="\t")) - 1, 0)


def _outputs(manifest_path: Path, loaded: dict[str, Any], root: Path) -> list[tuple[str, int]]:
    """``(repo path, rows)`` for every table the manifest describes."""
    outputs = loaded.get("outputs")
    if isinstance(outputs, dict):  # the phenotype-twin writer: {file name: description}
        return [
            (relative, _count_rows(root / relative, ""))
            for name in outputs
            if _is_table(relative := (manifest_path.parent / name).relative_to(root).as_posix())
        ]
    listed = [
        (str(out["path"]), int(out.get("rows") or 0))
        for out in outputs or []
        if _is_table(str(out.get("path") or ""))
    ]
    if listed or outputs:
        return listed
    stem = manifest_path.name.removesuffix(".provenance.json")
    for suffix in TABLE_SUFFIXES:
        sibling = manifest_path.with_name(stem + suffix)
        if sibling.is_file():
            relative = sibling.relative_to(root).as_posix()
            rows = loaded.get("rows")
            if rows is None:
                rows = _count_rows(sibling, str(loaded.get("sha256") or ""))
            return [(relative, int(rows))]
    return []


def _transform(loaded: dict[str, Any]) -> str:
    return next((str(loaded[key]) for key in TRANSFORM_KEYS if loaded.get(key)), "")


def _input_edges(
    inputs: list[dict[str, Any]], common: dict[str, object], *, patient: bool
) -> list[dict[str, object]]:
    """One edge per input (one per host for API replies); see the module docstring."""
    edges: list[dict[str, object]] = []
    hosts: dict[str, list[dict[str, Any]]] = {}
    for entry in inputs:
        path = _entry_path(entry)
        url = str(entry.get("url") or "")
        sha = str(entry.get("sha256") or "")
        role = str(entry.get("role") or entry.get("name") or "")
        if path.endswith(".provenance.json"):
            continue
        if _is_api(entry):
            hosts.setdefault(api_host(url), []).append(entry)
        elif _is_table(path):
            ref = f"{TRACK2_SCHEMA}.{target_name(path)}"
            edges.append(_edge(common, "table", ref, "", sha, role))
        elif patient and PurePosixPath(path).name == PATIENT_DERIVED:
            edges.append(_edge(common, "derived", path, "", sha, PATIENT_NOTE))
        elif url or path or sha:
            version = _file_version(entry)
            local = f"; local copy {path}" if url and path else ""
            ref = url or path or str(entry.get("name") or "")
            edges.append(_edge(common, "file", ref, version, sha, role + local))
    for host, entries in hosts.items():
        digest = rollup_digest(entries) if any(e.get("sha256") for e in entries) else ""
        note = "cached replies; the digest rolls up their sha256s" if digest else ""
        edges.append(_edge(common, "api", host, api_version(entries), digest, note))
    return edges


def _file_version(entry: dict[str, Any]) -> str:
    """The release the manifest states for a file, else the server's ``Last-Modified``."""
    for key in ("release", "version", "data_version"):
        if entry.get(key):
            return str(entry[key])
    modified = entry.get("last_modified")
    return f"last-modified {modified}" if modified else ""


def _edge(
    common: dict[str, object], kind: str, ref: str, version: str, sha: str, note: str
) -> dict[str, object]:
    notes = "; ".join(part for part in (str(common["notes"]), note) if part)
    return {
        **common,
        "source_kind": kind,
        "source_ref": ref,
        "source_version": version,
        "source_sha256": sha,
        "notes": notes,
    }


def manifest_edges(
    manifest_path: Path, root: Path, *, card: str = "", patient: bool = True
) -> list[dict[str, object]]:
    """Every edge one manifest implies, for every table it describes. Pure: reads disk only.

    ``card`` names a transfer case's configuration file (its ``card`` edge). ``patient`` is
    false for a transfer case: no ``derived`` or ``clinical`` edge can come from it.
    """
    try:
        loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    inputs = list(loaded.get("inputs") or [])
    universes = list(loaded.get("other_universes") or [])
    clinical = str((loaded.get("sources") or {}).get("clinical") or "")
    entry = str(loaded.get("entry") or "")
    edges: list[dict[str, object]] = []
    for path, rows in _outputs(manifest_path, loaded, root):
        common: dict[str, object] = {
            "target_schema": TRACK2_SCHEMA,
            "target_table": target_name(path),
            "target_rows": rows,
            "transform": _transform(loaded),
            "tool": str(loaded.get("built_by") or loaded.get("tool") or TOOL),
            "notes": f"entry {entry}" if entry else "",
        }
        # A generator's universe is widened by the other generators' universes (the twin's
        # rule); its list is not, so those inputs belong to the universe output only.
        widened = universes if path.endswith(".universe.tsv") else []
        found = _input_edges(inputs + widened, common, patient=patient)
        if card:
            found.insert(0, _card_edge(common, card, root))
        if patient and CLINICAL_FILE in clinical:
            found.append(
                _edge(
                    common,
                    "clinical",
                    CLINICAL_FILE,
                    CLINICAL_VERSION,
                    sha256_of(root / CLINICAL_FILE),
                    "the proband's HPO terms, named by the manifest's sources.clinical",
                )
            )
        edges += _unique(found)
    return edges


def _card_edge(common: dict[str, object], card: str, root: Path) -> dict[str, object]:
    try:
        version = json.loads((root / card).read_text(encoding="utf-8")).get("version")
    except (OSError, json.JSONDecodeError):
        version = None
    stated = f"v{version}" if version is not None else ""
    note = "the transfer case's configuration: public annotation only"
    return _edge(common, "card", card, stated, sha256_of(root / card), note)


def _unique(edges: list[dict[str, object]]) -> list[dict[str, object]]:
    seen: set[tuple[object, ...]] = set()
    kept = []
    for edge in edges:
        key = (edge["target_table"], edge["source_kind"], edge["source_ref"], edge["source_sha256"])
        if key not in seen:
            seen.add(key)
            kept.append(edge)
    return kept


def it4_edges(root: Path) -> list[dict[str, object]]:
    """Step 9's tables, step 10's ``it4/`` tree, then each step-11 transfer case."""
    track2 = root / TRACK2_DIR
    edges: list[dict[str, object]] = []
    for table in STEP9_TABLES:
        edges += manifest_edges(track2 / f"{table}.provenance.json", root)
    for manifest in sorted((root / IT4_DIR).rglob("*.provenance.json")):
        edges += manifest_edges(manifest, root)
    for case in sorted(p for p in (root / TRANSFER_IT4_DIR).glob("*") if p.is_dir()):
        card = case / CASE_FILE
        card_ref = card.relative_to(root).as_posix() if card.is_file() else ""
        for manifest in sorted(case.rglob("*.provenance.json")):
            if manifest.name != TRANSFER_RECORD:
                edges += manifest_edges(manifest, root, card=card_ref, patient=False)
    return edges
