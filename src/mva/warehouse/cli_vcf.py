"""The ``vcf-*`` verbs: inspect a callset, and prove reading it loses nothing.

Split out of :mod:`mva.warehouse.cli` because these answer a different question from the
rest of the tool. The other verbs move data that has already been trusted; these decide
whether it *can* be trusted, and are meant to be run before any bulk ingest rather than
as part of one.

``vcf-verify`` is the gate. It reconstructs every record from what the reader produced and
compares SHA-256 against the source file, with the source digest computed in plain Python
so the check never depends on the component it is testing.
"""

from pathlib import Path

from .vcfstage import EXPECTED_FIELDS, read_shape, stage_raw, verify_roundtrip


def do_shape(args) -> int:
    """Report what a VCF's header declares, without reading a record."""
    shape = read_shape(args.vcf)
    print(f"header lines : {shape.header_lines:,}")
    print(f"columns      : {len(shape.columns)}")
    print(f"sample       : {shape.sample}")
    if not shape.is_single_sample:
        print(
            f"\nWARNING: expected {EXPECTED_FIELDS} columns for a single-sample "
            f"callset; `vcf-stage` will refuse this file."
        )
        return 1
    return 0


def do_verify(args) -> int:
    """Prove the reader loses nothing, by reproducing the source bytes."""
    result = verify_roundtrip(args.vcf, limit=args.limit, parquet=args.parquet)
    print(f"source rows    : {result['source_rows']:,}")
    print(f"rebuilt rows   : {result['rebuilt_rows']:,}")
    print(f"source sha256  : {result['source_sha256']}")
    print(f"rebuilt sha256 : {result['rebuilt_sha256']}")
    if result["identical"]:
        print("\nIDENTICAL — every field of every record survived, in order.")
        return 0
    print("\nMISMATCH — do not ingest. The reader is losing or altering data.")
    return 1


def do_stage(args) -> int:
    """Write the lossless raw layer, then verify it before reporting success."""
    path, written = stage_raw(args.vcf, args.output, limit=args.limit)
    size = path.stat().st_size
    print(f"staged {written:,} records -> {path} ({size / 1e6:.0f} MB)")
    if args.no_verify:
        print("verification skipped (--no-verify)")
        return 0
    result = verify_roundtrip(args.vcf, limit=args.limit, parquet=path)
    print("round-trip:", "IDENTICAL" if result["identical"] else "MISMATCH")
    return 0 if result["identical"] else 1


def register(subparsers) -> None:
    """Attach the ``vcf-*`` verbs to the top-level parser."""
    shape = subparsers.add_parser("vcf-shape", help="report what a VCF header declares")
    shape.add_argument("vcf", type=Path)
    shape.set_defaults(handler=do_shape)

    verify = subparsers.add_parser(
        "vcf-verify", help="prove the reader loses nothing, by SHA-256 round trip"
    )
    verify.add_argument("vcf", type=Path)
    verify.add_argument("--limit", type=int, help="only the first N records")
    verify.add_argument(
        "--parquet", type=Path, help="verify a staged Parquet instead of the live read"
    )
    verify.set_defaults(handler=do_verify)

    stage = subparsers.add_parser(
        "vcf-stage", help="write the lossless all-text raw layer to Parquet"
    )
    stage.add_argument("vcf", type=Path)
    stage.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="destination Parquet; keep it OUTSIDE the repository",
    )
    stage.add_argument("--limit", type=int, help="only the first N records")
    stage.add_argument(
        "--no-verify", action="store_true", help="skip the round-trip check (not recommended)"
    )
    stage.set_defaults(handler=do_stage)

    ingest = subparsers.add_parser(
        "vcf-ingest", help="RUN ON THE SERVER: load the callset into PostgreSQL as the raw layer"
    )
    ingest.add_argument("--source", default=DEFAULT_VCF_OBJECT, help="s3:// object or a local path")
    ingest.add_argument("--table", default=RAW_TABLE, help="target table name")
    ingest.add_argument("--limit", type=int, help="only the first N records")
    ingest.add_argument("--skip", type=int, help="header lines + 1; required for an s3:// source")
    ingest.set_defaults(handler=do_ingest)


#: Where the delivered callset lives in the object store.
DEFAULT_VCF_OBJECT = "s3://mva/source/WGS_EX2312012_HGWCNDSX7.vcf.gz"

#: The lossless landing table for variant records.
RAW_TABLE = "variants_raw"


def do_ingest(args) -> int:
    """Load the callset into PostgreSQL as the lossless raw layer, and record lineage.

    Every field lands as text and nothing is filtered — non-PASS records included, because
    a suppressed allele is exactly what this case may turn on. Typing and multi-allelic
    splitting belong in tables derived from this one, which can always be rebuilt.

    Run this **on the server**. A gzip stream cannot be range-requested, so reading the
    object means transferring all of it; doing that from a laptop moves the bytes twice
    over the slow link for no benefit.
    """
    from .lineage import LINEAGE_TABLE, ensure_tables, record
    from .objects import connect as connect_objects
    from .postgres import ALIAS, safe_identifier
    from .settings import Postgres, object_store
    from .vcfstage import FILE_COLUMNS, RAW_SPEC, read_shape

    settings = Postgres.from_env()
    schema = safe_identifier(settings.schema)
    source_ref = str(args.source)
    remote = source_ref.startswith("s3://")

    if remote:
        connection = connect_objects(object_store())
        skip = args.skip
        if skip is None:
            print(
                "reading a remote gzip requires --skip (header lines + 1); "
                "for this delivery that is 2618"
            )
            return 1
    else:
        import duckdb

        connection = duckdb.connect()
        shape = read_shape(args.source)
        skip = args.skip if args.skip is not None else shape.header_lines + 1
        print(f"header lines {shape.header_lines}, sample {shape.sample}")

    reader = (
        f"read_csv('{source_ref}', delim=chr(9), header=false, all_varchar=true, "
        f"quote='', escape='', skip={skip}, columns={RAW_SPEC}, "
        f"max_line_size=100000000)"
    )
    bounded = f"SELECT * FROM {reader}" + (f" LIMIT {args.limit}" if args.limit else "")

    print(f"source  {source_ref}")
    print(f"target  {settings.host}/{settings.database} {settings.schema}.{args.table}")

    connection.execute("INSTALL postgres; LOAD postgres;")
    connection.execute(f"ATTACH '{settings.dsn()}' AS {ALIAS} (TYPE postgres)")
    ensure_tables(connection, settings.schema)

    connection.execute(
        f"CREATE OR REPLACE TABLE {ALIAS}.{schema}.{args.table} AS "
        f"SELECT row_number() OVER () AS line_no, * FROM ({bounded})"
    )
    rows = connection.execute(f"SELECT count(*) FROM {ALIAS}.{schema}.{args.table}").fetchone()[0]
    print(f"loaded  {rows:,} records")

    # Lineage is looked up rather than asserted: the object's hash and version come from
    # the inventory, so the edge names the exact bytes this table was built from.
    provenance = connection.execute(
        f"SELECT sha256, version_id FROM {ALIAS}.{schema}.source_objects WHERE object_key = ?",
        [source_ref.split("/", 3)[-1] if remote else ""],
    ).fetchone() or ("", "")
    record(
        connection,
        settings.schema,
        target_schema=settings.schema,
        target_table=args.table,
        target_rows=rows,
        source_kind="object" if remote else "file",
        source_ref=source_ref,
        source_version=provenance[1],
        source_sha256=provenance[0],
        transform="read_csv all_varchar, no filtering, no typing",
        notes=f"columns: line_no + {', '.join(FILE_COLUMNS)}",
    )
    connection.close()
    print(f"lineage recorded in {settings.schema}.{LINEAGE_TABLE}")
    return 0
