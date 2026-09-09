"""Read what a result table says about one selected allele — never its position.

A selector (:mod:`mva.warehouse.submission_spec`) picks exactly one allele. This module
re-runs the same ``WHERE`` clause and reads the *fact* columns the table has — gene,
consequence, zygosity, filter, depth, allele fraction, gnomAD frequency, ClinVar
significance, dbSNP id — so that a submission note can only quote a value a table holds.
The single-allele **score** is the ranker's rarity × severity term
(:func:`mva.pipeline.ranking.allele_score`); one heuristic, one place.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from mva.pipeline.annotation import Annotation
from mva.pipeline.ranking import allele_score

from .submission_spec import Selector, SelectorError, to_sql

__all__ = ["FACT_COLUMNS", "AlleleFacts", "fetch_facts", "table_columns"]

#: Fact columns a result table may carry; the ones present are read, the rest stay ``None``.
FACT_COLUMNS = (
    "gene",
    "consequence",
    "impact",
    "gt",
    "zygosity",
    "filter",
    "dp",
    "vaf",
    "gnomad_af",
    "clin_sig",
    "rsid",
    "is_clinvar_plp",
)


@dataclass(frozen=True)
class AlleleFacts:
    """What the selector's table says about one allele — never its position."""

    name: str
    table: str
    gene: str | None = None
    consequence: str | None = None
    impact: str | None = None
    zygosity: str | None = None
    filter: str | None = None
    dp: int | None = None
    vaf: float | None = None
    gnomad_af: float | None = None
    clin_sig: str | None = None
    rsid: str | None = None
    is_clinvar_plp: bool | None = None

    @property
    def most_severe(self) -> str | None:
        """VEP lists consequences most-severe first; the ranker scores one term."""
        return self.consequence.split(",")[0].strip() if self.consequence else None

    @property
    def annotation(self) -> Annotation:
        return Annotation(gene=self.gene, consequence=self.most_severe, gnomad_af=self.gnomad_af)

    @property
    def score(self) -> float:
        """Rarity × severity, the ranker's single-allele term."""
        return allele_score(self.annotation)

    def describe(self) -> str:
        """One allele, as a note fragment built only from table columns."""
        parts = [f"{self.gene or '?'} {self.most_severe or 'unannotated'}"]
        call = " ".join(p for p in (self.zygosity, self.filter) if p)
        if self.dp is not None:
            call += f" DP {self.dp}"
        if self.vaf is not None:
            call += f" VAF {self.vaf:.2f}"
        if call.strip():
            parts.append(call.strip())
        parts.append("gnomAD absent" if self.gnomad_af is None else f"gnomAD {self.gnomad_af:.3g}")
        parts.append(f"ClinVar {self.clin_sig}" if self.clin_sig else "ClinVar not listed")
        if self.rsid:
            parts.append(self.rsid)
        return ", ".join(parts)

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "table": self.table,
            "gene": self.gene,
            "consequence": self.consequence,
            "impact": self.impact,
            "zygosity": self.zygosity,
            "filter": self.filter,
            "dp": self.dp,
            "vaf": self.vaf,
            "gnomad_af": self.gnomad_af,
            "clin_sig": self.clin_sig,
            "rsid": self.rsid,
            "is_clinvar_plp": self.is_clinvar_plp,
            "score": round(self.score, 4),
        }


def table_columns(connection: Any, table: str) -> list[str]:
    """Column names of ``pg.<table>``, from an empty projection."""
    description = connection.execute(f"SELECT * FROM pg.{table} LIMIT 0").description or []
    return [str(column[0]) for column in description]


def fetch_facts(connection: Any, name: str, selector: Selector) -> AlleleFacts:
    """Read the fact columns the selector's table has, for the one allele it picks."""
    present = [
        column for column in FACT_COLUMNS if column in table_columns(connection, selector.table)
    ]
    where_sql, params = to_sql(selector)
    where = where_sql.split(" WHERE ", 1)[1]
    sql = f"SELECT DISTINCT {', '.join(present)} FROM pg.{selector.table} WHERE {where}"
    rows = connection.execute(sql, params).fetchall()
    if len(rows) != 1:
        raise SelectorError(f"{name}: facts matched {len(rows)} rows, need exactly 1")
    found = dict(zip(present, rows[0], strict=True))
    zygosity = found.get("zygosity") or _zygosity_from_gt(found.get("gt"))
    return AlleleFacts(
        name=name,
        table=selector.table,
        gene=_text(found.get("gene")),
        consequence=_text(found.get("consequence")),
        impact=_text(found.get("impact")),
        zygosity=_text(zygosity),
        filter=_text(found.get("filter")),
        dp=int(found["dp"]) if found.get("dp") is not None else None,
        vaf=float(found["vaf"]) if found.get("vaf") is not None else None,
        gnomad_af=float(found["gnomad_af"]) if found.get("gnomad_af") is not None else None,
        clin_sig=_text(found.get("clin_sig")),
        rsid=_text(found.get("rsid")),
        is_clinvar_plp=(
            bool(found["is_clinvar_plp"]) if found.get("is_clinvar_plp") is not None else None
        ),
    )


def _zygosity_from_gt(gt: Any) -> str | None:
    if not gt:
        return None
    alleles = re.split(r"[/|]", str(gt))
    if len(alleles) == 2 and alleles[0] == alleles[1]:
        return "hom" if alleles[0] != "0" else "ref"
    return "het"


def _text(value: Any) -> str | None:
    return None if value is None or value == "" else str(value)
