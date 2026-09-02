"""Format parsers, below every domain layer.

These read the plain-text shapes bioinformatics tools emit — TSV tables with rollup
lines, ``##``-sectioned files, ``bcftools stats``, BED intervals, VCF headers — and know
nothing about this proband, this panel or this challenge. Both the warehouse and the
exploration toolkit sit on top of them, so they live here rather than inside either.
"""

from .readers import (
    Region,
    Row,
    Sections,
    Table,
    VcfHeader,
    as_float,
    as_int,
    read_bcftools_stats,
    read_bed,
    read_sections,
    read_table,
    read_vcf_header,
    summary_numbers,
)

__all__ = [
    "Region",
    "Row",
    "Sections",
    "Table",
    "VcfHeader",
    "as_float",
    "as_int",
    "read_bcftools_stats",
    "read_bed",
    "read_sections",
    "read_table",
    "read_vcf_header",
    "summary_numbers",
]
