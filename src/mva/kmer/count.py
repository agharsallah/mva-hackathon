"""How many reads carry each k-mer — multiplicity, which membership cannot answer.

:mod:`mva.kmer.membership` answers *"is this k-mer in the set"* and :func:`~.membership.hits`
answers *"does this read touch the set"*. Both are booleans, and step 2 needed nothing more:
it was selecting reads, and a read either came from a baited region or it did not.

Step 3 asks the question that boolean throws away. An allele present on one of the two
inherited copies puts its k-mer into roughly **half** the reads covering that position; an
allele present on both puts it into nearly all of them; an allele that is not there at all
still shows a few from sequencing error. Those three cases differ only in *how many*, so
genotyping from k-mers is counting, and `contains` cannot count.

**Why not `mva.reads.scan.counts`.** That does answer multiplicity, through a multi-literal
string matcher validated at 20 literals and capped in practice around 500. Step 3 designs at
least three probe pairs per allele across tens of thousands of alleles. Three orders of
magnitude apart is a different data structure, not the same one run longer — the same
argument that put `membership` beside `scan` in the first place.

**Why not KMC or Jellyfish.** They build a table of every k-mer in the input. We hold the
few thousand we care about and want their counts, so the direction is reversed exactly as in
:mod:`mva.kmer.uniqueness`: the reads stream past the probe set. That is a smaller problem,
and it is why this runs on a laptop.

**Stride is not available here.** :func:`~.membership.hits` samples every 16th window and
still answers correctly, because a read overlapping the bait by ≥ 46 bases hits *some*
sampled window. A sampled count is not a count: a probe occurring once in a read is seen by
exactly one window, and sampling would miss it fifteen times in sixteen. Every window is
read, and the parameter does not exist.

**Two functions, because a read pair is one molecule.** :func:`tally` counts occurrences,
which is what a coverage-like quantity wants. :func:`hits_per_read` returns which read
carried which probe, so a caller that knows how reads pair up can collapse R1 and R2 of the
same fragment before counting — they are two reads of one piece of DNA, and at a ~266 bp
fragment against 2 × 150 bp of read they overlap, so a probe in the overlap would otherwise
be counted twice for one molecule.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .encode import strided_kmers
from .membership import Bait

#: Reads per chunk. A chunk materialises two arrays of ``rows × (length - k + 1)`` 64-bit
#: values, so 50,000 reads of 150 bases is ~2 × 48 MB — small enough to stay in cache-warm
#: working memory, large enough that per-chunk overhead disappears.
CHUNK_ROWS = 50_000


@dataclass(frozen=True)
class Tally:
    """Occurrences per probe, and what was read to get them."""

    counts: np.ndarray
    reads_scanned: int
    windows_scanned: int

    @property
    def observed(self) -> int:
        """Probes seen at least once."""
        return int((self.counts > 0).sum())

    @property
    def silent(self) -> int:
        """Probes no read carried. For an alternate k-mer this is the allele's absence —
        or its dropout, which the genotype model separates and this module does not."""
        return int((self.counts == 0).sum())

    def merged(self, other: Tally) -> Tally:
        """Two chunks of the same probe set, added. Counting is a fold, so a caller may
        stream a store in pieces and combine them without holding the reads."""
        if self.counts.shape != other.counts.shape:
            raise ValueError("tallies over different probe sets cannot be merged")
        return Tally(
            counts=self.counts + other.counts,
            reads_scanned=self.reads_scanned + other.reads_scanned,
            windows_scanned=self.windows_scanned + other.windows_scanned,
        )


def _chunks(rows: int, size: int) -> list[tuple[int, int]]:
    return [(start, min(start + size, rows)) for start in range(0, rows, size)]


def hits_per_read(
    codes: np.ndarray, probes: Bait, *, chunk_rows: int = CHUNK_ROWS
) -> tuple[np.ndarray, np.ndarray]:
    """Which probe each read carries, as two aligned arrays ``(read_row, probe_index)``.

    A read carrying one probe at several positions appears **once**: the pair is the fact
    "this read carries this probe", and a probe repeated inside a single read is a property
    of the sequence, not extra evidence. A read carrying two different probes appears twice,
    which is correct — a reference and an alternate probe of the same allele cannot both be
    on one read, but two probes of *different* alleles can.
    """
    rows: list[np.ndarray] = []
    cols: list[np.ndarray] = []
    for start, stop in _chunks(codes.shape[0], chunk_rows):
        block = codes[start:stop]
        kmers, valid = strided_kmers(block, probes.k, 1)
        if kmers.size == 0:
            continue
        slots = probes.positions(kmers)
        found = (slots >= 0) & valid
        if not found.any():
            continue
        row, offset = np.nonzero(found)
        pair = np.unique(
            np.stack([row + start, slots[row, offset]], axis=1),
            axis=0,
        )
        rows.append(pair[:, 0])
        cols.append(pair[:, 1])
    if not rows:
        return np.empty(0, dtype=np.int64), np.empty(0, dtype=np.int64)
    return np.concatenate(rows), np.concatenate(cols)


def tally(codes: np.ndarray, probes: Bait, *, chunk_rows: int = CHUNK_ROWS) -> Tally:
    """Total occurrences of every probe across a ``(rows, length)`` code matrix.

    Every window of every read is read; see the module docstring on why there is no stride.
    """
    counts = np.zeros(len(probes), dtype=np.uint32)
    windows = 0
    for start, stop in _chunks(codes.shape[0], chunk_rows):
        kmers, valid = strided_kmers(codes[start:stop], probes.k, 1)
        if kmers.size == 0:
            continue
        windows += int(valid.sum())
        slots = probes.positions(kmers)
        found = slots[(slots >= 0) & valid]
        if found.size:
            np.add.at(counts, found, 1)
    return Tally(counts=counts, reads_scanned=int(codes.shape[0]), windows_scanned=windows)


def by_fragment(
    read_rows: np.ndarray, probe_index: np.ndarray, fragment_of: np.ndarray, probes: int
) -> np.ndarray:
    """Collapse per-read hits to per-fragment counts.

    ``fragment_of`` maps each read row to an integer identifying the molecule it came from,
    so R1 and R2 of one pair share a value. A probe is counted **once per fragment**, which
    is the unit the genotype model's coverage parameter is about: two reads of one piece of
    DNA are one observation of that piece, not two.
    """
    counts = np.zeros(probes, dtype=np.uint32)
    if read_rows.size == 0:
        return counts
    pair = np.unique(np.stack([fragment_of[read_rows], probe_index], axis=1), axis=0)
    np.add.at(counts, pair[:, 1], 1)
    return counts


__all__ = ["CHUNK_ROWS", "Tally", "by_fragment", "hits_per_read", "tally"]
