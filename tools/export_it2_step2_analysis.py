#!/usr/bin/env python3
"""Export the numbers step 2's results figures are drawn from, straight from the warehouse.

Five result sets, one JSON file, no number typed anywhere between the database and the
figure. `render_it2_step2_results.py` reads only this file, so a figure cannot disagree
with the table it claims to show.

**Why this exists as a committed tool.** The first `analysis.json` was assembled by hand at
a prompt. It produced correct figures and no way to make them again: the repository's rule
is that a diagram commits its source, and an untracked file built by an unrecorded command
is not a source. This is that source.

Usage::

    uv run python tools/export_it2_step2_analysis.py
    uv run python tools/export_it2_step2_analysis.py --out build/it2/step-2/analysis.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mva.pipeline.stats import fisher_exact_greater
from mva.warehouse.postgres import ALIAS, attached
from mva.warehouse.settings import Postgres

DEFAULT_OUT = Path("build/it2/step-2/analysis.json")

#: Each block is ``name -> SQL``. Written out rather than derived from the ``Derivation``
#: registry because these are *summaries over* the result tables, not new result tables:
#: they belong to the figure, and putting them in ``results.`` would create a table nothing
#: else reads.
QUERIES: dict[str, str] = {
    # The filtered view: rare and protein-altering, over both annotation tables.
    "by_tier": f"""
        SELECT tier,
               count(*) AS genes,
               count(*) FILTER (biallelic) AS biallelic,
               sum(truncating) AS truncating,
               sum(novel_qualifying) AS novel_qualifying,
               sum(clinvar_flagged) AS clinvar_flagged,
               sum(unannotated_alleles) AS unannotated
        FROM {ALIAS}.results.it2_scored_pairs
        GROUP BY tier ORDER BY tier
    """,
    # The counterfactual: the same enumeration with no rarity or consequence filter. This
    # is the pair of numbers that shows the discriminating power is in the filter.
    "unfiltered_by_tier": f"""
        SELECT tier,
               count(*) AS genes,
               count(*) FILTER (biallelic) AS biallelic
        FROM {ALIAS}.results.it2_read_pairs
        GROUP BY tier ORDER BY tier
    """,
    "concordance": f"SELECT * FROM {ALIAS}.results.it2_concordance ORDER BY caller",
    "sv_consensus": f"""
        SELECT * FROM {ALIAS}.results.it2_sv_consensus
        ORDER BY spans_unbaited, bait_edge, consensus_calls DESC
    """,
    # Every gene the filter leaves standing, target or decoy, in the table's own order.
    "leads": f"""
        SELECT symbol, tier, rare_het, rare_hom_alt, truncating, clinvar_flagged,
               novel_qualifying, unannotated_alleles, bait_density, mean_depth
        FROM {ALIAS}.results.it2_scored_pairs
        WHERE biallelic
        ORDER BY truncating DESC, clinvar_flagged DESC, rare_het DESC, symbol
    """,
}


#: The pre-registered restriction (entry 085): genes the bait could actually reach, so the
#: comparison is not decided by a bait-density imbalance between the two sets.
REACHABLE = "bait_density >= (SELECT median(density) / 2 FROM {alias}.results.it2_bait_density)"


def _contrast(connection, where: str) -> dict[str, object]:
    """Targets against decoys, as the 2x2 table H020 is written about."""
    rows = connection.execute(
        f"""
        SELECT (tier = 'decoy') AS is_decoy,
               count(*) AS genes,
               count(*) FILTER (biallelic) AS biallelic
        FROM {ALIAS}.results.it2_scored_pairs
        WHERE {where}
        GROUP BY 1 ORDER BY 1
        """
    ).fetchall()
    counts = {bool(row[0]): (int(row[1]), int(row[2])) for row in rows}
    target_genes, target_hits = counts.get(False, (0, 0))
    decoy_genes, decoy_hits = counts.get(True, (0, 0))
    return {
        "target_genes": target_genes,
        "target_biallelic": target_hits,
        "target_rate": target_hits / target_genes if target_genes else 0.0,
        "decoy_genes": decoy_genes,
        "decoy_biallelic": decoy_hits,
        "decoy_rate": decoy_hits / decoy_genes if decoy_genes else 0.0,
        "fisher_one_sided_p": fisher_exact_greater(
            target_hits, target_genes - target_hits, decoy_hits, decoy_genes - decoy_hits
        ),
    }


def export(settings: Postgres) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    with attached(settings, read_only=True) as connection:
        for name, sql in QUERIES.items():
            cursor = connection.execute(sql)
            columns = [description[0] for description in cursor.description]
            out[name] = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
        out["target_vs_decoy"] = [
            {"view": "all genes", **_contrast(connection, "TRUE")},
            {
                "view": "genes the bait reached",
                **_contrast(connection, REACHABLE.format(alias=ALIAS)),
            },
        ]
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    settings = Postgres.from_env()
    if settings.missing:
        print("missing settings: " + ", ".join(settings.missing))
        return 1
    data = export(settings)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, indent=2, default=float), encoding="utf-8")
    for name, rows in data.items():
        print(f"{name:>20}  {len(rows):>4} rows")
    print(f"\nanalysis -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
