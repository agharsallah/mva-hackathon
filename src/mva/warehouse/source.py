"""The raw landing zone: delivered files, unchanged, with a record of every upload.

This layer exists to be a **source of truth**. Files go into object storage exactly as
delivered — not parsed, not normalised, not filtered — and every upload is recorded in
PostgreSQL with a checksum taken *before* the bytes leave this machine. Nothing here ever
rewrites an object: the bucket carries S3 versioning, so re-uploading a changed file
creates a new version beside the old one rather than replacing it.

The reason to build this before any analysis: once derived tables exist, questions like
"which version of the input produced this result?" and "has the delivery changed since we
started?" have to be answerable from records, not memory. A checksum computed after the
fact proves nothing.

Three rules the implementation follows.

* **Checksum locally, verify remotely.** The SHA-256 is computed by reading the local file,
  and compared afterwards against what the store reports it holds. A hash produced by the
  system being audited is not evidence.
* **Append, never update.** :data:`LEDGER_TABLE` gains a row per upload. A file uploaded
  twice has two rows, and the history is the point.
* **Nothing is interpreted.** A FASTQ goes up as the gzip it arrived as. Parsing belongs in
  layers derived from this one, which can always be rebuilt.
"""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

#: Where the delivered files land inside the bucket.
PREFIX = "source"

#: Append-only record of every upload, in the ingest schema.
LEDGER_TABLE = "source_files"

#: Read size for hashing. Large enough that syscall overhead is irrelevant on an 11 GB file.
CHUNK = 8 * 1024 * 1024

#: Files that are the delivery itself rather than something about it.
SKIP_NAMES = {".gitattributes", ".DS_Store"}


@dataclass(frozen=True)
class SourceFile:
    """One delivered file, as it exists on disk."""

    path: Path
    size: int
    modified: datetime
    sha256: str = ""

    @property
    def key(self) -> str:
        """Where it belongs in the bucket."""
        return f"{PREFIX}/{self.path.name}"

    @property
    def kind(self) -> str:
        """A coarse label, so the ledger can be grouped without parsing filenames twice."""
        name = self.path.name.lower()
        if ".fastq" in name or ".fq" in name:
            return "fastq"
        if name.endswith((".vcf", ".vcf.gz")):
            return "vcf"
        if name.endswith(".tbi") or name.endswith(".csi"):
            return "index"
        if name.endswith((".docx", ".md", ".txt", ".pdf")):
            return "document"
        return "other"


def scan(directory: Path) -> list[SourceFile]:
    """Inventory a delivery directory, without reading file contents."""
    found: list[SourceFile] = []
    for path in sorted(Path(directory).iterdir()):
        if not path.is_file() or path.name in SKIP_NAMES:
            continue
        stat = path.stat()
        found.append(SourceFile(
            path=path, size=stat.st_size,
            modified=datetime.fromtimestamp(stat.st_mtime, tz=UTC)))
    return found


def checksum(path: Path, progress=None) -> str:
    """SHA-256 of a file, streamed so an 11 GB input costs no more memory than 8 MB."""
    digest = hashlib.sha256()
    done = 0
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK):
            digest.update(chunk)
            done += len(chunk)
            if progress:
                progress(done)
    return digest.hexdigest()


def client(store):
    """A boto3 S3 client pointed at the object store.

    boto3 rather than DuckDB because this uploads *opaque bytes*. DuckDB's S3 support reads
    and writes tabular formats; a FASTQ must arrive as the gzip it is, and an 11 GB object
    needs multipart upload with retries, which is exactly what boto3 already does well.
    """
    import boto3
    from botocore.config import Config

    scheme = "https" if store.use_ssl else "http"
    return boto3.client(
        "s3",
        endpoint_url=f"{scheme}://{store.endpoint}",
        aws_access_key_id=store.access_key,
        aws_secret_access_key=store.secret_key,
        region_name=store.region,
        config=Config(signature_version="s3v4",
                      s3={"addressing_style": "path"},
                      retries={"max_attempts": 5, "mode": "standard"}),
    )


def enable_versioning(store) -> str:
    """Turn on bucket versioning, so an overwrite can never destroy an earlier upload."""
    s3 = client(store)
    s3.put_bucket_versioning(Bucket=store.bucket,
                             VersioningConfiguration={"Status": "Enabled"})
    return s3.get_bucket_versioning(Bucket=store.bucket).get("Status", "Unknown")


def remote_state(store, key: str) -> dict | None:
    """What the store currently holds at ``key``, or ``None`` if nothing."""
    s3 = client(store)
    try:
        head = s3.head_object(Bucket=store.bucket, Key=key)
    except Exception:
        return None
    return {
        "size": int(head["ContentLength"]),
        "etag": head["ETag"].strip('"'),
        "version_id": head.get("VersionId", ""),
        "sha256": head.get("Metadata", {}).get("sha256", ""),
    }


def upload(store, item: SourceFile, progress=None) -> dict:
    """Upload one file unchanged, tagging it with the locally computed SHA-256.

    The checksum travels as object metadata so the store carries its own provenance: anyone
    with the bucket can check an object against the hash of the file that produced it,
    without access to this repository or its database.
    """
    from boto3.s3.transfer import TransferConfig

    s3 = client(store)
    config = TransferConfig(multipart_threshold=64 * 1024 * 1024,
                            multipart_chunksize=64 * 1024 * 1024,
                            max_concurrency=4, use_threads=True)
    s3.upload_file(
        str(item.path), store.bucket, item.key,
        ExtraArgs={"Metadata": {
            "sha256": item.sha256,
            "source-name": item.path.name,
            "source-size": str(item.size),
            "source-mtime": item.modified.isoformat(),
        }},
        Config=config, Callback=progress)
    state = remote_state(store, item.key) or {}
    return {"key": item.key, "version_id": state.get("version_id", ""),
            "etag": state.get("etag", ""), "size": state.get("size", 0)}


def ensure_ledger(connection, schema: str) -> None:
    """Create the append-only upload ledger if it is not already there."""
    from .postgres import ALIAS, safe_identifier

    safe = safe_identifier(schema)
    connection.execute(f"""
        CREATE TABLE IF NOT EXISTS {ALIAS}.{safe}.{LEDGER_TABLE} (
            uploaded_at   TIMESTAMP,
            file_name     VARCHAR,
            kind          VARCHAR,
            object_key    VARCHAR,
            version_id    VARCHAR,
            size_bytes    BIGINT,
            sha256        VARCHAR,
            etag          VARCHAR,
            source_mtime  TIMESTAMP,
            verified      BOOLEAN
        )""")


def record(connection, schema: str, item: SourceFile, result: dict,
           verified: bool) -> None:
    """Append one upload to the ledger. Never updates an existing row."""
    from .postgres import ALIAS, safe_identifier

    safe = safe_identifier(schema)
    connection.execute(
        f"INSERT INTO {ALIAS}.{safe}.{LEDGER_TABLE} VALUES "
        "(now(), ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [item.path.name, item.kind, result["key"], result.get("version_id", ""),
         item.size, item.sha256, result.get("etag", ""),
         item.modified.replace(tzinfo=None), verified])


#: Committed record of the publisher's own SHA-256 for each Git-LFS file.
PUBLISHED_HASHES = Path("ressources/data-profile/hf_lfs_sha256.tsv")


def published_hashes(path: Path | None = None) -> dict[str, str]:
    """The source dataset's own SHA-256 per file, for verifying a fresh download.

    Only Git-LFS objects carry one; small non-LFS files record a 40-character git blob
    SHA-1 instead, which is a different algorithm over different bytes and must not be
    compared against a file digest. Those are filtered out when the table is written.
    """
    table = path or PUBLISHED_HASHES
    if not table.exists():
        return {}
    out: dict[str, str] = {}
    for line in table.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 3 and len(parts[2]) == 64:
            out[parts[0]] = parts[2]
    return out


def fetch(repo: str, filename: str, into: Path, token: str | None = None) -> Path:
    """Download one file from a Hugging Face dataset repository.

    Run this **on the server**. The point is to avoid pushing 85 GB up a domestic
    connection when the machine that needs the data has its own, far faster link to the
    publisher — and the publisher's SHA-256 makes the result verifiable, so a fresh
    download is not a weaker provenance story than a re-upload. It is a stronger one: the
    bytes come from the source rather than from a copy.
    """
    from huggingface_hub import hf_hub_download

    into.mkdir(parents=True, exist_ok=True)
    return Path(hf_hub_download(
        repo_id=repo, filename=filename, repo_type="dataset",
        local_dir=str(into), token=token))


def hub_url(repo: str, filename: str) -> str:
    """The resolve URL for one file in a Hugging Face dataset repository."""
    from huggingface_hub import hf_hub_url

    return hf_hub_url(repo_id=repo, filename=filename, repo_type="dataset")


class _StreamAdapter:
    """A minimal read-only file object over a streaming HTTP response.

    boto3's ``upload_fileobj`` needs something with ``read(n)``; an HTTP response exposes
    chunks. Wrapping one in the other is what lets the bytes go from the publisher to the
    bucket **without ever landing on disk** — no staging directory, no second write, and
    no 85 GB of scratch space on the server.

    Deliberately not seekable. boto3 checks, and falls back to a streaming multipart
    upload rather than trying to rewind, which is exactly the behaviour wanted.
    """

    def __init__(self, response, callback=None, sink=None):
        self._iter = response.iter_content(chunk_size=CHUNK)
        self._buffer = b""
        self._callback = callback
        self._sink = sink        # optional open file: every byte read is also written

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            chunks = [self._buffer]
            self._buffer = b""
            chunks.extend(self._iter)
            data = b"".join(chunks)
        else:
            while len(self._buffer) < size:
                try:
                    self._buffer += next(self._iter)
                except StopIteration:
                    break
            data, self._buffer = self._buffer[:size], self._buffer[size:]
        if data:
            # Written before the callback so a crash mid-upload still leaves the bytes
            # that were already pulled off the wire.
            if self._sink is not None:
                self._sink.write(data)
            if self._callback:
                self._callback(len(data))
        return data


def stream_to_bucket(store, repo: str, filename: str, key: str,
                     token: str | None = None, progress=None,
                     tee: Path | None = None) -> dict:
    """Pipe a file from the publisher straight into the bucket, never touching disk.

    One pass over the network in each direction, concurrently. Returns the same shape as
    :func:`upload`, so the ledger records a streamed object exactly as it records an
    uploaded one.

    ``tee`` names a file to mirror the bytes into as they pass. It exists for one reason:
    the download is the expensive half — tens of gigabytes from the publisher — and the
    upload is the fragile half. Without a tee, an upload that fails at 90% throws away the
    whole download. With one, the bytes are on disk and the transfer can be finished with
    ``source-upload`` instead of being repeated.

    A failed upload deliberately leaves the tee file behind; the caller decides whether it
    is complete enough to use.
    """
    import requests
    from boto3.s3.transfer import TransferConfig

    headers = {"Authorization": f"Bearer {token}"} if token else {}
    response = requests.get(hub_url(repo, filename), headers=headers,
                            stream=True, timeout=60, allow_redirects=True)
    response.raise_for_status()
    declared = int(response.headers.get("Content-Length", 0))

    s3 = client(store)
    config = TransferConfig(multipart_threshold=64 * 1024 * 1024,
                            multipart_chunksize=64 * 1024 * 1024,
                            max_concurrency=4, use_threads=True)
    sink = None
    try:
        if tee is not None:
            tee.parent.mkdir(parents=True, exist_ok=True)
            sink = tee.open("wb")
        s3.upload_fileobj(
            _StreamAdapter(response, progress, sink), store.bucket, key,
            ExtraArgs={"Metadata": {"source-repo": repo, "source-name": filename}},
            Config=config)
    finally:
        if sink is not None:
            sink.close()

    state = remote_state(store, key) or {}
    return {"key": key, "version_id": state.get("version_id", ""),
            "etag": state.get("etag", ""), "size": state.get("size", 0),
            "declared_size": declared}
