"""Adapters for the external tools that turn recovered reads into alleles.

Each module wraps one published tool as a subprocess, pins the version it actually ran,
writes a provenance manifest beside its output, and parses the result into plain rows.
None of them touches the warehouse: putting rows anywhere is the loader's job, which is
what keeps the chain swappable — replace an adapter, keep the table.

| Module | Tool | What it answers |
|---|---|---|
| `align` | minimap2 + samtools | where did each recovered read come from |
| `coverage` | mosdepth | how much evidence is there per region |
| `smallvars` | freebayes, bcftools | which bases differ, said twice by two models |
| `sv` | delly, dysgu | which larger rearrangements are there, and how much to trust each type |
| `phase` | whatshap | which copy is each allele on |

A leaf package: it imports nothing from `mva`.
"""

from .tools import Invocation, Provenance, ToolMissingError, require, run, version_of

__all__ = [
    "Invocation",
    "Provenance",
    "ToolMissingError",
    "require",
    "run",
    "version_of",
]
