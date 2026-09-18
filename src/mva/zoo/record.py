"""Step 1 — one normalized **allele record** per allele, with its lineage.

Every model in the zoo reads a different spelling of the same change: a precomputed table
is keyed on HGVS, a protein language model wants an amino-acid window, a DNA model wants
raw bases. Rather than teach each adapter to go and find its own spelling, step 1 builds
one row that carries all of them — the *allele record* — and every adapter reads that.
Think of it as the single normalized DTO in front of a dozen consumers, so a new model is
a new reader, never a new query against the warehouse.

Where the fields come from:

====================  ==================================================================
field                 source
====================  ==================================================================
``allele_id``         computed — SHA-256 over the normalized change
                      (:func:`mva.zoo.types.allele_id`), and the only key that may leave
                      ``build/``
``gene``              ``it2_insilico_annotations`` → ``coding_annotations`` →
                      ``coding_alleles``, first non-null
``consequence``       the same order; what kind of change VEP called it
``af_gnomad``         population frequency, same order
``clin_sig``          ClinVar's class — a **catalogue field**, nulled by
                      ``--mask-catalogue`` so a ClinVar-trained model cannot read the
                      answer out of its own input
``is_read_only``      true for the alleles only the raw reads saw, which have no VCF row
``transcript``,       the VEP HGVS pass, :mod:`mva.zoo.record_hgvs`
``hgvs_c``,
``hgvs_p``
====================  ==================================================================

The MVP writes no sequence windows (plan §5, opt-A/opt-B); the parquet already carries the
columns so adding them later is a fill, not a migration.

Two outputs, on purpose:

* ``results.it4_allele_records`` — coordinate-free, replaced on every run, and therefore
  safe to read from the dashboard or quote in a report.
* ``build/it4/records.parquet`` — the same rows **plus** the coordinate, gitignored, with a
  sibling ``records.provenance.json`` naming every input, parameter and row count and the
  parquet's own sha256. One :data:`~mva.warehouse.lineage.LINEAGE_TABLE` edge records the
  same thing inside the warehouse.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..pipeline.annotate_vep import DEFAULT_BASE_URL
from ..warehouse.postgres import ALIAS, attached, safe_identifier
from ..warehouse.settings import Postgres
from .record_hgvs import (
    DEFAULT_CHECKPOINT,
    Annotates,
    Coordinate,
    HgvsAnnotator,
    hgvs_pass,
)
from .record_write import (
    DEFAULT_OUT_DIR,
    PARQUET_COLUMNS,
    TOOL,
    TRANSFORM,
    RunSummary,
    Written,
    ensure_records_table,
    summarise,
    write,
)
from .types import AlleleRecord

__all__ = [
    "DEFAULT_OUT_DIR",
    "PARQUET_COLUMNS",
    "TOOL",
    "TRANSFORM",
    "Alleles",
    "Coordinate",
    "RunSummary",
    "Schemas",
    "Written",
    "build_records",
    "consequence_classes",
    "ensure_records_table",
    "read_alleles",
    "run",
    "summarise",
    "write",
]

#: The four tables step 1 reads. Two spellings of ``chrom`` live across them (``chr1`` and
#: ``1``), so every join goes through the normalized id rather than the raw columns.
CODING_ALLELES = "coding_alleles"
CODING_ANNOTATIONS = "coding_annotations"
INSILICO_ANNOTATIONS = "it2_insilico_annotations"
READ_ANNOTATIONS = "it2_read_annotations"


@dataclass(frozen=True)
class Schemas:
    """Which two schemas to read and write. Accepts the settings object or plain names."""

    warehouse: str = "warehouse"
    results: str = "results"

    @classmethod
    def of(cls, source: Postgres | Schemas) -> Schemas:
        if isinstance(source, Schemas):
            return source
        return cls(warehouse=source.schema, results=source.result_schema)


@dataclass(frozen=True)
class Alleles:
    """What one read of the warehouse produced: records, their coordinates, their sources."""

    records: list[AlleleRecord]
    coordinates: dict[str, Coordinate]
    inputs: dict[str, int] = field(default_factory=dict)


# ── the id, computed in SQL exactly as Python computes it ────────────────────────────────


def contig_sql(column: str) -> str:
    """``chrom`` normalized the way :func:`mva.zoo.types.allele_id` normalizes it.

    The Python side strips a leading ``chr``, then a leading ``CHR``, then uppercases —
    in that order, which is not the same as uppercasing first. The SQL mirrors it step for
    step so the two agree on every spelling in the warehouse, including the odd ones; the
    agreement is asserted in ``tests/test_zoo_record.py`` rather than assumed.
    """
    stripped = f"CASE WHEN starts_with({column}, 'chr') THEN substr({column}, 4) ELSE {column} END"
    return (
        f"upper(CASE WHEN starts_with({stripped}, 'CHR') "
        f"THEN substr({stripped}, 4) ELSE {stripped} END)"
    )


def allele_id_sql(
    chrom: str = "chrom", pos: str = "pos", ref: str = "ref", alt: str = "alt"
) -> str:
    """The SQL expression that equals :func:`mva.zoo.types.allele_id` for every row."""
    return (
        f"substr(sha256(concat({contig_sql(chrom)}, ':', CAST({pos} AS BIGINT), ':', "
        f"upper({ref}), ':', upper({alt}))), 1, 16)"
    )


def _query(schemas: Schemas, limit: int | None = None) -> str:
    """The one statement that builds every record: dedupe, two left joins, one union.

    Grouping is by the **id**, not by the raw quadruple, so two spellings of one contig
    collapse into one record instead of two rows with the same key. ``min()`` rather than
    ``any_value()`` picks the representative columns, because a query that returns a
    different row each run is not reproducible.
    """
    res = f"{ALIAS}.{safe_identifier(schemas.results)}"
    war = f"{ALIAS}.{safe_identifier(schemas.warehouse)}"
    key = allele_id_sql()
    facts = (
        "min(gene) AS gene, min(consequence) AS consequence, "
        "min(gnomad_af) AS gnomad_af, min(clin_sig) AS clin_sig"
    )
    place = "min(chrom) AS chrom, min(CAST(pos AS BIGINT)) AS pos, min(ref) AS ref, min(alt) AS alt"
    tail = f" LIMIT {int(limit)}" if limit else ""
    return f"""
        WITH coding AS (
            SELECT {key} AS allele_id, {place}, min(gene) AS gene
            FROM {res}.{CODING_ALLELES} GROUP BY {key}
        ),
        ann AS (
            SELECT {key} AS allele_id, {facts}
            FROM {war}.{CODING_ANNOTATIONS} GROUP BY {key}
        ),
        insilico AS (
            SELECT {key} AS allele_id, {facts}
            FROM {war}.{INSILICO_ANNOTATIONS} GROUP BY {key}
        ),
        readonly AS (
            SELECT {key} AS allele_id, {place}, {facts}
            FROM {war}.{READ_ANNOTATIONS} GROUP BY {key}
        )
        SELECT c.allele_id, c.chrom, c.pos, c.ref, c.alt,
               coalesce(i.gene, a.gene, c.gene) AS gene,
               coalesce(i.consequence, a.consequence) AS consequence,
               coalesce(i.gnomad_af, a.gnomad_af) AS af_gnomad,
               coalesce(i.clin_sig, a.clin_sig) AS clin_sig,
               false AS is_read_only
        FROM coding c
        LEFT JOIN ann a ON a.allele_id = c.allele_id
        LEFT JOIN insilico i ON i.allele_id = c.allele_id
        UNION ALL
        SELECT r.allele_id, r.chrom, r.pos, r.ref, r.alt,
               r.gene, r.consequence, r.gnomad_af, r.clin_sig, true
        FROM readonly r
        WHERE r.allele_id NOT IN (SELECT allele_id FROM coding)
        ORDER BY is_read_only, allele_id{tail}"""


# ── reading ──────────────────────────────────────────────────────────────────────────────


def read_alleles(
    connection: Any,
    settings_or_schemas: Postgres | Schemas,
    *,
    mask_catalogue: bool = False,
    limit: int | None = None,
) -> Alleles:
    """Every allele in scope as a record, with its coordinate kept alongside, not inside."""
    schemas = Schemas.of(settings_or_schemas)
    rows = connection.execute(_query(schemas, limit)).fetchall()
    records: list[AlleleRecord] = []
    coordinates: dict[str, Coordinate] = {}
    for key, chrom, pos, ref, alt, gene, consequence, af, clin, read_only in rows:
        record = AlleleRecord(
            allele_id=str(key),
            gene=gene,
            consequence=consequence,
            is_read_only=bool(read_only),
            af_gnomad=float(af) if af is not None else None,
            clin_sig=clin,
        )
        records.append(record.masked() if mask_catalogue else record)
        coordinates[str(key)] = Coordinate(str(chrom), int(pos), str(ref), str(alt))
    return Alleles(records, coordinates, inputs=_input_rows(connection, schemas))


def build_records(
    connection: Any,
    settings_or_schemas: Postgres | Schemas,
    *,
    mask_catalogue: bool = False,
) -> list[AlleleRecord]:
    """The records alone, for a caller that does not need the coordinates."""
    return read_alleles(connection, settings_or_schemas, mask_catalogue=mask_catalogue).records


def _input_rows(connection: Any, schemas: Schemas) -> dict[str, int]:
    """Row count of every table the records were built from — the provenance denominator."""
    sources = (
        (schemas.results, CODING_ALLELES),
        (schemas.warehouse, CODING_ANNOTATIONS),
        (schemas.warehouse, INSILICO_ANNOTATIONS),
        (schemas.warehouse, READ_ANNOTATIONS),
    )
    counts: dict[str, int] = {}
    for schema, name in sources:
        qualified = f"{ALIAS}.{safe_identifier(schema)}.{safe_identifier(name)}"
        found = connection.execute(f"SELECT count(*) FROM {qualified}").fetchone()
        counts[f"{schema}.{name}"] = int(found[0])
    return counts


def consequence_classes(
    records: Sequence[AlleleRecord], gene: str = "BUB1B"
) -> dict[str, str | None]:
    """Which consequence class each of ``gene``'s alleles falls in, keyed by ``allele_id``.

    This is the day-1 answer to open question O7 / risk R9 of the plan: the MVP lanes are
    missense and splice tables, so if the confirmed pair's two alleles land in a class no
    MVP lane covers, a DNA-level lane (GPN-MSA) has to be promoted before step 2 runs.
    Gene symbol, never a position — the gate and the DTA both require that.
    """
    wanted = gene.upper()
    return {
        record.allele_id: record.consequence
        for record in records
        if (record.gene or "").upper() == wanted
    }


# ── the one entry point ──────────────────────────────────────────────────────────────────


def run(
    settings: Postgres,
    *,
    mask_catalogue: bool,
    out_dir: Path = DEFAULT_OUT_DIR,
    limit: int | None = None,
    annotator: Annotates | None = None,
    base_url: str = DEFAULT_BASE_URL,
    batch_size: int = 200,
    timeout: float = 60.0,
    progress: Callable[[str], None] | None = None,
) -> RunSummary:
    """Read → HGVS pass → write, and report the counts. What ``mva-zoo records`` calls.

    ``annotator`` is injected so the whole path runs against a fake; leaving it ``None``
    opens a real VEP REST client and closes it again.
    """
    say = progress or (lambda _line: None)
    with attached(settings) as connection:
        alleles = read_alleles(connection, settings, mask_catalogue=mask_catalogue, limit=limit)
        say(f"records {len(alleles.records):,}")
        client = annotator or HgvsAnnotator(
            base_url=base_url, batch_size=batch_size, timeout=timeout
        )
        try:
            passed = hgvs_pass(
                alleles.records,
                alleles.coordinates,
                client,
                checkpoint_dir=out_dir / DEFAULT_CHECKPOINT.name,
                batch_size=batch_size,
                progress=progress,
            )
        finally:
            if annotator is None:
                closer = getattr(client, "close", None)
                if callable(closer):
                    closer()
        written = write(
            connection,
            settings.result_schema,
            settings.schema,
            passed.records,
            alleles.coordinates,
            out_dir=out_dir,
            run_id="",
            source=passed.source,
            inputs=alleles.inputs,
            parameters={
                "mask_catalogue": mask_catalogue,
                "limit": limit,
                "batch_size": batch_size,
                "base_url": base_url,
            },
        )
    return summarise(
        passed.records,
        run_id=written.run_id,
        masked=mask_catalogue,
        rows=written.rows,
        parquet=str(written.parquet),
        provenance=str(written.provenance),
        sha256=written.sha256,
        source=passed.source,
        asked=passed.asked,
        resumed=passed.resumed,
    )
