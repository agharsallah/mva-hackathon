"""The report's inputs: aggregates read from the result schema, never a coordinate.

Three shapes, each a plain dataclass so :mod:`mva.report.figures` needs no database and
the tests can hand it literals:

* :class:`Funnel` — the filtering funnel from the whole callset down to one gene;
* :class:`GeneRow` — one row of ``results.gene_biallelic`` with its gene name and counts;
* the decode table, built from a submission spec through :mod:`mva.pipeline.probe_design`
  and reduced to labels — the spec holds real positions, the table it yields holds none.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ..pipeline.probe_design import Design, Hypothesis, design
from ..pipeline.submission import Row
from ..pipeline.variant import Variant
from ..warehouse.postgres import query
from ..warehouse.settings import Postgres

__all__ = ["Funnel", "GeneRow", "decode_design", "funnel", "gene_rows"]

RES = "pg.results"
SRC = "pg.warehouse"


@dataclass(frozen=True)
class Funnel:
    """Row counts at each stage, from every record to the one gene left standing."""

    callset_records: int
    coding_rows: int
    coding_alleles: int
    annotated: int
    rare: int
    rare_protein_altering: int
    rare_protein_altering_pass: int
    genes_with_candidate: int
    genes_biallelic_pass: int
    genes_biallelic_plp: int
    genes_biallelic_plp_top30: int

    def stages(self) -> list[tuple[str, int]]:
        """Label → count, in funnel order, for a chart."""
        return [
            ("variant records in the VCF", self.callset_records),
            ("inside a coding interval (gene × allele)", self.coding_rows),
            ("distinct coding alleles annotated by VEP", self.annotated),
            ("rare (gnomAD AF absent or < 0.01)", self.rare),
            ("rare and protein-altering", self.rare_protein_altering),
            ("… on PASS calls", self.rare_protein_altering_pass),
            ("genes carrying any such allele", self.genes_with_candidate),
            ("genes biallelic on PASS calls", self.genes_biallelic_pass),
            ("… with a ClinVar pathogenic allele", self.genes_biallelic_plp),
            ("… and phenotype rank ≤ 30", self.genes_biallelic_plp_top30),
        ]


@dataclass(frozen=True)
class GeneRow:
    """One gene of ``results.gene_biallelic`` — names and counts only."""

    gene: str
    n_het_pass: int
    n_multi_pass: int
    n_hom_pass: int
    n_nonpass: int
    n_lof_pass: int
    n_plp_pass: int
    n_novel_pass: int
    biallelic_pass: bool
    biallelic_with_rescue: bool
    phenotype_rank: int | None
    consequences: str

    @property
    def n_pass(self) -> int:
        return self.n_het_pass + self.n_multi_pass + self.n_hom_pass


def funnel(settings: Postgres) -> Funnel:
    """Count every stage live. One statement per stage; each is a full-table aggregate."""

    def one(sql: str) -> int:
        result = query(settings, sql)
        return int(result.rows[0][0]) if result.rows else 0

    return Funnel(
        callset_records=one(f"SELECT count(*) FROM {SRC}.variants_raw"),
        coding_rows=one(f"SELECT count(*) FROM {RES}.coding_alleles"),
        coding_alleles=one(
            f"SELECT count(DISTINCT (chrom, pos, ref, alt)) FROM {RES}.coding_alleles"
        ),
        annotated=one(
            f"SELECT count(*) FROM {SRC}.coding_annotations WHERE consequence IS NOT NULL"
        ),
        rare=one(
            f"SELECT count(DISTINCT (chrom, pos, ref, alt)) FROM {RES}.coding_candidates "
            "WHERE is_rare_recessive"
        ),
        rare_protein_altering=one(
            f"SELECT count(DISTINCT (chrom, pos, ref, alt)) FROM {RES}.coding_candidates "
            "WHERE is_rare_recessive AND is_protein_altering"
        ),
        rare_protein_altering_pass=one(
            f"SELECT count(DISTINCT (chrom, pos, ref, alt)) FROM {RES}.coding_candidates "
            "WHERE is_rare_recessive AND is_protein_altering AND filter = 'PASS'"
        ),
        genes_with_candidate=one(f"SELECT count(*) FROM {RES}.gene_biallelic"),
        genes_biallelic_pass=one(f"SELECT count(*) FROM {RES}.gene_biallelic WHERE biallelic_pass"),
        genes_biallelic_plp=one(
            f"SELECT count(*) FROM {RES}.gene_biallelic WHERE biallelic_pass AND n_plp_pass >= 1"
        ),
        genes_biallelic_plp_top30=one(
            f"SELECT count(*) FROM {RES}.gene_biallelic "
            "WHERE biallelic_pass AND n_plp_pass >= 1 AND phenotype_rank <= 30"
        ),
    )


def gene_rows(settings: Postgres) -> list[GeneRow]:
    """Every row of ``gene_biallelic``, in the table's own order (the genome-wide answer first)."""
    result = query(
        settings,
        f"SELECT gene, n_het_pass, n_multi_pass, n_hom_pass, n_nonpass, n_lof_pass, n_plp_pass, "
        f"n_novel_pass, biallelic_pass, biallelic_with_rescue, phenotype_rank, consequences "
        f"FROM {RES}.gene_biallelic",
    )
    return [
        GeneRow(
            gene=str(r[0]),
            n_het_pass=int(r[1]),
            n_multi_pass=int(r[2]),
            n_hom_pass=int(r[3]),
            n_nonpass=int(r[4]),
            n_lof_pass=int(r[5]),
            n_plp_pass=int(r[6]),
            n_novel_pass=int(r[7]),
            biallelic_pass=bool(r[8]),
            biallelic_with_rescue=bool(r[9]),
            phenotype_rank=None if r[10] is None else int(r[10]),
            consequences=str(r[11] or ""),
        )
        for r in result.rows
    ]


def decode_design(spec_path: Path) -> tuple[Design, list[str]]:
    """The decode table for a submission spec (the shape ``tools/design_submission.py`` reads).

    Returns the design and the coordinate-free row labels, in rank order.
    """
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    alleles = {
        name: Variant.from_vcf(f["chrom"], f["pos"], f["ref"], f["alt"])
        for name, f in spec["alleles"].items()
    }

    def member(name: str) -> Variant:
        if name.startswith("_unknown"):
            tail = name.rsplit("_", 1)[-1]
            return Variant("chrUnknown", 1 + (int(tail) if tail.isdigit() else 0), "N", "N")
        return alleles[name]

    rows = [
        Row(
            variant=alleles[item["variant"]],
            partner=alleles[item["partner"]] if item.get("partner") else None,
            epcr=float(item["epcr"]),
            finding_type=item.get("finding_type", "primary"),
            notes=item.get("notes", ""),
        )
        for item in spec["rows"]
    ]
    space = [
        Hypothesis(
            frozenset(member(n) for n in item["alleles"]),
            item["label"],
            float(item.get("prior", 1.0)),
        )
        for item in spec["hypotheses"]
    ]
    labels = [
        item.get("label")
        or item["variant"] + (f"+{item['partner']}" if item.get("partner") else "")
        for item in spec["rows"]
    ]
    return design(rows, space), labels
