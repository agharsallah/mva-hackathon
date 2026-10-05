"""Format parsers, below every domain layer.

These read the plain-text shapes command-line tools emit — TSV tables with rollup lines
glued to the bottom, ``##``-sectioned files — and know nothing about one dataset or one
challenge. Every layer above sits on them, so they live here rather than inside any one
of those layers.
"""

from .readers import Row, Sections, Table, as_float, as_int, read_sections, read_table
from .writers import cell, write_json, write_tsv

__all__ = [
    "Row",
    "Sections",
    "Table",
    "as_float",
    "as_int",
    "cell",
    "read_sections",
    "read_table",
    "write_json",
    "write_tsv",
]
