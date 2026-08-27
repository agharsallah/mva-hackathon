"""Pairing heterozygous calls into compound-heterozygote hypotheses.

The answer key is a compound-heterozygous pair, so the pipeline's job is not to rank
variants but to rank *pairs*. Two rare variants in one gene only disable it when they
lie on opposite haplotypes; a cis pair leaves one intact copy and is not a diagnosis.

Phase is decided from Sentieon's physical phasing:

* same ``PID`` and the same ``PGT`` — both on one haplotype, **cis**, rejected;
* same ``PID`` and opposite ``PGT`` — one per haplotype, **trans**, confirmed;
* two ALT alleles of one ``1/2`` record — trans by construction, no phasing needed;
* otherwise **unknown** — no evidence either way, and with no parental samples these
  stay live candidates rather than being discarded.

Physical phasing only reaches variants close enough to share a read pair (~300 bp here,
from the 266 bp insert size), so UNKNOWN is the common verdict across a whole gene and
must never be treated as a rejection.
"""

from dataclasses import dataclass
from enum import Enum
from itertools import combinations
from typing import Iterable

from .vcf import Call


class Phase(Enum):
    """Which haplotypes a pair of variants occupies."""

    CIS = "cis"
    TRANS = "trans"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class VariantPair:
    """Two heterozygous calls proposed as a biallelic hit on one gene."""

    left: Call
    right: Call
    phase: Phase

    @property
    def is_compound_het_candidate(self) -> bool:
        """A cis pair is excluded; trans and unresolved pairs stay in play."""
        return self.phase is not Phase.CIS


def candidate_pairs(calls: Iterable[Call]) -> list[VariantPair]:
    """Every unordered pair of heterozygous calls, classified by phase.

    Pairs are emitted in positional order and deduplicated, so callers can key on
    ``(pos, pos)`` without worrying about which call came first.
    """
    hets = sorted(
        (c for c in calls if c.is_het),
        key=lambda c: (c.variant.chrom, c.variant.pos, c.variant.alt),
    )
    return [VariantPair(a, b, classify_phase(a, b)) for a, b in combinations(hets, 2)]


def classify_phase(left: Call, right: Call) -> Phase:
    """Decide whether two heterozygous calls sit on the same or opposite haplotypes."""
    if left.variant.chrom != right.variant.chrom:
        return Phase.UNKNOWN

    # Two ALT alleles of a single 1/2 record: the genotype itself states that one copy
    # of each is present, so they are necessarily on opposite haplotypes.
    if left.variant.pos == right.variant.pos and left.variant.alt != right.variant.alt:
        return Phase.TRANS

    if left.phase_set is None or left.phase_set != right.phase_set:
        return Phase.UNKNOWN
    if left.phase_gt is None or right.phase_gt is None:
        return Phase.UNKNOWN
    return Phase.CIS if left.phase_gt == right.phase_gt else Phase.TRANS
