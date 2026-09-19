"""Load iteration 2's step-8 mosaic tables into the warehouse, with their lineage.

Same shape as :mod:`mva.warehouse.it2_step6_tables`, and for the same reason: these rows are
produced in Python — a beta-binomial fit, a BIC, a simulated power curve — so this module's
job is to put them where SQL and the dashboard can read them, and to record where each one
came from.

**Step 8's lineage names one raw input and one absence.** Every table here is derived from
the delivered callset through the three ``it2_mosaic_*`` derivations, and from the committed
reference geometry that decided which arm each call sat on. The **clinical** row is the
unusual one and it is recorded deliberately: the clinical document lists no karyotype and no
term that a blood-DNA aneuploid fraction would predict, and the delivery never says which
tissue was sequenced. So the clinical source is named as *what this result may not be read
against*, rather than as an input — the alternative is a reader quietly treating a cell
fraction as a severity statement.

**Nothing here carries a position.** A row is a contig, an arm, a model name, a fraction and
a count. The derivations aggregated position away before these tables existed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from . import lineage
from .it2_step8_schema import (
    CALLSET_REF,
    CLINICAL_REF,
    CLINICAL_TRANSFORM,
    LIMITS_FIXED,
    LIMITS_TABLE,
    SCHEMAS,
    SOURCES,
    TOOL,
    TRANSFORMS,
)
from .postgres import ALIAS, safe_identifier

__all__ = ["SCHEMAS", "Loaded", "load"]


@dataclass(frozen=True)
class Loaded:
    """One table after loading: what it is called and how many rows arrived."""

    table: str
    rows: int
    source: Path


def _columns_for(table: str, path: Path) -> tuple[tuple[str, str], ...]:
    """The declared schema, narrowed to what this TSV actually carries.

    The schema is a promise about **types**, not about presence. A table written by an
    earlier run legitimately has fewer columns -- the fits on disk predate two of theirs --
    and loading should carry what is there rather than refuse the file or invent nulls for
    the rest. The limits table takes the opposite shape for the same reason: its power
    columns are one per simulated fraction, which is a parameter of the run.
    """
    header = tuple(path.read_text(encoding="utf-8").split("\n", 1)[0].rstrip("\r").split("\t"))
    if table == LIMITS_TABLE:
        declared = (
            *LIMITS_FIXED,
            *((name, "DOUBLE") for name in header if name.startswith("power_")),
        )
    else:
        declared = SCHEMAS[table]
    return tuple((name, sql_type) for name, sql_type in declared if name in header)


def _create(connection, schema: str, table: str, columns: tuple[tuple[str, str], ...]) -> str:
    """Replace the table: rebuilding from the TSV is the only way it is ever written, so a
    partial old copy left behind would be a silent mixture of two runs."""
    qualified = f"{ALIAS}.{safe_identifier(schema)}.{safe_identifier(table)}"
    body = ", ".join(f'"{name}" {sql_type}' for name, sql_type in columns)
    connection.execute(f"DROP TABLE IF EXISTS {qualified}")
    connection.execute(f"CREATE TABLE {qualified} ({body})")
    return qualified


def _load_tsv(
    connection, schema: str, table: str, path: Path, columns: tuple[tuple[str, str], ...]
) -> int:
    qualified = _create(connection, schema, table, columns)
    names = ", ".join(f'"{name}"' for name, _ in columns)
    casts = ", ".join(f"CAST(NULLIF(\"{name}\", '') AS {sql_type})" for name, sql_type in columns)
    connection.execute(
        f"INSERT INTO {qualified} ({names}) "
        f"SELECT {casts} FROM read_csv(?, delim='\t', header=true, all_varchar=true, "
        f"quote='\"', escape='\"')",
        [str(path)],
    )
    counted = connection.execute(f"SELECT count(*) FROM {qualified}").fetchone()
    return int((counted or [0])[0])


def _thinning(path: Path) -> str:
    """``thinning=0.11765`` from a dosage TSV, or an empty string if it carries no such column."""
    lines = path.read_text(encoding="utf-8").split("\n", 2)
    if len(lines) < 2:
        return ""
    header = lines[0].rstrip("\r").split("\t")
    first = lines[1].rstrip("\r").split("\t")
    fields = dict(zip(header, first, strict=False))
    return " ".join(
        f"{name}={fields[name]}" for name in ("shards_swept", "thinning") if name in fields
    )


def load(connection, *, schema: str, result_schema: str, out_dir: Path) -> list[Loaded]:
    """Load every step-8 table present in ``out_dir``, and record its lineage.

    A table whose TSV is absent is skipped rather than created empty: an empty table and a
    stage that did not run look identical in SQL, and only one of them is a result.
    """
    analysis_path = out_dir / "analysis.json"
    analysis = (
        json.loads(analysis_path.read_text(encoding="utf-8")) if analysis_path.exists() else {}
    )
    constants = analysis.get("constants", {})
    version = " ".join(
        f"{name}={value}"
        for name, value in (
            ("centre", constants.get("centre", "")),
            ("rho", constants.get("rho", "")),
            ("seed", constants.get("seed", "")),
        )
    )
    lineage.ensure_tables(connection, schema)

    loaded: list[Loaded] = []
    for table in (*SCHEMAS, LIMITS_TABLE):
        path = out_dir / "tables" / f"{table}.tsv"
        if not path.exists():
            continue
        rows = _load_tsv(connection, result_schema, table, path, _columns_for(table, path))
        loaded.append(Loaded(table=table, rows=rows, source=path))
        source_kind, source_ref = SOURCES.get(table, ("derived", CALLSET_REF))
        # How much of the read store a dosage pass swept is a parameter of the derivation,
        # not a property of the numbers, so it belongs in the lineage row rather than only
        # in the column beside them.
        source_version = f"{version} {_thinning(path)}".strip() if table in SOURCES else version
        lineage.record(
            connection,
            schema,
            target_schema=result_schema,
            target_table=table,
            target_rows=rows,
            source_kind=source_kind,
            source_ref=source_ref,
            source_version=source_version,
            transform=TRANSFORMS[table],
            tool=TOOL,
            notes=(
                "every result is 'in the sequenced sample': the delivery does not say which "
                "tissue was sequenced, and a karyotype's aneuploid fraction is measured in "
                "cultured cells"
            ),
        )
        lineage.record(
            connection,
            schema,
            target_schema=result_schema,
            target_table=table,
            target_rows=rows,
            source_kind="clinical",
            source_ref=CLINICAL_REF,
            transform=CLINICAL_TRANSFORM,
            tool=TOOL,
        )
    return loaded
