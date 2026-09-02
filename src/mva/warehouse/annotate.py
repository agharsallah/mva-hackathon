"""Annotate the panel's alleles through VEP and land the answer in the warehouse.

The callset arrives with no annotation worth ranking on — ``INFO/AF`` is *within-sample*,
0.5 or 1.0 for one person, not a population frequency. Everything the ranker needs about a
variant's consequence and rarity therefore comes from outside, through the annotator port.
This module is the warehouse half of that: it decides *which* alleles to ask about, and
where the answers live.

Three decisions are worth knowing before reading the SQL.

* **One scan, not eight.** ``variants_raw`` is 5,012,204 all-text rows with no index. The
  eight panel intervals are compiled into a single ``OR``-ed predicate so the server reads
  the table once instead of once per gene.
* **The interval is the BED's, converted.** A BED ``start`` is 0-based and half-open; the
  VCF's ``POS`` is 1-based. The query therefore spans ``start + 1 .. end``, which is what
  makes its counts comparable with ``warehouse.panel_variant_counts`` instead of one base
  wider.
* **ALT is split here, not in the raw layer.** ``variants_raw`` keeps a multi-allelic site
  exactly as delivered, ``G`` → ``A,C`` in one row, because the raw layer is lossless by
  contract. VEP must be asked about one allele at a time — a comma-packed query returns a
  single merged consequence that belongs to neither allele — so the split happens on the
  way out.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from ..pipeline.annotate_vep import DEFAULT_BASE_URL, VepRestAnnotator, batches
from ..pipeline.variant import Variant, to_vcf_contig
from ..pipeline.vep_response import VepRecord
from . import lineage
from .postgres import ALIAS, attached, safe_identifier
from .settings import Postgres

__all__ = [
    "ANNOTATIONS_TABLE",
    "DEFAULT_BASE_URL",
    "PANEL_TABLE",
    "RAW_TABLE",
    "TRANSFORM",
    "Interval",
    "alleles",
    "ensure_table",
    "intervals",
    "plan",
    "row_of",
    "run",
    "summarise",
    "write",
]

#: Where the annotations land. One row per (site, ALT allele).
ANNOTATIONS_TABLE = "panel_annotations"

#: The committed panel, as ingested. Its contigs are ``chr``-prefixed.
PANEL_TABLE = "mva_panel_grch38"

#: The lossless callset layer the alleles are read from.
RAW_TABLE = "variants_raw"

#: Written into ``panel_annotations.source`` and the lineage edge's transform.
TRANSFORM = "annotate-panel"


@dataclass(frozen=True)
class Interval:
    """One panel gene as the callset spells it: bare contig, 1-based inclusive bounds."""

    gene: str
    chrom: str
    start: int
    end: int


def intervals(connection, schema: str) -> list[Interval]:
    """The panel's genes, converted from BED to the callset's coordinate convention.

    The contig goes through :func:`~mva.pipeline.variant.to_vcf_contig`, the repository's
    single owner of the ``chr``-prefix bridge. A prefixed name matched against the bare
    callset returns zero rows, which is indistinguishable from a gene with no variants —
    the exact silent failure that rule exists to prevent.
    """
    safe = safe_identifier(schema)
    rows = connection.execute(
        f'SELECT name, chrom, start, "end" FROM {ALIAS}.{safe}.{PANEL_TABLE} ORDER BY name'
    ).fetchall()
    return [
        Interval(name, to_vcf_contig(chrom), int(start) + 1, int(end))
        for name, chrom, start, end in rows
    ]


def alleles(connection, schema: str, spans: list[Interval]) -> list[Variant]:
    """Every distinct ALT allele inside the panel, in submission representation.

    ``pos`` is cast because the raw layer is all text, where ``'999' > '1000'``. The result
    is de-duplicated and sorted so a re-run asks the API the same questions in the same
    order, which makes two runs comparable.
    """
    if not spans:
        return []
    safe = safe_identifier(schema)
    where = " OR ".join(["(chrom = ? AND CAST(pos AS BIGINT) BETWEEN ? AND ?)"] * len(spans))
    params: list = []
    for span in spans:
        params += [span.chrom, span.start, span.end]
    rows = connection.execute(
        f"SELECT DISTINCT chrom, CAST(pos AS BIGINT) AS pos, ref, alt "
        f"FROM {ALIAS}.{safe}.{RAW_TABLE} WHERE {where}",
        params,
    ).fetchall()

    found = {
        Variant.from_vcf(chrom, pos, ref, one)
        for chrom, pos, ref, alt in rows
        for one in str(alt).split(",")
        if one and one != "."
    }
    return sorted(found)


def ensure_table(connection, schema: str) -> None:
    """Create the annotation table, replacing whatever shape was there before.

    ``CREATE OR REPLACE`` matches every other ingest in this warehouse: the table is a pure
    function of the callset plus one VEP release, so a re-run should leave no residue of
    the previous one. The history that matters is the lineage edge, which is append-only.
    """
    safe = safe_identifier(schema)
    connection.execute(f"""
        CREATE OR REPLACE TABLE {ALIAS}.{safe}.{ANNOTATIONS_TABLE} (
            chrom             VARCHAR,
            pos               BIGINT,
            ref               VARCHAR,
            alt               VARCHAR,
            rsid              VARCHAR,
            gene              VARCHAR,
            consequence       VARCHAR,
            impact            VARCHAR,
            gnomad_af         DOUBLE,
            gnomad_af_grpmax  DOUBLE,
            clin_sig          VARCHAR,
            annotated_at      TIMESTAMP,
            source            VARCHAR
        )""")


def row_of(record: VepRecord, annotated_at: datetime, source: str) -> list:
    """One record as the table's column order.

    The contig is written **bare**, the way ``variants_raw`` spells it, so this table joins
    to the callset without a normalisation step at every call site. The submission's
    ``chr``-prefixed form is one :func:`~mva.pipeline.variant.to_submission_contig` away.
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
        annotated_at,
        source,
    ]


def write(
    connection, schema: str, records: list[VepRecord], source: str, annotated_at: datetime
) -> int:
    """Replace the annotation table with ``records`` and return the row count."""
    safe = safe_identifier(schema)
    ensure_table(connection, schema)
    placeholders = ", ".join(["?"] * 13)
    for record in records:
        connection.execute(
            f"INSERT INTO {ALIAS}.{safe}.{ANNOTATIONS_TABLE} VALUES ({placeholders})",
            row_of(record, annotated_at, source),
        )
    return len(records)


def summarise(records: list[VepRecord]) -> dict:
    """What the run actually produced, for the CLI to print and the entry to record."""
    return {
        "rows": len(records),
        "annotated": sum(1 for r in records if r.consequence),
        "with_gnomad_af": sum(1 for r in records if r.gnomad_af is not None),
        "with_grpmax": sum(1 for r in records if r.gnomad_af_grpmax is not None),
        "with_clin_sig": sum(1 for r in records if r.clin_sig),
        "with_rsid": sum(1 for r in records if r.rsid),
        "genes": sorted({r.gene for r in records if r.gene}),
    }


def plan(settings: Postgres, batch_size: int) -> dict:
    """What a run would ask for, without asking. Backs ``--dry-run``."""
    with attached(settings, read_only=True) as connection:
        spans = intervals(connection, settings.schema)
        wanted = alleles(connection, settings.schema, spans)
    return {
        "intervals": spans,
        "variants": wanted,
        "batches": len(batches(wanted, batch_size)),
        "batch_size": min(batch_size, len(wanted) or batch_size),
    }


def run(
    settings: Postgres, *, batch_size: int = 200, base_url: str = DEFAULT_BASE_URL, annotator=None
) -> dict:
    """Read the panel's alleles, annotate them, write the table, record the lineage.

    ``annotator`` is injectable so the whole path can be exercised against a fake; left
    unset it builds a :class:`~mva.pipeline.annotate_vep.VepRestAnnotator`.
    """
    with attached(settings) as connection:
        spans = intervals(connection, settings.schema)
        wanted = alleles(connection, settings.schema, spans)
        genes = [span.gene for span in spans]

        owned = annotator is None
        client = annotator or VepRestAnnotator(
            base_url=base_url, genes=genes, batch_size=batch_size
        )
        try:
            version = client.version()
            records = client.annotate_many(wanted)
        finally:
            if owned:
                client.close()

        source = (
            f"ensembl-vep-rest release={version.get('release', '?')} "
            f"assembly={version.get('assembly', '?')}"
        )
        annotated_at = datetime.now(UTC).replace(tzinfo=None)
        rows = write(connection, settings.schema, records, source, annotated_at)

        lineage.ensure_tables(connection, settings.schema)
        lineage.record(
            connection,
            settings.schema,
            target_schema=settings.schema,
            target_table=ANNOTATIONS_TABLE,
            target_rows=rows,
            source_kind="api",
            source_ref=f"{base_url}/vep/homo_sapiens/region",
            source_version=source,
            transform=f"{TRANSFORM}: distinct ALT-split alleles inside the "
            f"{len(spans)} panel intervals, annotated by Ensembl VEP REST",
            tool="mva-warehouse annotate-panel",
            notes=f"genes: {', '.join(genes)}; requests: {getattr(client, 'requests', 0)}",
        )

    return {
        "intervals": spans,
        "version": version,
        "source": source,
        "records": records,
        **summarise(records),
    }
