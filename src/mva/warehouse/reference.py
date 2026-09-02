"""The three public reference tables, and how they are typed on the way in.

``ressources/reference/`` holds non-patient, committable comparison data: gnomAD's
per-gene constraint metrics, the ClinVar records inside the candidate panel, and a
hand-curated table of what a healthy human callset is *expected* to look like. See that
directory's ``README.md`` for provenance, licences and the ten gotchas measured in the
files.

These are staged by the same code path as the delivered profile — one
:class:`~mva.warehouse.catalog.Dataset` each, normalised and written to Parquet by
:mod:`mva.warehouse.stage`. Two things make them different from a profile file, and both
are carried on the dataset rather than in a second staging path:

* **They live outside the profile directory**, so each declares its own ``root``.
* **Their types cannot be sniffed.** ``NA`` is gnomAD's null, so a sniffer reads every
  constraint metric as text; ``chrom`` arrives ``chr``-prefixed where the rest of this
  warehouse is bare; and ClinVar's ``ref`` runs to 7,027 characters, which no sample-based
  width guess should be allowed to truncate. Each therefore declares a ``transform``: the
  file is read all-VARCHAR and every cast is written down.

The lineage edges are declared here too, beside the specs, so a table cannot arrive in the
database without the upstream URL and release that produced it.
"""

from pathlib import Path

from .catalog import Dataset

#: Where the committed reference tables live, relative to the repository root.
DEFAULT_ROOT = Path("ressources/reference")

#: gnomAD's null. Written literally in the file, in every column, including ``gene``.
NA = "'NA'"


def _nullable(column: str) -> str:
    """A text column with gnomAD's ``NA`` sentinel turned into a real null."""
    return f"nullif({column}, {NA})"


def _number(column: str, sql_type: str) -> str:
    """One gnomAD numeric column: ``NA`` to null, then an explicit cast.

    ``TRY_CAST`` rather than ``CAST`` so a single malformed cell in an 18,314-row public
    file becomes one null instead of a failed staging run — the file is re-downloaded from
    upstream, not edited, so there is nothing to fix locally.
    """
    return f"TRY_CAST({_nullable(column)} AS {sql_type}) AS {column}"


#: gnomAD constraint: 6 integer counts, 12 real-valued metrics, the rest text.
_GNOMAD_INTEGERS = (
    "cds_length",
    "num_coding_exons",
    "lof_obs",
    "loeuf_decile",
    "mis_obs",
    "syn_obs",
)
_GNOMAD_DOUBLES = (
    "lof_exp",
    "oe_lof",
    "oe_lof_lower",
    "loeuf",
    "pli",
    "lof_z",
    "mis_exp",
    "oe_mis",
    "mis_z",
    "syn_exp",
    "oe_syn",
    "syn_z",
)

GNOMAD_TRANSFORM = ", ".join(
    [
        f"{_nullable('gene')} AS gene",
        f"{_nullable('ensembl_gene_id')} AS ensembl_gene_id",
        f"{_nullable('transcript')} AS transcript",
        # The repository rule is bare contigs, owned by `Variant.from_vcf` /
        # `to_vcf_contig`. gnomAD ships `chr19`; a prefixed contig matched against the bare
        # callset returns zero rows, which is indistinguishable from a real absence.
        f"replace({_nullable('chrom')}, 'chr', '') AS chrom",
        f"TRY_CAST({_nullable('mane_select')} AS BOOLEAN) AS mane_select",
        f"TRY_CAST({_nullable('canonical')} AS BOOLEAN) AS canonical",
        f"{_nullable('transcript_type')} AS transcript_type",
        *[_number(name, "BIGINT") for name in _GNOMAD_INTEGERS],
        *[_number(name, "DOUBLE") for name in _GNOMAD_DOUBLES],
        # An empty `constraint_flags` means "gnomAD raised no caveat", which is information;
        # it is normalised to null so a reader tests IS NULL rather than = ''.
        "nullif(nullif(constraint_flags, 'NA'), '') AS constraint_flags",
    ]
)

#: ClinVar: two integers, everything else unbounded text with '' meaning absent.
_CLINVAR_TEXT = ("chrom", "ref", "alt", "rsid", "gene", "clnsig", "clnrevstat", "condition")

CLINVAR_TRANSFORM = ", ".join(
    [
        *[f"nullif({name}, '') AS {name}" for name in _CLINVAR_TEXT],
        "TRY_CAST(pos AS BIGINT) AS pos",
        # The stable ClinVar key. The rsid is not: 4,442 of these rows have none.
        "TRY_CAST(variation_id AS BIGINT) AS variation_id",
    ]
)

QC_NORMS_TRANSFORM = ", ".join(
    [
        "metric",
        "TRY_CAST(expected_low AS DOUBLE) AS expected_low",
        "TRY_CAST(expected_high AS DOUBLE) AS expected_high",
        "unit",
        "applies_to",
        "source",
        "url",
        "basis",
    ]
)


def datasets(root: Path | None = None) -> list[Dataset]:
    """The three reference tables as staging specs, rooted at ``root``."""
    where = str(root or DEFAULT_ROOT)
    return [
        Dataset(
            table="gnomad_constraint",
            source="gnomad_constraint.tsv",
            root=where,
            transform=GNOMAD_TRANSFORM,
            description="gnomAD v4.1 per-gene constraint: how much loss-of-function, "
            "missense and synonymous variation healthy people carry against "
            "what a mutation model expects. Autosomes only. Bare contigs.",
        ),
        Dataset(
            table="clinvar_panel",
            source="clinvar_panel.tsv",
            root=where,
            transform=CLINVAR_TRANSFORM,
            description="ClinVar germline classifications inside the candidate panel's "
            "eight genes plus 20 kb of padding. Multi-value cells are "
            "pipe-packed; an absent clnsig means no germline classification.",
        ),
        Dataset(
            table="qc_norms",
            source="qc_norms.tsv",
            root=where,
            transform=QC_NORMS_TRANSFORM,
            description="What a healthy human callset is expected to look like: one "
            "cited range per QC metric, with the publication it came from.",
        ),
    ]


#: One lineage edge per reference table: what it was extracted from, and by which rule.
#: The upstream URLs and releases are the ones recorded in
#: ``ressources/reference/README.md``.
LINEAGE: dict[str, dict[str, str]] = {
    "gnomad_constraint": {
        "source_version": "gnomAD v4.1 constraint metrics, upstream Last-Modified "
        "2024-04-18, downloaded 2026-08-31",
        "source_sha256": "68d8abdb7fc48f570869b02dfaa74b9fecaece7fcc5f301ddca40ec1ce12da00",
        "transform": "tools/build_reference_data.py gnomad: Ensembl canonical AND "
        "protein_coding rows only, 26 columns kept; staged with NULLIF(col,"
        "'NA') and the chr prefix stripped from chrom",
        "notes": "upstream https://storage.googleapis.com/gcp-public-data--gnomad/"
        "release/4.1/constraint/gnomad.v4.1.constraint_metrics.tsv (CC0); "
        "autosomes only, so a missing gene is not an unconstrained gene",
    },
    "clinvar_panel": {
        "source_version": "ClinVar GRCh38 VCF, fileDate 2026-08-29, 4,468,152 records "
        "genome-wide, downloaded 2026-08-31",
        "transform": "tools/build_reference_data.py clinvar: bcftools query -r over the "
        "8 intervals of ressources/data-profile/mva_panel_grch38.bed "
        "(each gene +/- 20 kb); staged with '' normalised to NULL",
        "notes": "upstream https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/"
        "clinvar.vcf.gz; cite PMID 29165669; not for direct diagnostic use "
        "without review by a genetics professional",
    },
    "qc_norms": {
        "source_version": "hand-curated 2026-08-31, no generator",
        "transform": "expected_low and expected_high cast to DOUBLE; every other column "
        "kept as text",
        "notes": "every row carries its own PMID/DOI in `source` and a paraphrase of the "
        "sentence the number came from in `basis`; a metric with no citable "
        "range is absent rather than guessed",
    },
}


def record_lineage(settings, landed) -> list[str]:
    """Append a lineage edge for each reference table present in ``landed``.

    Called by ``pg-ingest`` rather than being a separate verb, for the same reason
    ``pg-derive`` records its own edges: lineage that depends on someone remembering a
    second command is lineage that will be missing.
    """
    from . import lineage
    from .postgres import attached

    wanted = [item for item in landed if item.table in LINEAGE]
    if not wanted:
        return []
    with attached(settings) as connection:
        lineage.ensure_tables(connection, settings.schema)
        for item in wanted:
            spec = LINEAGE[item.table]
            lineage.record(
                connection,
                settings.schema,
                target_schema=item.schema,
                target_table=item.table,
                target_rows=item.rows,
                source_kind="file",
                source_ref=str(DEFAULT_ROOT / f"{item.table}.tsv"),
                source_version=spec["source_version"],
                source_sha256=spec.get("source_sha256", ""),
                transform=spec["transform"],
                tool="mva-warehouse pg-ingest",
                notes=spec["notes"],
            )
    return [item.table for item in wanted]
