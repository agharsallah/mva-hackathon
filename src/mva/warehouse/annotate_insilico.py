"""The in-silico lanes step 4 scores with, landed beside the annotations already held.

``warehouse.coding_annotations`` holds what every allele in the callset *is* — gene,
consequence, population frequency, ClinVar. Step 4's likelihood ratio needs one more thing
per allele: what a **calibrated predictor** says about it, one predictor per consequence
class, chosen before any score was seen.

Ensembl's REST VEP serves two of the three the plan named:

* ``AlphaMissense=1`` → ``am_pathogenicity`` and the tool's own three-class ``am_class``,
  the missense lane;
* ``SpliceAI=1`` → the four delta scores, whose maximum is the splice lane;
* ``numbers=1`` → ``exon n/m``, without which a LOFTEE-style nonsense-mediated-decay rule
  cannot be applied at all.

``CADD=1`` and ``LoF=1`` are **not** served — both return HTTP 500 — so the CADD lane does
not exist in this iteration and LOFTEE is reimplemented from its published rules rather than
run. Both absences are recorded in methodology entry 098 rather than discovered at report
time.

**A sibling table, not a widened one.** ``coding_annotations`` is a platform table that
iteration 1's derivations read; altering its shape would rewrite history for a finished
iteration. This lands in its own table on the same four-key join
(``chrom, pos, ref, alt``), exactly as :mod:`mva.warehouse.annotate_reads` does, so every
query that wants the extra columns adds one ``LEFT JOIN`` and every query that does not is
untouched.

The request loop, the checkpointing and the lineage edge belong to
:mod:`mva.warehouse.annotate_coding`; this module supplies the destination shape and
nothing else.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ..pipeline.variant import to_vcf_contig
from ..pipeline.vep_response import VepRecord
from .postgres import ALIAS, safe_identifier

__all__ = [
    "CHECKPOINT",
    "INSILICO_TABLE",
    "TRANSFORM",
    "ensure_table",
    "row_of",
    "write",
]

#: Where the in-silico annotations land, in the ingest schema.
INSILICO_TABLE = "it2_insilico_annotations"

#: Gitignored: holds patient positions.
CHECKPOINT = Path("build/it2-insilico-annotations")

#: Written into the table's ``source`` and the lineage edge's transform.
TRANSFORM = "annotate-it2-insilico"

#: The column order, declared once. ``row_of`` and the INSERT both read it, so a column
#: added in one place cannot silently misalign the other.
COLUMNS: tuple[tuple[str, str], ...] = (
    ("chrom", "VARCHAR"),
    ("pos", "BIGINT"),
    ("ref", "VARCHAR"),
    ("alt", "VARCHAR"),
    ("rsid", "VARCHAR"),
    ("gene", "VARCHAR"),
    ("consequence", "VARCHAR"),
    ("impact", "VARCHAR"),
    ("gnomad_af", "DOUBLE"),
    ("gnomad_af_grpmax", "DOUBLE"),
    ("clin_sig", "VARCHAR"),
    ("am_pathogenicity", "DOUBLE"),
    ("am_class", "VARCHAR"),
    ("spliceai_ds_max", "DOUBLE"),
    ("spliceai", "VARCHAR"),
    ("exon_index", "INTEGER"),
    ("exon_total", "INTEGER"),
    ("annotated_at", "TIMESTAMP"),
    ("source", "VARCHAR"),
)


def ensure_table(connection, schema: str, table: str = INSILICO_TABLE) -> None:
    """Create the table, replacing whatever shape was there before.

    ``CREATE OR REPLACE`` matches every other ingest here: the table is a pure function of
    the callset plus one VEP release, so a re-run leaves no residue. The history that
    matters is the lineage edge, which is append-only.
    """
    body = ",\n            ".join(f"{name:<18} {kind}" for name, kind in COLUMNS)
    connection.execute(
        f"CREATE OR REPLACE TABLE {ALIAS}.{safe_identifier(schema)}."
        f"{safe_identifier(table)} (\n            {body}\n        )"
    )


def row_of(record: VepRecord, annotated_at: datetime, source: str) -> list:
    """One record in :data:`COLUMNS` order.

    The contig is written **bare**, the way ``variants_raw`` and ``coding_annotations``
    spell it, so the four-key join needs no normalisation at the call site.
    """
    return [
        to_vcf_contig(record.variant.chrom),
        record.variant.pos,
        record.variant.ref,
        record.variant.alt,
        record.rsid,
        record.gene,
        record.consequence,
        record.impact,
        record.gnomad_af,
        record.gnomad_af_grpmax,
        ";".join(record.clin_sig) or None,
        record.am_pathogenicity,
        record.am_class,
        record.spliceai_ds_max,
        record.spliceai,
        record.exon_index,
        record.exon_total,
        annotated_at,
        source,
    ]


def write(
    connection,
    schema: str,
    records: list[VepRecord],
    source: str,
    annotated_at: datetime,
    table: str = INSILICO_TABLE,
) -> int:
    """Replace the table with ``records`` and return the row count.

    Staged through a local temporary table and copied across in one statement, for the same
    reason :func:`mva.warehouse.annotate.write` does it: row-by-row ``INSERT`` over an
    attached connection is one network round trip per row, which is an hour at this scale.
    """
    safe = safe_identifier(schema)
    ensure_table(connection, schema, table)
    connection.execute(
        "CREATE OR REPLACE TEMP TABLE _insilico_rows AS "
        f"SELECT * FROM {ALIAS}.{safe}.{safe_identifier(table)} LIMIT 0"
    )
    if records:
        placeholders = ", ".join(["?"] * len(COLUMNS))
        connection.executemany(
            f"INSERT INTO _insilico_rows VALUES ({placeholders})",
            [row_of(record, annotated_at, source) for record in records],
        )
    connection.execute(
        f"INSERT INTO {ALIAS}.{safe}.{safe_identifier(table)} SELECT * FROM _insilico_rows"
    )
    (rows,) = connection.execute("SELECT count(*) FROM _insilico_rows").fetchone()
    return int(rows)
