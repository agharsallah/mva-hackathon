"""Turn whatever a publisher shipped into one Parquet a lane can join.

A published score table arrives in one of four shapes, and the difference is the
publisher's habit, not anything about the model: a flat delimited file (possibly
bgzipped), or a zip of one file per protein that is either already long (one row per
variant) or a **matrix** (one column per position, one row per substituted amino acid).
This module is the adapter between those four shapes and the one shape the zoo joins on.

It is a leaf: it imports the registry for the card's ``params`` and
:mod:`mva.zoo.tables` for the reshaping, and nothing else. It was split out of
``tools/fetch_zoo_tables.py`` when that script gained the tabix subset mode and outgrew
the 400-line rule; the code is unchanged.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any

from . import registry, tables

__all__ = ["LAYOUTS", "extract", "to_parquet"]

#: How the downloaded file is shaped, from ``params.layout`` in the roster.
LAYOUTS = ("tsv", "csv", "matrix-zip", "csv-zip")


def extract(archive: Path, into: Path) -> list[Path]:
    """Unpack a zip into ``into`` and return the member files, largest first."""
    into.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(into)
    return sorted((p for p in into.rglob("*") if p.is_file()), key=lambda p: -p.stat().st_size)


def to_parquet(
    card: registry.ModelCard, raw: Path, target: Path, only: frozenset[str] = frozenset()
) -> int:
    """Turn whatever was downloaded into one parquet keyed for lookup. Returns row count."""
    import duckdb

    layout = str(card.params.get("layout", "tsv"))
    if layout not in LAYOUTS:
        raise SystemExit(f"{card.key}: layout={layout!r} is not one of {LAYOUTS}")
    con = duckdb.connect()
    try:
        if layout in ("tsv", "csv"):
            rows = _convert_flat(con, raw, target, layout)
        else:
            rows = _convert_archive(con, card, raw, target, layout, only)
    finally:
        con.close()
    return rows


def _convert_flat(con: Any, raw: Path, target: Path, layout: str) -> int:
    """A single delimited table (possibly bgzipped) → parquet, columns unchanged."""
    delimiter = "\t" if layout == "tsv" else ","
    source = str(raw)
    con.execute(
        "COPY (SELECT * FROM read_csv(?, delim=?, header=true, union_by_name=true, "
        "filename=false, auto_detect=true)) TO ? (FORMAT parquet)",
        [source, delimiter, str(target)],
    )
    return int(con.execute("SELECT count(*) FROM read_parquet(?)", [str(target)]).fetchone()[0])


def _convert_archive(
    con: Any,
    card: registry.ModelCard,
    raw: Path,
    target: Path,
    layout: str,
    only: frozenset[str] = frozenset(),
) -> int:
    """A zip of per-protein files → one long parquet.

    ``csv-zip``: every member is already long (one row per variant) and they are simply
    unioned. ``matrix-zip`` (ESM1b): every member is a matrix — one column per protein
    position, one row per substituted amino acid — so it is unpivoted into
    ``(uniprot, hgvs_p, score)``. The member layout is printed before the conversion runs
    so the assumption is checked against the real file rather than trusted.

    ``only`` restricts the conversion to the accessions named — one member per accession.
    This is the plan's own tier-1 rule, "a parquet subset for the ~40k records only"
    (§10 R7): a case carries a few thousand proteins, not every protein a publisher scored.
    The reshaping itself is :func:`mva.zoo.tables.unpivot_matrix_members`, whose docstring
    records why it is Python and not one SQL statement.
    """
    members = extract(raw, raw.parent / f"{card.key}-extracted")
    if not members:
        raise SystemExit(f"{card.key}: the archive held no files")
    if only:
        members = [item for item in members if tables.accession_of(item) in only]
        if not members:
            raise SystemExit(
                f"{card.key}: no member matched the {len(only):,} accessions asked for"
            )
    print(f"    {len(members):,} members; first: {members[0].name}")
    head = con.execute("SELECT * FROM read_csv(?, header=true) LIMIT 3", [str(members[0])])
    print(f"    columns: {[d[0] for d in head.description][:8]} …")
    # DuckDB will not take the COPY target (or a read_csv path inside COPY) as a bound
    # parameter — "Unsupported parameter type for filename: expected e.g. TARGET
    # 'file.parquet'". Paths are interpolated as single-quoted literals instead; they are
    # ones this script built, never user input.
    dst = _literal(str(target))
    if layout == "csv-zip":
        pattern = _literal(str(members[0].parent / str(card.params.get("member_glob", "*.csv"))))
        con.execute(
            f"COPY (SELECT * FROM read_csv({pattern}, header=true, union_by_name=true, "
            f"filename=true)) TO {dst} (FORMAT parquet)"
        )
    else:
        # The publisher's numbers are written **verbatim**, sign and all. Orientation is
        # the lane's job (`score_sign` on the card, applied in the adapter), and applying
        # it here as well would flip it twice — which it silently did until a BUB1B spot
        # check came back negative for a damaging change (entry 119).
        tables.unpivot_matrix_members(members, target, progress=print)
    return int(con.execute("SELECT count(*) FROM read_parquet(?)", [str(target)]).fetchone()[0])


def _literal(value: str) -> str:
    """A SQL string literal, single quotes doubled — for the places DuckDB refuses a `?`."""
    escaped = value.replace("'", "''")
    return f"'{escaped}'"
