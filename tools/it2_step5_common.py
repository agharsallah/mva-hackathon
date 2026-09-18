#!/usr/bin/env python3
"""What every step-5 stage needs: the gene set, the allele list, and one TSV writer.

The four stages of step 5 ask four different public APIs, but they all start from the same
two SQL questions and end in the same file layout, so both live here once. A gene set
spelled slightly differently in two stages would silently produce two different decoy
comparisons, which is the kind of defect that never announces itself.

**The gene set is fixed here, and it is three sets unioned:** the 404 symptom-nominated
targets, the 396 size-matched decoys, and whatever genes the genome-wide ranking put at the
top. The decoys are not an afterthought — they are the only reason any number step 5
produces can be read as a measurement rather than as a list of famous genes.

Nothing here writes a coordinate. Alleles travel as ``(gene, dbSNP identifier, consequence
class)``, which is what the ranking tables already carry.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mva.viz.queries.access import fetch
from mva.warehouse.postgres import ALIAS
from mva.warehouse.settings import Postgres

DEFAULT_OUT = Path("build/it2/step-5")

#: How many genes off the top of the step-4 ranking join the target and decoy sets. The
#: plan hands "the top-20 gene list" to this step; the leaders are what the catalogue and
#: the protein stage are actually about.
TOP_LEADERS = 20

#: The gene set, as one SQL expression every stage substitutes. ``lr_rank`` comes along so
#: a stage can report where the genome-wide ranking put a gene without a second query.
GENE_SET = f"""
    SELECT g.gene,
           bool_or(t.symbol IS NOT NULL) AS is_target,
           bool_or(d.symbol IS NOT NULL) AS is_decoy,
           bool_or(l.gene_rank <= {TOP_LEADERS}) AS in_top_leaders,
           min(l.gene_rank) AS lr_rank,
           bool_or(l.curated) AS curated
    FROM (
        SELECT symbol AS gene FROM {ALIAS}.results.it2_targets
        UNION SELECT symbol FROM {ALIAS}.results.it2_decoys
        UNION SELECT gene FROM {ALIAS}.results.it2_lr_top_pairs WHERE gene_rank <= {TOP_LEADERS}
    ) g
    LEFT JOIN {ALIAS}.results.it2_targets t ON t.symbol = g.gene
    LEFT JOIN {ALIAS}.results.it2_decoys  d ON d.symbol = g.gene
    LEFT JOIN {ALIAS}.results.it2_lr_top_pairs l ON l.gene = g.gene
    GROUP BY g.gene
"""


def settings() -> Postgres:
    return Postgres.from_env()


def genes(where: str = "") -> list[dict[str, Any]]:
    """The step-5 gene set, one row per gene, ordered so a resumed run repeats itself."""
    clause = f"WHERE {where}" if where else ""
    return fetch(settings(), f"SELECT * FROM ({GENE_SET}) s {clause} ORDER BY gene")


def alleles() -> list[dict[str, Any]]:
    """Every allele the ranking scored in a gene of the set, with its ClinVar significance.

    One row per distinct ``(gene, rsid, consequence class)``. The ranking scores both sides
    of every biallelic hypothesis, so the same allele arrives through many pairs; the
    ``DISTINCT`` is what stops a popular allele being asked about — and counted — twice.

    An allele with no dbSNP identifier keeps its row with an empty ``rsid``. That is the
    case the catalogue's denominator exists for, and dropping it here would make the
    coverage number look better by deleting its own counter-example.
    """
    sql = f"""
    WITH gene_set AS ({GENE_SET}),
    sides AS (
        SELECT p.gene, coalesce(p.left_rsid, '')  AS rsid, p.left_class  AS consequence_class
        FROM {ALIAS}.results.it2_lr_pairs p JOIN gene_set g USING (gene)
        UNION ALL
        SELECT p.gene, coalesce(p.right_rsid, '') AS rsid, p.right_class AS consequence_class
        FROM {ALIAS}.results.it2_lr_pairs p JOIN gene_set g USING (gene)
    ),
    distinct_alleles AS (
        SELECT DISTINCT gene, rsid, consequence_class FROM sides WHERE consequence_class IS NOT NULL
    )
    SELECT a.gene,
           a.rsid,
           a.consequence_class,
           coalesce(max(n.clin_sig), '') AS clin_sig,
           coalesce(max(n.am_class), '') AS am_class,
           g.is_target,
           g.is_decoy,
           g.in_top_leaders
    FROM distinct_alleles a
    JOIN gene_set g ON g.gene = a.gene
    LEFT JOIN {ALIAS}.warehouse.it2_insilico_annotations n
           ON n.rsid = a.rsid AND n.gene = a.gene AND a.rsid <> ''
    GROUP BY a.gene, a.rsid, a.consequence_class, g.is_target, g.is_decoy, g.in_top_leaders
    ORDER BY a.gene, a.rsid, a.consequence_class
    """
    return fetch(settings(), sql)


def clinvar_carried() -> list[dict[str, Any]]:
    """Public ClinVar pathogenic alleles step 3 typed as present in this child.

    This is the other half of the catalogue and it comes from a completely different
    instrument: k-mer counts in the raw reads, with no aligner and no caller
    (``results.it2_kmer_genotypes``, ``origin`` starting ``clinvar``). LitVar says somebody
    *published* about a variant; this says the child *carries* one. Only the second is
    evidence about the patient.
    """
    sql = f"""
    SELECT k.symbol AS gene,
           k.call   AS child_call,
           k.posterior AS child_posterior,
           k.probes,
           k.probes_agreeing
    FROM {ALIAS}.results.it2_kmer_genotypes k
    WHERE k.origin LIKE 'clinvar%' AND k.call IN ('het', 'hom-alt')
    ORDER BY k.symbol, k.posterior DESC
    """
    return fetch(settings(), sql)


def write_tsv(path: Path, rows: list[dict[str, Any]], columns: tuple[str, ...]) -> int:
    """Write rows as a TSV the warehouse loader can read, and return how many were written.

    Quoting is explicit rather than left to the dialect default: step 5 is the one step
    whose rows carry free text — paper titles with commas, quotes and semicolons — and a
    sniffed dialect here would corrupt the evidence itself.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([_cell(row.get(name)) for name in columns])
    return len(rows)


def write_json(path: Path, payload: dict[str, Any]) -> Path:
    """The numbers no table holds — counts, correlations, intervals — beside the tables."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _cell(value: Any) -> str:
    """One TSV cell. Booleans go out as ``true``/``false`` for DuckDB's CAST, and a tab or
    a newline inside free text is replaced by a space rather than escaped — a paper title
    is display text, and a literal tab in it would move every column right of it."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).replace("\t", " ").replace("\r", " ").replace("\n", " ")
