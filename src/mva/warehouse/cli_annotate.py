"""The ``annotate-panel`` verb: fill the one gap the callset cannot fill itself.

Split from :mod:`mva.warehouse.cli` for the same reason ``vcf-*`` is: this verb reaches a
*third party* over the network, so it is the only one whose result depends on something
outside this repository and outside the delivery. ``--dry-run`` exists so the question
"what would we send?" can be answered without spending a request.
"""

from pathlib import Path

from . import annotate, annotate_coding, annotate_reads
from .settings import Postgres


def do_annotate_panel(args) -> int:
    """Annotate every panel allele through VEP REST and land the table."""
    settings = Postgres.from_env()
    if settings.missing:
        print("missing settings: " + ", ".join(settings.missing))
        return 1

    if args.dry_run:
        return _print_plan(settings, args.batch_size)

    result = annotate.run(settings, batch_size=args.batch_size, base_url=args.base_url)
    version = result["version"]
    print(
        f"source   {result['source']}"
        + (f" ({version['accession']})" if version.get("accession") else "")
    )
    print(f"wrote    {result['rows']:,} rows into {settings.schema}.{annotate.ANNOTATIONS_TABLE}")
    print(f"  with a consequence   {result['annotated']:,}")
    print(f"  with a gnomAD AF     {result['with_gnomad_af']:,}")
    print(f"  with a grpmax AF     {result['with_grpmax']:,}")
    print(f"  with a ClinVar call  {result['with_clin_sig']:,}")
    print(f"  with an rsID         {result['with_rsid']:,}")
    print(f"  distinct genes       {len(result['genes'])}  ({', '.join(result['genes'])})")
    print(f"\nlineage edge appended to {settings.schema}.data_lineage")
    return 0


def _print_plan(settings: Postgres, batch_size: int) -> int:
    """Show what would be sent, and to how many requests it would amount."""
    found = annotate.plan(settings, batch_size)
    spans = found["intervals"]
    print(f"panel    {len(spans)} intervals")
    width = max((len(span.gene) for span in spans), default=0)
    for span in spans:
        print(
            f"  {span.gene:<{width}}  {span.chrom:>2}:"
            f"{span.start:,}-{span.end:,}  ({span.end - span.start + 1:,} bp)"
        )
    print(f"\nalleles  {len(found['variants']):,} distinct, after splitting multi-allelic ALT")
    print(f"batches  {found['batches']} request(s) of up to {batch_size}")
    print("\ndry run — no request was sent.")
    return 0


def do_annotate_coding(args) -> int:
    """Annotate every coding allele genome-wide (layer 2) and land ``coding_annotations``."""
    settings = Postgres.from_env()
    if settings.missing:
        print("missing settings: " + ", ".join(settings.missing))
        return 1

    if args.dry_run:
        found = annotate_coding.plan(settings, args.batch_size, args.checkpoint)
        print(
            f"alleles      {found['alleles']:,} distinct in {settings.result_schema}."
            f"{annotate_coding.ALLELES_TABLE}"
        )
        print(f"checkpointed {found['checkpointed']:,} already answered under {args.checkpoint}")
        print(
            f"to ask       {found['todo']:,} in {found['batches']} request(s) of up to "
            f"{args.batch_size}"
        )
        print("\ndry run — no request was sent.")
        return 0

    result = annotate_coding.run(
        settings,
        batch_size=args.batch_size,
        base_url=args.base_url,
        checkpoint=args.checkpoint,
        progress=print,
        workers=args.workers,
    )
    print(f"source   {result['source']}")
    print(f"wrote    {result['rows']:,} rows into {settings.schema}.{annotate_coding.CODING_TABLE}")
    print(f"  asked this run       {result['asked']:,}")
    print(f"  with a consequence   {result['annotated']:,}")
    print(f"  with a gnomAD AF     {result['with_gnomad_af']:,}")
    print(f"  with a ClinVar call  {result['with_clin_sig']:,}")
    print(f"  distinct genes       {result['genes']:,}")
    print(f"\nlineage edge appended to {settings.schema}.data_lineage")
    return 0


def do_annotate_it2_reads(args) -> int:
    """Annotate the read-derived alleles the delivered callset never reported.

    Same loop as ``annotate-coding``; a different allele source and a different
    destination table, so "the vendor reported this" stays distinguishable from "only the
    read route saw this".
    """
    settings = Postgres.from_env()
    if settings.missing:
        print("missing settings: " + ", ".join(settings.missing))
        return 1

    if args.dry_run:
        found = annotate_coding.plan(
            settings, args.batch_size, args.checkpoint, source=annotate_reads.alleles
        )
        print(
            f"alleles      {found['alleles']:,} read-derived, unannotated, within "
            f"{annotate_reads.EXON_PAD} bp of a coding exon"
        )
        print(f"checkpointed {found['checkpointed']:,} already answered under {args.checkpoint}")
        print(
            f"to ask       {found['todo']:,} in {found['batches']} request(s) of up to "
            f"{args.batch_size}"
        )
        print("\ndry run — no request was sent.")
        return 0

    result = annotate_coding.run(
        settings,
        batch_size=args.batch_size,
        base_url=args.base_url,
        checkpoint=args.checkpoint,
        progress=print,
        workers=args.workers,
        source=annotate_reads.alleles,
        table=annotate_reads.READ_TABLE,
        transform=annotate_reads.TRANSFORM,
        source_note=(
            f"every distinct allele of {settings.result_schema}."
            f"{annotate_reads.READ_ALLELES_TABLE} that lies within "
            f"{annotate_reads.EXON_PAD} bp of a coding exon and has no row in "
            f"{settings.schema}.coding_annotations — the alleles the delivered callset "
            "never reported"
        ),
    )
    print(f"source   {result['source']}")
    print(f"wrote    {result['rows']:,} rows into {settings.schema}.{annotate_reads.READ_TABLE}")
    print(f"  asked this run       {result['asked']:,}")
    print(f"  with a consequence   {result['annotated']:,}")
    print(f"  with a gnomAD AF     {result['with_gnomad_af']:,}")
    print(f"  with a ClinVar call  {result['with_clin_sig']:,}")
    print(f"  distinct genes       {result['genes']:,}")
    print(f"\nlineage edge appended to {settings.schema}.data_lineage")
    return 0


def _shared_flags(parser) -> None:
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the variant count and batch plan, send nothing",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=200,
        help="alleles per request (the endpoint's ceiling is 200)",
    )
    parser.add_argument(
        "--base-url",
        default=annotate.DEFAULT_BASE_URL,
        help="Ensembl REST server (GRCh37 lives on a different host)",
    )


def register(subparsers) -> None:
    """Attach the three ``annotate-*`` verbs to the top-level parser."""
    coding = subparsers.add_parser(
        "annotate-coding",
        help="annotate every coding allele genome-wide (results.coding_alleles) through VEP REST",
    )
    _shared_flags(coding)
    coding.add_argument(
        "--checkpoint",
        type=Path,
        default=annotate_coding.DEFAULT_CHECKPOINT,
        help="gitignored directory holding answered batches; a re-run resumes from it",
    )
    coding.add_argument(
        "--workers",
        type=int,
        default=1,
        help="requests in flight at once (each is ~30 s of server time; 4 is conservative)",
    )
    coding.set_defaults(handler=do_annotate_coding)

    reads = subparsers.add_parser(
        "annotate-it2-reads",
        help="annotate the read-derived alleles the delivered callset never reported",
    )
    _shared_flags(reads)
    reads.add_argument(
        "--checkpoint",
        type=Path,
        default=annotate_reads.CHECKPOINT,
        help="gitignored directory holding answered batches; a re-run resumes from it",
    )
    reads.add_argument(
        "--workers",
        type=int,
        default=1,
        help="requests in flight at once (each is ~30 s of server time; 4 is conservative)",
    )
    reads.set_defaults(handler=do_annotate_it2_reads)

    parser = subparsers.add_parser(
        "annotate-panel", help="annotate every panel allele through Ensembl VEP REST"
    )
    _shared_flags(parser)
    parser.set_defaults(handler=do_annotate_panel)
