"""Read the delivery's file-naming convention into structured facts.

A **FASTQ** (raw sequencer reads, one text record per read) or **VCF** (variant call
format — one row per candidate mutation) file name encodes lane, read number and
flowcell (the sequencing run that produced it). Those facts get re-parsed ad hoc in a
dozen places unless they are extracted once, here, independent of any database or object
store. :mod:`mva.warehouse.lineage` re-exports :class:`Enriched` and :func:`enrich` for
callers; :mod:`mva.warehouse.lineage_inventory` calls :func:`enrich` while building the
object inventory.
"""

import re
from dataclasses import dataclass

#: The delivery's filename convention:
#: ``<sample>_<flowcell>_S<n>_L00<lane>_R<read>_001.fastq.gz``
#:
#: Anchored on the **right**, because the sample identifier itself contains underscores
#: (``WGS_EX2312012``). Splitting from the left assigns the sample's own suffix to the
#: flowcell and then matches nothing at all.
FASTQ_NAME = re.compile(
    r"^(?P<prefix>.+)_S(?P<snum>\d+)_L(?P<lane>\d+)_R(?P<read>\d)_\d+\.fastq\.gz$"
)

#: ``<sample>_<flowcell>.vcf.gz`` and its index, same right-anchored reasoning.
VCF_NAME = re.compile(r"^(?P<prefix>.+)\.vcf\.gz(?P<idx>\.tbi)?$")


def _split_prefix(prefix: str) -> tuple[str, str | None]:
    """Separate ``<sample>_<flowcell>``: the flowcell is the final underscore-delimited part."""
    sample, _, flowcell = prefix.rpartition("_")
    return (sample, flowcell) if sample else (prefix, None)


@dataclass(frozen=True)
class Enriched:
    """Facts read out of an object's name, or ``None`` where the name does not carry them."""

    sample: str | None = None
    flowcell: str | None = None
    lane: int | None = None
    read_num: int | None = None
    role: str = "other"

    @property
    def mate_key(self) -> str | None:
        """Identifies the pair a FASTQ belongs to: both mates share it."""
        if self.lane is None or self.flowcell is None:
            return None
        return f"{self.flowcell}:L{self.lane}"


def enrich(file_name: str) -> Enriched:
    """Parse the delivery's naming convention into structured facts.

    Deliberately conservative: an unrecognised name yields empty fields rather than a
    guess. A wrong lane number silently attached to a read is worse than a null.
    """
    match = FASTQ_NAME.match(file_name)
    if match:
        sample, flowcell = _split_prefix(match["prefix"])
        return Enriched(
            sample=sample,
            flowcell=flowcell,
            lane=int(match["lane"]),
            read_num=int(match["read"]),
            role="reads",
        )
    match = VCF_NAME.match(file_name)
    if match:
        sample, flowcell = _split_prefix(match["prefix"])
        return Enriched(
            sample=sample, flowcell=flowcell, role="variant_index" if match["idx"] else "variants"
        )
    if file_name.lower().endswith((".md", ".docx", ".txt", ".pdf")):
        return Enriched(role="document")
    return Enriched()
