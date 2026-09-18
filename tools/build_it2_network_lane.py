#!/usr/bin/env python3
"""Score the genes the symptom ranker cannot score at all, by who they sit beside.

**73.6 % of protein-coding genes carry no HPO curation** (step 1, entry 084), so the
human-only ranker returns nothing for them — not a low score, no score. Step 4 is the only
step that sees those genes, and this is the lane that lets them enter: ask STRING for the
high-confidence interaction partners of the best-ranked genes, and score an uncurated gene
by how strongly it connects to them.

**This repeats step 1's network tier against a different endpoint.** Step 1 called STRING's
``/network``, which returns only the edges *among* the identifiers given, so by construction
it can never name a gene that was not already a seed — and it produced zero rows. The lane
needs ``/interaction_partners``, which reaches outward. The correction is the point of
running it here.

The lane is **capped**: a neighbour has no phenotype evidence of its own, only a neighbour
that has some, so its likelihood ratio never exceeds what the cap allows however many seeds
it touches.

Usage::

    uv run python tools/build_it2_network_lane.py --seeds 50
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mva.phenotype.network import HIGH_CONFIDENCE, neighbours, parse_string_network, partners_url
from mva.warehouse.postgres import ALIAS, attached, safe_identifier
from mva.warehouse.settings import Postgres

DEFAULT_OUT = Path("build/it2/step-4")

#: The phenotype term set the seeds are taken from — the child's own terms, not the
#: parents'. Same choice as every other iteration-2 query (entry 067 §5, H002).
TERM_SET = "proband-only"

#: Partners per seed. STRING orders by score, so this is a depth cut, not a quality cut.
PARTNERS_PER_SEED = 50


def seeds_and_curated(settings: Postgres, count: int) -> tuple[list[str], set[str]]:
    """The top ``count`` ranked genes, and every gene the ranker could score at all."""
    schema = safe_identifier(settings.schema)
    with attached(settings, read_only=True) as connection:
        rows = connection.execute(
            f"""
            SELECT gene_symbol, rank
            FROM {ALIAS}.{schema}.hpo_gene_scores
            WHERE term_set = ?
            ORDER BY rank
            """,
            [TERM_SET],
        ).fetchall()
    symbols = [str(symbol) for symbol, _ in rows]
    return symbols[:count], set(symbols)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--seeds", type=int, default=50, help="how many top-ranked genes to seed")
    parser.add_argument("--minimum-score", type=int, default=HIGH_CONFIDENCE)
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args(argv)

    settings = Postgres.from_env()
    seeds, curated = seeds_and_curated(settings, args.seeds)
    if not seeds:
        print("no ranked genes: the phenotype ranking has not been loaded", file=sys.stderr)
        return 1

    url = partners_url(seeds, limit=PARTNERS_PER_SEED, required_score=args.minimum_score)
    response = httpx.get(url, timeout=args.timeout)
    response.raise_for_status()
    payload = response.json()
    edges = parse_string_network(payload)
    scored = neighbours(edges, seeds, exclude=curated, minimum_score=args.minimum_score)

    args.out.mkdir(parents=True, exist_ok=True)
    table = args.out / "network.tsv"
    with table.open("w", encoding="utf-8") as handle:
        handle.write("symbol\tproximity\tdegree\tpartners\n")
        for item in scored:
            handle.write(
                f"{item.symbol}\t{item.proximity:.6f}\t{item.degree}\t{','.join(item.partners)}\n"
            )

    summary = {
        "endpoint": "interaction_partners",
        "url": url,
        "term_set": TERM_SET,
        "seeds": len(seeds),
        "minimum_score": args.minimum_score,
        "partners_per_seed": PARTNERS_PER_SEED,
        "edges": len(edges),
        "curated_genes_excluded": len(curated),
        "uncurated_neighbours": len(scored),
        "top": [
            {"symbol": item.symbol, "proximity": round(item.proximity, 6), "degree": item.degree}
            for item in scored[:20]
        ],
    }
    (args.out / "network.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "top"}, indent=2))
    print(f"wrote {table}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
