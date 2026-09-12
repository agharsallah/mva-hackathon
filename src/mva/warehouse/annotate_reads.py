"""Annotate the alleles the **reads** carry that the delivered callset never reported.

Step 2's whole point is to discover alleles with callers that share no code with the
vendor's. Its scoring query then joined ``warehouse.coding_annotations``, which is built
from the delivered callset — so an allele only our callers saw had no consequence, no
gnomAD frequency and no ClinVar row, and was silently dropped before any filter ran.

That is a circle: a route built to find what the vendor missed could only ever rediscover
what the vendor found. **1,199 distinct read-derived alleles** sit in or beside a coding
exon with no annotation row, and they are precisely the class the second caller exists
for. This module asks VEP about them.

Two deliberate choices:

* **A separate table, not a top-up of ``coding_annotations``.** Where an allele came from
  is evidence. Keeping ``it2_read_annotations`` apart preserves "the vendor reported this"
  versus "only the read route saw this" as a fact a query can read, and leaves the
  iteration-1 table byte-identical.
* **Exons padded by ``EXON_PAD``, not exon bodies.** ``coding_regions`` is exon-level, and
  a canonical splice donor or acceptor sits 1-8 bases *outside* the exon while being the
  most damaging class of variant there is. Padding by 10 takes the whole splice region
  with margin; it is fixed here rather than tuned per gene.

The loop, the checkpointing and the lineage edge are :mod:`mva.warehouse.annotate_coding`'s
— this module supplies the allele source and the destination table and nothing else.
"""

from __future__ import annotations

from pathlib import Path

from ..pipeline.variant import Variant
from .postgres import ALIAS, safe_identifier
from .settings import Postgres

__all__ = ["CHECKPOINT", "EXON_PAD", "READ_ALLELES_TABLE", "READ_TABLE", "TRANSFORM", "alleles"]

#: Where the read-derived annotations land, in the ingest schema, panel-shaped so every
#: join written for ``coding_annotations`` works against it unchanged.
READ_TABLE = "it2_read_annotations"

#: The step-2 table the alleles are read from, in the *result* schema.
READ_ALLELES_TABLE = "it2_read_alleles"

#: Bases of slack around each coding exon. A splice donor/acceptor is 1-8 bases into the
#: intron and VEP calls it ``splice_region_variant`` out to 8; 10 covers it with margin.
EXON_PAD = 10

#: Gitignored: holds patient positions.
CHECKPOINT = Path("build/it2-read-annotations")

#: Written into the annotation table's ``source`` and the lineage edge's transform.
TRANSFORM = "annotate-it2-reads"


def alleles(connection, settings: Postgres) -> list[Variant]:
    """Read-derived alleles in or beside a coding exon that no annotation covers yet.

    The anti-join against ``coding_annotations`` is what makes a re-run cheap and what
    makes the result table mean "new to the read route" rather than "everything".
    """
    result = safe_identifier(settings.result_schema)
    ingest = safe_identifier(settings.schema)
    rows = connection.execute(
        f"""
        WITH ours AS (
            SELECT DISTINCT chrom, pos, ref, alt
            FROM {ALIAS}.{result}.{READ_ALLELES_TABLE}
        )
        SELECT DISTINCT o.chrom, o.pos, o.ref, o.alt
        FROM ours o
        JOIN {ALIAS}.{ingest}.coding_regions r
          ON o.chrom = r.chrom
         AND o.pos BETWEEN r.start - {EXON_PAD} AND r."end" + {EXON_PAD}
        LEFT JOIN {ALIAS}.{ingest}.coding_annotations a
          ON o.chrom = a.chrom AND o.pos = a.pos AND o.ref = a.ref AND o.alt = a.alt
        WHERE a.chrom IS NULL
        """
    ).fetchall()
    return sorted(Variant.from_vcf(chrom, int(pos), ref, alt) for chrom, pos, ref, alt in rows)
