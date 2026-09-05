"""Lineage edges for a submission iteration: what the uploaded CSV was actually built from.

Every derived table in this warehouse has a row in ``warehouse.data_lineage`` saying which
object, at which version, through which transform produced it. A **submission** had none —
the last hop, from the result tables to the eight rows an organiser scores, lived only in a
README. That is the hop a judge most wants to check, so this module writes it as edges like
any other derivation.

The target is not a table. ``target_schema`` is the literal ``submissions`` and
``target_table`` is ``<track>/iteration-<n>``, which is the folder path — the iteration
*is* the artefact, and inventing a fake table name for it would be worse than naming the
thing that exists. Nothing joins on it; ``/api/submissions`` reads it by exact match.

Four kinds of source are recorded, and they are the four honest answers to "where did this
come from":

* ``table`` — each warehouse result table a selector resolves an allele against;
* ``file`` — the committed, coordinate-free ``spec.selectors.json``, by digest;
* ``clinical`` — the delivered phenotype document, by digest. It never touches a variant,
  but it decided which gene was believed, so a lineage that omits it is incomplete.

**The predictions CSV is not a source and is not hashed here.** It holds real coordinates
and lives outside the tree; what is recorded is the digest the README *claims* for it,
carried in ``notes`` so a reply can be tied back to the exact bytes uploaded.

Appending is idempotent on ``(target_table, source_kind, source_ref, source_sha256)``. The
edge list is append-only, so a second run must not double every row; a *changed* digest is
a new edge, which is correct — it is a different file.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from .lineage_edges import ensure_lineage_table, record
from .postgres import ALIAS, attached, safe_identifier
from .settings import Postgres

#: The schema name written into the edge. Not a real schema — see the module docstring.
SUBMISSION_SCHEMA = "submissions"

#: The delivered phenotype document. Public per the challenge rules; no coordinate in it.
CLINICAL_FILE = "ressources/hackathon-rules/Challenge_Clinical_Phenotype_1.md"
CLINICAL_VERSION = "8 HPO terms"

#: What the recorded hop actually is, in one line.
TRANSFORM = "resolve selectors -> spec (coordinates, gitignored) -> design_submission CSV"

#: The tool that writes these edges, for the ``tool`` column.
TOOL = "resolve_submission_spec"

#: Tables every Track-1 iteration rests on beyond the ones its selectors name: the
#: biallelic gene set the verdict was drawn from and the phenotype ranking that ordered it.
#: Recorded as sources by ``/api/submissions``; not written as edges, because this tool
#: only witnesses what the selectors prove it used.
JOINED_TABLES = ("results.gene_biallelic", "warehouse.hpo_gene_scores")

SHA256_IN_TEXT = re.compile(r"\b([0-9a-f]{64})\b")

#: ``<schema>.<table>`` and nothing else — used to decide whether a ``source_ref`` names
#: another table (so the lineage walk can follow it) or an object, a URL or a file.
TABLE_REF = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class Recorded:
    """What one ``record_iteration`` run did."""

    target_table: str
    appended: int
    already_present: int

    def describe(self) -> str:
        return (
            f"{self.target_table}: {self.appended} edge(s) appended, "
            f"{self.already_present} already present"
        )


def sha256_of(path: Path) -> str:
    """The digest of a file, or ``""`` when it is not on this machine.

    An absent file is not an error here: the clinical document is part of the delivery and
    a checkout without it should still be able to record the rest of the lineage rather
    than fail the whole run over a hash it cannot compute.
    """
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def selector_tables(spec: dict) -> list[str]:
    """Every distinct ``schema.table`` the spec's alleles resolve against, sorted."""
    return sorted({allele["table"] for allele in spec.get("alleles", {}).values()})


def csv_digest(readme: str) -> str:
    """The predictions-CSV digest the README claims, or ``""`` when it claims none."""
    match = SHA256_IN_TEXT.search(readme)
    return match.group(1) if match else ""


def target_of(folder: Path) -> str:
    """``<track>/iteration-<n>`` — the value written into ``target_table``."""
    return f"{folder.parent.name}/{folder.name}"


def planned_edges(folder: Path, root: Path) -> list[dict[str, object]]:
    """The edges this iteration implies, before anything is written.

    Pure: reads the folder and hashes two files, touches no database. Exposed separately
    so a caller — or a test — can see what *would* be appended.
    """
    spec = json.loads((folder / "spec.selectors.json").read_text(encoding="utf-8"))
    readme_path = folder / "README.md"
    readme = readme_path.read_text(encoding="utf-8") if readme_path.is_file() else ""
    digest = csv_digest(readme)
    selectors_path = folder / "spec.selectors.json"
    relative = (
        selectors_path.relative_to(root).as_posix()
        if selectors_path.is_relative_to(root)
        else selectors_path.as_posix()
    )
    common = {
        "target_schema": SUBMISSION_SCHEMA,
        "target_table": target_of(folder),
        "target_rows": len(spec.get("rows", [])),
        "transform": TRANSFORM,
        "tool": TOOL,
        "notes": f"csv sha256 {digest}" if digest else "csv sha256 not recorded in the README",
    }
    edges: list[dict[str, object]] = [
        {
            **common,
            "source_kind": "table",
            "source_ref": table,
            "source_version": "",
            "source_sha256": "",
        }
        for table in selector_tables(spec)
    ]
    edges.append(
        {
            **common,
            "source_kind": "file",
            "source_ref": relative,
            "source_version": "",
            "source_sha256": sha256_of(selectors_path),
        }
    )
    edges.append(
        {
            **common,
            "source_kind": "clinical",
            "source_ref": CLINICAL_FILE,
            "source_version": CLINICAL_VERSION,
            "source_sha256": sha256_of(root / CLINICAL_FILE),
        }
    )
    return edges


def existing_keys(connection, schema: str, target_table: str) -> set[tuple[str, str, str]]:
    """The ``(source_kind, source_ref, source_sha256)`` already recorded for one target."""
    safe = safe_identifier(schema)
    found = connection.execute(
        f"SELECT source_kind, source_ref, source_sha256 "
        f"FROM {ALIAS}.{safe}.data_lineage "
        f"WHERE target_schema = ? AND target_table = ?",
        [SUBMISSION_SCHEMA, target_table],
    ).fetchall()
    return {(row[0] or "", row[1] or "", row[2] or "") for row in found}


def append_edges(connection, schema: str, edges: list[dict[str, object]]) -> Recorded:
    """Append the edges this target is missing. Idempotent; nothing is ever updated."""
    target_table = str(edges[0]["target_table"]) if edges else ""
    ensure_lineage_table(connection, schema)
    present = existing_keys(connection, schema, target_table)
    appended = 0
    for edge in edges:
        key = (
            str(edge["source_kind"]),
            str(edge["source_ref"]),
            str(edge["source_sha256"]),
        )
        if key in present:
            continue
        record(connection, schema, **edge)  # type: ignore[arg-type]  # a fixed, typed dict
        present.add(key)
        appended += 1
    return Recorded(target_table, appended, len(edges) - appended)


def record_iteration(settings: Postgres, folder: Path, root: Path | None = None) -> Recorded:
    """Write this iteration's lineage edges, skipping the ones already there."""
    base = (root or Path.cwd()).resolve()
    edges = planned_edges(folder.resolve(), base)
    with attached(settings) as connection:
        return append_edges(connection, settings.schema, edges)
