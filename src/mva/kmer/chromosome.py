"""Reference 31-mers that name a chromosome — the probe set a dosage pass counts.

Allele balance cannot see a chromosome the proband has only one copy of: with no
heterozygous sites there is nothing to be unbalanced. The male X is exactly that case, and
so is any chromosome whose event is a clean gain in every cell. What can see it is **dosage**
— how many reads came from that chromosome relative to the rest — and the alignment-free way
to measure dosage is to pick a fixed set of k-mers that occur exactly once in the reference
copy of each chromosome, count them in the reads, and compare.

**The probes are reference sequence, and that is what makes them publishable.** They are cut
from GRCh38, never from the child's reads. A probe carries no patient information at all, so
the set can be built, hashed and described in the open; only the *counts* are about anybody.

**Uniqueness is the whole design.** A 31-mer that also occurs on another chromosome would
count reads from there too, and a repeat-derived one would count a variable number of times
in the same sample. Both are dropped by :mod:`mva.kmer.uniqueness` against the genome-wide
table before the set is published, and how many were dropped is reported rather than assumed.

**Two sets, not one.** Per-chromosome probes give a *ratio* to whatever denominator the
caller chooses, and every denominator over chromosomes assumes some chromosome is normal —
which is the assumption a variegated aneuploidy breaks. So a **calibration set** is sampled
across the whole genome, and its total gives an absolute scale: k-mer mass per base, which
no chromosome can move on its own.

The calibration set is drawn **from the same pool** rather than cut separately, so it
inherits the identical spacing and the identical uniqueness filtering and carries no bias of
its own. The consequence is that its probes are also somebody's per-chromosome probes: the
two sets are read as two views of one pass, never added together.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass

import numpy as np

from .encode import K, codes_of, kmers_at
from .fasta import Contig

__all__ = ["CALIBRATION_NAME", "ChromosomeProbes", "design", "gc_content", "sample_contig"]

#: How many probes each chromosome gets by default. Ten thousand at ~44x depth is ~440,000
#: expected observations per chromosome: enough that the count's own sampling noise is well
#: under the 5 % shift a 10 % mosaic trisomy produces.
DEFAULT_PER_CHROMOSOME = 10_000

#: The genome-wide set is named rather than numbered, so a row of counts cannot be mistaken
#: for a 25th chromosome.
CALIBRATION_NAME = "calibration"


@dataclass(frozen=True)
class ChromosomeProbes:
    """One probe set: the k-mers, which contig each came from, and what was dropped."""

    kmers: np.ndarray
    contigs: tuple[str, ...]
    #: index into ``contigs`` for every k-mer
    owner: np.ndarray
    #: per contig, how many candidates were cut before the uniqueness filter
    considered: dict[str, int]
    k: int = K

    def __post_init__(self) -> None:
        if self.kmers.shape != self.owner.shape:
            raise ValueError("every probe must name the contig it came from")

    def __len__(self) -> int:
        return int(self.kmers.size)

    def per_contig(self) -> dict[str, int]:
        """How many probes survived for each contig — the number a dosage divides by."""
        counts = np.bincount(self.owner, minlength=len(self.contigs))
        return {name: int(counts[index]) for index, name in enumerate(self.contigs)}

    def as_dict(self) -> dict[str, object]:
        survived = self.per_contig()
        return {
            "k": self.k,
            "probes": len(self),
            "contigs": list(self.contigs),
            "per_contig": survived,
            "considered": dict(self.considered),
            "kept_share": {
                name: round(survived[name] / self.considered[name], 4)
                for name in self.contigs
                if self.considered.get(name)
            },
        }


def sample_contig(
    contig: Contig,
    *,
    count: int,
    rng: np.random.Generator,
    k: int = K,
    margin: int = 5_000_000,
) -> np.ndarray:
    """``count`` canonical k-mers spread evenly along one contig, skipping ambiguous windows.

    **Evenly, not randomly.** A random sample concentrates wherever the sequence happens to
    be callable and leaves megabase gaps elsewhere; an even stride gives every part of the
    contig the same weight in the dosage, which is what makes the number a property of the
    chromosome rather than of its best-behaved half.

    ``margin`` skips the ends, where telomeric and subtelomeric repeat makes almost nothing
    unique and the uniqueness filter would simply delete the sample.
    """
    codes = codes_of(contig.bases)
    usable = codes.size - k + 1
    if usable <= 0:
        return np.array([], dtype=np.uint64)
    # Never let the margin eat the contig: on anything shorter than 50 Mb -- a test fixture,
    # or a contig that is mostly telomere -- a fixed 5 Mb at each end would leave a sliver
    # and the sample would be one probe from the middle.
    edge = min(margin, usable // 10)
    start, stop = edge, max(usable - edge, edge + 1)
    # Three times the quota, because ambiguous windows will delete some of them and a
    # second pass to top up would break the even spacing the sample exists for.
    wanted = min(count * 3, max(stop - start, 1))
    positions = np.linspace(start, stop - 1, num=wanted, dtype=np.int64)

    # Only these positions, never every window: cutting ten thousand probes from a
    # 249-megabase chromosome through `window_kmers` would allocate two gigabytes to
    # produce ten thousand values, twenty-four times over.
    kmers, valid = kmers_at(codes, positions, k=k)
    chosen = kmers[valid]
    if chosen.size > count:
        # Thin evenly again rather than taking the first `count`, which would crowd the
        # probes into the start of the contig whenever its early windows are cleaner.
        chosen = chosen[np.linspace(0, chosen.size - 1, num=count, dtype=np.int64)]
    _ = rng  # the sampling is deterministic; the generator is accepted for interface parity
    return np.unique(chosen)


def design(
    contigs: Sequence[Contig] | Iterator[Contig],
    *,
    per_chromosome: int = DEFAULT_PER_CHROMOSOME,
    calibration: int = DEFAULT_PER_CHROMOSOME,
    seed: int = 0,
    k: int = K,
) -> ChromosomeProbes:
    """Cut a probe set: ``per_chromosome`` k-mers per contig, plus a genome-wide calibration.

    The calibration set is drawn from the same contigs at a lower density, so its total is a
    denominator that no single chromosome can move — the absolute scale a variegated genome
    needs. Uniqueness filtering is the caller's next step: this function decides *where* to
    look, :mod:`mva.kmer.uniqueness` decides which survive.
    """
    rng = np.random.default_rng(seed)
    names: list[str] = []
    blocks: list[np.ndarray] = []
    owners: list[np.ndarray] = []
    considered: dict[str, int] = {}

    pool: list[np.ndarray] = []
    for contig in contigs:
        picked = sample_contig(contig, count=per_chromosome, rng=rng, k=k)
        if not picked.size:
            continue
        names.append(contig.name)
        blocks.append(picked)
        owners.append(np.full(picked.size, len(names) - 1, dtype=np.int64))
        considered[contig.name] = int(picked.size)
        pool.append(picked)

    if pool:
        everywhere = np.concatenate(pool)
        drawn = rng.choice(everywhere, size=min(calibration, everywhere.size), replace=False)
        names.append(CALIBRATION_NAME)
        blocks.append(np.unique(drawn))
        owners.append(np.full(blocks[-1].size, len(names) - 1, dtype=np.int64))
        considered[CALIBRATION_NAME] = int(blocks[-1].size)

    if not blocks:
        return ChromosomeProbes(np.array([], dtype=np.uint64), (), np.array([], dtype=np.int64), {})
    return ChromosomeProbes(
        kmers=np.concatenate(blocks),
        contigs=tuple(names),
        owner=np.concatenate(owners),
        considered=considered,
        k=k,
    )


def gc_content(contig: Contig) -> float:
    """The GC fraction of one reference contig, over its called bases only.

    Runs of ``N`` -- centromeres, the acrocentric short arms, any gap the assembly did not
    close -- are excluded rather than counted as neither G nor C, because a chromosome with
    30 Mb of ``N`` would otherwise read as composition-poor when it is simply unassembled.
    Soft-masked (lower-case) sequence is folded onto upper: masking marks repeats, and a
    repeat is still made of bases.

    This is the regressor :func:`mva.kmer.dosage.composition` wants. It is deliberately the
    *chromosome's* composition and not the probes': GC bias in short-read sequencing acts on
    fragments of a few hundred bases, and a probe set is a filtered sample of the
    chromosome, so the two are not interchangeable.
    """
    upper = contig.bases & ~np.uint8(0x20)
    counts = np.bincount(upper, minlength=ord("T") + 1)
    a, c, g, t = (int(counts[ord(base)]) for base in "ACGT")
    called = a + c + g + t
    return (g + c) / called if called else 0.0
