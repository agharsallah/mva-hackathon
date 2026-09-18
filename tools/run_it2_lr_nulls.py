#!/usr/bin/env python3
"""How high would the leading pair have scored by chance? Two nulls, and one ablation.

Something is always at the top of a genome-wide ranking, so a large posterior is not by
itself a result. Three runs answer three different versions of "so what":

**the decoy null** — the 396 size-matched control genes of step 1 went through the identical
scoring, so the separation between targets and decoys measures the *filter*, which is where
discriminating power actually lives. Reported as an AUC with a bootstrap interval; an
interval covering 0.5 means no measured separation, however large the point estimate.

**the phenotype-permutation null** — a thousand random seven-term sets, each drawn to match
the child's own term-depth profile, each re-ranking every gene and re-scoring every
hypothesis. Because LIRICAL's degradation is a power, substituting the phenotype lane is
exact arithmetic rather than an approximation (:meth:`ScoredPair.rescored`), so a thousand
draws cost a thousand *rankings*, not a thousand re-annotations.

**the genotype-only ablation** — the same table with the phenotype lane set to 1, which is
what the DNA alone would have nominated. Not a null: a control that shows how much of the
answer the symptoms are carrying.

Usage::

    uv run python tools/run_it2_lr_nulls.py --draws 1000
    uv run python tools/run_it2_lr_nulls.py --draws 10     # the timing probe, run first
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mva.phenotype.associations import parse_genes_to_phenotype
from mva.phenotype.lanes import phenotype_likelihood
from mva.phenotype.ontology import ROOT, Ontology, parse_obo
from mva.phenotype.prioritise import rank_genes
from mva.phenotype.terms import Term, TermSet, term_set
from mva.pipeline.nulls import Separation, permutation, separation
from mva.pipeline.rank_lr import RankLikelihood

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rank_it2_pairs import BENCHMARK, CORPUS, DEFAULT_OUT, STEP1_SUMMARY

OBO = Path("build/reference-scratch/hp.obo")

#: Seed for every draw and every bootstrap, so the p-value is as reproducible as the ranking.
SEED = 20260918

#: The term set the observed ranking used.
TERM_SET = "proband-only"


def read_best(path: Path) -> dict[str, dict]:
    """The best hypothesis per gene, with the two fields a re-score needs."""
    best: dict[str, dict] = {}
    with path.open(encoding="utf-8") as handle:
        header = handle.readline().rstrip("\n").split("\t")
        for line in handle:
            row = dict(zip(header, line.rstrip("\n").split("\t"), strict=False))
            gene = row["gene"]
            item = {
                "gene": gene,
                "combined_lr": float(row["combined_lr"]),
                "without": float(row["lr_without_phenotype"]),
                "exponent": float(row["exponent"]),
                "is_target": row["is_target"] == "true",
                "is_decoy": row["is_decoy"] == "true",
                "curated": row["curated"] == "true",
                "shape": row["shape"],
            }
            if gene not in best or item["combined_lr"] > best[gene]["combined_lr"]:
                best[gene] = item
    return best


def decoy_null(best: dict[str, dict], *, seed: int, resamples: int) -> Separation:
    """Target versus matched decoy, on the score the ranking actually orders by."""
    targets = [row["combined_lr"] for row in best.values() if row["is_target"]]
    decoys = [row["combined_lr"] for row in best.values() if row["is_decoy"]]
    return separation(targets, decoys, seed=seed, resamples=resamples)


def depth_profile(ids: list[str], ontology: Ontology) -> list[int]:
    """The child's own term depths — the shape every random draw has to match."""
    return [ontology.depth(hpo) for hpo in ids if hpo in ontology]


def by_depth(ontology: Ontology) -> dict[int, list[str]]:
    """Every term in the ontology, bucketed by how deep it sits below the root."""
    buckets: dict[int, list[str]] = defaultdict(list)
    for hpo, concept in ontology.concepts.items():
        if hpo == ROOT or concept.obsolete:
            continue
        buckets[ontology.depth(hpo)].append(hpo)
    return dict(buckets)


def draw(profile: list[int], buckets: dict[int, list[str]], rng: random.Random) -> list[str]:
    """One random term set with the child's depth profile — same shape, no relation to the case."""
    out: list[str] = []
    for depth in profile:
        pool = buckets.get(depth) or buckets.get(depth - 1) or []
        if pool:
            out.append(rng.choice(pool))
    return list(dict.fromkeys(out))


def _permuted(ids: list[str], index: int) -> TermSet:
    """One draw, wrapped in the same named object the real term set uses.

    Named rather than a bare list because every ranking in this package records which term
    set produced it, and a permuted ranking is a claim about a *different* term set.
    """
    return TermSet(
        name=f"permuted-{index:04d}",
        terms=tuple(Term(hpo, hpo, "random draw at the child's term depth") for hpo in ids),
        rationale="a random term set with the proband's term-depth profile, for the null",
    )


def top_under(
    ranks: dict[str, int], best: dict[str, dict], likelihood: RankLikelihood
) -> tuple[float, str]:
    """The best score any gene reaches under a given ranking, and which gene reaches it."""
    top, winner = 0.0, ""
    for gene, row in best.items():
        value = (row["without"] * likelihood.lr(ranks.get(gene))) ** row["exponent"]
        if value > top:
            top, winner = value, gene
    return top, winner


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--draws", type=int, default=1000)
    parser.add_argument(
        "--resamples", type=int, default=1000, help="bootstrap resamples for the AUC"
    )
    parser.add_argument("--obo", type=Path, default=OBO)
    parser.add_argument("--corpus", type=Path, default=CORPUS)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args(argv)

    pairs = args.out / "tables" / "it2_lr_pairs.tsv"
    if not pairs.is_file():
        print(f"no ranking to read: {pairs} is absent — run tools/rank_it2_pairs.py first")
        return 1

    best = read_best(pairs)
    likelihood = phenotype_likelihood(BENCHMARK, STEP1_SUMMARY)
    observed = max(row["combined_lr"] for row in best.values())
    observed_gene = max(best.values(), key=lambda row: row["combined_lr"])["gene"]

    decoys = decoy_null(best, seed=args.seed, resamples=args.resamples)

    ontology = parse_obo(args.obo)
    corpus = parse_genes_to_phenotype(args.corpus, ontology)
    ontology = ontology.with_frequencies(corpus.direct_counts, len(corpus.genes))
    profile = depth_profile(list(term_set(TERM_SET).ids), ontology)
    buckets = by_depth(ontology)

    rng = random.Random(args.seed)
    tops: list[float] = []
    beaten: list[int] = []
    started = time.monotonic()
    for index in range(args.draws):
        ids = draw(profile, buckets, rng)
        ranking = rank_genes(_permuted(ids, index), corpus, ontology)
        ranks = {score.symbol: score.rank for score in ranking.scores}
        top, _ = top_under(ranks, best, likelihood)
        tops.append(top)
        beaten.append(
            sum(
                1
                for gene, row in best.items()
                if (row["without"] * likelihood.lr(ranks.get(gene))) ** row["exponent"] >= observed
            )
        )
        if (index + 1) % 10 == 0:
            rate = (time.monotonic() - started) / (index + 1)
            print(f"  draw {index + 1}/{args.draws}  {rate:.2f} s/draw", flush=True)

    result = permutation(observed, tops, beaten)
    genotype_only = sorted(
        (
            {"gene": gene, "lr": row["without"] ** row["exponent"], "shape": row["shape"]}
            for gene, row in best.items()
        ),
        key=lambda item: item["lr"],
        reverse=True,
    )[:20]

    summary = {
        "seed": args.seed,
        "observed_top": observed,
        "observed_gene": observed_gene,
        "genes": len(best),
        "decoy_null": {
            "auc": decoys.auc,
            "low": decoys.low,
            "high": decoys.high,
            "targets": decoys.positives,
            "decoys": decoys.negatives,
            "resamples": decoys.resamples,
            "separates": decoys.separates,
            "verdict": decoys.verdict,
        },
        "permutation_null": {
            "draws": len(result.draws),
            "exceeded": result.exceeded,
            "p_value": result.p_value,
            "null_median_top": result.null_median,
            "expected_false_leads": result.expected_false_leads,
            "seconds": round(time.monotonic() - started, 1),
        },
        "genotype_only_top": genotype_only,
        "term_depth_profile": profile,
    }
    (args.out / "nulls.json").write_text(
        json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8"
    )
    with (args.out / "tables" / "it2_lr_nulls.tsv").open("w", encoding="utf-8") as handle:
        handle.write("draw\ttop_lr\tgenes_above_observed\n")
        for index, (top, count) in enumerate(zip(tops, beaten, strict=True), start=1):
            handle.write(f"{index}\t{top:.6g}\t{count}\n")
    print(
        json.dumps(
            {k: v for k, v in summary.items() if k != "genotype_only_top"}, indent=2, default=str
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
