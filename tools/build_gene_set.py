"""Resolve a curated list of gene symbols against Ensembl into a committed TSV.

    uv run python tools/build_gene_set.py --spec ressources/reference/structure_genes.spec.tsv
    uv run python tools/build_gene_set.py --group panel=BUB1B,TP53 --note BUB1B="MVA1"
    uv run python tools/build_gene_set.py --spec … --alias CCDC84=CENATAC --dry-run

Case-agnostic on purpose: nothing about MVA is hardcoded, and a *group* is a free-form id
the spec invents, carrying its own display label and sort order. The work lives in two
importable modules so a foreign spec can be built in a test instead of only on a command
line — :mod:`mva.viz.genesetbuild` (the spec format, Ensembl, the alias check, the TSV) and
:mod:`mva.viz.genesetpanel` (the two steps that assume an annotated panel BED exists).
This file is the command line and nothing else.

``--reuse`` rewrites only the curation columns — group id, label, rank, note — carrying
every Ensembl-derived column over from the committed TSV and calling nothing. Renaming a
group is curation, so it should not spend 23 upstream lookups nor silently re-measure 23
genes against whatever release answers today. A *new* symbol still needs a live run.

**Run order: this tool first, then ``tools/build_protein_fixture.py``**, which records this
TSV's sha256 as an input and goes stale otherwise — rerun it with ``--index-only`` when the
groups changed and ``--manifest-only`` always. See ``docs/step-0/methodology/063``.

Reads one public keyless API. Touches no warehouse table and no patient record, so it runs
on a bare checkout and its output is publishable.
"""

import argparse
import json
import sys
from pathlib import Path

import httpx

from mva.viz import ensembl, geneset, genesetbuild, genesetmanifest, genesetpanel, panelbed

DEFAULT_OUT = Path("ressources/reference/structure_genes.tsv")
DEFAULT_SPEC = Path("ressources/reference/structure_genes.spec.tsv")
DEFAULT_PROVENANCE = Path("ressources/reference/structure_genes.provenance.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, help=f"TSV of symbol/group/… (e.g. {DEFAULT_SPEC})")
    parser.add_argument("--group", action="append", default=[], help="name=SYM,SYM")
    parser.add_argument("--group-label", action="append", default=[], help="name=display text")
    parser.add_argument("--note", action="append", default=[], help="SYM=one-line note")
    parser.add_argument("--alias", action="append", default=[], help="ALIAS=PRIMARY to verify")
    parser.add_argument(
        "--bed",
        type=Path,
        default=panelbed.DEFAULT_BED,
        help=f"panel BED whose gene ids --panel-group is asserted against "
        f"(default: {panelbed.DEFAULT_BED}; a path that does not exist asserts nothing)",
    )
    parser.add_argument(
        "--panel-group",
        default="panel",
        help="group whose ids must match the BED (default: panel; pass '' to skip)",
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="where to write the TSV")
    parser.add_argument(
        "--provenance",
        type=Path,
        default=DEFAULT_PROVENANCE,
        help=f"where to write the build manifest (default: {DEFAULT_PROVENANCE})",
    )
    parser.add_argument("--base-url", default=genesetbuild.ENSEMBL_BASE, help="Ensembl REST base")
    parser.add_argument(
        "--reuse",
        type=Path,
        nargs="?",
        const=DEFAULT_OUT,
        help="rewrite only the curation columns (group id, label, rank, note) from the spec, "
        f"carrying every Ensembl-derived column over from this TSV (default: {DEFAULT_OUT}). "
        "Calls nothing. Use it to rename or re-rank a group; a new symbol needs a live run.",
    )
    parser.add_argument("--dry-run", action="store_true", help="resolve and print, write nothing")
    return parser.parse_args()


def read_wanted(args: argparse.Namespace) -> list:
    """The spec (or the flags), with the BED's notes borrowed and the groups reported."""
    wanted = (
        genesetbuild.read_spec(args.spec)
        if args.spec
        else genesetbuild.read_flags(args.group, args.note, args.group_label)
    )
    if not wanted:
        raise SystemExit("nothing to resolve: pass --spec or --group")
    wanted = genesetpanel.borrow_bed_notes(wanted, args.bed)
    groups = {row.group: (row.group_label, row.group_order) for row in wanted}
    print(f"{len(wanted)} symbols in {len(groups)} groups")
    for group, (label, order) in sorted(groups.items(), key=lambda pair: pair[1][1] or 0):
        print(f"  group {order} {group!r} — {label}")
    return wanted


def relabel(args: argparse.Namespace) -> tuple[list, str | None]:
    """``--reuse``: the curation columns from the spec, every measured column carried over.

    Returns the rows and the release the *previous* manifest recorded, which is what the
    new manifest names — carried, not observed. See :func:`mva.viz.genesetbuild.reuse`.
    """
    existing = geneset.genes(args.reuse)
    if not existing:
        raise SystemExit(f"--reuse {args.reuse}: no rows to carry over")
    found = genesetbuild.reuse(read_wanted(args), existing)
    release = geneset.provenance(args.provenance).get("ensembl_release")
    print(f"--reuse {args.reuse}: {len(found)} rows carried over, release {release or 'unknown'}")
    return found, release


def build(args: argparse.Namespace, client: httpx.Client) -> tuple[list, str | None, list[str]]:
    """Resolve every wanted symbol and verify every alias. Returns rows, release, failures.

    Split out of :func:`main` so a test can drive the whole build over a mocked transport
    without an ``argparse`` round trip — see ``tests/test_viz_genesetbuild.py``.
    """
    wanted = read_wanted(args)
    print(f"resolving against {args.base_url}")
    # Asked first and printed, because it is the fact that dates every other line below:
    # the same symbol resolves to different biotypes across releases.
    release = ensembl.release(args.base_url, client=client)
    print(f"ensembl release {release or 'unknown'} (GET {args.base_url}/info/data)")
    found = [genesetbuild.resolve(client, args.base_url, entry) for entry in wanted]
    refused = [
        f"{alias} is not the same gene as {primary}"
        for alias, primary in (pair.split("=", 1) for pair in args.alias)
        if not genesetbuild.check_alias(client, args.base_url, alias, primary)
    ]
    return found, release, refused


def write(args: argparse.Namespace, found: list, release: str | None, fetched: bool) -> None:
    """The TSV, then the manifest — in that order, so the digest describes what is on disk."""
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(genesetbuild.render(found), encoding="utf-8")
    print(f"{args.out} — {args.out.stat().st_size:,} bytes, {len(found)} rows")
    built = genesetmanifest.manifest(
        genesetbuild.manifest_rows(found),
        args.out,
        args.spec,
        args.bed,
        args.base_url,
        release,
        fetched=fetched,
    )
    args.provenance.write_text(json.dumps(built, indent=2) + "\n", encoding="utf-8")
    print(
        f"{args.provenance} — sha256 {built['outputs'][0]['sha256']}, "
        f"{len(built['literature'])} genes with a cited OMIM/PMID"
    )


def main() -> None:
    args = parse_args()
    if args.reuse:
        found, release = relabel(args)
        refused: list[str] = []
    else:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            found, release, refused = build(args, client)

    problems = genesetpanel.check_panel(found, args.bed, args.panel_group) + refused
    if problems:
        for line in problems:
            print(f"FAIL {line}", file=sys.stderr)
        raise SystemExit(1)

    coding = [entry.wanted.symbol for entry in found if entry.coding]
    print(f"\n{len(coding)} of {len(found)} genes have a translating canonical transcript")
    print(f"non-coding: {[e.wanted.symbol for e in found if not e.coding] or 'none'}")
    if args.dry_run:
        print("--dry-run: nothing written")
        return
    write(args, found, release, fetched=not args.reuse)


if __name__ == "__main__":
    main()
