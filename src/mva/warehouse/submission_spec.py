"""Resolve a coordinate-free submission spec into the one the designer reads.

The submission spec (``build/submission/spec.json``) names real patient coordinates, so it
is gitignored — and therefore lives on one laptop. What *can* be committed is how each
allele was chosen: "the BUB1B stop_gained in ``results.coding_candidates``", "the rare
intronic BUB1B allele absent from gnomAD". This module turns those **selectors** into
``(chrom, pos, ref, alt)`` against the warehouse, so an iteration folder is reproducible
from the repository plus database access, and a judge can read *why* every row is there
without ever seeing *where*.

A selector must match **exactly one** row. Zero or several is an error that names the count
and the selector, never a position.

Selector shape::

    {
        "table": "results.coding_candidates",
        "where": [
            ["gene", "=", "BUB1B"],
            ["consequence", "like", "%stop_gained%"],
            ["gnomad_af", "is", null],
            ["is_clinvar_plp", "=", true],
        ],
    }

Operators: ``=``, ``!=``, ``<``, ``<=``, ``>``, ``>=``, ``like``, ``is`` and ``is not``
(with ``null`` only). Column and table names are validated as identifiers before they are
interpolated; values are bound as parameters.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .postgres import attached
from .settings import Postgres

__all__ = ["Allele", "Selector", "SelectorError", "resolve", "resolve_all", "to_sql"]

IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$")
OPERATORS = {"=", "!=", "<", "<=", ">", ">=", "like"}
NULL_OPERATORS = {"is", "is not"}

#: Result tables carry the VCF's bare contig; the designer re-prefixes with ``chr``.
COLUMNS = ("chrom", "pos", "ref", "alt")


class SelectorError(ValueError):
    """A selector that is malformed or does not pick exactly one allele."""


@dataclass(frozen=True)
class Selector:
    table: str
    where: tuple[tuple[str, str, Any], ...]

    @classmethod
    def from_json(cls, name: str, raw: dict) -> Selector:
        table = raw.get("table", "")
        if not IDENTIFIER.match(table):
            raise SelectorError(f"{name}: table {table!r} is not a plain identifier")
        clauses = []
        for clause in raw.get("where", []):
            if len(clause) != 3:
                raise SelectorError(f"{name}: a where clause is [column, operator, value]")
            column, operator, value = clause
            operator = str(operator).lower()
            if not IDENTIFIER.match(str(column)) or "." in str(column):
                raise SelectorError(f"{name}: column {column!r} is not a plain identifier")
            if operator in NULL_OPERATORS and value is not None:
                raise SelectorError(f"{name}: {operator!r} takes null only")
            if operator not in OPERATORS | NULL_OPERATORS:
                raise SelectorError(f"{name}: operator {operator!r} not allowed")
            clauses.append((str(column), operator, value))
        if not clauses:
            raise SelectorError(f"{name}: a selector needs at least one where clause")
        return cls(table, tuple(clauses))


@dataclass(frozen=True)
class Allele:
    chrom: str
    pos: int
    ref: str
    alt: str

    def to_json(self) -> dict:
        return {"chrom": self.chrom, "pos": self.pos, "ref": self.ref, "alt": self.alt}


def to_sql(selector: Selector) -> tuple[str, list[Any]]:
    """The parameterised statement a selector compiles to, for the attached database."""
    parts, params = [], []
    for column, operator, value in selector.where:
        if operator in NULL_OPERATORS:
            parts.append(f"{column} {operator.upper()} NULL")
        else:
            parts.append(f"{column} {operator.upper()} ?")
            params.append(value)
    sql = (
        f"SELECT DISTINCT {', '.join(COLUMNS)} FROM pg.{selector.table} WHERE {' AND '.join(parts)}"
    )
    return sql, params


def resolve(connection, name: str, selector: Selector) -> Allele:
    """Run one selector; exactly one distinct allele must come back."""
    sql, params = to_sql(selector)
    rows = connection.execute(sql, params).fetchall()
    if len(rows) != 1:
        raise SelectorError(
            f"{name}: selector matched {len(rows)} alleles, need exactly 1 "
            f"({selector.table}: {selector.where})"
        )
    chrom, pos, ref, alt = rows[0]
    return Allele(str(chrom), int(pos), str(ref), str(alt))


def resolve_all(settings: Postgres, selectors: dict[str, dict]) -> dict[str, Allele]:
    """Resolve every named selector over one read-only connection."""
    parsed = {name: Selector.from_json(name, raw) for name, raw in selectors.items()}
    with attached(settings, read_only=True) as connection:
        return {name: resolve(connection, name, selector) for name, selector in parsed.items()}
