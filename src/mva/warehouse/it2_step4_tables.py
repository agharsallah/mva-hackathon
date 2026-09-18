"""Load iteration 2's step-4 tables into the warehouse, with their lineage.

Same shape as :mod:`mva.warehouse.it2_step3_tables`, and for the same reason: the rows are
produced by Python — a likelihood ratio per allele, a posterior per biallelic hypothesis, a
thousand permuted rankings, a gnomAD lookup — so this module's job is to put them where SQL
and the dashboard can read them, and to record where each one came from.

**Every table names three inputs, not two.** The callset is one; the clinical document is
another, because the phenotype lane is a likelihood ratio computed from the child's own
seven terms and the ranker's measured recall on them; and the **public annotation sources**
are the third — Ensembl VEP, AlphaMissense, SpliceAI, gnomAD, ClinVar. A posterior naming
only the VCF would let a reader assume the ordering came out of this child's DNA alone. It
did not: the DNA supplies the alleles, and public knowledge supplies almost all of the
weight.

**No table here carries a coordinate.** A hypothesis is reported as a gene, a shape
(compound, homozygous or single), the lanes that scored it and the resulting ratio. The
alleles behind it are named by consequence class and rsID, which is what
``tools/check_coordinates.py`` permits and what the blind protocol requires.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from . import lineage
from .postgres import ALIAS, safe_identifier

#: One row per table: the columns, written out rather than sniffed, because these schemas
#: are a promise the analysis SQL and the dashboard both read.
SCHEMAS: dict[str, tuple[tuple[str, str], ...]] = {
    "it2_lr_pairs": (
        ("gene", "VARCHAR"),
        ("shape", "VARCHAR"),
        ("phase", "VARCHAR"),
        ("tier", "VARCHAR"),
        ("is_target", "BOOLEAN"),
        ("is_decoy", "BOOLEAN"),
        ("curated", "BOOLEAN"),
        ("phenotype_rank", "BIGINT"),
        ("loeuf", "DOUBLE"),
        ("reachable", "BOOLEAN"),
        ("biallelic_confirmed", "BOOLEAN"),
        ("left_class", "VARCHAR"),
        ("left_scored_by", "VARCHAR"),
        ("right_class", "VARCHAR"),
        ("right_scored_by", "VARCHAR"),
        ("left_rsid", "VARCHAR"),
        ("right_rsid", "VARCHAR"),
        ("left_filters", "VARCHAR"),
        ("right_filters", "VARCHAR"),
        ("combined_lr", "DOUBLE"),
        ("lr_without_phenotype", "DOUBLE"),
        ("exponent", "DOUBLE"),
        ("posterior", "DOUBLE"),
        ("log10_lr", "DOUBLE"),
        ("baseline", "DOUBLE"),
        ("unphaseable", "BOOLEAN"),
        ("terms", "VARCHAR"),
        ("damped", "VARCHAR"),
    ),
    "it2_ptrans": (
        ("gene", "VARCHAR"),
        ("shape", "VARCHAR"),
        ("phase", "VARCHAR"),
        ("rank", "BIGINT"),
        ("combined_lr", "DOUBLE"),
        ("p_trans", "DOUBLE"),
        ("state", "VARCHAR"),
        ("left_rsid", "VARCHAR"),
        ("right_rsid", "VARCHAR"),
        ("left_id", "VARCHAR"),
        ("right_id", "VARCHAR"),
        ("source", "VARCHAR"),
        ("note", "VARCHAR"),
    ),
    "it2_lr_nulls": (
        ("draw", "BIGINT"),
        ("top_lr", "DOUBLE"),
        ("genes_above_observed", "BIGINT"),
    ),
}

#: What each table is, in one sentence, recorded as the lineage row's transform.
TRANSFORMS: dict[str, str] = {
    "it2_lr_pairs": (
        "every biallelic hypothesis in the callset — compound, homozygous and single — "
        "scored by a product of likelihood ratios with no hard filter anywhere: a "
        "phenotype lane calibrated on step 1's own held-out recall curve, a network lane "
        "for uncurated genes, a pre-registered inheritance factor, and per-allele lanes "
        "for consequence, AlphaMissense, SpliceAI, ClinVar, frequency and FILTER"
    ),
    "it2_ptrans": (
        "P(trans) for the leading pairs from gnomAD v2 variant co-occurrence (Guo 2024), "
        "resolved by dbSNP identifier; a pair with either allele absent is reported at the "
        "uninformative prior and labelled undetermined, never zero and never silently one"
    ),
    "it2_lr_nulls": (
        "one row per permuted draw: a random seven-term set with the proband's term-depth "
        "profile, the whole ranking recomputed, recording the top ratio it reached and how "
        "many genes it put at or above the observed leader"
    ),
}

#: The three inputs, named once and quoted in every lineage row.
CALLSET_REF = "s3://mva/source/WGS_EX2312012_HGWCNDSX7.vcf.gz -> results.coding_alleles"
CLINICAL_REF = "ressources/hackathon-rules/Challenge_Clinical_Phenotype_1.md"
CLINICAL_TRANSFORM = (
    "the phenotype lane is a likelihood ratio per rank, computed from the proband's seven "
    "HPO terms and the measured recall of the step-1 ranker on held-out recessive diseases "
    "(entries 084 and 091); no row here is genomic in origin alone"
)
ANNOTATION_REF = (
    "Ensembl VEP REST (AlphaMissense, SpliceAI, exon numbering) -> "
    "warehouse.it2_insilico_annotations; gnomAD v2 co-occurrence; ClinVar via VEP"
)
ANNOTATION_TRANSFORM = (
    "public annotation supplies almost all of the weight: the callset supplies which "
    "alleles exist, and every lane but FILTER is read from a public source"
)
TOOL = "mva-warehouse pg-load-it2-step4"


@dataclass(frozen=True)
class Loaded:
    """One table after loading: what it is called and how many rows arrived."""

    table: str
    rows: int
    source: Path


def _create(connection, schema: str, table: str, columns: tuple[tuple[str, str], ...]) -> str:
    """Replace the table: rebuilding from the TSV is the only way it is ever written, so a
    partial old copy left behind would be a silent mixture of two runs."""
    qualified = f"{ALIAS}.{safe_identifier(schema)}.{safe_identifier(table)}"
    body = ", ".join(f'"{name}" {sql_type}' for name, sql_type in columns)
    connection.execute(f"DROP TABLE IF EXISTS {qualified}")
    connection.execute(f"CREATE TABLE {qualified} ({body})")
    return qualified


def _load_tsv(
    connection, schema: str, table: str, path: Path, columns: tuple[tuple[str, str], ...]
) -> int:
    qualified = _create(connection, schema, table, columns)
    names = ", ".join(f'"{name}"' for name, _ in columns)
    casts = ", ".join(f"CAST(NULLIF(\"{name}\", '') AS {sql_type})" for name, sql_type in columns)
    connection.execute(
        f"INSERT INTO {qualified} ({names}) "
        # ``quote`` explicit, never sniffed — the step-3 defect that turned every empty
        # field into two literal quote marks and moved a headline rate from 0.91 to 0.34.
        f"SELECT {casts} FROM read_csv(?, delim='\t', header=true, all_varchar=true, "
        f"quote='\"', escape='\"')",
        [str(path)],
    )
    counted = connection.execute(f"SELECT count(*) FROM {qualified}").fetchone()
    return int((counted or [0])[0])


def load(connection, *, schema: str, result_schema: str, out_dir: Path) -> list[Loaded]:
    """Load every step-4 table present in ``out_dir``, and record its lineage.

    A table whose TSV is absent is skipped rather than created empty: an empty table and a
    stage that did not run look identical in SQL, and only one of them is a result.
    """
    manifest_path = out_dir / "ranking.json"
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    )
    version = " ".join(
        f"{name}={manifest.get(key, '')}"
        for name, key in (
            ("alleles", "alleles"),
            ("hypotheses", "hypotheses"),
            ("genes", "genes_scored"),
            ("prior", "prior"),
        )
    )
    lineage.ensure_tables(connection, schema)

    loaded: list[Loaded] = []
    for table, columns in SCHEMAS.items():
        path = out_dir / "tables" / f"{table}.tsv"
        if not path.exists():
            continue
        rows = _load_tsv(connection, result_schema, table, path, columns)
        loaded.append(Loaded(table=table, rows=rows, source=path))
        for kind, ref, transform in (
            ("derived", CALLSET_REF, TRANSFORMS[table]),
            ("clinical", CLINICAL_REF, CLINICAL_TRANSFORM),
            ("api", ANNOTATION_REF, ANNOTATION_TRANSFORM),
        ):
            lineage.record(
                connection,
                schema,
                target_schema=result_schema,
                target_table=table,
                target_rows=rows,
                source_kind=kind,
                source_ref=ref,
                source_version=version if kind == "derived" else "",
                transform=transform,
                tool=TOOL,
                notes="no hard filter: every gene in the callset is scored"
                if kind == "derived"
                else "",
            )
    return loaded
