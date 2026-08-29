"""What each table was made from, and what each source object actually is.

The upload ledger in :mod:`mva.warehouse.source` answers "what did we put in the bucket,
and when". That is necessary but not sufficient. Two further questions get asked the moment
a result is disputed, and neither can be answered after the fact from memory:

* **What is this object?** A filename encodes lane, read number and flowcell, and those
  facts get re-parsed ad hoc in a dozen places unless they are extracted once. That is what
  :func:`enrich` does — it reads the delivery's naming convention into columns.
* **Where did this table come from?** Not "a VCF", but *which object, at which version,
  through which transformation, producing how many rows*. That is :data:`LINEAGE_TABLE`,
  an append-only edge list. A derived table with no lineage row is, by construction, a
  table nobody can vouch for.

Both tables are rebuilt or appended, never updated in place. Lineage that can be edited is
not evidence.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timezone

#: Current state of the bucket: one row per object, replaced wholesale on each check.
OBJECTS_TABLE = "source_objects"

#: Append-only record of which inputs produced which table.
LINEAGE_TABLE = "data_lineage"

#: The delivery's filename convention:
#: ``<sample>_<flowcell>_S<n>_L00<lane>_R<read>_001.fastq.gz``
#:
#: Anchored on the **right**, because the sample identifier itself contains underscores
#: (``WGS_EX2312012``). Splitting from the left assigns the sample's own suffix to the
#: flowcell and then matches nothing at all.
FASTQ_NAME = re.compile(
    r"^(?P<prefix>.+)_S(?P<snum>\d+)_L(?P<lane>\d+)_R(?P<read>\d)_\d+\.fastq\.gz$")

#: ``<sample>_<flowcell>.vcf.gz`` and its index, same right-anchored reasoning.
VCF_NAME = re.compile(r"^(?P<prefix>.+)\.vcf\.gz(?P<idx>\.tbi)?$")


def _split_prefix(prefix: str) -> tuple[str, str | None]:
    """Separate ``<sample>_<flowcell>``: the flowcell is the final underscore-delimited part."""
    sample, _, flowcell = prefix.rpartition("_")
    return (sample, flowcell) if sample else (prefix, None)


@dataclass(frozen=True)
class Enriched:
    """Facts read out of an object's name, or ``None`` where the name does not carry them."""

    sample: str | None = None
    flowcell: str | None = None
    lane: int | None = None
    read_num: int | None = None
    role: str = "other"

    @property
    def mate_key(self) -> str | None:
        """Identifies the pair a FASTQ belongs to: both mates share it."""
        if self.lane is None or self.flowcell is None:
            return None
        return f"{self.flowcell}:L{self.lane}"


def enrich(file_name: str) -> Enriched:
    """Parse the delivery's naming convention into structured facts.

    Deliberately conservative: an unrecognised name yields empty fields rather than a
    guess. A wrong lane number silently attached to a read is worse than a null.
    """
    match = FASTQ_NAME.match(file_name)
    if match:
        sample, flowcell = _split_prefix(match["prefix"])
        return Enriched(sample=sample, flowcell=flowcell,
                        lane=int(match["lane"]), read_num=int(match["read"]),
                        role="reads")
    match = VCF_NAME.match(file_name)
    if match:
        sample, flowcell = _split_prefix(match["prefix"])
        return Enriched(sample=sample, flowcell=flowcell,
                        role="variant_index" if match["idx"] else "variants")
    if file_name.lower().endswith((".md", ".docx", ".txt", ".pdf")):
        return Enriched(role="document")
    return Enriched()


def ensure_tables(connection, schema: str) -> None:
    """Create the object inventory and the lineage edge list if absent."""
    from .postgres import ALIAS, safe_identifier

    safe = safe_identifier(schema)
    connection.execute(f"""
        CREATE TABLE IF NOT EXISTS {ALIAS}.{safe}.{OBJECTS_TABLE} (
            checked_at     TIMESTAMP,
            bucket         VARCHAR,
            object_key     VARCHAR,
            file_name      VARCHAR,
            kind           VARCHAR,
            role           VARCHAR,
            sample         VARCHAR,
            flowcell       VARCHAR,
            lane           INTEGER,
            read_num       INTEGER,
            mate_key       VARCHAR,
            size_bytes     BIGINT,
            etag           VARCHAR,
            version_id     VARCHAR,
            last_modified  TIMESTAMP,
            content_type   VARCHAR,
            sha256         VARCHAR,
            sha256_source  VARCHAR,
            hash_verified  BOOLEAN
        )""")
    connection.execute(f"""
        CREATE TABLE IF NOT EXISTS {ALIAS}.{safe}.{LINEAGE_TABLE} (
            produced_at    TIMESTAMP,
            target_schema  VARCHAR,
            target_table   VARCHAR,
            target_rows    BIGINT,
            source_kind    VARCHAR,
            source_ref     VARCHAR,
            source_version VARCHAR,
            source_sha256  VARCHAR,
            transform      VARCHAR,
            tool           VARCHAR,
            notes          VARCHAR
        )""")


def survey(store, published: dict[str, str], ledger: dict[str, str]) -> list[dict]:
    """Describe every object in the bucket, enriched and hash-checked.

    ``published`` is the source dataset's own SHA-256 per file; ``ledger`` is what we
    recorded on upload. Preferring the publisher's hash as the reference means the check
    compares against an *external* authority rather than against our own earlier claim.
    """
    from .source import PREFIX, client

    s3 = client(store)
    rows: list[dict] = []
    token = None
    while True:
        kwargs = {"Bucket": store.bucket, "Prefix": f"{PREFIX}/"}
        if token:
            kwargs["ContinuationToken"] = token
        page = s3.list_objects_v2(**kwargs)
        for entry in page.get("Contents", []):
            key = entry["Key"]
            name = key.split("/")[-1]
            head = s3.head_object(Bucket=store.bucket, Key=key)
            stored = head.get("Metadata", {}).get("sha256", "")
            reference = published.get(name) or ledger.get(name) or ""
            facts = enrich(name)
            rows.append({
                "object_key": key, "file_name": name,
                "kind": _kind(name), "role": facts.role,
                "sample": facts.sample, "flowcell": facts.flowcell,
                "lane": facts.lane, "read_num": facts.read_num,
                "mate_key": facts.mate_key,
                "size_bytes": int(entry["Size"]),
                "etag": entry["ETag"].strip('"'),
                "version_id": head.get("VersionId", ""),
                "last_modified": entry["LastModified"].astimezone(
                    timezone.utc).replace(tzinfo=None),
                "content_type": head.get("ContentType", ""),
                "sha256": stored or reference,
                "sha256_source": ("publisher" if name in published
                                  else "upload" if stored or ledger.get(name) else ""),
                "hash_verified": bool(reference) and bool(stored) and stored == reference,
            })
        if not page.get("IsTruncated"):
            break
        token = page.get("NextContinuationToken")
    return sorted(rows, key=lambda r: r["file_name"])


def _kind(name: str) -> str:
    from .source import SourceFile
    from pathlib import Path
    return SourceFile(Path(name), 0, datetime.now(timezone.utc)).kind


def replace_objects(connection, schema: str, bucket: str, rows: list[dict]) -> None:
    """Rewrite the object inventory to match what the bucket holds right now.

    Replaced rather than appended because it describes *current* state. The history lives
    in the upload ledger, which is append-only; duplicating it here would make two records
    that could disagree.
    """
    from .postgres import ALIAS, safe_identifier

    safe = safe_identifier(schema)
    connection.execute(f"DELETE FROM {ALIAS}.{safe}.{OBJECTS_TABLE}")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for row in rows:
        connection.execute(
            f"INSERT INTO {ALIAS}.{safe}.{OBJECTS_TABLE} VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [now, bucket, row["object_key"], row["file_name"], row["kind"], row["role"],
             row["sample"], row["flowcell"], row["lane"], row["read_num"],
             row["mate_key"], row["size_bytes"], row["etag"], row["version_id"],
             row["last_modified"], row["content_type"], row["sha256"],
             row["sha256_source"], row["hash_verified"]])


def record(connection, schema: str, *, target_schema: str, target_table: str,
           target_rows: int, source_kind: str, source_ref: str,
           source_version: str = "", source_sha256: str = "",
           transform: str = "", tool: str = "mva-warehouse", notes: str = "") -> None:
    """Append one lineage edge: this table came from that input, this way."""
    from .postgres import ALIAS, safe_identifier

    safe = safe_identifier(schema)
    connection.execute(
        f"INSERT INTO {ALIAS}.{safe}.{LINEAGE_TABLE} VALUES "
        "(now(), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [target_schema, target_table, target_rows, source_kind, source_ref,
         source_version, source_sha256, transform, tool, notes])
