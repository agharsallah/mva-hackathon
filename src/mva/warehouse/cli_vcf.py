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
        print(f"\nWARNING: expected {EXPECTED_FIELDS} columns for a single-sample "
              f"callset; `vcf-stage` will refuse this file.")
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
        "vcf-verify", help="prove the reader loses nothing, by SHA-256 round trip")
    verify.add_argument("vcf", type=Path)
    verify.add_argument("--limit", type=int, help="only the first N records")
    verify.add_argument("--parquet", type=Path,
                        help="verify a staged Parquet instead of the live read")
    verify.set_defaults(handler=do_verify)

    stage = subparsers.add_parser(
        "vcf-stage", help="write the lossless all-text raw layer to Parquet")
    stage.add_argument("vcf", type=Path)
    stage.add_argument("-o", "--output", type=Path, required=True,
                       help="destination Parquet; keep it OUTSIDE the repository")
    stage.add_argument("--limit", type=int, help="only the first N records")
    stage.add_argument("--no-verify", action="store_true",
                       help="skip the round-trip check (not recommended)")
    stage.set_defaults(handler=do_stage)
