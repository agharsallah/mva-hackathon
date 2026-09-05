"""The coding-regions reference table: where a variant can change a protein.

Split from :mod:`mva.warehouse.reference` so that module stays under the size gate. This
is the sixth staged reference table, and the first one that is *geometry* rather than a
score: one row per merged coding interval per gene, built by
``tools/build_coding_regions.py`` from the Ensembl GTF. The genome-wide coding scan in
:mod:`mva.warehouse.analysis_coding` joins the callset to it, which is what turns "annotate
five million alleles" into "annotate the few tens of thousands that can alter a protein".

Its lineage is read off the manifest the build tool writes beside the TSV, the same way
the HPO tables' is: the digest and the release are observed at build time, never typed.
"""

from __future__ import annotations

import json
from pathlib import Path

from .catalog import Dataset

__all__ = ["CODING_REGIONS_TRANSFORM", "PROVENANCE_FILE", "TABLE", "dataset", "lineage"]

TABLE = "coding_regions"

#: The provenance sidecar ``tools/build_coding_regions.py`` writes beside the TSV.
PROVENANCE_FILE = "coding_regions.provenance.json"

CODING_REGIONS_TRANSFORM = ", ".join(
    [
        # Bare contig already; the builder restricts to the 25 canonical names.
        "chrom",
        "TRY_CAST(start AS BIGINT) AS start",
        'TRY_CAST("end" AS BIGINT) AS "end"',
        "gene",
        "gene_id",
        "TRY_CAST(n_cds AS INTEGER) AS n_cds",
        "TRY_CAST(n_transcripts AS INTEGER) AS n_transcripts",
    ]
)


def dataset(root: str) -> Dataset:
    """The staging spec, rooted where the committed TSV lives."""
    return Dataset(
        table=TABLE,
        source="coding_regions.tsv",
        root=root,
        transform=CODING_REGIONS_TRANSFORM,
        description="Every merged coding interval (CDS plus stop codon, widened by a short "
        "splice flank) per protein-coding gene, from the Ensembl GTF. Bare "
        "contigs, 1-based inclusive bounds. An allele inside two overlapping "
        "genes appears once per gene when joined. Deep-intronic and UTR "
        "positions are outside this table by construction.",
    )


def read_provenance(root: Path) -> dict:
    """The manifest as a dict, or ``{}`` when it has not been built."""
    path = root / PROVENANCE_FILE
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def lineage(root: Path) -> dict[str, str] | None:
    """The lineage edge for ``coding_regions``, read off its manifest.

    ``None`` when there is no manifest: an edge naming a digest nobody observed would be
    fabricated, so the table simply carries no lineage until the tool has run.
    """
    manifest = read_provenance(root)
    if not manifest:
        return None
    inputs = manifest.get("inputs") or []
    gtf = next((item for item in inputs if isinstance(item, dict)), {})
    outputs = manifest.get("outputs") or [{}]
    return {
        "source_version": (
            f"Ensembl release {gtf.get('release', '?')} GTF, {gtf.get('name', '?')} "
            f"{gtf.get('bytes') or 0:,} bytes, built {manifest.get('built_at', 'unknown')}"
        ),
        "source_sha256": str(gtf.get("sha256") or ""),
        "transform": (
            f"tools/build_coding_regions.py at {manifest.get('code_version', 'unknown')}: "
            f"{manifest.get('method', '')}"
        ),
        "notes": (
            f"upstream {gtf.get('url', '?')}; {manifest.get('licence', '')}. "
            f"Output sha256 {str(outputs[0].get('sha256', ''))[:12]}, "
            f"{outputs[0].get('rows', 0):,} rows. {manifest.get('note', '')}"
        ),
    }
