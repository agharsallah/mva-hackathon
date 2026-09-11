"""The set of bait k-mers, and the question "does this read touch it?".

A bait of 42 Mb of reference is ~40 million distinct 31-mers. Three shapes were available
for membership and only one survives the arithmetic:

===========================  ===========================================================
Python ``set`` of ints       ~3 GB of boxed objects, one interpreter call per lookup
Aho-Corasick over strings    what :mod:`mva.reads.scan` uses; validated at 20 literals,
                             an automaton over 40 M is a different problem
**sorted uint64 + bitmap**   320 MB of contiguous integers, ``np.searchsorted`` on a whole
                             batch at once, behind a bitmap that rejects ~96 % of misses
                             with a single memory access
===========================  ===========================================================

**The bitmap is a prefilter, never an answer.** A set bit means "this k-mer *might* be in
the bait" (hash collisions are possible); a clear bit means "definitely not". Every
surviving candidate is still confirmed against the sorted array, so the result is exact
and the bitmap only changes how long it takes. Its size is a memory/speed trade recorded
with the run, not a correctness knob.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .encode import K, strided_kmers

#: Bits in the default prefilter: 2**30 bits = 128 MiB of packed words. At ~40 M bait
#: k-mers that is ~4 % of bits set, so ~96 % of misses are rejected without touching the
#: sorted array.
DEFAULT_BITMAP_BITS = 30

_U64 = np.uint64
_MASK64 = _U64(0xFFFFFFFFFFFFFFFF)


def _mix(values: np.ndarray) -> np.ndarray:
    """SplitMix64's finaliser — spreads k-mers whose top bits are correlated (GC-rich
    regions, repeats) so that the bitmap's load stays even."""
    with np.errstate(over="ignore"):
        mixed = values ^ (values >> _U64(30))
        mixed = (mixed * _U64(0xBF58476D1CE4E5B9)) & _MASK64
        mixed = mixed ^ (mixed >> _U64(27))
        mixed = (mixed * _U64(0x94D049BB133111EB)) & _MASK64
        return np.asarray(mixed ^ (mixed >> _U64(31)), dtype=np.uint64)


def build_bitmap(kmers: np.ndarray, bits: int = DEFAULT_BITMAP_BITS) -> np.ndarray:
    """Pack a presence bitmap of ``2**bits`` bits over ``kmers``."""
    if not 3 <= bits <= 34:
        raise ValueError(f"bitmap bits must be between 3 and 34, got {bits}")
    slots = _mix(kmers.astype(np.uint64)) & _U64((1 << bits) - 1)
    words = np.zeros(1 << (bits - 6), dtype=np.uint64)
    np.bitwise_or.at(words, slots >> _U64(6), _U64(1) << (slots & _U64(63)))
    return words


@dataclass(frozen=True)
class Bait:
    """A sorted, unique, canonical k-mer set, with its prefilter.

    ``kmers`` must be sorted and unique — :meth:`of` is the constructor that guarantees it.
    ``bitmap`` may be ``None``, in which case every lookup goes to the sorted array; the
    answer is identical either way.
    """

    kmers: np.ndarray
    k: int = K
    bitmap: np.ndarray | None = None
    bits: int = DEFAULT_BITMAP_BITS

    def __len__(self) -> int:
        return int(self.kmers.size)

    @classmethod
    def of(cls, kmers: np.ndarray, k: int = K, bits: int | None = DEFAULT_BITMAP_BITS) -> Bait:
        """Sort, de-duplicate and (unless ``bits`` is ``None``) index a k-mer array."""
        unique = np.unique(np.asarray(kmers, dtype=np.uint64))
        bitmap = build_bitmap(unique, bits) if bits is not None and unique.size else None
        return cls(kmers=unique, k=k, bitmap=bitmap, bits=bits or DEFAULT_BITMAP_BITS)

    def _prefilter(self, values: np.ndarray) -> np.ndarray:
        if self.bitmap is None:
            return np.ones(values.shape, dtype=bool)
        slots = _mix(values) & _U64((1 << self.bits) - 1)
        words = self.bitmap[slots >> _U64(6)]
        return np.asarray((words >> (slots & _U64(63))) & _U64(1), dtype=bool)

    def contains(self, values: np.ndarray) -> np.ndarray:
        """Exact membership for an array of packed k-mers, of any shape."""
        flat = np.ascontiguousarray(values, dtype=np.uint64).ravel()
        answer = np.zeros(flat.shape, dtype=bool)
        if self.kmers.size == 0 or flat.size == 0:
            return answer.reshape(values.shape)
        maybe = self._prefilter(flat)
        candidates = flat[maybe]
        index = np.searchsorted(self.kmers, candidates)
        np.clip(index, 0, self.kmers.size - 1, out=index)
        answer[maybe] = self.kmers[index] == candidates
        return answer.reshape(values.shape)

    def positions(self, values: np.ndarray) -> np.ndarray:
        """Index into :attr:`kmers` for each value, or ``-1`` when absent.

        Used by :mod:`mva.kmer.uniqueness`, which needs to count *which* bait k-mer a
        genome window hit, not merely that one did.
        """
        flat = np.ascontiguousarray(values, dtype=np.uint64).ravel()
        found = np.full(flat.shape, -1, dtype=np.int64)
        if self.kmers.size == 0 or flat.size == 0:
            return found.reshape(values.shape)
        maybe = self._prefilter(flat)
        candidates = flat[maybe]
        index = np.searchsorted(self.kmers, candidates)
        np.clip(index, 0, self.kmers.size - 1, out=index)
        hit = self.kmers[index] == candidates
        slot = np.where(hit, index, -1)
        found[maybe] = slot
        return found.reshape(values.shape)

    def subset(self, keep: np.ndarray) -> Bait:
        """A new bait holding only the k-mers ``keep`` selects, re-indexed."""
        return Bait.of(self.kmers[keep], k=self.k, bits=self.bits)

    def save(self, path: Path) -> Path:
        """Write just the k-mers (``.npy``); the bitmap is cheap to rebuild on load."""
        path.parent.mkdir(parents=True, exist_ok=True)
        np.save(path, self.kmers)
        return path

    @classmethod
    def load(cls, path: Path, k: int = K, bits: int | None = DEFAULT_BITMAP_BITS) -> Bait:
        return cls.of(np.load(path), k=k, bits=bits)


def hits(codes: np.ndarray, bait: Bait, stride: int = 1) -> np.ndarray:
    """Which reads of a ``(rows, length)`` code matrix share a k-mer with the bait.

    One boolean per row. A row whose sampled windows all contain ``N`` is ``False``, which
    is the honest answer: the machine did not read enough of that fragment to say.
    """
    kmers, valid = strided_kmers(codes, bait.k, stride)
    if kmers.size == 0:
        return np.zeros(codes.shape[0], dtype=bool)
    return np.asarray((bait.contains(kmers) & valid).any(axis=1), dtype=bool)
