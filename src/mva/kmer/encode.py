"""Turn DNA letters into 64-bit integers, so that "is this k-mer in that set" is one
integer comparison instead of a string search.

**The packing.** Each base is two bits (``A=0, C=1, G=2, T=3``), so a 31-mer is 62 bits
and fits in one ``uint64`` with room to spare. A sequence of *n* bases yields *n - k + 1*
overlapping windows, and every window is built in ``k`` vectorised passes over the whole
array rather than a Python loop per window — the same trick a rolling hash uses, kept
exact because 62 bits are enough to hold the k-mer itself.

**Canonical form.** A fragment is sequenced from whichever strand it came off, so the same
physical k-mer arrives as either its forward spelling or its reverse complement. Both are
computed in the same pass and the smaller integer is kept — the **canonical k-mer**. That
replaces :func:`mva.reads.scan.reverse_complement`'s "search for both spellings" with
"store one".

**Invalid bases.** Real reads contain ``N`` (the machine declined to call a base). A window
containing one has no k-mer; it is reported through a validity mask rather than silently
encoded as ``A``.
"""

from __future__ import annotations

import numpy as np

#: The k this project uses everywhere. 31 is odd (so a k-mer can never equal its own
#: reverse complement) and fits in 62 of a uint64's 64 bits.
K = 31

#: Largest k this packing can hold.
MAX_K = 32

#: Code for a base that is not A, C, G or T.
INVALID = np.uint8(255)

_TWO = np.uint64(2)
_THREE = np.uint64(3)


def _code_table() -> np.ndarray:
    """ASCII byte -> 2-bit code, with everything else :data:`INVALID`."""
    table = np.full(256, INVALID, dtype=np.uint8)
    for value, base in enumerate(b"ACGT"):
        table[base] = value
    for value, base in enumerate(b"acgt"):
        table[base] = value
    return table


#: The lookup itself. Indexing a uint8 array of ASCII by this is the whole decoder.
CODES = _code_table()


def codes_of(sequence: bytes | str | np.ndarray) -> np.ndarray:
    """2-bit codes for a sequence given as bytes, ``str`` or a uint8 array of ASCII."""
    if isinstance(sequence, str):
        sequence = sequence.encode("ascii", errors="replace")
    if isinstance(sequence, bytes | bytearray | memoryview):
        sequence = np.frombuffer(bytes(sequence), dtype=np.uint8)
    return np.asarray(CODES[sequence], dtype=np.uint8)


def _check_k(k: int) -> None:
    if not 1 <= k <= MAX_K:
        raise ValueError(f"k must be between 1 and {MAX_K}, got {k}")


def window_kmers(codes: np.ndarray, k: int = K) -> tuple[np.ndarray, np.ndarray]:
    """Every overlapping k-mer of **one** sequence, canonical.

    ``codes`` is the 1-D output of :func:`codes_of`. Returns ``(kmers, valid)``, both of
    length ``len(codes) - k + 1``; a false entry in ``valid`` means that window contained a
    base that is not A/C/G/T and its k-mer value is meaningless.
    """
    _check_k(k)
    count = codes.size - k + 1
    if count <= 0:
        return np.empty(0, dtype=np.uint64), np.empty(0, dtype=bool)
    forward = np.zeros(count, dtype=np.uint64)
    reverse = np.zeros(count, dtype=np.uint64)
    broken = np.zeros(count, dtype=bool)
    top = np.uint64(2 * (k - 1))
    for offset in range(k):
        column = codes[offset : offset + count]
        bad = column > 3
        clean = np.where(bad, 0, column).astype(np.uint64)
        forward = (forward << _TWO) | clean
        reverse = (reverse >> _TWO) | ((_THREE - clean) << top)
        broken |= bad
    return np.minimum(forward, reverse), ~broken


def kmers_at(codes: np.ndarray, positions: np.ndarray, k: int = K) -> tuple[np.ndarray, np.ndarray]:
    """Canonical k-mers at the named start positions only — not every window.

    :func:`window_kmers` builds every overlapping k-mer of a sequence, which is right when
    every one of them is wanted. Sampling a few thousand probes from a 249-megabase
    chromosome is not that case: the full pass allocates two gigabytes to produce ten
    thousand values. This takes the same arithmetic to the positions asked for, so the cost
    is the sample rather than the chromosome.

    The canonical form is identical to :func:`window_kmers`' — the smaller of the forward
    k-mer and its reverse complement — and ``tests/test_kmer_encode.py`` asserts the two
    agree window for window.
    """
    _check_k(k)
    positions = np.asarray(positions, dtype=np.int64)
    usable = positions[(positions >= 0) & (positions + k <= codes.size)]
    if not usable.size:
        return np.empty(0, dtype=np.uint64), np.empty(0, dtype=bool)
    forward = np.zeros(usable.size, dtype=np.uint64)
    reverse = np.zeros(usable.size, dtype=np.uint64)
    broken = np.zeros(usable.size, dtype=bool)
    top = np.uint64(2 * (k - 1))
    for offset in range(k):
        column = codes[usable + offset]
        bad = column > 3
        clean = np.where(bad, 0, column).astype(np.uint64)
        forward = (forward << _TWO) | clean
        reverse = (reverse >> _TWO) | ((_THREE - clean) << top)
        broken |= bad
    return np.minimum(forward, reverse), ~broken


def offsets_for(length: int, k: int = K, stride: int = 1) -> np.ndarray:
    """Which start positions of a ``length``-base read are sampled at this stride.

    Stride is the one knob that makes a full-store pass affordable: a 150 bp read holds
    120 31-mers, and testing every one of them is ~15x the work of testing every 16th. A
    read that overlaps the bait by at least ``k + stride - 1`` bases still lands on a
    sampled offset, so the cost of the stride is a small loss at the edges of the baited
    region — measured, not assumed (H021).
    """
    _check_k(k)
    count = length - k + 1
    if count <= 0:
        return np.empty(0, dtype=np.int64)
    return np.arange(0, count, max(1, stride), dtype=np.int64)


def strided_kmers(codes: np.ndarray, k: int = K, stride: int = 1) -> tuple[np.ndarray, np.ndarray]:
    """Canonical k-mers of **many equal-length sequences** at every ``stride``-th offset.

    ``codes`` is a ``(rows, length)`` matrix of 2-bit codes — one row per read. Returns
    ``(kmers, valid)``, both ``(rows, n_offsets)``. The loop is over ``k``, not over rows,
    so a batch of 200,000 reads costs 31 vectorised passes however many reads it holds.
    """
    _check_k(k)
    if codes.ndim != 2:
        raise ValueError(f"expected a (rows, length) matrix, got shape {codes.shape}")
    starts = offsets_for(codes.shape[1], k, stride)
    if starts.size == 0:
        return (
            np.empty((codes.shape[0], 0), dtype=np.uint64),
            np.empty((codes.shape[0], 0), dtype=bool),
        )
    shape = (codes.shape[0], starts.size)
    forward = np.zeros(shape, dtype=np.uint64)
    reverse = np.zeros(shape, dtype=np.uint64)
    broken = np.zeros(shape, dtype=bool)
    top = np.uint64(2 * (k - 1))
    for offset in range(k):
        column = codes[:, starts + offset]
        bad = column > 3
        clean = np.where(bad, 0, column).astype(np.uint64)
        forward = (forward << _TWO) | clean
        reverse = (reverse >> _TWO) | ((_THREE - clean) << top)
        broken |= bad
    return np.minimum(forward, reverse), ~broken


def decode(kmer: int, k: int = K) -> str:
    """The DNA spelling of one packed k-mer — for tests and QC output, not for scanning."""
    _check_k(k)
    letters = "ACGT"
    return "".join(letters[(int(kmer) >> (2 * (k - 1 - i))) & 3] for i in range(k))
