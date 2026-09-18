#!/usr/bin/env python3
"""Rank every biallelic hypothesis in the callset by posterior, with no hard filter anywhere.

Iteration 1 used a funnel: rare **and** protein-altering **and** biallelic **and** PASS, and
a gene was in or out. This replaces every one of those cuts with a multiplier. A common
allele is divided down, not deleted; a filtered call is down-weighted, not dropped; a gene
nobody has curated keeps a ratio below 1 instead of vanishing; and a gene with one damaging
allele and no partner is scored at the square root of its evidence rather than at zero.

What comes out is three files under ``--out``:

``tables/it2_lr_alleles.tsv``
    one row per carried ALT allele, with every lane's ratio and which lane spoke for it
``tables/it2_lr_pairs.tsv``
    one row per biallelic hypothesis — compound, homozygous or single — with the posterior,
    the phase, and the same gene's Exomiser-style baseline score beside it
``ranking.json``
    the counts and the top of the table, which is what the figures and the entry read

Every gene goes through the identical code path, targets and decoys alike: the decoy null
is a column on the row, never a second pipeline.

Usage::

    uv run python tools/rank_it2_pairs.py
    uv run python tools/rank_it2_pairs.py --no-inheritance   # the prior switched off
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mva.phenotype.lanes import inheritance_lane, network_lane, phenotype_likelihood
from mva.pipeline import genotype_lr, pair_lr
from mva.pipeline.acmg import Strength
from mva.pipeline.annotation import Annotation
from mva.pipeline.rank_lr import RankLikelihood
from mva.pipeline.ranking import allele_score
from mva.warehouse.it2_lr_inputs import AlleleRow, GeneRow, alleles, gene_context
from mva.warehouse.settings import Postgres

DEFAULT_OUT = Path("build/it2/step-4")
BENCHMARK = Path("build/it2/step-1/benchmark-full.json")
STEP1_SUMMARY = Path("build/it2/step-1/summary.json")
CORPUS = Path("build/reference-scratch/genes_to_phenotype.txt")

#: Pairs beyond this many alleles in one gene are not enumerated exhaustively — the count is
#: recorded and the strongest alleles are paired instead. A gene with 60 carried alleles is
#: a mapping artefact, and 1,770 pairs of it would swamp the table it belongs in.
MAX_ALLELES_PER_GENE = 12


def baseline(left: AlleleRow, right: AlleleRow | None) -> float:
    """Exomiser's gene-level rule, printed beside the posterior as the comparator.

    A compound-heterozygous gene scores the mean of its two best variant scores
    (Smedley 2015, p. 2012). Reuses :func:`mva.pipeline.ranking.allele_score` so the
    comparator is the repository's existing heuristic rather than a second one.
    """
    scores = [_allele_score(left)] + ([_allele_score(right)] if right is not None else [])
    return sum(scores) / len(scores)


def _allele_score(row: AlleleRow) -> float:
    return allele_score(
        Annotation(
            gene=row.gene,
            consequence=row.evidence.consequence or None,
            gnomad_af=row.evidence.gnomad_af,
        )
    )


def hypotheses(
    rows: list[AlleleRow],
    context: dict[str, GeneRow],
    *,
    likelihood: RankLikelihood,
    network: dict[str, float],
    network_source: str,
    inheritance: dict[str, float],
    prior: float,
    source: str,
) -> tuple[list[dict], dict[str, int]]:
    """Every biallelic hypothesis in the callset, scored. One row per hypothesis."""
    by_gene: dict[str, list[AlleleRow]] = defaultdict(list)
    for row in rows:
        by_gene[row.gene].append(row)

    out: list[dict] = []
    counts = {"genes": 0, "compound": 0, "homozygous": 0, "single": 0, "capped_genes": 0}
    for gene, carried in sorted(by_gene.items()):
        info = context.get(gene, GeneRow(symbol=gene))
        lanes = pair_lr.context_lanes(
            phenotype_lr=likelihood.lr(info.phenotype_rank),
            phenotype_source=likelihood.source,
            phenotype_rank=info.phenotype_rank,
            network_lr=network.get(gene, 1.0),
            network_source=network_source or "no network lane",
            inheritance_lr=inheritance.get(gene, 1.0),
            inheritance_source="mva.pipeline.inheritance, pre-registered in step 1",
        )
        counts["genes"] += 1
        hets = [row for row in carried if row.is_het]
        homs = [row for row in carried if row.is_hom]
        if len(hets) > MAX_ALLELES_PER_GENE:
            counts["capped_genes"] += 1
            hets = sorted(hets, key=_allele_score, reverse=True)[:MAX_ALLELES_PER_GENE]

        for left, right in combinations(hets, 2):
            out.append(
                _row(
                    pair_lr.score(
                        gene,
                        left.evidence,
                        right.evidence,
                        shape=pair_lr.Shape.COMPOUND,
                        context=lanes,
                        prior=prior,
                        source=source,
                        left_call=left.call(),
                        right_call=right.call(),
                    ),
                    info,
                    left,
                    right,
                )
            )
            counts["compound"] += 1
        for row in homs:
            out.append(
                _row(
                    pair_lr.score(
                        gene,
                        row.evidence,
                        None,
                        shape=pair_lr.Shape.HOMOZYGOUS,
                        context=lanes,
                        prior=prior,
                        source=source,
                    ),
                    info,
                    row,
                    None,
                )
            )
            counts["homozygous"] += 1
        if not homs and len(hets) == 1:
            out.append(
                _row(
                    pair_lr.score(
                        gene,
                        hets[0].evidence,
                        None,
                        shape=pair_lr.Shape.SINGLE,
                        context=lanes,
                        prior=prior,
                        source=source,
                    ),
                    info,
                    hets[0],
                    None,
                )
            )
            counts["single"] += 1
    out.sort(key=lambda item: item["combined_lr"], reverse=True)
    return out, counts


def _row(
    scored: pair_lr.ScoredPair, info: GeneRow, left: AlleleRow, right: AlleleRow | None
) -> dict:
    return {
        "gene": scored.gene,
        "shape": scored.shape.value,
        "phase": scored.phase.value,
        "tier": info.tier,
        "is_target": info.is_target,
        "is_decoy": info.is_decoy,
        "curated": info.curated,
        "phenotype_rank": info.phenotype_rank,
        "loeuf": info.loeuf,
        "reachable": info.reachable,
        "biallelic_confirmed": info.biallelic_confirmed,
        "left_class": scored.left.lane_class,
        "left_scored_by": scored.left.scored_by,
        "right_class": scored.right.lane_class if scored.right else "",
        "right_scored_by": scored.right.scored_by if scored.right else "",
        "left_rsid": left.rsid,
        "right_rsid": right.rsid if right else "",
        "left_filters": left.filters,
        "right_filters": right.filters if right else "",
        "combined_lr": scored.combined_lr,
        "lr_without_phenotype": scored.lr_without_phenotype,
        "exponent": scored.exponent,
        "posterior": scored.probability,
        "log10_lr": scored.posterior.log10_lr,
        "baseline": baseline(left, right),
        "unphaseable": scored.unphaseable,
        "terms": ";".join(f"{name}={value:.4g}" for name, value in scored.posterior.terms),
        "damped": ";".join(scored.posterior.damped),
    }


def write_tsv(path: Path, rows: list[dict], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write("\t".join(columns) + "\n")
        for row in rows:
            handle.write("\t".join(_cell(row.get(column)) for column in columns) + "\n")


def _cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--benchmark", type=Path, default=BENCHMARK)
    parser.add_argument("--summary", type=Path, default=STEP1_SUMMARY)
    parser.add_argument("--corpus", type=Path, default=CORPUS)
    parser.add_argument(
        "--no-inheritance",
        action="store_true",
        help="switch the pre-registered inheritance prior off; the run the report compares against",
    )
    parser.add_argument("--top", type=int, default=50, help="how many rows to carry into the JSON")
    # The sensitivity knobs. Entry 098 pre-registered the two caps and the FILTER
    # down-weight as *choices*, so the run that tests whether they decided the answer has to
    # be the same code with the constants moved — not a second scorer.
    parser.add_argument(
        "--missense-ceiling",
        choices=[s.name.lower() for s in Strength if not s.is_benign],
        help="raise or lower the cap on the AlphaMissense lane (default: moderate)",
    )
    parser.add_argument(
        "--splice-ceiling",
        choices=[s.name.lower() for s in Strength if not s.is_benign],
        help="raise or lower the cap on the SpliceAI lane (default: moderate)",
    )
    parser.add_argument(
        "--non-pass-lr",
        type=float,
        help="multiplier for a call the caller filtered (default: one third)",
    )
    parser.add_argument("--label", default="", help="suffix for the output files of a variant run")
    args = parser.parse_args(argv)

    if args.missense_ceiling:
        genotype_lr.MISSENSE_CEILING = Strength[args.missense_ceiling.upper()]
    if args.splice_ceiling:
        genotype_lr.SPLICE_CEILING = Strength[args.splice_ceiling.upper()]
    if args.non_pass_lr is not None:
        genotype_lr.NON_PASS_LR = args.non_pass_lr

    settings = Postgres.from_env()
    rows = alleles(settings)
    context = gene_context(settings)
    likelihood = phenotype_likelihood(args.benchmark, args.summary)
    network, network_source = network_lane(args.out / "network.tsv")
    inheritance, reasons = inheritance_lane(args.corpus, enabled=not args.no_inheritance)
    prior = pair_lr.gene_prior(likelihood.universe)

    scored, counts = hypotheses(
        rows,
        context,
        likelihood=likelihood,
        network=network,
        network_source=network_source,
        inheritance=inheritance,
        prior=prior,
        source="warehouse.coding_annotations + warehouse.it2_insilico_annotations",
    )

    suffix = args.label or ("-no-inheritance" if args.no_inheritance else "")
    tables = args.out / "tables"
    write_tsv(
        tables / f"it2_lr_pairs{suffix}.tsv",
        scored,
        [
            "gene",
            "shape",
            "phase",
            "tier",
            "is_target",
            "is_decoy",
            "curated",
            "phenotype_rank",
            "loeuf",
            "reachable",
            "biallelic_confirmed",
            "left_class",
            "left_scored_by",
            "right_class",
            "right_scored_by",
            "left_rsid",
            "right_rsid",
            "left_filters",
            "right_filters",
            "combined_lr",
            "lr_without_phenotype",
            "exponent",
            "posterior",
            "log10_lr",
            "baseline",
            "unphaseable",
            "terms",
            "damped",
        ],
    )

    genes_best: dict[str, dict] = {}
    for row in scored:
        genes_best.setdefault(row["gene"], row)
    ordered = list(genes_best.values())
    summary = {
        "prior": prior,
        "universe": likelihood.universe,
        "alleles": len(rows),
        "hypotheses": len(scored),
        "counts": counts,
        "phenotype_bins": [
            {
                "low": b.low,
                "high": b.high,
                "causal_mass": b.causal_mass,
                "null_mass": b.null_mass,
                "likelihood_ratio": b.likelihood_ratio,
            }
            for b in likelihood.bins()
        ],
        "phenotype_unranked_lr": likelihood.unranked_lr(),
        "network_genes": len(network),
        "inheritance_genes": len(inheritance),
        "inheritance_applied": not args.no_inheritance,
        "missense_ceiling": genotype_lr.MISSENSE_CEILING.value,
        "splice_ceiling": genotype_lr.SPLICE_CEILING.value,
        "non_pass_lr": genotype_lr.NON_PASS_LR,
        "genes_scored": len(genes_best),
        "genes_uncurated_scored": sum(1 for row in ordered if not row["curated"]),
        "top_genes": ordered[: args.top],
        "inheritance_reasons": {
            row["gene"]: reasons[row["gene"]] for row in ordered[:20] if row["gene"] in reasons
        },
    }
    (args.out / f"ranking{suffix}.json").write_text(
        json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                k: v
                for k, v in summary.items()
                if k not in ("top_genes", "phenotype_bins", "inheritance_reasons")
            },
            indent=2,
        )
    )
    for row in ordered[:10]:
        print(
            f"  {row['gene']:<12} {row['shape']:<10} LR {row['combined_lr']:>12.4g}  "
            f"rank {row['phenotype_rank']!s:>6}  "
            f"{row['tier'] or ('decoy' if row['is_decoy'] else '-')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
