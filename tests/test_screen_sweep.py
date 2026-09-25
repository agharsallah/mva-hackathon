"""The screen-wide sweep on synthetic matrices — no downloads, no PRISM file.

Each test pins one property entry 154's verdict rests on: a drug with several copies is
tested once (the BH family counts drugs, not copies), the eligibility floor is applied on
every contrast, "top 0.5 %" rounds up, the contrary-direction p is really the other tail,
PRISM spellings reach the shared join key, the Launched label is a union over releases,
and a drug listed by both contrasts carries both direction hints.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from mva.drugs.screen_replication import Group, benjamini_hochberg, contrast_item
from mva.drugs.screen_replication_prism import ResponseMatrix
from mva.drugs.screen_sweep import (
    Eligibility,
    eligible_items,
    family,
    opposite_p,
    sweep_contrast,
    top_k,
)
from mva.drugs.screen_sweep_prism import launched_cores, prism_join_key
from mva.drugs.screen_sweep_report import generator_rows, sweep_table

LINES = [f"L{i:02d}" for i in range(40)]
INSIDE = frozenset(LINES[:5])


def group(name: str = "g", inside: frozenset[str] = INSIDE) -> Group:
    return Group(name, inside, frozenset(LINES) - inside, "in", "out", "synthetic")


def screen(rows: dict[str, list[float]]) -> ResponseMatrix:
    return ResponseMatrix(
        item_ids=list(rows),
        lines=LINES,
        matrix=np.asarray(list(rows.values()), dtype=float),
        metric="synthetic LFC",
        release="synthetic",
    )


def kills_inside(strength: float, seed: int) -> list[float]:
    """Lower = more sensitive; the in-group lines are pushed down by ``strength``."""
    rng = np.random.default_rng(seed)
    return [float(rng.normal()) - (strength if ln in INSIDE else 0.0) for ln in LINES]


def test_top_k_rounds_up_and_is_at_least_one() -> None:
    assert top_k(613, 0.005) == 4
    assert top_k(100, 0.005) == 1
    assert top_k(0, 0.005) == 0


def test_prism_spellings_reach_the_shared_join_key() -> None:
    assert prism_join_key("CYPROTERONE-ACETATE") == "CYPROTERONE"
    assert prism_join_key("VALPROIC-ACID") == "VALPROIC ACID"
    assert prism_join_key("LEVOBUNOLOL-(+/-)") == "LEVOBUNOLOL"
    assert prism_join_key("PLX-4720") == "PLX 4720"
    assert prism_join_key("ATENOLOL-(+)") == "ATENOLOL (+)"


def test_launched_is_a_union_over_releases() -> None:
    a = pl.DataFrame({"broad_core": ["X", "Y"], "phase": ["Launched", "Phase 2"]})
    b = pl.DataFrame({"broad_core": ["Y", "Z"], "phase": ["Launched", "Preclinical"]})
    a = a.with_columns(release=pl.lit("primary"))
    b = b.with_columns(release=pl.lit("secondary"))
    assert launched_cores([a, b]) == {"X": "primary", "Y": "secondary"}


def test_eligibility_applies_every_rule() -> None:
    sparse = kills_inside(0.0, 1)
    for i in range(3):  # only 2 of the 5 in-group lines measured
        sparse[i] = float("nan")
    m = screen({"full": kills_inside(0.0, 0), "sparse": sparse})
    assert eligible_items(m, ["full", "sparse"], [Eligibility(group(), 3, 3)]) == ["full"]
    wide = Eligibility(group(), 3, 36)  # 35 comparison lines exist, so nothing passes
    assert eligible_items(m, ["full", "sparse"], [wide]) == []


def test_family_counts_drugs_not_copies() -> None:
    rows = {f"d{i}": kills_inside(0.0, i) for i in range(6)}
    rows["hit-a"] = kills_inside(3.0, 100)
    rows["hit-b"] = kills_inside(3.0, 101)
    m = screen(rows)
    g = group()
    items = sorted(rows)
    results = sweep_contrast(m, g, items, {}, seed=7, resamples=50, workers=1)
    drug_of = {i: ("HIT" if i.startswith("hit") else i.upper()) for i in items}
    fam = family(m, g, results, drug_of)
    reps = [r for r in fam if r.representative]
    assert len(reps) == 7  # 6 unrelated drugs + one representative of the two HIT copies
    hit = next(r for r in reps if r.drug == "HIT")
    assert hit.rank == 1
    # The family is exactly the 7 representatives: BH over their p values, nothing else.
    expected = benjamini_hochberg([r.result.p_raw for r in reps if r.result.p_raw is not None])
    assert [r.result.p_adjusted for r in reps] == expected


def test_sweep_seed_is_fixed_by_position() -> None:
    rows = {"a": kills_inside(1.0, 1), "b": kills_inside(0.5, 2)}
    m = screen(rows)
    swept = sweep_contrast(m, group(), ["a", "b"], {}, seed=10, resamples=40, workers=1)
    direct = contrast_item("b", "b", dict(zip(LINES, rows["b"], strict=True)), group(),
                           resamples=40, seed=11)  # fmt: skip
    assert swept[1] == direct


def test_opposite_p_is_the_other_tail() -> None:
    m = screen({"spares": kills_inside(-3.0, 5), "kills": kills_inside(3.0, 6)})
    p = opposite_p(m, group(), ["spares", "kills"])
    assert p["spares"] is not None and p["spares"] < 0.01
    assert p["kills"] is not None and p["kills"] > 0.99


def test_both_contrast_hit_carries_both_hints_and_hit_both() -> None:
    rows = {f"d{i}": kills_inside(0.0, i) for i in range(8)}
    rows["star"] = kills_inside(3.0, 50)
    m = screen(rows)
    items = sorted(rows)
    drug_of = {i: i.upper() for i in items}
    other = group("aneuploidy", frozenset(LINES[:6]))
    fams = {
        tag: family(m, g, sweep_contrast(m, g, items, {}, seed=1, resamples=20, workers=1), drug_of)
        for tag, g in (("rms", group("rms")), ("aneuploidy", other))
    }
    gen = generator_rows(
        fams, {"rms": "D4", "aneuploidy": "D2"}, {}, {"STAR": ["BRD-X"]}, {},
        generator="prism", fraction=0.005, approval_evidence="PRISM Launched",
    )  # fmt: skip
    star = gen.filter(pl.col("drug") == "STAR").row(0, named=True)
    assert star["rank"] == 1 and star["direction_hint"] == "D4|D2"
    table = sweep_table(fams, {}, alpha=0.5)
    assert set(table["contrast"].unique()) == {"rms", "aneuploidy"}
    assert table.height == 2 * len(items)
    assert table.filter(pl.col("drug") == "STAR")["hit_both"].all()
