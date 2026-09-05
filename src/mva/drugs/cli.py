"""``mva-drugs`` - turn a mechanism card into a repurposing evidence set.

Six verbs. The first five run one stage and print it; ``snapshot`` runs all of them and
writes the tables.

``card``        what the card says, and what the pipeline will therefore ask
``targets``     the seed + pathway target set, and the pathways the walk kept
``drugs``       the candidate table, approved rows first
``trials``      registered trial activity for the disease and for each approved candidate
``literature``  the publications behind the gene, the pathway and each direction
``snapshot``    every stage, five TSVs, five manifests and snapshot.json

Every verb reads the card given by ``--card`` and nothing else, so the same commands run a
different case unchanged. Replies are cached under ``build/track2-cache`` (gitignored), so
a second run of any verb is free; ``--refresh`` bypasses the cache for that run.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from .cache import DEFAULT_CACHE_DIR, SourceError
from .candidates import Candidate, Sources, gather
from .mechanism import DEFAULT_CARD, load
from .pathway import PATHWAY_PATTERN, expand
from .queries import literature, literature_queries, trials
from .snapshot import DEFAULT_OUT_DIR, build_fetchers, write_snapshot


def _say(line: str) -> None:
    print(line, file=sys.stderr)


def cmd_card(args: argparse.Namespace) -> int:
    card = load(args.card)
    print(f"card         {card.path}  v{card.version}")
    print(f"gene         {card.gene_symbol}  ({card.protein})")
    print(f"uniprot      {card.uniprot or '-'}    ensembl {card.ensembl_gene_id or '-'}")
    print(f"disease      {card.disease_name}")
    print(f"  as query   {card.disease_query}")
    print(f"tumour       {card.tumour_context or '-'}")
    print(f"pathway      {card.pathway or '-'}")
    print(f"mechanism    {card.mechanism_class}")
    print(f"\ndirections   {len(card.directions)}, {len(card.seed_targets)} distinct seed targets")
    for direction in card.directions:
        print(f"  {direction.id}  {direction.name}")
        print(f"      seeds  {', '.join(direction.seed_targets)}")
    print("\nliterature queries this card produces:")
    for query in literature_queries(card):
        print(f"  {query.family:10s} {query.term}")
    return 0


def cmd_targets(args: argparse.Namespace) -> int:
    card = load(args.card)
    fetchers = build_fetchers(args.cache_dir, refresh=args.refresh)
    try:
        result = expand(card, fetchers["reactome"], pattern=_pattern(args), progress=_say)
    finally:
        fetchers["reactome"].close()
    print(f"{'symbol':14s} {'role':9s} {'directions':14s} pathways")
    for row in result.targets:
        print(
            f"{row.symbol:14s} {row.role:9s} {','.join(row.direction_ids) or '-':14s} "
            f"{len(row.pathways) or ''}"
        )
    print(f"\nseeds {len(result.seeds)}  pathway members {len(result.members)}")
    print(f"pathways walked {len(result.pathways)}, kept {sum(p.matched for p in result.pathways)}")
    for pathway in result.pathways:
        mark = "keep" if pathway.matched else "drop"
        print(f"  {mark}  {pathway.st_id:16s} {pathway.display_name}  ({pathway.n_participants})")
    return 0


def cmd_drugs(args: argparse.Namespace) -> int:
    rows = _candidates(args)
    approved = [c for c in rows if c.approved]
    _print_candidates(approved if args.approved_only else rows, args.limit)
    print(f"\n{len(rows)} candidates, {len(approved)} approved")
    print(f"{len({c.drug_name.lower() for c in approved})} distinct approved drug names")
    return 0


def cmd_trials(args: argparse.Namespace) -> int:
    card = load(args.card)
    approved = [c for c in _candidates(args) if c.approved] if args.with_candidates else []
    fetchers = build_fetchers(args.cache_dir, refresh=args.refresh)
    try:
        rows, log = trials(fetchers["clinicaltrials"], card, approved, progress=_say)
    finally:
        fetchers["clinicaltrials"].close()
    for row in rows[: args.limit]:
        print(
            f"{row['nct_id']:14s} {row['phase'] or '-':12s} {row['overall_status']:20s} "
            f"{row['title'][:70]}"
        )
    print(f"\n{len(rows)} trial rows over {len(log)} queries")
    for entry in log:
        print(f"  {entry['hits']:5d}  {entry['family']:10s} {entry['query']}")
    return 0


def cmd_literature(args: argparse.Namespace) -> int:
    card = load(args.card)
    fetchers = build_fetchers(args.cache_dir, refresh=args.refresh)
    try:
        rows, log = literature(fetchers["pubmed"], card, retmax=args.limit, progress=_say)
    finally:
        fetchers["pubmed"].close()
    for row in rows[: args.limit]:
        print(f"{row['pmid']:10s} {row['year']:5s} {row['journal'][:24]:24s} {row['title'][:70]}")
    print(f"\n{len(rows)} literature rows over {len(log)} queries")
    for entry in log:
        print(f"  {entry['hits']:7d} hits, kept {entry.get('kept', 0):3d}  {entry['query']}")
    return 0


def cmd_snapshot(args: argparse.Namespace) -> int:
    result = write_snapshot(
        args.card,
        args.out_dir,
        cache_dir=args.cache_dir,
        refresh=args.refresh,
        pattern=_pattern(args),
        progress=_say,
    )
    counts = result.counts
    print("\n=== snapshot ===")
    print(
        f"card              {counts['card']['path']} v{counts['card']['version']} "
        f"({counts['card']['gene']})"
    )
    print(f"retrieved         {counts['retrieved_at']}")
    print(f"targets           {counts['targets']}")
    print(f"pathways          {counts['pathways']}")
    print(f"candidates        {counts['candidates']}")
    print(f"rows per table    {counts['rows']}")
    print(f"requests          {counts['requests']}")
    print("\nfiles:")
    for path in result.written:
        print(f"  {path}")
    return 0


# ── shared plumbing ─────────────────────────────────────────────────────────────────


def _candidates(args: argparse.Namespace) -> list[Candidate]:
    card = load(args.card)
    fetchers = build_fetchers(args.cache_dir, refresh=args.refresh)
    try:
        targets = expand(card, fetchers["reactome"], pattern=_pattern(args), progress=_say)
        return gather(
            targets.targets,
            Sources(
                opentargets=fetchers["opentargets"],
                chembl=fetchers["chembl"],
                dgidb=fetchers["dgidb"],
                openfda=fetchers["openfda"],
            ),
            progress=_say,
        )
    finally:
        for fetcher in fetchers.values():
            fetcher.close()


def _print_candidates(rows: list[Candidate], limit: int) -> None:
    ordered = sorted(rows, key=lambda c: (not c.approved, -(c.max_phase or 0), c.drug_name))
    print(f"{'drug':32s} {'target':12s} {'role':8s} {'ph':3s} {'appr':5s} {'fda':5s} source")
    for row in ordered[:limit]:
        print(
            f"{row.drug_name[:32]:32s} {row.target_symbol:12s} {row.target_role:8s} "
            f"{row.max_phase or '-'!s:3s} {'yes' if row.approved else 'no':5s} "
            f"{_flag(row.fda_label):5s} {','.join(row.source)}"
        )


def _flag(value: bool | None) -> str:
    return "-" if value is None else ("yes" if value else "no")


def _pattern(args: argparse.Namespace) -> re.Pattern[str]:
    return (
        re.compile(args.pathway_pattern, re.IGNORECASE) if args.pathway_pattern else PATHWAY_PATTERN
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mva-drugs", description=__doc__)
    parser.add_argument("--card", type=Path, default=DEFAULT_CARD, help="the mechanism card")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--refresh", action="store_true", help="bypass the HTTP cache")
    parser.add_argument(
        "--pathway-pattern",
        default=None,
        help=f"regex over Reactome pathway names (default: {PATHWAY_PATTERN.pattern})",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("card", help="what the card says").set_defaults(func=cmd_card)
    sub.add_parser("targets", help="the seed + pathway target set").set_defaults(func=cmd_targets)

    drugs = sub.add_parser("drugs", help="the candidate drug table")
    drugs.add_argument("--limit", type=int, default=40)
    drugs.add_argument("--approved-only", action="store_true")
    drugs.set_defaults(func=cmd_drugs)

    trial = sub.add_parser("trials", help="registered trial activity")
    trial.add_argument("--limit", type=int, default=40)
    trial.add_argument(
        "--with-candidates",
        action="store_true",
        help="also query one trial search per approved candidate (slow on a cold cache)",
    )
    trial.set_defaults(func=cmd_trials)

    lit = sub.add_parser("literature", help="the publications behind the card")
    lit.add_argument("--limit", type=int, default=40)
    lit.set_defaults(func=cmd_literature)

    snap = sub.add_parser("snapshot", help="every stage, written to disk")
    snap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    snap.set_defaults(func=cmd_snapshot)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result: int = args.func(args)
    except SourceError as error:
        print(f"source unavailable: {error}", file=sys.stderr)
        return 2
    return result


if __name__ == "__main__":
    raise SystemExit(main())
