"""Load iteration 2's step-1 tables into the warehouse, with their lineage.

The target set is not a SQL derivation and this module does not pretend it is. Tiering
walks the ontology's ancestor closure and the decoy draw matches gene shape from a seeded
random draw — graph and sampling work that belongs in :mod:`mva.phenotype.targets`, whose
output ``tools/build_it2_targets.py`` writes as TSV under ``build/``. What is left for the
warehouse is the honest part: put those rows where SQL and the dashboard can read them,
and record where they came from.

Every table written here gets a :mod:`~mva.warehouse.lineage` row naming **both** of the
case's inputs where both were used — the clinical HPO terms and the public ontology
release — because a target set derived from symptoms alone is exactly the kind of table
whose provenance a reader will otherwise assume was genomic.

The tables live in the **result** schema under the ``it2_`` prefix: iteration 2 re-derives
its own tables rather than reading iteration 1's, and the prefix is what makes that
visible in a table listing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from . import lineage
from .postgres import ALIAS, safe_identifier

#: Column types, so a rank sorts as a number and a tier compares as text. Written out
#: rather than sniffed: these two tables are small and their schema is a promise the
#: dashboard and step 2 both read.
TARGETS_COLUMNS: tuple[tuple[str, str], ...] = (
    ("symbol", "VARCHAR"),
    ("tier", "VARCHAR"),
    ("score_rank", "INTEGER"),
    ("score", "DOUBLE"),
    ("entered_by", "VARCHAR"),
    ("term_sets", "VARCHAR"),
)

DECOYS_COLUMNS: tuple[tuple[str, str], ...] = (
    ("symbol", "VARCHAR"),
    ("matched_to", "VARCHAR"),
    ("coding_length", "INTEGER"),
    ("exon_count", "INTEGER"),
)

TARGETS_TABLE = "it2_targets"
DECOYS_TABLE = "it2_decoys"


@dataclass(frozen=True)
class Loaded:
    """One table after loading: what it is called and how many rows arrived."""

    table: str
    rows: int
    source: Path


def _create(connection, schema: str, table: str, columns: tuple[tuple[str, str], ...]) -> str:
    """Replace the table. Rebuilding from the TSV is the only way it is ever written, so a
    partial old copy left behind would be a silent mixture of two runs."""
    qualified = f"{ALIAS}.{safe_identifier(schema)}.{safe_identifier(table)}"
    body = ", ".join(f"{name} {sql_type}" for name, sql_type in columns)
    connection.execute(f"DROP TABLE IF EXISTS {qualified}")
    connection.execute(f"CREATE TABLE {qualified} ({body})")
    return qualified


def _load_tsv(
    connection, schema: str, table: str, path: Path, columns: tuple[tuple[str, str], ...]
) -> int:
    qualified = _create(connection, schema, table, columns)
    names = ", ".join(name for name, _ in columns)
    casts = ", ".join(f"CAST(NULLIF({name}, '') AS {sql_type})" for name, sql_type in columns)
    connection.execute(
        f"INSERT INTO {qualified} ({names}) "
        f"SELECT {casts} FROM read_csv(?, delim='\t', header=true, all_varchar=true)",
        [str(path)],
    )
    counted = connection.execute(f"SELECT count(*) FROM {qualified}").fetchone()
    return int((counted or [0])[0])


def load(connection, *, schema: str, result_schema: str, out_dir: Path) -> list[Loaded]:
    """Load ``targets.tsv`` and ``decoys.tsv`` from a step-1 build, and record lineage.

    ``schema`` is where the append-only ``data_lineage`` table lives; ``result_schema`` is
    where the two tables are written.
    """
    manifest_path = out_dir / "provenance.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    lineage.ensure_tables(connection, schema)

    loaded: list[Loaded] = []
    for table, filename, columns, transform in (
        (
            TARGETS_TABLE,
            "targets.tsv",
            TARGETS_COLUMNS,
            (
                "phenotype ranking of both term sets, unioned on best rank, tiered into "
                "core / net / mechanism-term (mva.phenotype.targets.build)"
            ),
        ),
        (
            DECOYS_TABLE,
            "decoys.tsv",
            DECOYS_COLUMNS,
            (
                "one decoy per target matched on coding length and exon count, drawn from "
                f"seed {manifest['parameters']['seed']} "
                "(mva.phenotype.targets.draw_decoys)"
            ),
        ),
    ):
        path = out_dir / filename
        rows = _load_tsv(connection, result_schema, table, path, columns)
        loaded.append(Loaded(table=table, rows=rows, source=path))
        for source in manifest["inputs"]:
            lineage.record(
                connection,
                schema,
                target_schema=result_schema,
                target_table=table,
                target_rows=rows,
                source_kind="file",
                source_ref=source["path"],
                source_version=manifest.get("hpo_release", ""),
                source_sha256=source["sha256"],
                transform=transform,
                tool="tools/build_it2_targets.py",
                notes=source["role"],
            )
        # The clinical half of the lineage. Named separately because it is a different
        # kind of input — the child's own phenotype, not a public release — and a reader
        # must be able to see that this table was built from it.
        clinical = manifest["clinical_input"]
        lineage.record(
            connection,
            schema,
            target_schema=result_schema,
            target_table=table,
            target_rows=rows,
            source_kind="clinical",
            source_ref=clinical["source"],
            source_version=",".join(sorted(clinical["term_sets"])),
            transform=transform,
            tool="tools/build_it2_targets.py",
            notes=(
                "the proband's HPO terms: the only case-specific input to step 1, which "
                "reads no genomic data at all"
            ),
        )
    return loaded
