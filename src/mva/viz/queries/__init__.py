"""Every warehouse read the viz API makes, as one function per endpoint.

Two rules govern this package, and both exist to keep an HTTP request from becoming a
whole-genome scan:

* **Charts read derived tables, never the callset.** ``variants_raw`` is five million
  all-text rows with no index; the cheapest full aggregate over it is ~60 s. Anything a
  chart needs is precomputed by a :mod:`~mva.warehouse.analysis` derivation, so the
  request reads a few thousand rows.
* **The one exception pushes its filter down.** The locus endpoint has to touch the
  callset, so it always constrains ``chrom``, which PostgreSQL can satisfy without
  reading the other 24 chromosomes (~4.4 s instead of ~21 s).

Rows come back as dicts with JSON-safe values, because a chart component should not have
to know that PostgreSQL hands DuckDB a ``Decimal`` and a naive ``datetime``.

Four modules, one concern each:

===================  ====================================================================
:mod:`.access`       attach, execute, convert. No SQL of its own.
:mod:`.callset`      whole-callset shape: quality, composition, coverage, the funnel.
:mod:`.panel`        the gene panel, and the single query that reads the callset.
:mod:`.ledger`       the append-only ledgers: lineage, derivations, sources, probes.
===================  ====================================================================

This module re-exports all of them, so ``queries.locus(...)`` still resolves and callers
did not change when the file became a package.
"""

from .access import CANONICAL, fetch, jsonable, rows, table
from .callset import (
    allele_balance,
    baf_bins,
    candidate_funnel,
    contig_density,
    density_bins,
    depth_distribution,
    filters,
    genotypes,
    indel_lengths,
    observed_expected,
    sequencing_yield,
    substitutions,
    tstv,
    vcf_fields,
    zygosity_split,
)
from .ledger import derivations, lineage, probe_ledger, sources
from .panel import (
    clinvar_presence,
    gene_region,
    het_pairs,
    locus,
    panel_background,
    panel_candidates,
    panel_constraint,
    panel_filter_census,
    panel_genes,
    panel_suppressed,
)

__all__ = [
    "CANONICAL",
    "allele_balance",
    "baf_bins",
    "candidate_funnel",
    "clinvar_presence",
    "contig_density",
    "density_bins",
    "depth_distribution",
    "derivations",
    "fetch",
    "filters",
    "gene_region",
    "genotypes",
    "het_pairs",
    "indel_lengths",
    "jsonable",
    "lineage",
    "locus",
    "observed_expected",
    "panel_background",
    "panel_candidates",
    "panel_constraint",
    "panel_filter_census",
    "panel_genes",
    "panel_suppressed",
    "probe_ledger",
    "rows",
    "sequencing_yield",
    "sources",
    "substitutions",
    "table",
    "tstv",
    "vcf_fields",
    "zygosity_split",
]
