"""The step-3 route serves aggregates, and the SQL behind it cannot select a position.

Step 3's tables were built coordinate-free, but "built that way" is a property of one
loader and this test is the property of the *route*: a column added to a result table
later must not be able to reach the browser by being selected here. The step-2 route has
the same test for the same reason.
"""

import re

import pytest

from mva.viz import steps_it2_step3 as route

#: Column names that would be a genomic position if one ever appeared in these tables.
POSITION_COLUMNS = ("pos", "start", "end_pos", "chrom", "position")

#: A run of bases long enough to be sequence rather than an accident.
DNA_LITERAL = re.compile(r"(?<![A-Za-z0-9])[ACGTN]{12,}(?![A-Za-z0-9])")


@pytest.mark.parametrize("name", sorted(route.BLOCKS))
def test_no_block_selects_a_position_column(name):
    sql = route.BLOCKS[name]
    for column in POSITION_COLUMNS:
        assert not re.search(rf"(?<![_a-z]){column}(?![_a-z])", sql), (
            f"block {name!r} names {column!r}; this route serves aggregates only"
        )


@pytest.mark.parametrize("name", sorted(route.BLOCKS))
def test_no_block_carries_a_dna_literal(name):
    assert not DNA_LITERAL.search(route.BLOCKS[name])


def test_every_block_reads_a_table_something_actually_produces():
    """Two producers: the loader writes the measured tables, the derivations build the
    three that answer a claim. A block naming neither would render an empty page against a
    table nobody creates — which looks exactly like a step that found nothing."""
    from mva.warehouse.analysis_it2_kmer import IT2_KMER_DERIVATIONS
    from mva.warehouse.it2_step3_tables import SCHEMAS

    known = set(SCHEMAS) | {item.name for item in IT2_KMER_DERIVATIONS}
    for name, sql in route.BLOCKS.items():
        named = set(re.findall(r"results\.(\w+)", sql))
        unknown = named - known
        assert not unknown, f"block {name!r} reads {unknown}, which nothing produces"


def test_the_contrast_reports_targets_and_decoys_for_both_allele_sets():
    """H020 is refuted: a target-gene result does not outweigh a decoy's before the filter,
    and a rate quoted for only one side invites exactly that reading."""
    confirmation = [
        {"tier": "core", "novel": False, "fully_probed": 10, "confirmed": 9},
        {"tier": "decoy", "novel": False, "fully_probed": 20, "confirmed": 10},
        {"tier": "core", "novel": True, "fully_probed": 4, "confirmed": 1},
        {"tier": "decoy", "novel": True, "fully_probed": 4, "confirmed": 2},
    ]
    rows = {row["allele_set"]: row for row in route._contrast(confirmation)}
    assert set(rows) == {"reported by the delivered callset", "vendor-unreported"}
    reported = rows["reported by the delivered callset"]
    assert reported["target_rate"] == pytest.approx(0.9)
    assert reported["decoy_rate"] == pytest.approx(0.5)
    novel = rows["vendor-unreported"]
    assert novel["target_rate"] == pytest.approx(0.25)
    assert novel["decoy_rate"] == pytest.approx(0.5)


def test_the_contrast_survives_a_tier_with_nothing_in_it():
    """A rate over zero alleles is 0.0, not a division by zero — a step that found nothing
    must still render."""
    rows = route._contrast([{"tier": "core", "novel": False, "fully_probed": 0, "confirmed": 0}])
    assert rows[0]["target_rate"] == 0.0 and rows[0]["decoy_rate"] == 0.0


def test_the_route_is_registered_on_the_warehouse_router():
    from mva.viz import routes_warehouse

    assert "steps_it2_step3" in routes_warehouse.__dict__
