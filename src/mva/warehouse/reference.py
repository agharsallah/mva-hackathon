"""The five public reference tables, and how they are typed on the way in.

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

import json
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

#: The two HPO tables. Both are all-numeric-or-text with no sentinel of their own - the
#: builder writes real values or empty cells - so the casts are plain and there is no NULLIF
#: layer of the kind gnomAD's 'NA' forces.
HPO_TERM_IC_TRANSFORM = ", ".join(
    [
        "hpo_id",
        "name",
        "TRY_CAST(depth AS INTEGER) AS depth",
        "TRY_CAST(gene_count AS INTEGER) AS gene_count",
        "TRY_CAST(information_content AS DOUBLE) AS information_content",
    ]
)

HPO_GENE_SCORES_TRANSFORM = ", ".join(
    [
        "term_set",
        "TRY_CAST(genes_considered AS INTEGER) AS genes_considered",
        "gene_symbol",
        # Entrez ids stay TEXT. They are identifiers, not quantities: nothing is ever
        # summed or compared numerically, and the newer ids run past nine digits.
        "NULLIF(entrez_id, '') AS entrez_id",
        "TRY_CAST(rank AS INTEGER) AS rank",
        "TRY_CAST(score AS DOUBLE) AS score",
        "TRY_CAST(forward AS DOUBLE) AS forward",
        "TRY_CAST(reverse AS DOUBLE) AS reverse",
        "TRY_CAST(curated_terms AS INTEGER) AS curated_terms",
        "NULLIF(best_term, '') AS best_term",
        "NULLIF(best_common_ancestor, '') AS best_common_ancestor",
        "TRY_CAST(NULLIF(best_ic, '') AS DOUBLE) AS best_ic",
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
    """The five reference tables as staging specs, rooted at ``root``."""
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
        Dataset(
            table="hpo_term_ic",
            source="hpo_term_ic.tsv",
            root=where,
            transform=HPO_TERM_IC_TRANSFORM,
            description="Every HPO term with its depth, how many genes are curated to "
            "cause it, and its information content - the measured rarity that "
            "decides how much a phenotype match is worth. A term no gene "
            "carries scores 0.0, which is an absence of curation and not a "
            "measurement of commonness.",
        ),
        Dataset(
            table="hpo_gene_scores",
            source="hpo_gene_scores.tsv",
            root=where,
            transform=HPO_GENE_SCORES_TRANSFORM,
            description="Where every curated gene ranked against the child's HPO terms, "
            "for both term sets - all eight delivered terms, and the seven "
            "that describe the child rather than the parents. Produced "
            "without reading the callset or the candidate panel.",
        ),
    ]


#: The provenance sidecar ``tools/build_phenotype_data.py`` writes beside the HPO tables.
PROVENANCE_FILE = "hpo_provenance.json"


def read_provenance(root: Path | None = None) -> dict:
    """The HPO build manifest, or ``{}`` when it has never been written.

    Empty rather than raising: a checkout that has not run the builder has no HPO tables to
    stage either, so there is nothing for a missing manifest to break.
    """
    path = (Path(root) if root else DEFAULT_ROOT) / PROVENANCE_FILE
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _hpo_lineage(manifest: dict) -> dict[str, dict[str, str]]:
    """Build the HPO lineage specs from the manifest the same run produced.

    **Why these two are derived and the other three are literals.** gnomAD and ClinVar are
    fetched from versioned URLs whose content is fixed for a given release, so a hard-coded
    digest stays true. HPO publishes monthly and its PURLs always serve the *current*
    release — so a literal release and digest here would silently become a lie the first
    time anyone re-ran the builder, while still reading like provenance. Deriving them from
    a manifest written by the same run makes that failure impossible rather than merely
    unlikely.

    Every input digest is folded into ``source_version``, because a score is a function of
    *both* upstream files and disagreeing on either one invalidates the table.
    """
    if not manifest:
        return {}
    release = str(manifest.get("release", "unknown"))
    inputs = manifest.get("inputs") or []
    by_name = {str(item.get("name")): item for item in inputs if isinstance(item, dict)}
    obo = by_name.get("hp.obo", {})
    genes = by_name.get("genes_to_phenotype.txt", {})

    built = str(manifest.get("built_at", "unknown"))
    code = str(manifest.get("code_version", "unknown"))
    method = str(manifest.get("method", ""))
    licence = str(manifest.get("licence", ""))

    def version(item: dict, extra: str) -> str:
        return (
            f"HPO release {release}, {item.get('name', '?')} "
            f"{item.get('bytes', 0):,} bytes, {extra}, built {built}"
        )

    shared_notes = f"upstream {obo.get('url', '?')} and {genes.get('url', '?')}; {licence}"
    disclaimer = (
        "NOT Exomiser output: this is a reimplementation of hiPHIVE's human-only "
        f"phenotype path. {manifest.get('method_citation', '')}"
    )

    return {
        "hpo_term_ic": {
            "source_version": version(obo, f"{obo.get('terms', 0):,} terms"),
            "source_sha256": str(obo.get("sha256", "")),
            "transform": (
                f"tools/build_phenotype_data.py at {code}: hp.obo parsed to a DAG; per-term "
                "counts taken over the ancestor closure of each gene's own term set "
                "(distinct genes, never a sum of per-term counts) and turned into "
                f"-log(count/{genes.get('annotated_genes', 0)}); obsolete terms excluded"
            ),
            "notes": (
                f"{shared_notes}. Information content depends on the annotation corpus, so "
                f"it moves with each monthly release; 0.0 means no gene carries the term, "
                f"which is an absence of curation and not a measurement of commonness"
            ),
        },
        "hpo_gene_scores": {
            "source_version": (
                f"{version(genes, str(genes.get('annotated_genes', 0)) + ' annotated genes')}; "
                f"ontology sha256 {str(obo.get('sha256', ''))[:12]}"
            ),
            "source_sha256": str(genes.get("sha256", "")),
            "transform": (
                f"tools/build_phenotype_data.py at {code}: {method} "
                f"Known defect handled: {genes.get('known_defect', 'none recorded')}"
            ),
            "notes": (
                f"{shared_notes}. {disclaimer} Query terms are owned by "
                "src/mva/phenotype/terms.py; both term sets are in the table, distinguished "
                "by term_set. No patient data of any kind is an input"
            ),
        },
    }


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


def lineage_for(table: str, root: Path | None = None) -> dict[str, str] | None:
    """The lineage spec for one reference table, HPO's derived entries included.

    One lookup for every caller, so nobody has to know that three specs are literals and
    two are read off a manifest.
    """
    literal = LINEAGE.get(table)
    if literal is not None:
        return literal
    return _hpo_lineage(read_provenance(root)).get(table)


def record_lineage(settings, landed) -> list[str]:
    """Append a lineage edge for each reference table present in ``landed``.

    Called by ``pg-ingest`` rather than being a separate verb, for the same reason
    ``pg-derive`` records its own edges: lineage that depends on someone remembering a
    second command is lineage that will be missing.
    """
    from . import lineage
    from .postgres import attached

    specs = {item.table: lineage_for(item.table) for item in landed}
    wanted = [item for item in landed if specs.get(item.table)]
    if not wanted:
        return []
    with attached(settings) as connection:
        lineage.ensure_tables(connection, settings.schema)
        for item in wanted:
            spec = specs[item.table]
            assert spec is not None  # filtered above; narrows for the type checker
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
