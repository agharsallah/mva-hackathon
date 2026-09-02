"""Current state of the bucket: one hash-verified, enriched row per object.

Answers "what is this object" — not just its bytes, but its role (reads, variants,
document, ...) and, where the name carries them, its sample, flowcell, lane and read
number, read out by :func:`mva.warehouse.lineage_naming.enrich`. :data:`OBJECTS_TABLE` is
replaced wholesale on each check, not appended to: it describes the bucket *right now*,
and the append-only upload history already lives in
:mod:`mva.warehouse.source`. Duplicating that history here would make two records that
could disagree.
"""

from datetime import UTC, datetime

from .lineage_naming import enrich

#: Current state of the bucket: one row per object, replaced wholesale on each check.
OBJECTS_TABLE = "source_objects"


def ensure_objects_table(connection, schema: str) -> None:
    """Create the object inventory table if absent."""
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
            rows.append(
                {
                    "object_key": key,
                    "file_name": name,
                    "kind": _kind(name),
                    "role": facts.role,
                    "sample": facts.sample,
                    "flowcell": facts.flowcell,
                    "lane": facts.lane,
                    "read_num": facts.read_num,
                    "mate_key": facts.mate_key,
                    "size_bytes": int(entry["Size"]),
                    "etag": entry["ETag"].strip('"'),
                    "version_id": head.get("VersionId", ""),
                    "last_modified": entry["LastModified"].astimezone(UTC).replace(tzinfo=None),
                    "content_type": head.get("ContentType", ""),
                    "sha256": stored or reference,
                    "sha256_source": (
                        "publisher"
                        if name in published
                        else "upload"
                        if stored or ledger.get(name)
                        else ""
                    ),
                    "hash_verified": bool(reference) and bool(stored) and stored == reference,
                }
            )
        if not page.get("IsTruncated"):
            break
        token = page.get("NextContinuationToken")
    return sorted(rows, key=lambda r: r["file_name"])


def _kind(name: str) -> str:
    from pathlib import Path

    from .source import SourceFile

    return SourceFile(Path(name), 0, datetime.now(UTC)).kind


def replace_objects(connection, schema: str, bucket: str, rows: list[dict]) -> None:
    """Rewrite the object inventory to match what the bucket holds right now.

    Replaced rather than appended because it describes *current* state. The history lives
    in the upload ledger, which is append-only; duplicating it here would make two records
    that could disagree.
    """
    from .postgres import ALIAS, safe_identifier

    safe = safe_identifier(schema)
    connection.execute(f"DELETE FROM {ALIAS}.{safe}.{OBJECTS_TABLE}")
    now = datetime.now(UTC).replace(tzinfo=None)
    for row in rows:
        connection.execute(
            f"INSERT INTO {ALIAS}.{safe}.{OBJECTS_TABLE} VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                now,
                bucket,
                row["object_key"],
                row["file_name"],
                row["kind"],
                row["role"],
                row["sample"],
                row["flowcell"],
                row["lane"],
                row["read_num"],
                row["mate_key"],
                row["size_bytes"],
                row["etag"],
                row["version_id"],
                row["last_modified"],
                row["content_type"],
                row["sha256"],
                row["sha256_source"],
                row["hash_verified"],
            ],
        )
