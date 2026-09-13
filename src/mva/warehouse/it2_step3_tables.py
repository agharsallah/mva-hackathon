"""Load iteration 2's step-3 tables into the warehouse, with their lineage.

Same shape as :mod:`mva.warehouse.it2_step2_tables`, and for the same reason: the work that
produced these rows is not SQL — it is a probe design, a genome pass, a k-mer count and a
fitted negative binomial — so this module does the honest part, which is putting the rows
where SQL and the dashboard can read them and recording where each one came from.

**Every table here names both of the case's inputs.** The reads are one; the clinical
document is the other, because the *genes* these rows describe were chosen by ranking the
child's eight HPO terms and nothing else (entry 084). A genotype table naming only the FASTQ
would let a reader assume the gene list was genomic in origin. It was not.

**Not one of these tables carries a coordinate or a sequence.** A genotype is reported as a
gene, an ordinal within that gene, and counts; a probe as how many were designed and how many
survived. An alternate k-mer spells a base this child carries and stays under ``build/``,
where ``tools/check_coordinates.py`` rule 4 backstops it.

**The MAPQ profile travels with the genotypes rather than living in a build directory.** It
is the gate that decides which genes step 3 may report on at all (entry 093), and a genotype
read without it is a number with its caveat left behind.
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
    "it2_mapq_profile": (
        ("symbol", "VARCHAR"),
        ("tier", "VARCHAR"),
        ("reads", "BIGINT"),
        ("mapq0", "BIGINT"),
        ("mapq0_fraction", "DOUBLE"),
        ("median_mapq", "DOUBLE"),
        ("mean_mapq", "DOUBLE"),
        ("bait_density", "DOUBLE"),
        ("sparse_bait", "BOOLEAN"),
        ("mapq_refused", "BOOLEAN"),
        ("reachable", "BOOLEAN"),
    ),
    "it2_kmer_probes": (
        ("symbol", "VARCHAR"),
        ("origin", "VARCHAR"),
        ("alleles", "BIGINT"),
        ("probes_designed", "BIGINT"),
        ("probes_kept", "BIGINT"),
        ("alleles_fully_probed", "BIGINT"),
        ("alleles_without_probe", "BIGINT"),
    ),
    "it2_kmer_calibration": (
        ("stage", "VARCHAR"),
        ("metric", "VARCHAR"),
        ("value", "DOUBLE"),
        ("note", "VARCHAR"),
    ),
    "it2_kmer_genotypes": (
        ("symbol", "VARCHAR"),
        ("tier", "VARCHAR"),
        ("origin", "VARCHAR"),
        ("allele_ordinal", "BIGINT"),
        ("novel", "BOOLEAN"),
        ("probes", "BIGINT"),
        ("probes_agreeing", "BIGINT"),
        ("ref_count", "BIGINT"),
        ("alt_count", "BIGINT"),
        ("call", "VARCHAR"),
        ("posterior", "DOUBLE"),
        ("caller_genotype", "VARCHAR"),
        ("confirms_caller", "BOOLEAN"),
        ("reachable", "BOOLEAN"),
    ),
    "it2_exon_cn": (
        ("symbol", "VARCHAR"),
        ("tier", "VARCHAR"),
        ("label", "VARCHAR"),
        ("exon_ordinal", "BIGINT"),
        ("surviving_kmers", "BIGINT"),
        ("pooled", "BOOLEAN"),
        ("median_count", "DOUBLE"),
        ("cn_local", "DOUBLE"),
        ("cn_genome_wide", "DOUBLE"),
        ("denominator_disagreement", "DOUBLE"),
        ("below_null_band", "BOOLEAN"),
    ),
    "it2_cn_null": (
        ("percentile", "DOUBLE"),
        ("low", "DOUBLE"),
        ("high", "DOUBLE"),
        ("median", "DOUBLE"),
        ("regions", "BIGINT"),
    ),
}

#: What each table is, in one sentence, for the lineage row's ``transform`` field.
TRANSFORMS: dict[str, str] = {
    "it2_mapq_profile": (
        "per-gene mapping-quality profile of the baited alignment and the reachability rule "
        "read off it — bait density below half the median, or over half the reads at MAPQ 0 "
        "(samtools view via mva.calling.mapq; entry 093). Replaces the retired "
        "off-target < 5% gate"
    ),
    "it2_kmer_probes": (
        "reference/alternate 31-mer pairs designed per allele and how many survived the "
        "genome-wide uniqueness filter on the *alternate* k-mer (mva.kmer.probes), "
        "aggregated per gene and allele source"
    ),
    "it2_kmer_calibration": (
        "the fitted negative-binomial genotype model and its quality checks: per-copy "
        "coverage from both sides of the heterozygous calibration markers, dispersion, "
        "variance-to-mean ratio, error rate and minimum count (mva.kmer.genotype)"
    ),
    "it2_kmer_genotypes": (
        "genotype per allele from k-mer counts over the recovered baited reads, with no "
        "aligner and no caller in the chain — posterior over hom-ref/het/hom-alt/no-call, "
        "probe agreement, and whether it confirms what step 2's callers said "
        "(mva.kmer.count + mva.kmer.genotype)"
    ),
    "it2_exon_cn": (
        "alignment-free copy number per exon where at least 300 unique k-mers survived and "
        "per gene where they did not, against a local flanking denominator and the "
        "genome-wide median, with the disagreement between them (mva.kmer.copynumber)"
    ),
    "it2_cn_null": (
        "the copy-number null band measured on this sample — what normal looks like at this "
        "depth with this bait, and the threshold every deletion claim is read against"
    ),
}

#: Read once and quoted in every lineage row, so the two inputs are named and not implied.
READS_REF = "s3://mva/reads (1,071,835,104 reads) -> build/it2/step-2/baited-reads.parquet"
CLINICAL_REF = "ressources/hackathon-rules/Challenge_Clinical_Phenotype_1.md"
CLINICAL_TRANSFORM = (
    "the genes these rows describe were chosen by ranking the proband's eight HPO terms "
    "with the DNA unread (entry 084); no row here is genomic in origin alone"
)
TOOL = "mva-warehouse pg-load-it2-step3"


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
        # ``quote`` is passed explicitly rather than sniffed. Polars writes an empty field
        # as a quoted empty string, and DuckDB's dialect sniffer infers the quote character
        # from the first rows — so whether `""` parses as an empty field or as two literal
        # quote marks depended on whether an early row happened to contain one. It silently
        # turned every empty string into a two-character value and made `col <> ''` true for
        # every row.
        f"SELECT {casts} FROM read_csv(?, delim='\t', header=true, all_varchar=true, "
        f"quote='\"', escape='\"')",
        [str(path)],
    )
    counted = connection.execute(f"SELECT count(*) FROM {qualified}").fetchone()
    return int((counted or [0])[0])


def load(connection, *, schema: str, result_schema: str, out_dir: Path) -> list[Loaded]:
    """Load every step-3 table present in ``out_dir``, and record its lineage.

    Tables whose TSV is absent are skipped rather than created empty: an empty table and a
    stage that did not run look identical in SQL, and only one of them is a result.
    """
    manifest_path = out_dir / "probes-summary.json"
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    )
    version = " ".join(
        f"{name}={manifest.get(key, '')}"
        for name, key in (("k", "k"), ("probes", "probes_requested"), ("seed", "seed"))
    )
    lineage.ensure_tables(connection, schema)

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
            source_ref=READS_REF,
            source_version=version,
            transform=TRANSFORMS[table],
            tool=TOOL,
            notes="counted with no aligner and no caller in the chain",
        )
        lineage.record(
            connection,
            schema,
            target_schema=result_schema,
            target_table=table,
            target_rows=rows,
            source_kind="clinical",
            source_ref=CLINICAL_REF,
            transform=CLINICAL_TRANSFORM,
            tool=TOOL,
        )
    return loaded


__all__ = ["SCHEMAS", "TRANSFORMS", "Loaded", "load"]
