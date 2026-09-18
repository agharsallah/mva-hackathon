"""The cytoband-arms reference table: where each chromosome's short arm ends.

Split from :mod:`mva.warehouse.reference` for the same reason
:mod:`mva.warehouse.reference_coding` was — that module is at its size gate — and it is
the same *kind* of table: geometry of the reference, not a score about a population.

Step 8 tests the B-allele fraction of heterozygous calls per chromosome **and per arm**,
because a mosaic event that takes one arm disappears into a whole-chromosome mean. The
arm a position belongs to is decided by one comparison against the centromere, so the 24
rows here are joined against the callset rather than carried in Python: the boundary and
the calls meet inside the database, where the positions already are.

Built by ``tools/build_cytobands.py`` from UCSC's hg38 band table; its lineage is read
off the manifest that tool writes, never typed.
"""

from __future__ import annotations

import json
from pathlib import Path

from .catalog import Dataset

__all__ = ["CYTOBAND_TRANSFORM", "PROVENANCE_FILE", "TABLE", "dataset", "lineage"]

TABLE = "cytoband_arms"

#: The provenance sidecar ``tools/build_cytobands.py`` writes beside the TSV.
PROVENANCE_FILE = "cytoband_arms.provenance.json"

CYTOBAND_TRANSFORM = ", ".join(
    [
        # UCSC writes `chr1`; every other table in this warehouse is bare, and a join that
        # has to strip a prefix at read time is a join that will one day forget to.
        "replace(chrom, 'chr', '') AS chrom",
        "TRY_CAST(chrom_length AS BIGINT) AS chrom_length",
        "TRY_CAST(p_start AS BIGINT) AS p_start",
        "TRY_CAST(p_end AS BIGINT) AS p_end",
        "TRY_CAST(cen_start AS BIGINT) AS cen_start",
        "TRY_CAST(cen_end AS BIGINT) AS cen_end",
        "TRY_CAST(q_start AS BIGINT) AS q_start",
        "TRY_CAST(q_end AS BIGINT) AS q_end",
        "acrocentric = 'True' AS acrocentric",
        "TRY_CAST(bands AS INTEGER) AS bands",
    ]
)


def dataset(root: str) -> Dataset:
    """The staging spec, rooted where the committed TSV lives."""
    return Dataset(
        table=TABLE,
        source="cytoband_arms.tsv",
        root=root,
        transform=CYTOBAND_TRANSFORM,
        description="One row per canonical contig: the centromere span, the two arm "
        "boundaries either side of it, the assembly length, and whether the "
        "short arm is a ribosomal stalk with no callable sequence (13, 14, "
        "15, 21, 22). Bare contigs, 0-based half-open bounds as UCSC "
        "publishes them. Reference geometry: no sample appears here.",
    )


def read_provenance(root: Path) -> dict:
    """The manifest as a dict, or ``{}`` when it has not been built."""
    path = root / PROVENANCE_FILE
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def lineage(root: Path) -> dict[str, str] | None:
    """The lineage edge for ``cytoband_arms``, read off its manifest.

    ``None`` when there is no manifest: an edge naming a digest nobody observed would be
    fabricated, so the table carries no lineage until the tool has run.
    """
    manifest = read_provenance(root)
    if not manifest:
        return None
    inputs = manifest.get("inputs") or [{}]
    bands = next((item for item in inputs if isinstance(item, dict)), {})
    outputs = manifest.get("outputs") or [{}]
    return {
        "source_version": (
            f"UCSC {bands.get('release', '?')} cytoBand, {bands.get('bytes') or 0:,} bytes, "
            f"built {manifest.get('built_at', 'unknown')}"
        ),
        "source_sha256": str(bands.get("sha256") or ""),
        "transform": (
            f"tools/build_cytobands.py at {manifest.get('code_version', 'unknown')}: "
            f"{manifest.get('method', '')}"
        ),
        "notes": (
            f"upstream {bands.get('url', '?')}; {manifest.get('licence', '')}. "
            f"Output sha256 {str(outputs[0].get('sha256', ''))[:12]}, "
            f"{outputs[0].get('rows', 0):,} rows. {manifest.get('note', '')}"
        ),
    }
