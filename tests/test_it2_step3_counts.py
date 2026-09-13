"""The packing that makes the per-fragment collapse affordable, and the identity behind it.

The tool streams tens of millions of ``(fragment, probe)`` pairs, so the pair is packed into
one integer instead of two. These tests pin the two properties that packing must have: the
two reads of a pair get the same identity, and the probe index survives the round trip.
"""

import importlib.util
import sys
from pathlib import Path

import numpy as np
import polars as pl
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

_spec = importlib.util.spec_from_file_location(
    "run_it2_step3_counts", REPO / "tools" / "run_it2_step3_counts.py"
)
assert _spec and _spec.loader
counts = importlib.util.module_from_spec(_spec)
# Registered before execution: a dataclass resolves its annotations through
# ``sys.modules[cls.__module__]``, and a module loaded by path alone is not there yet.
sys.modules[_spec.name] = counts
_spec.loader.exec_module(counts)


def reads(rows: list[tuple[int, int, int, int]]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "lane": [row[0] for row in rows],
            "tile": [row[1] for row in rows],
            "x": [row[2] for row in rows],
            "y": [row[3] for row in rows],
        }
    )


def test_the_two_reads_of_a_pair_share_one_identity():
    """R1 and R2 come off the same cluster, so they carry the same flowcell coordinate —
    which is why `mva.reads.bait` uses it as the pair key and why it stands in for the
    molecule here."""
    identity = counts.fragment_ids(reads([(1, 1101, 1000, 2000), (1, 1101, 1000, 2000)]))
    assert identity[0] == identity[1]


def test_different_clusters_get_different_identities():
    rows = [(1, 1101, 1000, 2000), (1, 1101, 1000, 2001), (2, 1101, 1000, 2000)]
    identity = counts.fragment_ids(reads(rows))
    assert len(set(identity.tolist())) == 3


def test_every_field_of_the_coordinate_changes_the_identity():
    """A packing that dropped a field would silently merge distinct molecules."""
    base = (1, 1101, 1000, 2000)
    variants = [
        (2, 1101, 1000, 2000),
        (1, 1102, 1000, 2000),
        (1, 1101, 1001, 2000),
        (1, 1101, 1000, 2001),
    ]
    identity = counts.fragment_ids(reads([base, *variants]))
    assert len(set(identity.tolist())) == len(variants) + 1


def test_the_identity_leaves_room_for_the_probe_index():
    """The pair is packed into one uint64: the probe index takes the low bits and the hashed
    coordinate everything above them."""
    identity = counts.fragment_ids(reads([(4, 2678, 32985, 37059)]))
    assert int(identity[0]) < (1 << counts.FRAGMENT_BITS)


def test_a_packed_pair_round_trips_to_its_probe_index():
    identity = counts.fragment_ids(reads([(1, 1101, 1000, 2000)])).astype(np.uint64)
    for slot in (0, 1, 12345, counts.SLOT_MASK):
        packed = (identity[0] << np.uint64(counts.SLOT_BITS)) | np.uint64(slot)
        assert int(packed & np.uint64(counts.SLOT_MASK)) == slot


def test_more_probe_kmers_than_the_packing_holds_is_refused_not_wrapped():
    """Silently wrapping the probe index would mix two probes' counts together, which reads
    as a genotype rather than as an error."""
    from mva.kmer.membership import Bait

    too_many = Bait.of(np.arange(counts.SLOT_MASK + 2, dtype=np.uint64))
    with pytest.raises(ValueError, match="exceeds"):
        counts.count_reads(Path("unused.parquet"), too_many, batch=1, limit=1)
