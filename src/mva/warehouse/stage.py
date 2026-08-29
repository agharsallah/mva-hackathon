"""Turn a profile directory into typed Parquet, locally, before anything is shipped.

Staging is one pure-ish step: read each source with the parsers the exploration toolkit
already has, write it back out as a *tidy* table — one header row, every row the same
width — and let DuckDB sniff the column types on the way into Parquet.

Two things are worth knowing about why it works this way.

**Why re-write the file at all.** The delivered TSVs are not uniformly rectangular. Some
have no header, one is cut into ``##`` blocks, and several glue two-column rollup lines
(``est_raw_coverage_x  51.9``) under the table proper. Handing those to a CSV reader
directly gives either a parse error or a silently truncated table, so each is normalised
through :mod:`mva.explore.readers` first.

**Why DuckDB does the typing.** Writing every column as text would make the warehouse
useless for arithmetic — ``mean_dp > 40`` has to compare numbers, not strings. Rather than
hand-roll a type guesser, the normalised TSV is handed to DuckDB's own CSV sniffer, which
is the same one a user would get typing ``read_csv`` themselves. One inference engine, no
disagreement between staging and querying.

The rollup scalars that would otherwise be dropped are not lost: they are collected into a
single ``profile_scalars`` table keyed by source file, so a total stated at the bottom of
one file is still queryable alongside the rows above it.
"""

import csv
from dataclasses import dataclass
from pathlib import Path

from ..explore import readers
from .catalog import Dataset, discover

#: The table that collects every two-column rollup line found across all sources.
SCALARS_TABLE = "profile_scalars"

#: The table that records what every other table is, written into the database itself.
CATALOG_TABLE = "warehouse_catalog"


@dataclass(frozen=True)
class Staged:
    """One dataset after normalisation: where its Parquet is and how big it came out."""

    table: str
    parquet: Path
    rows: int
    columns: tuple[str, ...]
    description: str = ""


def normalise(dataset: Dataset, root: Path) -> tuple[tuple[str, ...], list[list[str]], dict[str, str]]:
    """Read one source into ``(columns, rows, scalars)``, whatever shape it arrived in.

    Every branch returns rectangular rows of plain strings. Typing happens later, in
    DuckDB; nothing is coerced here, because a column that is an integer in this case is a
    float or a sentinel like ``.`` in the next one.
    """
    path = dataset.path(root)
    if dataset.shape == "bed":
        columns = dataset.columns or ("chrom", "start", "end", "name")
        regions = readers.read_bed(path)
        rows = [[r.chrom, str(r.start), str(r.end), r.name] for r in regions]
        return columns, rows, {}

    if dataset.shape == "sections":
        columns = dataset.columns or ("section", "label", "value")
        sections = readers.read_sections(path)
        rows = [[name, label, value]
                for name, pairs in sections.blocks.items()
                for label, value in pairs]
        return columns, rows, dict(sections.scalars)

    if dataset.shape == "lines":
        columns = dataset.columns or ("line_no", "line")
        text = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return columns, [[str(n), line] for n, line in enumerate(text, 1)], {}

    return _normalise_table(dataset, path)


def _normalise_table(dataset: Dataset, path: Path) -> tuple[tuple[str, ...], list[list[str]], dict[str, str]]:
    """Read a plain TSV, supplying column names when the file itself has none.

    ``read_table`` treats the first non-comment line as the header. A headerless file
    declares its columns in the catalogue instead, and that first line is a real record —
    so it is read raw and zipped against the declared names.
    """
    if not dataset.columns:
        table = readers.read_table(path)
        rows = [[row.get(column, "") for column in table.columns] for row in table.rows]
        return table.columns, rows, dict(table.scalars)

    width = len(dataset.columns)
    rows = []
    scalars: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        cells = line.split("\t")
        if len(cells) == width:
            rows.append(cells)
        elif len(cells) == 2:
            scalars[cells[0]] = cells[1]
    return dataset.columns, rows, scalars


def stage(root: Path, outdir: Path, datasets: list[Dataset] | None = None) -> list[Staged]:
    """Normalise a whole profile directory into Parquet under ``outdir``.

    Returns one :class:`Staged` per table actually written. Empty sources are skipped
    rather than written as zero-row Parquet, because an empty file is indistinguishable
    from a failed upstream step and should not silently become an empty SQL table.
    """
    import duckdb

    datasets = discover(root) if datasets is None else datasets
    outdir.mkdir(parents=True, exist_ok=True)
    staged: list[Staged] = []
    all_scalars: list[list[str]] = []

    with duckdb.connect() as connection:
        for dataset in datasets:
            if not dataset.path(root).exists():
                continue
            columns, rows, scalars = normalise(dataset, root)
            all_scalars += [[dataset.source, key, value] for key, value in scalars.items()]
            if not rows:
                continue
            parquet = _write_parquet(connection, outdir, dataset.table, columns, rows)
            staged.append(Staged(dataset.table, parquet, len(rows),
                                 safe_columns(columns), dataset.description))

        if all_scalars:
            parquet = _write_parquet(connection, outdir, SCALARS_TABLE,
                                     ("source", "key", "value"), all_scalars)
            staged.append(Staged(SCALARS_TABLE, parquet, len(all_scalars),
                                 ("source", "key", "value"),
                                 "Rollup totals stated at the foot of a source file."))

        staged.append(_write_catalog(connection, outdir, staged))
    return staged


def _write_catalog(connection, outdir: Path, staged: list[Staged]) -> Staged:
    """Write the self-describing catalogue table listing everything else in the warehouse."""
    columns = ("table_name", "n_rows", "n_columns", "columns", "description")
    rows = [[s.table, str(s.rows), str(len(s.columns)), ",".join(s.columns), s.description]
            for s in staged]
    parquet = _write_parquet(connection, outdir, CATALOG_TABLE, columns, rows)
    return Staged(CATALOG_TABLE, parquet, len(rows), columns,
                  "What every other table in this warehouse holds.")


def safe_column(name: str) -> str:
    """Make one column name usable in SQL without quoting.

    A header cell like ``pct_in_0.40_0.60`` is legal in a TSV and legal in Parquet, but in
    SQL the dots read as qualifiers, so every query touching it needs double quotes. Since
    these headers are written by shell pipelines and nobody downstream depends on the
    punctuation, they are folded to ``[a-z0-9_]`` once, here, rather than being quoted at
    every call site forever.
    """
    cleaned = "".join(char if char.isalnum() else "_" for char in name).strip("_").lower()
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    if not cleaned:
        return "col"
    return f"c_{cleaned}" if cleaned[0].isdigit() else cleaned


def safe_columns(names: tuple[str, ...]) -> tuple[str, ...]:
    """Sanitise a whole header, keeping it unique by suffixing any collision."""
    out: list[str] = []
    for name in names:
        candidate = safe_column(name)
        if candidate in out:
            index = 2
            while f"{candidate}_{index}" in out:
                index += 1
            candidate = f"{candidate}_{index}"
        out.append(candidate)
    return tuple(out)


def _write_parquet(connection, outdir: Path, table: str,
                   columns: tuple[str, ...], rows: list[list[str]]) -> Path:
    """Write tidy rows to Parquet, letting DuckDB infer each column's type.

    The intermediate TSV exists only so DuckDB's CSV sniffer can do the typing; it is
    removed once the Parquet is on disk.
    """
    tsv = outdir / f"{table}.tsv"
    with tsv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", quoting=csv.QUOTE_MINIMAL)
        writer.writerow(safe_columns(columns))
        writer.writerows(rows)

    parquet = outdir / f"{table}.parquet"
    # `COPY ... TO` will not accept a bound parameter for its destination, and building
    # that path by string interpolation is how a filename with a quote in it becomes an
    # injection. The relation API takes both paths as values, so neither is ever parsed.
    relation = connection.read_csv(str(tsv), delimiter="\t", header=True, sample_size=-1)
    relation.write_parquet(str(parquet), compression="zstd")
    tsv.unlink()
    return parquet
