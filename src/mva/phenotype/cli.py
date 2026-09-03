"""``mva-phenotype`` - rank genes by the child's symptoms, and cross-check the ranking.

Four verbs, each answering one question:

``rank``       where does every gene place against a term set?
``gene``       why did one gene place there - which feature, through which ancestor?
``delta``      what changes when the parental term is dropped?
``agreement``  do two independent hosted services put the same genes on top?

The reference tables are read from ``ressources/reference/`` by default, so ``rank`` and
``gene`` need no network and no database. ``agreement`` is the only verb that reaches
outside, and it degrades to a printed reason rather than failing the run.
"""

import argparse
import sys
from pathlib import Path

from . import prior, terms
from .associations import Corpus, parse_genes_to_phenotype
from .ontology import Ontology, parse_obo
from .prioritise import Ranking, delta, rank_genes
from .remote import monarch_semsim, phen2gene

#: Where the builder leaves the raw ontology and annotation files.
DEFAULT_SCRATCH = Path("build/reference-scratch")

#: The eight-gene candidate panel, named here **only** so the output can mark which rows
#: happen to be panel genes. The ranking itself never sees this list - if it did, the whole
#: exercise would inherit the bias it exists to test.
PANEL = ("BUB1B", "CENPE", "CEP192", "CEP57", "DICER1", "SMC5", "TP53", "TRIP13")


def load(scratch: Path) -> tuple[Ontology, Corpus]:
    """Parse the ontology and the annotation corpus, with information content attached."""
    obo = scratch / "hp.obo"
    genes = scratch / "genes_to_phenotype.txt"
    for path in (obo, genes):
        if not path.exists():
            raise SystemExit(
                f"missing {path}\nRun: uv run tools/build_phenotype_data.py --scratch {scratch}"
            )
    graph = parse_obo(obo)
    corpus = parse_genes_to_phenotype(genes, graph)
    corpus.apply_to(graph)
    return graph, corpus


def mark(symbol: str) -> str:
    """Flag a panel gene in the output, so agreement is visible without a second lookup."""
    return f"{symbol} *" if symbol in PANEL else symbol


def cmd_rank(args: argparse.Namespace) -> int:
    graph, corpus = load(args.scratch)
    ranking = rank_genes(terms.term_set(args.term_set), corpus, graph)
    _report_unresolved(ranking)
    print(f"{ranking.term_set.name}: {len(ranking.term_set)} terms, {ranking.considered:,} genes")
    print(f"  {ranking.term_set.rationale}\n")
    for score in ranking.top(args.limit):
        print(f"{score.rank:5d}. {mark(score.symbol):16s} {score.score:.4f}  {score.summary}")
    if args.panel:
        print("\npanel genes (never shown to the ranker):")
        for symbol in PANEL:
            place = ranking.rank_of(symbol)
            where = f"rank {place:,} of {ranking.considered:,}" if place else "not curated in HPO"
            print(f"  {symbol:8s} {where}")
    return 0


def cmd_gene(args: argparse.Namespace) -> int:
    graph, corpus = load(args.scratch)
    ranking = rank_genes(terms.term_set(args.term_set), corpus, graph)
    score = ranking.by_symbol(args.symbol)
    if score is None:
        print(prior.explain(ranking, args.symbol))
        return 0

    print(prior.explain(ranking, args.symbol))
    print(f"\n  curated features: {score.term_count}")
    print(f"  forward {score.similarity.forward:.3f}  reverse {score.similarity.reverse:.3f}")
    print("\n  feature by feature:")
    for match in score.similarity.matches:
        label = graph.name(match.query_term)
        if not match.matched:
            print(f"    {match.query_term}  {label:34s} no informative match")
            continue
        ancestor = match.common_ancestor or ""
        print(
            f"    {match.query_term}  {label:34s} via {graph.name(ancestor)} "
            f"({ancestor}, IC {match.ic:.2f})"
        )
    return 0


def cmd_delta(args: argparse.Namespace) -> int:
    graph, corpus = load(args.scratch)
    rankings = {term_set.name: rank_genes(term_set, corpus, graph) for term_set in terms.TERM_SETS}
    with_parental = rankings[terms.WITH_PARENTAL.name]
    without = rankings[terms.PROBAND_ONLY.name]
    symbols = tuple(args.genes) if args.genes else PANEL

    print(
        f"Dropping {terms.PARENTAL_TERM} "
        f"({terms.by_id(terms.PARENTAL_TERM).label}) - a parental feature, not the child's.\n"
    )
    print(f"{'gene':10s} {'with':>10s} {'without':>10s} {'moved':>10s}")
    for move in delta(with_parental, without, symbols):
        before = f"{move.before:,}" if move.before else "-"
        after = f"{move.after:,}" if move.after else "-"
        moved = f"{move.moved:+d}" if move.moved is not None else "-"
        print(f"{move.symbol:10s} {before:>10s} {after:>10s} {moved:>10s}")
    print("\nA positive move means the gene rose when the parental term was removed.")
    return 0


def cmd_agreement(args: argparse.Namespace) -> int:
    graph, corpus = load(args.scratch)
    ranking = rank_genes(terms.term_set(args.term_set), corpus, graph)
    ours = ranking.top(args.limit)
    query = ranking.term_set.ids

    # Both services are asked for their widest window, not for ``limit`` rows. The table
    # shows where *our* top genes landed in *their* ranking, so truncating their list to
    # the size of ours would print "not returned" for every gene they ranked below our own
    # cut-off - which reads as disagreement and is nothing of the kind.
    hosted = [phen2gene(query), monarch_semsim(query)]

    for reply in hosted:
        state = f"{len(reply)} genes" if reply.ok else f"UNAVAILABLE - {reply.error}"
        print(f"{reply.source:16s} {state}")
    print()

    header = "  ours " + "".join(f"{reply.source:>18s}" for reply in hosted)
    print(f"{'gene':16s}{header}")
    for score in ours:
        cells = ""
        for reply in hosted:
            place = reply.rank_of(score.symbol)
            cells += f"{(str(place) if place else '-'):>18s}"
        print(f"{mark(score.symbol):16s}{score.rank:6d}{cells}")
    print(
        "\nA dash is 'this service did not return that gene', which is not disagreement.\n"
        "Every column is a different method; agreement across them is the claim worth making."
    )
    return 0


def _report_unresolved(ranking: Ranking) -> None:
    if ranking.unresolved:
        print(
            f"WARNING: {len(ranking.unresolved)} term(s) not in this HPO release: "
            f"{', '.join(ranking.unresolved)}",
            file=sys.stderr,
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mva-phenotype", description=__doc__)
    parser.add_argument("--scratch", type=Path, default=DEFAULT_SCRATCH)
    sub = parser.add_subparsers(dest="command", required=True)

    names = [term_set.name for term_set in terms.TERM_SETS]

    rank = sub.add_parser("rank", help="rank every gene against a term set")
    rank.add_argument("--term-set", choices=names, default=terms.PROBAND_ONLY.name)
    rank.add_argument("--limit", type=int, default=30)
    rank.add_argument("--panel", action="store_true", help="also show where panel genes placed")
    rank.set_defaults(func=cmd_rank)

    gene = sub.add_parser("gene", help="why one gene placed where it did")
    gene.add_argument("symbol")
    gene.add_argument("--term-set", choices=names, default=terms.PROBAND_ONLY.name)
    gene.set_defaults(func=cmd_gene)

    move = sub.add_parser("delta", help="what changes when the parental term is dropped")
    move.add_argument("--genes", nargs="*", default=None)
    move.set_defaults(func=cmd_delta)

    agree = sub.add_parser("agreement", help="compare against two hosted rankers")
    agree.add_argument("--term-set", choices=names, default=terms.PROBAND_ONLY.name)
    agree.add_argument("--limit", type=int, default=15)
    agree.set_defaults(func=cmd_agreement)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result: int = args.func(args)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
