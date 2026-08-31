"""The data catalogue: what raw data exists, and what every warehouse table holds.

Every other endpoint answers "what does the data *say*". These two answer "what data is
there at all" — the question a reviewer asks first and the one no chart covers.

Two rules shape the module.

* **Metadata is read, never restated.** Row counts, hashes, versions, lineage edges and
  table descriptions all come out of the database. The only text written here is the
  description of an object's *contents*, which nothing in the store records, and the
  one-liners for the handful of tables no catalogue row and no derivation owns.
* **A missing fact is null, not a guess.** An object with no upload-ledger row gets
  ``first_uploaded_at: null``; a table with no lineage edge gets four nulls. Both happen
  in the live warehouse, and inventing a plausible value would make the catalogue a
  worse record than no catalogue.

Distinct from :mod:`mva.warehouse.catalog`, which declares the *profile source files*
staging reads off disk. This module describes what ended up in the store and the database.
"""

from pathlib import Path

from ..warehouse.analysis import PROVENANCE_TABLE
from ..warehouse.lineage import LINEAGE_TABLE, OBJECTS_TABLE
from ..warehouse.postgres import ALIAS, attached, safe_identifier
from ..warehouse.settings import Postgres
from ..warehouse.source import LEDGER_TABLE
from ..warehouse.stage import CATALOG_TABLE
from .queries import rows

#: What an object of each ``role`` contains, in one sentence. Keyed by the role
#: :func:`mva.warehouse.lineage.enrich` parsed out of the file name, so a delivery with a
#: different naming convention still gets the right sentence — or the honest fallback.
ROLES = {
    "variants": "The callset: every small variant (SNV or short indel) called for this "
                "sample, as a bgzip-compressed VCF — one row per variant site, carrying "
                "the quality filters and the sample's genotype.",
    "variant_index": "Tabix index for the callset — the block offsets that let a reader "
                     "jump to one region without decompressing the whole VCF.",
    "reads": "Raw sequencing reads as the instrument delivered them — gzipped FASTQ, four "
             "lines per read: name, bases, separator, per-base quality.",
    "": "An object whose name matches no known convention, so nothing is claimed about "
        "its contents.",
}

#: Documents are told apart by extension rather than by role: the delivery ships prose in
#: several formats and the role parser cannot see inside any of them.
DOCUMENTS = {
    ".docx": "A delivered Word document. Prose, not data — no pipeline stage parses it.",
    ".pdf": "A delivered PDF. Prose, not data — no pipeline stage parses it.",
    ".md": "A delivered Markdown document — what the publisher says the dataset is.",
    ".txt": "A delivered plain-text note.",
    "": "A delivered document.",
}

#: Tables that neither the staging catalogue nor a derivation run describes: the ledgers,
#: the raw layer, and the catalogue table itself. Keyed by bare table name, because the
#: schema names are configurable.
UNCATALOGUED = {
    "variants_raw": "The callset as delivered, one row per VCF record with every column "
                    "kept as text — the lossless raw layer every derivation reads.",
    "panel_annotations": "Ensembl VEP's answer for every allele in the candidate panel: "
                         "consequence, impact, gnomAD frequency and ClinVar "
                         "significance, one row per allele, with the instant it was "
                         "fetched.",
    OBJECTS_TABLE: "Current contents of the object store's source prefix: one row per "
                   "object with its size, hash, version and the lane/read facts parsed "
                   "out of its name. Replaced wholesale on every survey.",
    LEDGER_TABLE: "Append-only upload ledger: one row per upload, carrying the SHA-256 "
                  "computed locally before the bytes left the machine.",
    LINEAGE_TABLE: "Append-only edge list: which input, at which version, through which "
                   "transform, produced which table and how many rows.",
    CATALOG_TABLE: "The self-describing catalogue staging writes: what every staged "
                   "table holds, its column list and its row count at staging time.",
    "probe_ledger": "Append-only record of every oracle submission spent against the "
                    "challenge budget, with the reply it returned.",
    PROVENANCE_TABLE: "Append-only log of every derivation run: when it ran, the question "
                      "it answers and how many rows it produced.",
}

#: The object inventory joined to the earliest upload recorded for the same key. A LEFT
#: JOIN because an object fetched straight from the publisher never passed through the
#: ledger, and that absence is a fact worth serving rather than a row worth dropping.
OBJECTS_SQL = """
    SELECT o.bucket, o.object_key, o.file_name, o.kind, o.role, o.size_bytes,
           o.content_type, o.sha256, o.sha256_source, o.hash_verified, o.version_id,
           o.last_modified, o.sample, o.flowcell, o.lane, o.read_num,
           u.first_uploaded_at
    FROM {alias}.{schema}.{objects} o
    LEFT JOIN (SELECT object_key, min(uploaded_at) AS first_uploaded_at
               FROM {alias}.{schema}.{ledger} GROUP BY object_key) u
      ON u.object_key = o.object_key
    ORDER BY o.role, o.file_name
"""


def describe(found: dict) -> str:
    """One human sentence about what an object contains, from its metadata alone."""
    role = found.get("role") or ""
    if role == "document":
        suffix = Path(found.get("file_name") or "").suffix.lower()
        body = DOCUMENTS.get(suffix, DOCUMENTS[""])
    else:
        body = ROLES.get(role, ROLES[""])
    context = _context(found)
    return f"{body} {context}" if context else body


def _context(found: dict) -> str:
    """The lane, mate, sample and flowcell the name carried, as a trailing clause."""
    bits = []
    if found.get("lane") is not None:
        bits.append(f"lane {found['lane']}")
    if found.get("read_num") is not None:
        bits.append(f"mate R{found['read_num']}")
    if found.get("sample"):
        bits.append(f"sample {found['sample']}")
    if found.get("flowcell"):
        bits.append(f"flowcell {found['flowcell']}")
    if not bits:
        return ""
    joined = ", ".join(bits)
    return f"{joined[0].upper()}{joined[1:]}."


def objects(settings: Postgres) -> list[dict]:
    """Every object in the store's source prefix, with what it is and where it lives.

    Live on every request: twelve rows off a table that is replaced wholesale by
    ``mva-warehouse source-check``, so a cache would only hide a fresh survey.
    """
    schema = safe_identifier(settings.schema)
    sql = OBJECTS_SQL.format(alias=ALIAS, schema=schema,
                             objects=OBJECTS_TABLE, ledger=LEDGER_TABLE)
    with attached(settings, read_only=True) as connection:
        found = rows(connection, sql)
    return [_object(row) for row in found]


def _object(found: dict) -> dict:
    """One inventory row in the catalogue's field order, with ``location`` built here.

    The bucket and the key are stored separately because the inventory is written by a
    survey of one bucket; a reader wants the addressable URL, and building it in the
    browser would put the store's layout into the front end.
    """
    return {
        "file_name": found["file_name"],
        "object_key": found["object_key"],
        "location": f"s3://{found['bucket']}/{found['object_key']}",
        "kind": found["kind"],
        "role": found["role"],
        "description": describe(found),
        "size_bytes": found["size_bytes"],
        "content_type": found["content_type"],
        "sha256": found["sha256"],
        "sha256_source": found["sha256_source"],
        "hash_verified": found["hash_verified"],
        "version_id": found["version_id"],
        "last_modified": found["last_modified"],
        "first_uploaded_at": found["first_uploaded_at"],
        "sample": found["sample"],
        "flowcell": found["flowcell"],
        "lane": found["lane"],
        "read_num": found["read_num"],
    }


def tables(settings: Postgres) -> list[dict]:
    """Every table in both managed schemas, with its description, size and lineage.

    One connection for four reads, for the reason :mod:`mva.viz.overview` gives: each
    ``ATTACH`` costs a round trip plus authentication.
    """
    schema = safe_identifier(settings.schema)
    results = safe_identifier(settings.result_schema)
    with attached(settings, read_only=True) as connection:
        listed = [(row["schema"], row["table"]) for row in rows(connection, f"""
            SELECT table_schema AS schema, table_name AS "table"
            FROM {ALIAS}.information_schema.tables
            WHERE table_schema IN (?, ?) ORDER BY table_schema, table_name
        """, [schema, results])]
        counts = _counts(connection, listed)
        staged = {row["table_name"]: row["description"] for row in rows(
            connection,
            f"SELECT table_name, description FROM {ALIAS}.{schema}.{CATALOG_TABLE}")}
        asked = {row["derivation"]: row["question"] for row in rows(
            connection,
            f"SELECT derivation, max_by(question, run_at) AS question "
            f"FROM {ALIAS}.{results}.{PROVENANCE_TABLE} GROUP BY derivation")}
        edges = {(row["target_schema"], row["target_table"]): row
                 for row in rows(connection, f"""
            SELECT target_schema, target_table,
                   max(produced_at)                 AS produced_at,
                   max_by(source_kind, produced_at) AS source_kind,
                   max_by(source_ref, produced_at)  AS source_ref,
                   max_by(tool, produced_at)        AS tool
            FROM {ALIAS}.{schema}.{LINEAGE_TABLE}
            GROUP BY target_schema, target_table
        """)}
    return [_table(name, counts, staged if name[0] == schema else {},
                   asked if name[0] == results else {}, edges) for name in listed]


def _table(name: tuple[str, str], counts: dict, staged: dict, asked: dict,
           edges: dict) -> dict:
    """One catalogue row. Three description sources, tried in order, then null."""
    schema, table = name
    edge = edges.get(name, {})
    return {
        "schema": schema,
        "table": table,
        "description": (staged.get(table) or asked.get(table)
                        or UNCATALOGUED.get(table)),
        "rows": counts.get(name),
        "produced_at": edge.get("produced_at"),
        "source_kind": edge.get("source_kind"),
        "source_ref": edge.get("source_ref"),
        "tool": edge.get("tool"),
    }


def _counts(connection, listed: list[tuple[str, str]]) -> dict[tuple[str, str], int]:
    """Exact row counts for every table, in one statement executed inside PostgreSQL.

    Measured on the live warehouse (38 tables, one of them 5,012,204 rows):

    * one ``UNION ALL`` pushed down through ``postgres_query`` — **2.7 s**
    * one ``count(*)`` round trip per table — 25.7 s
    * ``pg_class.reltuples`` — 0.2 s, and **unusable**: 22 of the 38 tables have never
      been analysed and report ``-1``, and the one large table is off by 2,172 rows.

    So the counts are exact, and the endpoint that serves them is cached.
    """
    if not listed:
        return {}
    # Both identifiers came out of information_schema and are re-validated before being
    # interpolated, so neither the table reference nor the quoted literal can be injected.
    union = " UNION ALL ".join(
        f"SELECT '{safe_identifier(schema)}' AS s, '{safe_identifier(table)}' AS t, "
        f"count(*) AS n FROM {schema}.{table}" for schema, table in listed)
    found = connection.execute(
        f"SELECT s, t, n FROM postgres_query('{ALIAS}', $${union}$$)").fetchall()
    return {(row[0], row[1]): int(row[2]) for row in found}
