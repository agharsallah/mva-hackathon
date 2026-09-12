"""``/api/steps/step-2``: one step's tables, aggregated before they leave the database.

Two things are worth pinning here and only one of them is about shape.

The first is **the coordinate rule**. Four of the six tables behind this route carry real
genomic positions of the proband, and the route's whole design is that no row of them is
served. A test that only checked the response would pass the day someone adds ``pos`` to a
SELECT; so the test reads the SQL itself and refuses a block that selects a position
column without grouping it away.

The second is the contrast, which is derived from the per-tier block rather than queried
again — so the two can never disagree on the page.
"""

import re

import pytest

from mva.viz import steps_it2 as route


class _Settings:
    schema = "warehouse"
    result_schema = "results"


#: Column names that are a genomic position of this child. ``median_length`` and the
#: structural-variant length columns are distances, not places, and are not on this list.
POSITION_COLUMNS = ("pos", "start", "end_pos")


@pytest.mark.parametrize("name", sorted(route.BLOCKS))
def test_no_block_selects_a_bare_position_column(name):
    """A position may be computed over (``"end" - start``) but never selected as itself."""
    sql = route.BLOCKS[name]
    selected = re.findall(r"(?:SELECT|,)\s+([a-z_]+)\s*(?:,|\n|$)", sql, re.IGNORECASE)
    assert not [column for column in selected if column.lower() in POSITION_COLUMNS], (
        f"block {name!r} selects a genomic position; aggregate it away before serving it"
    )


def test_the_alleles_and_sv_call_tables_are_never_read_row_by_row():
    """``it2_read_alleles`` and ``it2_sv_calls`` hold one row per variant, with its place.

    Every figure this page needs is already aggregated by a derivation, so the route reads
    the derived tables instead. Reaching back to the row-level ones is the mistake this
    test exists to catch.
    """
    everything = " ".join(route.BLOCKS.values())
    assert "it2_read_alleles" not in everything
    assert "results.it2_sv_calls" not in everything


def test_contrast_is_derived_from_the_tier_block_not_queried_again():
    by_tier = [
        {"tier": "core", "genes": 50, "biallelic_filtered": 3, "biallelic_unfiltered": 25},
        {"tier": "net", "genes": 150, "biallelic_filtered": 5, "biallelic_unfiltered": 75},
        {"tier": "decoy", "genes": 200, "biallelic_filtered": 8, "biallelic_unfiltered": 120},
    ]
    contrast = route._contrast(by_tier)
    filtered = next(row for row in contrast if row["filter"] == "rare and protein-altering")
    assert filtered["target_genes"] == 200
    assert filtered["target_biallelic"] == 8
    assert filtered["target_rate"] == pytest.approx(0.04)
    assert filtered["decoy_rate"] == pytest.approx(0.04)


def test_contrast_reports_both_filters_because_they_point_opposite_ways():
    by_tier = [
        {"tier": "core", "genes": 100, "biallelic_filtered": 2, "biallelic_unfiltered": 51},
        {"tier": "decoy", "genes": 100, "biallelic_filtered": 2, "biallelic_unfiltered": 57},
    ]
    contrast = route._contrast(by_tier)
    assert [row["filter"] for row in contrast] == ["rare and protein-altering", "any two variants"]
    unfiltered = contrast[1]
    assert unfiltered["decoy_rate"] > unfiltered["target_rate"]


def test_payload_runs_every_block_and_adds_the_contrast(monkeypatch):
    seen = []

    def fake_fetch(_settings, sql):
        seen.append(sql)
        return [{"tier": "core", "genes": 1, "biallelic_filtered": 0, "biallelic_unfiltered": 1}]

    monkeypatch.setattr(route, "fetch", fake_fetch)
    data = route.payload(_Settings())
    assert set(data) == set(route.BLOCKS) | {"contrast"}
    assert len(seen) == len(route.BLOCKS)
