#!/usr/bin/env python3
"""Build ``ressources/reference/coding_regions.tsv`` from an Ensembl GTF.

The callset has no annotation, and annotating five million alleles through a REST API is
not a realistic pass. What *is* realistic is annotating every allele that can change a
protein: the coding sequence (CDS, the exon bases that are translated) plus a short splice
flank on each side. That is about 1 % of the genome, so a genome-wide coding scan is a
few tens of thousands of alleles — a few hundred VEP requests.

This tool turns the GTF (Ensembl's gene-model file: one row per exon, CDS, transcript…)
into one row per **merged coding interval per gene**:

* only ``CDS`` and ``stop_codon`` rows of ``protein_coding`` transcripts are kept;
* each is widened by ``--flank`` bases (default 8, which covers the canonical ±2 splice
  sites and VEP's splice-region window on the intronic side);
* overlapping intervals of the same gene are merged, so an allele joins one row per gene
  it touches rather than one per transcript;
* contigs are written **bare** (``15``, not ``chr15``), the way the delivered VCF spells
  them, and are restricted to the 25 canonical contigs.

It is case-agnostic: nothing here knows the panel, the proband, or the phenotype. A
provenance manifest is written beside the TSV on every run, never by hand — see
``docs/iteration1/step-2/methodology/069``.

Usage::

    uv run python tools/build_coding_regions.py --gtf <scratch>/Homo_sapiens.GRCh38.116.gtf.gz
    uv run python tools/build_coding_regions.py --gtf ... --canonical-only   # smaller set
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

from mva.viz import referencemanifest, refprovenance

REFERENCE = Path("ressources/reference")
DEFAULT_OUT = REFERENCE / "coding_regions.tsv"
DEFAULT_RELEASE = "116"
ENSEMBL_URL = (
    "https://ftp.ensembl.org/pub/release-{release}/gtf/homo_sapiens/"
    "Homo_sapiens.GRCh38.{release}.gtf.gz"
)
CANONICAL_CONTIGS = (*(str(n) for n in range(1, 23)), "X", "Y", "MT")
LICENCE = (
    "Ensembl gene annotation is free of restrictions for any use; see "
    "https://www.ensembl.org/info/about/legal/disclaimer.html. Cite Ensembl 2025 "
    "(PMID 39656687) for the gene models."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--gtf", type=Path, required=True, help="Ensembl GTF (.gtf or .gtf.gz)")
    parser.add_argument("--release", default=DEFAULT_RELEASE, help="Ensembl release (manifest)")
    parser.add_argument("--flank", type=int, default=8, help="bases added on each side of a CDS")
    parser.add_argument(
        "--canonical-only",
        action="store_true",
        help="keep only transcripts tagged Ensembl_canonical (smaller, may miss exons)",
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def load_cds(connection: duckdb.DuckDBPyConnection, gtf: Path, canonical_only: bool) -> int:
    """Read the CDS/stop-codon rows of protein-coding transcripts into ``cds``."""
    tag = "AND attribute LIKE '%tag \"Ensembl_canonical\"%'" if canonical_only else ""
    contigs = ", ".join(f"'{c}'" for c in CANONICAL_CONTIGS)
    connection.execute(
        f"""
        CREATE TABLE cds AS
        SELECT seqname                                                        AS chrom,
               start,
               "end",
               regexp_extract(attribute, 'gene_id "([^"]+)"', 1)              AS gene_id,
               regexp_extract(attribute, 'gene_name "([^"]+)"', 1)            AS gene,
               regexp_extract(attribute, 'transcript_id "([^"]+)"', 1)        AS transcript_id
        FROM read_csv(?, auto_detect = false, delim = '\t', header = false,
                      comment = '#', quote = '', escape = '',
                      columns = {{'seqname': 'VARCHAR', 'source': 'VARCHAR',
                                 'feature': 'VARCHAR', 'start': 'BIGINT', 'end': 'BIGINT',
                                 'score': 'VARCHAR', 'strand': 'VARCHAR', 'frame': 'VARCHAR',
                                 'attribute': 'VARCHAR'}})
        WHERE feature IN ('CDS', 'stop_codon')
          AND attribute LIKE '%transcript_biotype "protein_coding"%'
          AND seqname IN ({contigs})
          {tag}
        """,
        [str(gtf)],
    )
    row = connection.execute("SELECT count(*) FROM cds").fetchone()
    return int(row[0]) if row else 0


MERGE_SQL = """
    WITH widened AS (
        SELECT chrom, gene_id,
               -- gene_name is absent on a few novel genes; fall back to the stable id so
               -- the row still names something a reader can look up.
               coalesce(nullif(gene, ''), gene_id)          AS gene,
               greatest(start - {flank}, 1)                 AS s,
               "end" + {flank}                              AS e,
               transcript_id
        FROM cds
    ),
    ordered AS (
        SELECT *,
               max(e) OVER (PARTITION BY gene_id ORDER BY s, e
                            ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS prev_max
        FROM widened
    ),
    islands AS (
        -- Gaps-and-islands: a new island starts wherever this interval begins after
        -- everything before it has ended. Adjacent (s = prev_max + 1) is merged too.
        SELECT *,
               sum(CASE WHEN prev_max IS NULL OR s > prev_max + 1 THEN 1 ELSE 0 END)
                   OVER (PARTITION BY gene_id ORDER BY s, e ROWS UNBOUNDED PRECEDING) AS island
        FROM ordered
    )
    SELECT chrom,
           min(s)                                AS start,
           max(e)                                AS "end",
           any_value(gene)                       AS gene,
           gene_id,
           count(*)                              AS n_cds,
           count(DISTINCT transcript_id)         AS n_transcripts
    FROM islands
    GROUP BY chrom, gene_id, island
    ORDER BY CASE WHEN chrom = 'X' THEN 23 WHEN chrom = 'Y' THEN 24
                  WHEN chrom = 'MT' THEN 25 ELSE CAST(chrom AS INTEGER) END,
             start, "end", gene_id
"""


def merge(connection: duckdb.DuckDBPyConnection, flank: int, out: Path) -> dict:
    """Merge the widened intervals per gene and write the TSV. Returns the counts."""
    connection.execute(f"CREATE TABLE regions AS {MERGE_SQL.format(flank=flank)}")
    out.parent.mkdir(parents=True, exist_ok=True)
    connection.execute(
        f"COPY regions TO '{out}' (FORMAT csv, DELIMITER '\t', HEADER true, QUOTE '')"
    )
    row = connection.execute(
        'SELECT count(*), count(DISTINCT gene_id), sum("end" - start + 1) FROM regions'
    ).fetchone()
    rows, genes, bases = row if row else (0, 0, 0)
    return {"rows": rows, "genes": genes, "bases": bases}


def build_manifest(args: argparse.Namespace, counts: dict, cds_rows: int) -> dict:
    """The provenance record: what was read, how it was cut, what came out."""
    sha, size = refprovenance.digest(args.gtf)
    scope = "Ensembl_canonical transcripts only" if args.canonical_only else "every transcript"
    return {
        "name": "coding_regions",
        "built_at": refprovenance.now(),
        "built_by": "tools/build_coding_regions.py",
        "code_version": refprovenance.code_version(),
        "code_version_note": (
            "the commit at build time, which precedes the commit that lands this file"
        ),
        "method": (
            f"CDS and stop_codon rows of protein_coding transcripts ({scope}) on the 25 "
            f"canonical contigs, each widened by {args.flank} bp on both sides, then merged "
            "per gene_id where they overlap or touch (gaps-and-islands over a running "
            "max). One row per merged interval per gene: an allele inside two overlapping "
            "genes joins twice, once per gene, which is the honest shape. Contigs are "
            "written bare to match the delivered VCF. n_cds counts the source rows in the "
            f"island; n_transcripts the distinct transcripts. {cds_rows:,} CDS rows in, "
            f"{counts['rows']:,} intervals out covering {counts['bases']:,} bp."
        ),
        "inputs": [
            {
                "name": args.gtf.name,
                "url": ENSEMBL_URL.format(release=args.release),
                "release": args.release,
                "sha256": sha,
                "bytes": size,
                "role": "the gene models: which bases are coding, per transcript",
            }
        ],
        "outputs": [_output(args.out, counts["rows"])],
        "licence": LICENCE,
        "patient_data": (
            "none. Public gene models only: a contig, two coordinates, a gene symbol and "
            "a stable id per row. Nothing here was derived from the callset."
        ),
        "note": (
            f"{counts['rows']:,} merged coding intervals over {counts['genes']:,} "
            f"protein-coding genes, ±{args.flank} bp splice flank. Deep-intronic and UTR "
            "variants fall outside these intervals by construction; a scan restricted to "
            "this table cannot see them."
        ),
    }


def _output(path: Path, rows: int) -> dict:
    sha, size = refprovenance.digest(path)
    return {
        "path": referencemanifest.repo_relative(path),
        "sha256": sha,
        "bytes": size,
        "rows": rows,
    }


def main() -> None:
    args = parse_args()
    if not args.gtf.is_file():
        sys.exit(f"GTF not found: {args.gtf}")
    connection = duckdb.connect()
    cds_rows = load_cds(connection, args.gtf, args.canonical_only)
    scope = "canonical only" if args.canonical_only else "all transcripts"
    print(f"cds rows  {cds_rows:,}  ({scope})")
    counts = merge(connection, args.flank, args.out)
    print(
        f"wrote     {args.out}  {counts['rows']:,} intervals, {counts['genes']:,} genes, "
        f"{counts['bases']:,} bp  (flank ±{args.flank})"
    )
    manifest = build_manifest(args, counts, cds_rows)
    path = referencemanifest.write(manifest, args.out.with_suffix(".provenance.json"))
    print(f"manifest  {path}  (sha256 {manifest['outputs'][0]['sha256'][:8]}…)")


if __name__ == "__main__":
    main()
