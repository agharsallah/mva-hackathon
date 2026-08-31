"""The ``annotate-panel`` verb: fill the one gap the callset cannot fill itself.

Split from :mod:`mva.warehouse.cli` for the same reason ``vcf-*`` is: this verb reaches a
*third party* over the network, so it is the only one whose result depends on something
outside this repository and outside the delivery. ``--dry-run`` exists so the question
"what would we send?" can be answered without spending a request.
"""

from . import annotate
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
    print(f"source   {result['source']}"
          + (f" ({version['accession']})" if version.get("accession") else ""))
    print(f"wrote    {result['rows']:,} rows into "
          f"{settings.schema}.{annotate.ANNOTATIONS_TABLE}")
    print(f"  with a consequence   {result['annotated']:,}")
    print(f"  with a gnomAD AF     {result['with_gnomad_af']:,}")
    print(f"  with a grpmax AF     {result['with_grpmax']:,}")
    print(f"  with a ClinVar call  {result['with_clin_sig']:,}")
    print(f"  with an rsID         {result['with_rsid']:,}")
    print(f"  distinct genes       {len(result['genes'])}"
          f"  ({', '.join(result['genes'])})")
    print(f"\nlineage edge appended to {settings.schema}.data_lineage")
    return 0


def _print_plan(settings: Postgres, batch_size: int) -> int:
    """Show what would be sent, and to how many requests it would amount."""
    found = annotate.plan(settings, batch_size)
    spans = found["intervals"]
    print(f"panel    {len(spans)} intervals")
    width = max((len(span.gene) for span in spans), default=0)
    for span in spans:
        print(f"  {span.gene:<{width}}  {span.chrom:>2}:"
              f"{span.start:,}-{span.end:,}  ({span.end - span.start + 1:,} bp)")
    print(f"\nalleles  {len(found['variants']):,} distinct, after splitting "
          f"multi-allelic ALT")
    print(f"batches  {found['batches']} request(s) of up to {batch_size}")
    print("\ndry run — no request was sent.")
    return 0


def register(subparsers) -> None:
    """Attach ``annotate-panel`` to the top-level parser."""
    parser = subparsers.add_parser(
        "annotate-panel",
        help="annotate every panel allele through Ensembl VEP REST")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the variant count and batch plan, send nothing")
    parser.add_argument("--batch-size", type=int, default=200,
                        help="alleles per request (the endpoint's ceiling is 200)")
    parser.add_argument("--base-url", default=annotate.DEFAULT_BASE_URL,
                        help="Ensembl REST server (GRCh37 lives on a different host)")
    parser.set_defaults(handler=do_annotate_panel)
