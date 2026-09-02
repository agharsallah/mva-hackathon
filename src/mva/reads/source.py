"""Where the FASTQ bytes come from — a local directory, or the object store itself.

Two things live here.

**A source is a name plus a way to open a byte stream.** Some engines want a real path
(and are faster with one); all of them can take a stream. Keeping that behind one small
type means "convert the delivery" reads the same whether the delivery is on the disk next
to you or in a bucket on the same box.

**The MinIO trap.** MinIO's own storage directory is *not* a folder of files. Every object
is a **directory** holding `xl.meta` plus one `part.N` per multipart chunk, so
``~/mva-objects/<bucket>/source/reads.fastq.gz`` looks like the delivery and is not
readable as one. Pointing a tool at it produces a baffling error deep inside a parser, so
:func:`resolve` detects the layout and says what to use instead. The bytes there are
reachable the supported way — over the S3 API, which is what ``s3://`` sources do.
"""

import io
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import IO

from . import schema

#: A ``s3://bucket/prefix`` spec, or the bare word ``s3`` meaning the configured bucket.
S3_SPEC = re.compile(r"^s3://(?P<bucket>[^/]+)/?(?P<prefix>.*)$")

#: MinIO writes this beside the parts of every object it stores.
MINIO_MARKER = "xl.meta"

#: Read size when streaming an object out of the store.
CHUNK = 8 * 1024 * 1024

#: How long a presigned read link stays valid. Long enough to convert 8 files; short
#: enough that a leaked link is not a standing grant.
PRESIGN_SECONDS = 12 * 60 * 60


class NotADelivery(RuntimeError):
    """The place given does not hold readable FASTQ files, with a reason attached."""


@dataclass(frozen=True)
class Source:
    """One FASTQ to convert: its filename, and how to get its bytes.

    Three ways in, in descending order of what an engine can do with them:

    * ``path`` — a real local file. Fastest, and every engine takes it.
    * ``url`` — a presigned HTTPS link to the object. Readers built on fsspec (oxbow)
      open it directly and get *random access*, which matters because some readers must
      seek. Treat it as a secret: see :func:`presigned_url`.
    * ``open_stream`` — always available, but yields a **non-seekable** stream, so only
      the shell pipeline can consume it.
    """

    name: str
    open_stream: Callable[[], IO[bytes]]
    path: Path | None = None
    url: str = ""
    size: int = 0

    @property
    def lane_and_read(self) -> tuple[int, int]:
        return schema.lane_and_read(self.name)


def resolve(spec: str, store=None) -> list[Source]:
    """Every FASTQ at ``spec``, which is a local directory or an ``s3://`` prefix."""
    match = S3_SPEC.match(spec.strip())
    if spec.strip() == "s3" or match:
        return _from_object_store(match, store)
    return _from_directory(Path(spec).expanduser())


def _from_directory(directory: Path) -> list[Source]:
    """FASTQ files in a local directory — refusing MinIO's storage layout by name."""
    if not directory.is_dir():
        raise NotADelivery(f"{directory} is not a directory")

    candidates = sorted(path for path in directory.iterdir() if schema.FASTQ_NAME.search(path.name))
    if candidates and all(path.is_dir() for path in candidates):
        raise NotADelivery(_minio_diagnosis(directory, candidates[0]))

    files = [path for path in candidates if path.is_file()]
    if not files:
        raise NotADelivery(
            f"no readable FASTQ files in {directory}\n"
            f"  looked for names ending in _L00<n>_R<1|2>_001.fastq.gz"
        )
    return [
        Source(name=path.name, path=path, size=path.stat().st_size, open_stream=_local_opener(path))
        for path in files
    ]


def _minio_diagnosis(directory: Path, example: Path) -> str:
    """Say plainly that this is a store's internals, and what to use instead."""
    marker = "" if (example / MINIO_MARKER).exists() else " (no xl.meta, but same shape)"
    return (
        f"{directory} looks like MinIO's internal storage, not a delivery{marker}.\n"
        f"  Every object there is a *directory* of parts — '{example.name}' is one — so "
        f"nothing can read it as a FASTQ.\n"
        f"  Use the delivery as it was downloaded, or read the bucket over the S3 API:\n"
        f"    mva-reads convert --source s3\n"
        f"  Never read or write MinIO's data directory directly; it is the store's own "
        f"bookkeeping."
    )


def _local_opener(path: Path) -> Callable[[], IO[bytes]]:
    return lambda: path.open("rb")


def _from_object_store(match, store) -> list[Source]:
    """FASTQ objects under a bucket prefix, streamed over the S3 API."""
    from ..warehouse.settings import object_store
    from ..warehouse.source import PREFIX, client

    store = store or object_store()
    bucket = match.group("bucket") if match else store.bucket
    prefix = (match.group("prefix") if match else "") or f"{PREFIX}/"

    s3 = client(store)
    sources: list[Source] = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for item in page.get("Contents", []):
            key = item["Key"]
            name = key.rsplit("/", 1)[-1]
            if schema.FASTQ_NAME.search(name):
                sources.append(
                    Source(
                        name=name,
                        size=item["Size"],
                        url=presigned_url(s3, bucket, key),
                        open_stream=_s3_opener(store, bucket, key),
                    )
                )
    if not sources:
        raise NotADelivery(f"no FASTQ objects under s3://{bucket}/{prefix}")
    return sorted(sources, key=lambda source: source.name)


def presigned_url(s3, bucket: str, key: str, expires: int = PRESIGN_SECONDS) -> str:
    """A time-limited HTTPS URL that reads one object, range requests included.

    This is how a reader that must **seek** gets at an object in the store without a
    second S3 client library. `s3fs`, the usual answer, drags in `aiobotocore`, which
    pins `botocore` to a narrow range and collides with the `boto3` the rest of the
    warehouse uses; a presigned URL needs nothing but HTTP. The signature covers the
    bucket, the key and the expiry, so the link grants read access to exactly one object
    for a bounded time — but it *is* a bearer credential until it expires: never log it,
    never commit it, never paste it anywhere shared.
    """
    return s3.generate_presigned_url(
        "get_object", ExpiresIn=expires, Params={"Bucket": bucket, "Key": key}
    )


def _s3_opener(store, bucket: str, key: str) -> Callable[[], IO[bytes]]:
    """A fresh readable stream of one object, each time it is called."""
    from ..warehouse.source import client

    def opener() -> IO[bytes]:
        body = client(store).get_object(Bucket=bucket, Key=key)["Body"]
        return io.BufferedReader(_StreamingBodyIO(body), buffer_size=CHUNK)

    return opener


class _StreamingBodyIO(io.RawIOBase):
    """Adapt a boto3 ``StreamingBody`` to the file protocol readers expect.

    ``StreamingBody`` offers ``read``; PyArrow and every other consumer here want a real
    binary file object with ``readinto``. Wrapping rather than buffering the whole object
    is the point: an 11 GB read file must never be materialised to convert it.
    """

    def __init__(self, body):
        self._body = body

    def readable(self) -> bool:
        return True

    def readinto(self, buffer) -> int:
        chunk = self._body.read(len(buffer))
        if not chunk:
            return 0
        buffer[: len(chunk)] = chunk
        return len(chunk)

    def close(self) -> None:
        try:
            self._body.close()
        finally:
            super().close()
