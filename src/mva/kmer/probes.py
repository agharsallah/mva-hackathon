"""Reference/alternate k-mer pairs — the instrument that reads an allele without an aligner.

An allele is a difference between this child's DNA and the reference at one place. Write
out the *k* letters around that place twice — once as the reference has them, once as the
allele has them — and you have two k-mers that differ only by the variant. Counting how
often each appears in the reads says which copies of the gene carry which, with no aligner
deciding where a read belongs and no caller deciding what a haplotype looks like. That is
the whole of FastGT's idea (Pajuste 2017) and it is what this module builds.

**Three pairs per allele, not one.** A single probe can be destroyed by something that has
nothing to do with the allele being typed: another variant this child happens to carry a
few bases away changes the k-mer, and the probe then reads as absent. Three windows shifted
across the variant fail independently, so disagreement between them is visible instead of
being mistaken for a genotype. Alleles that cannot get three are kept and **listed**, never
silently dropped — an allele with two usable probes is a weaker measurement, not a missing
one.

**Uniqueness is checked on the alternate k-mer.** Step 2 filtered its witness probes on the
*reference* k-mer's uniqueness while the strike searched for the *alternate*, and its recall
loss concentrated exactly there (entry 087). The alternate is the one being counted, so it
is the one that has to be unambiguous: an alternate k-mer that already occurs somewhere in
GRCh38 would be found in reads from that other place and read as this allele being present.
The expected count of a true alternate k-mer in the reference is therefore **zero**, and the
expected count of a reference k-mer is **one**.

**Probe sequences are patient data.** A reference k-mer is public; an alternate k-mer spells
out a base this child carries. Nothing here writes a sequence anywhere — the module returns
packed integers, and the tool that calls it keeps them under ``build/``, which
``tools/check_coordinates.py`` rule 4 backstops.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import fasta
from .encode import CODES, INVALID, K, window_kmers
from .membership import Bait

#: Probe pairs per allele. Three is FastGT's rule and the number H024 is written about.
DEFAULT_PROBES = 3

#: Bases of reference kept either side of the variant when building the two local
#: haplotypes. ``k`` is enough for any window that spans the variant; ``2 * k`` leaves room
#: for an insertion longer than ``k`` without a second read of the contig.
FLANK = 2


@dataclass(frozen=True)
class Allele:
    """One difference from the reference, in VCF's spelling.

    ``position`` is 1-based and names the first base of ``ref``, exactly as a VCF row does.
    ``label`` is how the allele is named in every committed table — a gene and an ordinal,
    never the position.
    """

    contig: str
    position: int
    ref: str
    alt: str
    label: str

    @property
    def is_snv(self) -> bool:
        return len(self.ref) == 1 and len(self.alt) == 1


@dataclass(frozen=True)
class ProbePair:
    """One window, spelled both ways."""

    allele: int
    offset: int
    ref_kmer: int
    alt_kmer: int


@dataclass(frozen=True)
class Design:
    """The probes, and an honest account of every allele that did not get its three."""

    alleles: tuple[Allele, ...]
    pairs: tuple[ProbePair, ...]
    skipped: dict[str, int]

    def by_allele(self) -> dict[int, list[ProbePair]]:
        grouped: dict[int, list[ProbePair]] = {}
        for pair in self.pairs:
            grouped.setdefault(pair.allele, []).append(pair)
        return grouped

    def counts_per_allele(self) -> np.ndarray:
        """Probe pairs surviving per allele, in allele order — including the zeros."""
        counts = np.zeros(len(self.alleles), dtype=np.int32)
        for pair in self.pairs:
            counts[pair.allele] += 1
        return counts

    def kmers(self) -> np.ndarray:
        """Every probe k-mer, reference and alternate together — the uniqueness pass's input.

        One array rather than two, because the pass costs a full reference stream either way
        and a k-mer that is one allele's alternate and another's reference must be counted
        once, not twice with two different answers.
        """
        values = [(pair.ref_kmer, pair.alt_kmer) for pair in self.pairs]
        return np.array([value for pair in values for value in pair], dtype=np.uint64)


def _offsets(k: int, ref_len: int, alt_len: int, shift: int, probes: int) -> list[int]:
    """Window starts, relative to the variant's first base, that actually discriminate.

    ``shift`` is the length of the common prefix of ``ref`` and ``alt``. For a substitution
    it is 0; for a VCF-spelled indel it is 1, because VCF repeats the base before the change
    on both sides as an anchor. The first *informative* base is therefore at ``shift``, not
    at 0 — and a window that stops short of it spells the two haplotypes identically. That
    is not a probe that failed, it is not a probe.

    So a usable window must reach the informative base on **both** haplotypes:
    ``shift - k + 1 <= offset <= min(ref_len, alt_len) - 1``. For a pure insertion the upper
    bound is the anchor itself, which is why a window flush against an insertion's left edge
    is excluded rather than discovered later to be useless.

    The requested number is spread evenly across that range rather than taken from one end:
    adjacent windows share all but one base and fail together, and probes that fail together
    are one probe wearing three names.
    """
    low, high = shift - k + 1, min(ref_len, alt_len) - 1
    span = high - low
    if probes <= 1 or span <= 0:
        return [low + max(span, 0) // 2]
    step = span / (probes - 1)
    return sorted({round(low + index * step) for index in range(probes)})


def _common_prefix(ref: str, alt: str) -> int:
    """How many leading bases the two spellings share.

    VCF writes an indel with the base before it repeated on both sides as an anchor, so the
    change starts one base in. Reading that off the strings rather than assuming it means a
    callset that spells its indels differently still gets windows that discriminate.
    """
    shared = 0
    for left, right in zip(ref, alt, strict=False):
        if left != right:
            break
        shared += 1
    return shared


def _haplotypes(bases: np.ndarray, allele: Allele, k: int) -> tuple[np.ndarray, np.ndarray]:
    """The local reference and alternate sequences as 2-bit codes, variant at ``flank``."""
    flank = FLANK * k
    start = allele.position - 1
    left = bases[max(0, start - flank) : start]
    right = bases[start + len(allele.ref) : start + len(allele.ref) + flank]
    reference = np.concatenate([left, np.frombuffer(allele.ref.encode(), dtype=np.uint8), right])
    alternate = np.concatenate([left, np.frombuffer(allele.alt.encode(), dtype=np.uint8), right])
    return CODES[reference], CODES[alternate]


def _window(codes: np.ndarray, at: int, k: int) -> int | None:
    """The canonical k-mer starting at ``at``, or ``None`` if it runs off or holds an ``N``."""
    if at < 0 or at + k > codes.size:
        return None
    piece = codes[at : at + k]
    if (piece == INVALID).any():
        return None
    kmers, valid = window_kmers(piece, k)
    return int(kmers[0]) if valid[0] else None


def _pairs_for(
    bases: np.ndarray, index: int, allele: Allele, k: int, probes: int, skipped: dict[str, int]
) -> list[ProbePair]:
    reference, alternate = _haplotypes(bases, allele, k)
    anchor = min(FLANK * k, allele.position - 1)
    shift = _common_prefix(allele.ref, allele.alt)
    found: list[ProbePair] = []
    for offset in _offsets(k, len(allele.ref), len(allele.alt), shift, probes):
        ref_kmer = _window(reference, anchor + offset, k)
        # An indel shifts everything right of the variant, so the alternate window that
        # spans the variant is not the same window on the reference. Both still span it,
        # which is what the pair is for; they are not the same coordinates, and for an
        # indel they cannot be.
        alt_kmer = _window(alternate, anchor + offset, k)
        if ref_kmer is None or alt_kmer is None:
            skipped["window_off_contig_or_n"] = skipped.get("window_off_contig_or_n", 0) + 1
            continue
        if ref_kmer == alt_kmer:
            # Possible for an indel inside a repeat: the alternate spelling of this window
            # is the reference spelling of it. The probe cannot discriminate and is not one.
            skipped["ref_equals_alt"] = skipped.get("ref_equals_alt", 0) + 1
            continue
        found.append(ProbePair(allele=index, offset=offset, ref_kmer=ref_kmer, alt_kmer=alt_kmer))
    return found


def _by_contig(alleles: Iterable[Allele]) -> dict[str, list[tuple[int, Allele]]]:
    grouped: dict[str, list[tuple[int, Allele]]] = {}
    for index, allele in enumerate(alleles):
        grouped.setdefault(allele.contig, []).append((index, allele))
    return grouped


def design(
    reference: Path,
    alleles: Iterable[Allele],
    *,
    k: int = K,
    probes: int = DEFAULT_PROBES,
) -> Design:
    """Build ``probes`` reference/alternate pairs for every allele, in one reference pass.

    Alleles are grouped by contig and the reference is streamed once, because holding all
    of GRCh38 to slice a few hundred bases per allele is the shape of problem
    :mod:`mva.kmer.uniqueness` already refused.
    """
    ordered = tuple(alleles)
    grouped = _by_contig(ordered)
    skipped: dict[str, int] = {}
    pairs: list[ProbePair] = []
    seen: set[str] = set()
    for contig in fasta.contigs(reference, wanted=set(grouped)):
        seen.add(contig.name)
        for index, allele in grouped[contig.name]:
            pairs.extend(_pairs_for(contig.bases, index, allele, k, probes, skipped))
    for name, rows in grouped.items():
        if name not in seen:
            skipped["contig_not_in_reference"] = skipped.get("contig_not_in_reference", 0) + len(
                rows
            )
    return Design(alleles=ordered, pairs=tuple(pairs), skipped=skipped)


def unique_only(design_: Design, counts: dict[int, int]) -> tuple[Design, dict[str, int]]:
    """Keep pairs whose alternate k-mer is absent from the reference and whose reference
    k-mer occurs exactly once.

    ``counts`` maps a packed k-mer to its occurrence count in the genome — the output of
    :func:`mva.kmer.uniqueness.count_in_genome` over :meth:`Design.kmers`. Two rules, both
    with a reason:

    * **alternate count must be 0.** A non-zero count means this spelling already exists
      somewhere in GRCh38, so reads from that place would be counted as this allele.
    * **reference count must be 1.** More than one and the reference side of the ratio
      collects reads from elsewhere, which inflates the denominator and reads the allele as
      under-represented.
    """
    report = dict(design_.skipped)
    kept: list[ProbePair] = []
    for pair in design_.pairs:
        if counts.get(pair.alt_kmer, 0) != 0:
            report["alt_kmer_occurs_in_reference"] = (
                report.get("alt_kmer_occurs_in_reference", 0) + 1
            )
            continue
        if counts.get(pair.ref_kmer, 0) != 1:
            report["ref_kmer_not_unique"] = report.get("ref_kmer_not_unique", 0) + 1
            continue
        kept.append(pair)
    return Design(alleles=design_.alleles, pairs=tuple(kept), skipped=report), report


def occurrence_map(design_: Design, counts: np.ndarray) -> dict[int, int]:
    """Pair each probe k-mer with its genome count, via the deduplicated set that was scanned."""
    values = design_.kmers()
    bait = Bait.of(values)
    slots = bait.positions(values)
    return {int(value): int(counts[slot]) for value, slot in zip(values, slots, strict=True)}


def stream_alleles(rows: Iterable[tuple[str, int, str, str, str]]) -> Iterator[Allele]:
    """``(contig, position, ref, alt, label)`` tuples as alleles — the SQL-shaped entry point."""
    for contig, position, ref, alt, label in rows:
        yield Allele(contig=str(contig), position=int(position), ref=ref, alt=alt, label=label)


__all__ = [
    "DEFAULT_PROBES",
    "Allele",
    "Design",
    "ProbePair",
    "design",
    "occurrence_map",
    "stream_alleles",
    "unique_only",
]
