"""Load iteration 2's step-2 tables into the warehouse, with their lineage.

The shape is step 1's (:mod:`mva.warehouse.it2_tables`) and for the same reason: the work
that produced these rows is not SQL — it is a k-mer sweep, an aligner, four callers and a
phaser — so this module does the honest part, which is putting the rows where SQL and the
dashboard can read them and recording where each one came from.

**Every table here names both of the case's inputs.** The reads are one; the other is the
clinical document, because the *regions* these rows describe were chosen by ranking the
child's eight HPO terms (entry 084) and nothing else. A depth table that named only the
FASTQ would let a reader assume the gene list was genomic in origin. It was not.

**The bait density table is not decoration.** The off-target gate failed at 8.79 %
(entry 085), and the per-gene density is what the gate was actually proxying for, so it
travels in the warehouse beside the calls rather than staying in a build directory — every
per-gene claim step 2 makes is read against it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from . import lineage
from .postgres import ALIAS, safe_identifier

#: One row per table: the columns, written out rather than sniffed, because these schemas
#: are a promise the pair SQL and the dashboard both read.
SCHEMAS: dict[str, tuple[tuple[str, str], ...]] = {
    "it2_bait_qc": (
        ("stage", "VARCHAR"),
        ("metric", "VARCHAR"),
        ("value", "DOUBLE"),
        ("note", "VARCHAR"),
    ),
    "it2_bait_density": (
        ("symbol", "VARCHAR"),
        ("tier", "VARCHAR"),
        ("bases", "BIGINT"),
        ("windows", "BIGINT"),
        ("surviving", "BIGINT"),
        ("density", "DOUBLE"),
        ("lost", "DOUBLE"),
    ),
    "it2_exon_depth": (
        ("chrom", "VARCHAR"),
        ("start", "BIGINT"),
        ("end", "BIGINT"),
        ("symbol", "VARCHAR"),
        ("mean_depth", "DOUBLE"),
    ),
    "it2_read_alleles": (
        ("caller", "VARCHAR"),
        ("chrom", "VARCHAR"),
        ("pos", "BIGINT"),
        ("ref", "VARCHAR"),
        ("alt", "VARCHAR"),
        ("genotype", "VARCHAR"),
        ("filters", "VARCHAR"),
        ("depth", "INTEGER"),
        ("ref_depth", "INTEGER"),
        ("alt_depth", "INTEGER"),
        ("is_het", "BOOLEAN"),
        ("is_hom_alt", "BOOLEAN"),
        ("vaf", "DOUBLE"),
        ("phase_set", "VARCHAR"),
    ),
    "it2_sv_calls": (
        ("caller", "VARCHAR"),
        ("method_class", "VARCHAR"),
        ("chrom", "VARCHAR"),
        ("pos", "BIGINT"),
        ("end_pos", "BIGINT"),
        ("sv_type", "VARCHAR"),
        ("sv_len", "BIGINT"),
        ("filters", "VARCHAR"),
        ("genotype", "VARCHAR"),
        ("bait_edge", "BOOLEAN"),
        ("precision_prior", "DOUBLE"),
    ),
    "it2_phase_blocks": (
        ("chrom", "VARCHAR"),
        ("start", "BIGINT"),
        ("end", "BIGINT"),
        ("variants", "INTEGER"),
    ),
}

#: What each table is, in one sentence, for the lineage row's ``transform`` field.
TRANSFORMS: dict[str, str] = {
    "it2_bait_qc": (
        "the bait pass funnel: bases and k-mers cut, k-mers dropped as repeated, reads "
        "scanned and matched, fragments recovered (mva.reads.baitjob)"
    ),
    "it2_bait_density": (
        "surviving unique k-mers per base per gene after the genome-wide uniqueness pass "
        "(mva.kmer.bait.profile) — what the failed off-target gate was proxying for"
    ),
    "it2_exon_depth": (
        "mean read depth over each merged baited interval, MAPQ>=20 (mosdepth via "
        "mva.calling.coverage)"
    ),
    "it2_read_alleles": (
        "small-variant calls from two callers of disjoint model class (freebayes; "
        "bcftools call -m), normalised with bcftools norm -m -both -f, unfiltered "
        "(mva.calling.smallvars)"
    ),
    "it2_sv_calls": (
        "structural-variant calls from two method classes (delly: read-pair/split-read; "
        "dysgu: local assembly), with the bait-edge flag and Kosugi 2019's type-specific "
        "precision prior (mva.calling.sv)"
    ),
    "it2_phase_blocks": (
        "read-backed phase blocks, grouped by the PS field of the phased callset "
        "(WhatsHap via mva.calling.phase)"
    ),
}


@dataclass(frozen=True)
class Loaded:
    """One table after loading: what it is called and how many rows arrived."""

    table: str
    rows: int
    source: Path


def _create(connection, schema: str, table: str, columns: tuple[tuple[str, str], ...]) -> str:
    """Replace the table. Rebuilding from the TSV is the only way it is written, so a
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
        f"SELECT {casts} FROM read_csv(?, delim='\t', header=true, all_varchar=true)",
        [str(path)],
    )
    counted = connection.execute(f"SELECT count(*) FROM {qualified}").fetchone()
    return int((counted or [0])[0])


def load(connection, *, schema: str, result_schema: str, out_dir: Path) -> list[Loaded]:
    """Load every step-2 table present in ``out_dir``, and record its lineage.

    Tables whose TSV is absent are skipped rather than created empty: an empty table and a
    stage that did not run look identical in SQL, and only one of them is a result.
    """
    manifest = json.loads((out_dir / "provenance.json").read_text(encoding="utf-8"))
    lineage.ensure_tables(connection, schema)
    clinical = manifest.get("inputs", {}).get("targets", {}).get("produced_by", "step 1")

    loaded: list[Loaded] = []
    for table, columns in SCHEMAS.items():
        path = out_dir / "tables" / f"{table}.tsv"
        if not path.exists():
            continue
        rows = _load_tsv(connection, result_schema, table, path, columns)
        loaded.append(Loaded(table=table, rows=rows, source=path))
        lineage.record(
            connection,
            schema,
            target_schema=result_schema,
            target_table=table,
            target_rows=rows,
            source_kind="object",
            source_ref="s3://mva/reads (1,071,835,104 reads) + s3://mva/source (FASTQ delivery)",
            source_version=str(manifest.get("code_version", "")),
            transform=TRANSFORMS[table],
            tool="mva-warehouse pg-load-it2-step2",
            notes=f"regions chosen by the step-1 target set ({clinical})",
        )
        lineage.record(
            connection,
            schema,
            target_schema=result_schema,
            target_table=table,
            target_rows=rows,
            source_kind="clinical",
            source_ref="ressources/hackathon-rules/Challenge_Clinical_Phenotype_1.md",
            transform=(
                "the intervals these rows describe were chosen by ranking the proband's "
                "HPO terms with the DNA unread (entry 084); no row here is genomic in "
                "origin alone"
            ),
            tool="mva-warehouse pg-load-it2-step2",
        )
    return loaded
