"""Load iteration 2's step-5 knowledge tables into the warehouse, with their lineage.

Same shape as :mod:`mva.warehouse.it2_step4_tables`, and for the same reason: the rows are
produced by Python against public APIs — a publication count per allele, a matched-term
count per paper, a domain map, a pair of rankings — so this module's job is to put them
where SQL and the dashboard can read them, and to record where each one came from.

**Three inputs, and the third is the one that makes this step honest.** The callset is one;
the clinical document is another, because every anchor row is scored by how many of the
child's own seven terms a paper covers; and the **public literature and protein resources**
are the third — LitVar 2.0, PubTator 3.0, NCBI E-utilities, UniProt, InterPro and
AlphaFold DB. A knowledge table naming only the callset would let a reader assume the
evidence came out of this child's DNA. It did not: the DNA supplies which alleles and
genes to ask about, and everything else is somebody else's publication.

**No table here carries a coordinate, and none carries a residue.** An allele is named by
its consequence class and its dbSNP identifier; a protein position is recorded only as a
*fraction* of protein length, which is what ``tools/check_coordinates.py`` permits and what
the blind protocol requires. The residue numbers stay under ``build/``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from . import lineage
from .postgres import ALIAS, safe_identifier

__all__ = ["CALLSET_REF", "SCHEMAS", "TOOL", "Loaded", "load"]

#: One row per table: the columns, written out rather than sniffed, because these schemas
#: are a promise the analysis SQL and the dashboard both read.
SCHEMAS: dict[str, tuple[tuple[str, str], ...]] = {
    "it2_pub_alleles": (
        ("gene", "VARCHAR"),
        ("rsid", "VARCHAR"),
        ("consequence_class", "VARCHAR"),
        # -1 is "not asked": the allele has no dbSNP identifier, so a literature index
        # keyed on dbSNP could not have had an opinion. 0 would read as "asked, nobody
        # published", which is a different statement about a different allele.
        ("pmid_count", "BIGINT"),
        ("top_pmid", "VARCHAR"),
        ("clin_sig", "VARCHAR"),
        ("child_call", "VARCHAR"),
        ("child_posterior", "DOUBLE"),
        ("is_target", "BOOLEAN"),
        ("is_decoy", "BOOLEAN"),
        ("in_top_leaders", "BOOLEAN"),
    ),
    "it2_anchors": (
        ("gene", "VARCHAR"),
        ("pmid", "VARCHAR"),
        ("title", "VARCHAR"),
        ("journal", "VARCHAR"),
        ("year", "VARCHAR"),
        ("terms_matched", "BIGINT"),
        ("terms_total", "BIGINT"),
        ("matched_terms", "VARCHAR"),
        ("is_target", "BOOLEAN"),
        ("is_decoy", "BOOLEAN"),
        ("in_top_leaders", "BOOLEAN"),
    ),
    "it2_anchor_terms": (
        ("gene", "VARCHAR"),
        ("term_label", "VARCHAR"),
        ("papers", "BIGINT"),
        ("is_target", "BOOLEAN"),
        ("is_decoy", "BOOLEAN"),
    ),
    "it2_protein_domains": (
        ("gene", "VARCHAR"),
        ("uniprot", "VARCHAR"),
        ("protein_length", "BIGINT"),
        ("interpro", "VARCHAR"),
        ("domain_name", "VARCHAR"),
        ("entry_type", "VARCHAR"),
        ("start_fraction", "DOUBLE"),
        ("end_fraction", "DOUBLE"),
    ),
    "it2_protein_residues": (
        ("gene", "VARCHAR"),
        ("uniprot", "VARCHAR"),
        ("rsid", "VARCHAR"),
        ("consequence_class", "VARCHAR"),
        ("gene_rank", "BIGINT"),
        ("in_domain", "BOOLEAN"),
        ("domain_accession", "VARCHAR"),
        ("domain_name", "VARCHAR"),
        ("plddt", "DOUBLE"),
        ("confident", "BOOLEAN"),
        ("fraction", "DOUBLE"),
        ("am_class", "VARCHAR"),
        ("am_agrees", "BOOLEAN"),
        ("note", "VARCHAR"),
    ),
    "it2_knowledge_ranks": (
        ("gene", "VARCHAR"),
        ("knowledge_rank", "BIGINT"),
        ("knowledge_score", "DOUBLE"),
        ("best_terms_matched", "BIGINT"),
        ("terms_with_any_paper", "BIGINT"),
        ("described_alleles", "BIGINT"),
        ("pubmed_count", "BIGINT"),
        ("citation_rank", "BIGINT"),
        ("lr_rank", "BIGINT"),
        ("is_target", "BOOLEAN"),
        ("is_decoy", "BOOLEAN"),
        ("curated", "BOOLEAN"),
    ),
}

#: What each table is, in the words the lineage row carries.
TRANSFORMS: dict[str, str] = {
    "it2_pub_alleles": (
        "one row per allele of a queried gene that the ranking scored: LitVar 2.0 asked "
        "once per distinct dbSNP identifier whether anyone has published about that exact "
        "variant, joined to the child's own k-mer multiplicity from step 3 where it exists"
    ),
    "it2_anchors": (
        "one row per paper PubTator 3.0 returned for a (gene, clinical term) search, with "
        "the count of the child's seven proband terms whose search returned it; anchors "
        "are derived by script from the gene list, never typed from a reading list"
    ),
    "it2_anchor_terms": (
        "per gene and clinical term, how many papers PubTator holds for the pair across "
        "every page - the denominator behind each anchor row"
    ),
    "it2_protein_domains": (
        "InterPro entries mapped onto the reviewed human UniProt entry of each scored "
        "gene, recorded as fractions of protein length so no residue reaches a table"
    ),
    "it2_protein_residues": (
        "one row per missense allele of a leading pair: whether it falls inside an "
        "annotated InterPro domain, the AlphaFold pLDDT at that residue, and whether the "
        "AlphaMissense class already in the warehouse agrees"
    ),
    "it2_knowledge_ranks": (
        "the knowledge ordering beside the two baselines it has to beat - a raw PubMed "
        "publication count per gene, and the step-4 likelihood-ratio rank; citation volume "
        "never enters the knowledge score, only the baseline it is measured against"
    ),
}

#: The three inputs, named once and quoted in every lineage row.
CALLSET_REF = "results.it2_lr_pairs (step 4) + results.it2_kmer_genotypes (step 3)"
CLINICAL_REF = "ressources/hackathon-rules/Challenge_Clinical_Phenotype_1.md"
CLINICAL_TRANSFORM = (
    "every anchor row is scored by how many of the proband's seven HPO term labels "
    "returned the paper; the term set is owned by mva.phenotype.terms and no term is "
    "retyped here"
)
LITERATURE_REF = (
    "LitVar 2.0 + PubTator 3.0 + NCBI E-utilities (literature); "
    "UniProt + InterPro + AlphaFold DB (protein)"
)
LITERATURE_TRANSFORM = (
    "public knowledge supplies every value in these tables; the case supplies only which "
    "genes and which dbSNP identifiers were asked about"
)
TOOL = "mva-warehouse pg-load-it2-step5"


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
        # ``quote`` explicit, never sniffed — a paper title carries commas and quotes, and
        # this is the step where a sniffed dialect would corrupt the evidence itself.
        f"SELECT {casts} FROM read_csv(?, delim='\t', header=true, all_varchar=true, "
        f"quote='\"', escape='\"')",
        [str(path)],
    )
    counted = connection.execute(f"SELECT count(*) FROM {qualified}").fetchone()
    return int((counted or [0])[0])


def load(connection, *, schema: str, result_schema: str, out_dir: Path) -> list[Loaded]:
    """Load every step-5 table present in ``out_dir``, and record its lineage.

    A table whose TSV is absent is skipped rather than created empty: an empty table and a
    stage that did not run look identical in SQL, and only one of them is a result.
    """
    manifest_path = out_dir / "catalogue.json"
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    )
    version = " ".join(
        f"{name}={manifest.get(key, '')}"
        for name, key in (
            ("genes", "genes"),
            ("alleles", "alleles"),
            ("queryable", "queryable"),
            ("described", "described"),
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
            ("api", LITERATURE_REF, LITERATURE_TRANSFORM),
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
                notes="decoy genes run through the identical queries" if kind == "derived" else "",
            )
    return loaded
