"""How many times each bait k-mer occurs in the whole reference — the off-target gate.

**Why a bait k-mer can be a liar.** ~50 % of the human genome is repetitive. A 31-mer cut
from a gene's intron may also occur in a pseudogene, a transposon or a paralogue somewhere
else entirely, and every read from *those* places would be recovered too. The plan's gate
is "bait k-mers present more than once in GRCh38 are dropped **and counted**", and the
count is the honest measure of how repetitive the chosen target set is.

**How, without KMC or Jellyfish.** Those tools build a table of *every* k-mer in the
genome (billions of entries, tens of GB, Linux-only builds). We do not need that table —
we only need the occurrence count of the ~40 M k-mers we already hold. So the direction is
reversed: stream the reference once, and for each of its 3.1 billion windows ask the bait
"is this one of yours, and which?". The bitmap prefilter rejects ~96 % of windows with one
memory access, so the expensive sorted-array lookup runs on the remainder.

That is a genuinely smaller problem than the one the k-mer counters solve, and it is why
this stage runs on a laptop at all.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import fasta
from .encode import codes_of, window_kmers
from .membership import Bait

#: Reference bases per counting chunk. Each chunk allocates a few arrays of this length in
#: uint64, so 8 M bases is ~200 MB of working set — small enough to stay resident, large
#: enough that the per-chunk overhead disappears.
CHUNK_BASES = 8_000_000


@dataclass(frozen=True)
class Occurrence:
    """The result of the genome pass."""

    counts: np.ndarray
    windows_scanned: int

    @property
    def unique(self) -> np.ndarray:
        """Mask of bait k-mers occurring exactly once in the reference."""
        return np.asarray(self.counts == 1, dtype=bool)

    @property
    def repeated(self) -> int:
        return int((self.counts > 1).sum())

    @property
    def unseen(self) -> int:
        """Bait k-mers the genome pass never found.

        Should be zero: every bait k-mer was cut from this same reference. A non-zero
        value means the bait and the reference disagree — a different build, a different
        contig naming, or a truncated download — and is a hard failure, not a warning.
        """
        return int((self.counts == 0).sum())


def _chunks(bases: np.ndarray, k: int, size: int = CHUNK_BASES) -> Iterator[np.ndarray]:
    """Overlapping slices, so no window that straddles a chunk boundary is lost."""
    if bases.size < k:
        return
    step = max(size, k)
    start = 0
    while start < bases.size - k + 1:
        yield bases[start : start + step + k - 1]
        start += step


def count_in_genome(
    reference: Path, bait: Bait, *, chunk_bases: int = CHUNK_BASES, contigs: set[str] | None = None
) -> Occurrence:
    """One streaming pass over the reference, counting hits per bait k-mer.

    ``contigs`` restricts the pass; the default is every contig in the file, which is the
    correct choice for the gate — a bait k-mer that also occurs on a decoy or unplaced
    contig is exactly as off-target as one that occurs on another chromosome.
    """
    counts = np.zeros(len(bait), dtype=np.uint32)
    scanned = 0
    for contig in fasta.contigs(reference, wanted=contigs):
        codes = codes_of(contig.bases)
        for piece in _chunks(codes, bait.k, chunk_bases):
            kmers, valid = window_kmers(piece, bait.k)
            scanned += int(valid.sum())
            slots = bait.positions(kmers[valid])
            found = slots[slots >= 0]
            if found.size:
                np.add.at(counts, found, 1)
    return Occurrence(counts=counts, windows_scanned=scanned)


def drop_repeats(bait: Bait, occurrence: Occurrence) -> tuple[Bait, dict[str, int]]:
    """Keep only the k-mers that occur once; report what was dropped and why."""
    kept = bait.subset(occurrence.unique)
    report = {
        "bait_kmers": len(bait),
        "unique": len(kept),
        "repeated": occurrence.repeated,
        "unseen": occurrence.unseen,
        "windows_scanned": occurrence.windows_scanned,
    }
    return kept, report
