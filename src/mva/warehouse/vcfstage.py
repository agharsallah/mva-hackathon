"""Stage a VCF into a provably lossless raw layer.

The warehouse keeps variants in **two layers**, and the split is what makes "we kept 100%
of the data" a checkable claim rather than a hope.

``variants_raw``
    One row per VCF data line, ten columns, **every one of them text**, nothing parsed,
    nothing normalised, nothing dropped — not even the records a caller flagged. Plus a
    ``line_no`` recording the record's position in the file. Because nothing is
    interpreted, the original file can be reconstructed from this table and compared
    against the source digest. That reconstruction is the proof.

``variants`` (built later, from the raw layer)
    Typed, one row per ALT allele, INFO exploded into columns — everything that makes the
    data pleasant to query, and everything that could conceivably lose information.

Keeping them apart means an analytical mistake in the second layer is always recoverable
from the first, and the expensive read of an 85 GB-scale input happens once.

Two details of the raw layer are deliberate and easy to get wrong:

* **Text, not types.** Typing at this stage is the single largest source of silent loss —
  a ``.`` becoming NULL, an empty cell vanishing, a large integer saturating. Types are a
  second-layer concern where they can be checked against the raw column.
* **Line numbers.** Without them, a reconstruction can only prove the *set* of records
  survived, not the file. With them, the original is byte-reproducible.
"""

import gzip
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

#: The eight fixed VCF columns, plus FORMAT and one sample. Lower-cased and with `#CHROM`
#: reduced to `chrom`, because `#CHROM` is not a usable SQL identifier.
#:
#: ``line_no`` leads the tuple but is *not* one of them: it is our own bookkeeping,
#: recording where the record sat in the file, and it is the one column that is typed
#: (BIGINT). Everything that actually came out of the VCF stays text — see
#: :data:`FILE_COLUMNS`.
RAW_COLUMNS = ("line_no", "chrom", "pos", "id", "ref", "alt",
               "qual", "filter", "info", "format", "sample_call")

#: The subset of :data:`RAW_COLUMNS` that came from the file. All VARCHAR, always.
FILE_COLUMNS = RAW_COLUMNS[1:]

#: How many VCF fields a single-sample callset carries.
EXPECTED_FIELDS = 10


@dataclass(frozen=True)
class VcfShape:
    """What the header of a VCF declares, before any record is read."""

    header_lines: int
    columns: tuple[str, ...]
    sample: str | None

    @property
    def is_single_sample(self) -> bool:
        return len(self.columns) == EXPECTED_FIELDS


def open_text(path: str | Path):
    """Open a VCF whether or not it is compressed. BGZF is gzip-compatible."""
    path = Path(path)
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", errors="strict")
    return path.open("rt", encoding="utf-8", errors="strict")


def read_shape(path: str | Path) -> VcfShape:
    """Read only the header, and report what the file says it contains."""
    header_lines = 0
    with open_text(path) as handle:
        for line in handle:
            if line.startswith("##"):
                header_lines += 1
                continue
            if line.startswith("#CHROM"):
                columns = tuple(line.rstrip("\n").split("\t"))
                sample = columns[9] if len(columns) > 9 else None
                return VcfShape(header_lines, columns, sample)
            break
    return VcfShape(header_lines, (), None)


def iter_raw(path: str | Path, limit: int | None = None) -> Iterator[list[str]]:
    """Yield each data line as ``[line_no, *fields]``, entirely uninterpreted.

    A record whose field count differs from the header's is *not* silently dropped or
    padded — it raises. A malformed line in a callset is a fact about the data that must
    surface during ingest, not a row that quietly goes missing.
    """
    line_no = 0
    with open_text(path) as handle:
        for line in handle:
            if line.startswith("#"):
                continue
            line_no += 1
            fields = line.rstrip("\n").split("\t")
            if len(fields) != EXPECTED_FIELDS:
                raise ValueError(
                    f"{path}: record {line_no} has {len(fields)} fields, "
                    f"expected {EXPECTED_FIELDS}")
            yield [str(line_no), *fields]
            if limit is not None and line_no >= limit:
                return


def source_digest(path: str | Path, limit: int | None = None) -> tuple[str, int]:
    """SHA-256 over the *data* lines of a VCF, plus how many there were.

    The header is excluded so the digest describes the records alone, which is what the
    raw table stores. Computed by reading the file directly — never through DuckDB — so
    the verification does not depend on the thing it is verifying.
    """
    digest = hashlib.sha256()
    count = 0
    with open_text(path) as handle:
        for line in handle:
            if line.startswith("#"):
                continue
            count += 1
            digest.update(line.rstrip("\n").encode("utf-8"))
            digest.update(b"\n")
            if limit is not None and count >= limit:
                break
    return digest.hexdigest(), count


#: DuckDB column spec for the raw layer: every VCF field as text, nothing inferred.
RAW_SPEC = ("{" + ", ".join(f"'{name}':'VARCHAR'" for name in FILE_COLUMNS) + "}")


def read_csv_sql(path: str | Path, shape: VcfShape) -> str:
    """The ``read_csv`` call that reads a VCF's records losslessly.

    Every argument here is defending against a specific way the value could change:

    * ``all_varchar`` / explicit ``columns`` — no type inference, so nothing is coerced
      and no sentinel becomes a NULL.
    * ``quote=''`` and ``escape=''`` — a VCF is tab-separated but *not* CSV-quoted. Left
      on, a field containing a double quote would be silently unwrapped.
    * ``skip`` past the whole header — the sniffer cannot make sense of 2,600 ``##``
      lines and gives up if asked to.
    * ``max_line_size`` generous — an INFO field on a multi-allelic site gets very long,
      and the default cap would reject the record rather than truncate it, but rejecting
      is still a failure we do not want.
    """
    return (f"read_csv('{path}', delim=chr(9), header=false, all_varchar=true, "
            f"quote='', escape='', skip={shape.header_lines + 1}, "
            f"columns={RAW_SPEC}, max_line_size=100000000)")


def line_expression() -> str:
    """SQL rebuilding the original tab-separated record from the stored columns."""
    return "concat_ws(chr(9), " + ", ".join(FILE_COLUMNS) + ")"


def stage_raw(path: str | Path, out: Path, limit: int | None = None) -> tuple[Path, int]:
    """Write a VCF's records to Parquet as the all-text raw layer.

    Uses DuckDB's own CSV reader rather than looping in Python. That is not only ~200x
    faster on this callset; it also means the ingest path and the verification path
    exercise the same reader, so a verification pass actually tells you something about
    the ingest.

    ``line_no`` is assigned from the scan's row order, which is the file's order because
    ``preserve_insertion_order`` is on. That is checked rather than assumed — see
    :func:`verify_roundtrip`, which compares reconstructed bytes in that order.
    """
    import duckdb

    out.parent.mkdir(parents=True, exist_ok=True)
    shape = read_shape(path)
    if not shape.is_single_sample:
        raise ValueError(
            f"{path}: expected {EXPECTED_FIELDS} columns, header declares "
            f"{len(shape.columns)} — this stager handles single-sample callsets")

    connection = duckdb.connect()
    source = read_csv_sql(path, shape)
    bounded = f"SELECT * FROM {source}" + (f" LIMIT {limit}" if limit else "")
    connection.execute(f"""
        COPY (
            SELECT row_number() OVER () AS line_no, *
            FROM ({bounded})
        ) TO '{out}' (FORMAT parquet, COMPRESSION zstd)
    """)
    written = connection.execute(
        f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]
    connection.close()
    return out, written


def verify_roundtrip(path: str | Path, limit: int | None = None,
                     parquet: Path | None = None) -> dict[str, object]:
    """Rebuild the VCF's data lines through DuckDB and compare digests with the source.

    This is the strongest retention evidence available: it does not compare a summary of
    the data, it checks that the original bytes can be reproduced. Matching digests mean
    every field of every record survived, in the right order.

    The source digest is computed by reading the file directly in Python — never through
    DuckDB — so the check does not depend on the component it is testing. Pass ``parquet``
    to verify a staged file instead of the live read.
    """
    import duckdb

    expected_digest, expected_rows = source_digest(path, limit)
    connection = duckdb.connect()
    if parquet is not None:
        source = f"read_parquet('{parquet}')"
        order = " ORDER BY line_no"
    else:
        source = read_csv_sql(path, read_shape(path))
        order = ""
    bound = f" LIMIT {limit}" if limit else ""

    rebuilt = hashlib.sha256()
    seen = 0
    query = connection.execute(
        f"SELECT {line_expression()} FROM {source}{order}{bound}")
    while True:
        chunk = query.fetchmany(50_000)
        if not chunk:
            break
        for (line,) in chunk:
            rebuilt.update(line.encode("utf-8"))
            rebuilt.update(b"\n")
            seen += 1
    connection.close()

    actual_digest = rebuilt.hexdigest()
    return {
        "source_sha256": expected_digest,
        "rebuilt_sha256": actual_digest,
        "source_rows": expected_rows,
        "rebuilt_rows": seen,
        "identical": expected_digest == actual_digest and expected_rows == seen,
    }
