"""Variant identity, in the exact representation the challenge scorer compares.

The scorer builds its key as ``(chrom.strip(), int(pos), ref.upper(), alt.upper())`` and
compares it verbatim — it never normalizes the chromosome. The proband VCF was called
against ``GCA_000001405.15_GRCh38..._no_chr.fasta``, so its contigs are bare (``15``),
while the submission template uses ``chr15``. Bridging that gap is this module's job,
and doing it in one place is what keeps it from being re-decided at every call site.
"""

from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class Variant:
    """A single ALT allele at a position, in submission representation."""

    chrom: str
    pos: int
    ref: str
    alt: str

    @classmethod
    def from_vcf(cls, chrom: str, pos: int, ref: str, alt: str) -> "Variant":
        """Build from a VCF record, converting to the scorer's representation."""
        pos = int(pos)
        if pos < 1:
            raise ValueError(f"VCF positions are 1-based; got {pos}")
        return cls(to_submission_contig(chrom), pos, ref.upper(), alt.upper())


def to_submission_contig(chrom: str) -> str:
    """Return the ``chr``-prefixed GRCh38 name for a VCF contig."""
    name = chrom.strip()
    if name.startswith("chr"):
        return name
    # The no-chr analysis set spells the mitochondrion "M"; "MT" appears in Ensembl-style
    # references. Both are chrM in the chr-prefixed convention.
    if name in ("M", "MT"):
        return "chrM"
    return f"chr{name}"
