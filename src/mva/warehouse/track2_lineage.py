"""Lineage edges for the Track 2 tables: what each drug table was actually built from.

``ressources/track2/*.tsv`` are the only committed tables in this repository that came from
**public APIs** rather than from the delivered callset. Each carries a provenance manifest
beside it, which is a complete record — but a manifest is a file a reader has to know to
open, while ``warehouse.data_lineage`` is the one ledger every provenance surface in the
project already reads. This module puts the Track 2 tables into that ledger.

``target_schema`` is the literal ``track2``. There is no such PostgreSQL schema and there
is not meant to be: the tables live on disk as TSV, and naming a schema that does not exist
would be worse than naming the thing that does. ``/api/track2`` reads these rows by exact
match on that value, exactly as ``/api/submissions`` reads its own.

Four kinds of source are recorded, and they are the four honest answers to "where did this
table come from":

* ``card`` — ``ressources/track2/mechanism.json``, by version and digest. Every query in
  the snapshot is derived from it: the gene, the disease, the directions, the seed targets.
* ``api`` — one edge per distinct API **host** the manifest read. A public API has no byte
  stream to hash, so ``source_sha256`` is a roll-up: the sha256 over that host's input
  digests, sorted and concatenated. ``source_version`` is the release the API states about
  itself when it states one, and otherwise the ``retrieved_at`` window of the replies used
  — never a version invented to fill the column.
* ``submission`` — the Track 1 iteration whose research record the card was written from.
  This is the hop that makes Track 2 traceable to the patient evidence at all.
* ``table`` — ``track2.targets`` for the three tables derived from the target set.

**Transfer cases.** ``ressources/track2/transfer/<CASE>/`` holds the same tables for a
*different case* run through the same pipeline (:mod:`mva.drugs.transfer`). Their edges are
recorded as ``transfer.<CASE>.<table>`` so they can never be confused with the real card's,
and they carry **no ``submission`` edge**: a transfer case is built from public annotation
(OMIM, MONDO, HPO, PubMed), not from the child's record, and pointing it at a Track 1
iteration would assert a provenance it does not have. The cross-case
``transfer_comparison`` table rests on both cards and gets one ``card`` edge each; the walk
back to the patient evidence still runs, through the real card's tables that it cites.

**Why this lives in ``mva.warehouse`` and not in ``mva.drugs``.** ``mva.drugs`` sits below
``mva.warehouse`` in the package layering and may not import it, so the recorder cannot
live beside the snapshot writer. It reads the manifests off disk instead, which also means
lineage can be recorded from a checkout long after the snapshot ran.

Appending is idempotent on ``(target_table, source_kind, source_ref, source_sha256)``. The
edge list is append-only: a second run must not double every row, and a *changed* digest is
a new edge, because it is a different input.

No coordinate can reach here. These tables name genes, drugs, trials and papers; the
manifests name URLs, digests and counts.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .lineage_edges import ensure_lineage_table, record
from .postgres import ALIAS, attached, safe_identifier
from .settings import Postgres
from .submission_lineage import Recorded, sha256_of

#: The schema name written into the edge. Not a real schema — see the module docstring.
TRACK2_SCHEMA = "track2"

#: Where the snapshot writes, relative to the repository root.
TRACK2_DIR = "ressources/track2"

#: The mechanism card. The one input every Track 2 query is derived from.
CARD_FILE = f"{TRACK2_DIR}/mechanism.json"

#: The tool that produced the tables, for the ``tool`` column.
TOOL = "mva-drugs snapshot"

#: The tables, in the order the snapshot writes them.
TABLES = ("targets", "drug_candidates", "trials", "literature", "pathways")

#: Step 7's enrichment tables (iteration 2), written by ``tools/track2_enrich.py`` beside the
#: five above. Their manifests name the tables they read under ``inputs[].path``, so their
#: edges point at ``track2.<table>`` rows rather than at the target set.
STEP7_TABLES = (
    "evidence",
    "drug_mechanism_literature",
    "pediatric_trials",
    "evidence_ladder",
    "shortlist",
    "do_not",
    "decoy_comparison",
)

#: Where a **transfer** card and its tables live: one folder per second case, built by
#: ``tools/track2_transfer.py``. A transfer case is public annotation (OMIM, MONDO, HPO,
#: PubMed) run through the same pipeline; it asserts no allele in any person, so its edges
#: carry **no** ``submission`` source — there is no patient record behind it to point at.
TRANSFER_DIR = f"{TRACK2_DIR}/transfer"

#: What a transfer card produces: the snapshot's five, plus the automated half of the
#: enrichment. No ``evidence`` (nobody curated one for a demonstration case) and no
#: ``decoy_comparison`` (no decoys sit beside it).
TRANSFER_TABLES = (
    *TABLES,
    "drug_mechanism_literature",
    "pediatric_trials",
    "evidence_ladder",
    "shortlist",
    "do_not",
)

#: The cross-case table at the Track 2 root: one row per case, real and transfer.
TRANSFER_COMPARISON = "transfer_comparison"

#: Every table lineage is recorded for.
ALL_TABLES = TABLES + STEP7_TABLES

#: The table every other table but ``pathways`` is derived from: the candidate drugs, the
#: trials and the literature are all searched *per target*, so the target set is an input.
TARGET_TABLE_REF = f"{TRACK2_SCHEMA}.targets"
DERIVED_FROM_TARGETS = ("drug_candidates", "trials", "literature")

#: The Track 1 iteration the card was written from, and the claims it cites. Constants
#: rather than parsed from the card: the card states the provenance in prose
#: (``"written ... from the research record (H003-H009, methodology 070-074)"``), and
#: parsing prose into a lineage edge would be a guess dressed as a reading.
SOURCE_ITERATION = "track1/iteration-1"
SOURCE_ITERATION_CLAIMS = "H003-H009"
SOURCE_ITERATION_NOTE = "the mechanism card derives from this iteration's record"

#: From card version 3 on, the card also carries iteration 2's measured facts (its
#: ``measured_facts`` block names the entries), so a second submission edge is written.
SOURCE_ITERATION_V3 = "track1/iteration-2"
SOURCE_ITERATION_V3_CLAIMS = "measured facts F1-F9 (methodology 083, 088-109)"
SOURCE_ITERATION_V3_FROM_VERSION = 3


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


def table_edges(
    directory: Path,
    table: str,
    root: Path,
    *,
    target: str | None = None,
    card_files: tuple[str, ...] = (CARD_FILE,),
    submission: bool = True,
) -> list[dict[str, object]]:
    """Every edge one Track 2 table implies. Pure: reads the manifest and hashes the cards.

    ``target`` renames the edge's ``target_table`` — a transfer case's tables are recorded
    as ``transfer.<CASE>.<table>`` so they can never be mistaken for the real card's table
    of the same name. ``card_files`` is a tuple because one table (the cross-case
    comparison) rests on more than one card. ``submission`` is false for a case that came
    from public annotation rather than from the child's record: there is no iteration to
    point at, and inventing one would be the opposite of lineage.
    """
    manifest = read_manifest(directory, table)
    if manifest is None:
        return []
    common = {
        "target_schema": TRACK2_SCHEMA,
        "target_table": target or table,
        "target_rows": manifest.rows,
        "transform": manifest.method,
        "tool": manifest.built_by,
        "notes": "",
    }
    edges: list[dict[str, object]] = [
        {
            **common,
            "source_kind": "card",
            "source_ref": card_file,
            "source_version": card_version((root / card_file).parent),
            "source_sha256": sha256_of(root / card_file),
        }
        for card_file in card_files
    ]
    edges += [
        {
            **common,
            "source_kind": "api",
            "source_ref": host,
            "source_version": api_version(manifest.for_host(host)),
            "source_sha256": rollup_digest(manifest.for_host(host)),
        }
        for host in manifest.hosts
    ]
    if submission:
        edges.append(
            {
                **common,
                "source_kind": "submission",
                "source_ref": SOURCE_ITERATION,
                "source_version": SOURCE_ITERATION_CLAIMS,
                "source_sha256": "",
                "notes": SOURCE_ITERATION_NOTE,
            }
        )
        if _card_number(directory) >= SOURCE_ITERATION_V3_FROM_VERSION:
            edges.append(
                {
                    **common,
                    "source_kind": "submission",
                    "source_ref": SOURCE_ITERATION_V3,
                    "source_version": SOURCE_ITERATION_V3_CLAIMS,
                    "source_sha256": "",
                    "notes": "card version 3+ carries iteration 2's measured facts",
                }
            )
    if table in DERIVED_FROM_TARGETS:
        edges.append(
            {
                **common,
                "source_kind": "table",
                "source_ref": _targets_ref(str(common["target_table"])),
                "source_version": "",
                "source_sha256": "",
            }
        )
    edges += [
        {
            **common,
            "source_kind": "table",
            "source_ref": _table_ref(str(entry["path"])),
            "source_version": "",
            "source_sha256": str(entry.get("sha256") or ""),
        }
        for entry in manifest.tables
    ]
    return edges


def _targets_ref(target_table: str) -> str:
    """The ``targets`` table of the *same* case as ``target_table``.

    ``drug_candidates`` is searched per target, so its input is the target set beside it —
    ``track2.targets`` for the real card, ``track2.transfer.TRIP13.targets`` for a transfer
    case. Pointing a transfer table at the real card's target set would be a false edge.
    """
    prefix = target_table.rsplit(".", 1)[0] + "." if "." in target_table else ""
    return f"{TRACK2_SCHEMA}.{prefix}targets"


def _card_number(directory: Path) -> int:
    text = card_version(directory)
    return int(text[1:]) if text.startswith("v") and text[1:].isdigit() else 0


def _table_ref(path: str) -> str:
    """The dotted table reference for one input path.

    ``ressources/track2/decoys/XDH/drug_candidates.tsv`` becomes
    ``track2.decoys.XDH.drug_candidates``: the decoy folder stays in the reference, so a
    decoy's table is never mistaken for the real card's table of the same name.
    """
    inner = path.split(f"{TRACK2_DIR}/", 1)[-1]
    return f"{TRACK2_SCHEMA}." + inner.removesuffix(".tsv").replace("/", ".")


def transfer_folders(root: Path) -> list[Path]:
    """Every transfer case that has a card on disk, in folder-name order."""
    return sorted(p for p in (root / TRANSFER_DIR).glob("*") if (p / "mechanism.json").is_file())


def transfer_edges(root: Path) -> list[dict[str, object]]:
    """Every edge a transfer case implies — and no ``submission`` edge on any of them.

    The cross-case comparison sits at the Track 2 root and rests on *both* cards, so it
    gets one ``card`` edge each. It also gets ``table`` edges to each case's committed
    TSVs from its own manifest, which is how the walk still reaches the Track 1 iteration:
    through the real card's tables, which carry the submission edges themselves.
    """
    folders = transfer_folders(root)
    if not folders:
        return []
    edges: list[dict[str, object]] = []
    for folder in folders:
        card_file = f"{TRANSFER_DIR}/{folder.name}/mechanism.json"
        for table in TRANSFER_TABLES:
            edges += table_edges(
                folder,
                table,
                root,
                target=f"transfer.{folder.name}.{table}",
                card_files=(card_file,),
                submission=False,
            )
    edges += table_edges(
        root / TRACK2_DIR,
        TRANSFER_COMPARISON,
        root,
        card_files=(
            CARD_FILE,
            *(f"{TRANSFER_DIR}/{folder.name}/mechanism.json" for folder in folders),
        ),
        submission=False,
    )
    return edges


def planned_edges(root: Path | None = None) -> list[dict[str, object]]:
    """Every edge the Track 2 tables imply, before anything is written."""
    base = (root or Path.cwd()).resolve()
    directory = base / TRACK2_DIR
    edges: list[dict[str, object]] = []
    for table in ALL_TABLES:
        edges += table_edges(directory, table, base)
    edges += transfer_edges(base)
    return edges


def existing_keys(connection, schema: str) -> set[tuple[str, str, str, str]]:
    """The ``(target_table, source_kind, source_ref, source_sha256)`` already recorded."""
    safe = safe_identifier(schema)
    found = connection.execute(
        f"SELECT target_table, source_kind, source_ref, source_sha256 "
        f"FROM {ALIAS}.{safe}.data_lineage WHERE target_schema = ?",
        [TRACK2_SCHEMA],
    ).fetchall()
    return {(row[0] or "", row[1] or "", row[2] or "", row[3] or "") for row in found}


def append_edges(connection, schema: str, edges: list[dict[str, object]]) -> Recorded:
    """Append the edges that are missing. Idempotent; nothing is ever updated."""
    ensure_lineage_table(connection, schema)
    present = existing_keys(connection, schema)
    appended = 0
    for edge in edges:
        key = (
            str(edge["target_table"]),
            str(edge["source_kind"]),
            str(edge["source_ref"]),
            str(edge["source_sha256"]),
        )
        if key in present:
            continue
        record(connection, schema, **edge)  # type: ignore[arg-type]  # a fixed, typed dict
        present.add(key)
        appended += 1
    return Recorded(TRACK2_SCHEMA, appended, len(edges) - appended)


def record_tables(settings: Postgres, root: Path | None = None) -> Recorded:
    """Write the Track 2 lineage edges, skipping the ones already there."""
    edges = planned_edges(root)
    with attached(settings) as connection:
        return append_edges(connection, settings.schema, edges)
