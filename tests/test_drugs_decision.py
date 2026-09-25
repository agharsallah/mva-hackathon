"""The decision engine: a hand-worked positive control, then the rules that guard it.

The positive control (also written out, arithmetic and all, in
``docs/iteration5/step-1/work/r4-entry.md``) is one variable, ``missense_class``, with
P(unstable) = 0.6 and four drugs:

====== ================= ======== ======= ========= ==========================
drug   branch            strength control safety    u(unstable), u(inactive)
====== ================= ======== ======= ========= ==========================
A      missense_unstable 0.8/0.5  passed  unflagged 0.8, 0      (two spellings)
B      any               0.4      passed  pheno 0.5 0.2, 0.2
C      missense_inactive 0.9      failed  unflagged 0, 0.45     (penalty 0.5)
D      any               0.1      passed  absent    0.06, 0.06  (unassessed 0.6)
====== ================= ======== ======= ========= ==========================

EU: A 0.48, B 0.20, C 0.18, D 0.06 -> A. EVPI = 0.6*0.8 + 0.4*0.45 - 0.48 = 0.18.
Blot (sens 0.9, spec 0.8): P(+) = 0.62, best A (0.432 / 0.62); P(-) = 0.38, best C
(0.144 / 0.38); EVSI = 0.432 + 0.144 - 0.48 = 0.096. Flip: 0.8 p = 0.45 (1 - p) -> p = 0.36.
"""

from __future__ import annotations

import copy
import json
import random
from pathlib import Path
from typing import Any

import pytest

from mva.drugs import decision_avoid, decision_config, decision_priors
from mva.drugs.decision_io import (
    COLUMNS,
    expand_aliases,
    read_candidates,
    read_safety,
    safety_class,
)
from mva.drugs.decision_model import EvidenceRow, build_table
from mva.drugs.decision_run import analyse
from mva.drugs.decision_sensitivity import envelope, flip_points
from mva.drugs.decision_voi import evpi, evsi, expected

RAW: dict[str, Any] = {
    "state_variables": {
        "missense_class": {"prior": {"unstable": 0.6, "inactive": 0.4}, "source": "test"}
    },
    "applicability": {
        "stop_allele": {},
        "missense_unstable": {"missense_class": {"unstable": 1.0, "inactive": 0.0}},
        "missense_inactive": {"missense_class": {"unstable": 0.0, "inactive": 1.0}},
        "any": {},
    },
    "safety": {
        "factors": {
            "unflagged": 1.0,
            "genome_flag": 0.5,
            "phenotype_flag": 0.5,
            "both_flag": 0.25,
            "unassessed": 0.6,
            "caution": 0.5,
            "avoid": 0.0,
        }
    },
    "control": {"policy": "penalty", "failed_factor": 0.5, "unknown_factor": 0.5},
    "baseline": {"name": "defer", "utility": 0.0},
    "tests": [
        {
            "name": "blot",
            "variable": "missense_class",
            "positive": "unstable",
            "sensitivity": 0.9,
            "specificity": 0.8,
        }
    ],
    "tornado": [{"param": "prior:missense_class=unstable", "low": 0.2, "high": 0.9}],
}
SAFETY = {"DRUG A": "unflagged", "DRUG B": "phenotype_flag", "DRUG C": "unflagged"}


def _row(name: str, route: str, branch: str, strength: float, control: str) -> EvidenceRow:
    return EvidenceRow(name, route, branch, "test", strength, control, "test", "", "test")


ROWS = [
    _row("Drug A hydrochloride", "r1", "missense_unstable", 0.8, "passed"),
    _row("DRUG A", "r2", "missense_unstable", 0.5, "passed"),
    _row("Drug B", "r1", "any", 0.4, "passed"),
    _row("Drug C", "r3", "missense_inactive", 0.9, "failed"),
    _row("Drug D", "r1", "any", 0.1, "passed"),
]


def _config(**changes: Any) -> Any:
    raw = copy.deepcopy(RAW)
    for key, value in changes.items():
        raw[key] = value
    return decision_config.parse(raw)


def test_positive_control_reproduces_the_hand_worked_numbers() -> None:
    config = _config()
    table = build_table(config, ROWS, SAFETY)
    assert table.actions == ("defer", "DRUG A", "DRUG B", "DRUG C", "DRUG D")
    flat = [u for row in table.utility for u in row]
    assert flat == pytest.approx([0, 0, 0.8, 0, 0.2, 0.2, 0, 0.45, 0.06, 0.06])
    assert expected(table.utility, table.probs) == pytest.approx([0, 0.48, 0.2, 0.18, 0.06])
    assert evpi(table.utility, table.probs) == pytest.approx(0.18)
    report = analyse(config, ROWS, SAFETY)
    assert report["best"]["action"] == "DRUG A"
    blot = next(v for v in report["voi"] if v["kind"] == "evsi")
    assert blot["value"] == pytest.approx(0.096)
    outcomes = {o["result"]: o for o in blot["outcomes"]}
    assert outcomes["positive"]["probability"] == pytest.approx(0.62)
    assert outcomes["positive"]["best"] == "DRUG A"
    assert outcomes["negative"]["best"] == "DRUG C"
    assert outcomes["negative"]["eu"] == pytest.approx(0.144 / 0.38)
    assert [f["action"] for f in report["flips"]] == ["DRUG C", "DRUG A"]
    ends = [(f["start"], f["end"]) for f in report["flips"]]
    assert [x for pair in ends for x in pair] == pytest.approx([0.0, 0.36, 0.36, 1.0])


def test_two_spellings_are_one_drug_supported_by_both_routes() -> None:
    report = analyse(_config(), ROWS, SAFETY)
    row = next(r for r in report["utilities"] if r["action"] == "DRUG A")
    assert row["routes"] == ("r1", "r2")
    assert row["n_rows"] == 2


def test_missing_from_the_safety_table_is_unassessed_never_safe() -> None:
    table = build_table(_config(), ROWS, SAFETY)
    assert table.safety["DRUG D"] == "unassessed"
    assert build_table(_config(), ROWS, {}).safety["DRUG A"] == "unassessed"


def test_exclude_policy_drops_the_failed_route_and_changes_the_answer() -> None:
    control = {"policy": "exclude", "failed_factor": 0.5, "unknown_factor": 0.5}
    report = analyse(_config(control=control), ROWS, SAFETY)
    assert [e["drug_name"] for e in report["excluded"]] == ["Drug C"]
    evpi_row = next(v for v in report["voi"] if v["kind"] == "evpi")
    assert evpi_row["value"] == pytest.approx(0.6 * 0.8 + 0.4 * 0.2 - 0.48)


def test_evsi_never_exceeds_evpi_and_is_never_negative() -> None:
    rng = random.Random(20260925)
    for _ in range(200):
        n_states = rng.randint(2, 4)
        weights = [rng.random() + 1e-3 for _ in range(n_states)]
        probs = [w / sum(weights) for w in weights]
        utility = [[rng.random() for _ in range(n_states)] for _ in range(rng.randint(1, 5))]
        pos = [rng.random() for _ in range(n_states)]
        gain, _ = evsi(utility, probs, {"+": pos, "-": [1 - p for p in pos]})
        assert -1e-12 <= gain <= evpi(utility, probs) + 1e-12


def test_envelope_finds_every_crossing_and_skips_dominated_lines() -> None:
    lines = [(0.0, 0.0), (0.45, -0.45), (0.2, 0.0), (0.0, 0.8)]
    pieces = envelope(lines)
    assert [(round(a, 9), round(b, 9), i) for a, b, i in pieces] == [(0, 0.36, 1), (0.36, 1, 3)]


def test_flip_points_on_a_three_valued_variable_rescale_the_others() -> None:
    raw = copy.deepcopy(RAW)
    raw["state_variables"]["missense_class"]["prior"] = {
        "unstable": 0.5,
        "inactive": 0.3,
        "benign": 0.2,
    }
    config = decision_config.parse(raw)
    swept = decision_config.with_prior(config, "missense_class", "unstable", 0.0)
    assert dict(swept.variable("missense_class").prior) == pytest.approx(
        {"unstable": 0.0, "inactive": 0.6, "benign": 0.4}
    )
    segments = flip_points(
        config, lambda c: build_table(c, ROWS, SAFETY), "missense_class", "unstable"
    )
    assert segments[-1].action == "DRUG A"


def test_config_refuses_a_prior_that_does_not_sum_to_one() -> None:
    raw = copy.deepcopy(RAW)
    raw["state_variables"]["missense_class"]["prior"] = {"unstable": 0.6, "inactive": 0.6}
    with pytest.raises(ValueError, match="sums to"):
        decision_config.parse(raw)


def test_candidate_reader_validates_the_pinned_schema(tmp_path: Path) -> None:
    good = tmp_path / "good.tsv"
    good.write_text(
        "\t".join(COLUMNS)
        + "\nDrug A\tr1\tstop_allele\tassay\t0.7\tyes\tPMID:1\t"
        + "\nDrug B\tr1\tany\tlit\t0.2\t\ts\tn\n"
    )
    rows = read_candidates([good])
    assert [r.control for r in rows] == ["passed", "unknown"]
    bad = tmp_path / "bad.tsv"
    bad.write_text("\t".join(COLUMNS) + "\nDrug A\tr1\tnonsense\tk\t0.7\tyes\ts\t\n")
    with pytest.raises(ValueError, match="branch"):
        read_candidates([bad])
    strong = tmp_path / "strong.tsv"
    strong.write_text("\t".join(COLUMNS) + "\nDrug A\tr1\tany\tk\t1.7\tyes\ts\t\n")
    with pytest.raises(ValueError, match="outside"):
        read_candidates([strong])
    short = tmp_path / "short.tsv"
    short.write_text("drug_name\troute\nDrug A\tr1\n")
    with pytest.raises(ValueError, match="missing pinned"):
        read_candidates([short])


def test_safety_reader_maps_iteration_4_sentences(tmp_path: Path) -> None:
    assert safety_class("both sources flag a question") == "both_flag"
    assert safety_class("unflagged by these two sources (not evidence of safety)") == "unflagged"
    assert safety_class("") == "unassessed"
    path = tmp_path / "s.tsv"
    path.write_text("drug\tcombined_flag\nvincristine sulfate\tboth sources flag a question\n")
    assert read_safety(path) == {"VINCRISTINE": "both_flag"}


def test_the_committed_config_parses_and_names_its_todos() -> None:
    path = Path("ressources/track2/it5/decision_config.json")
    config, raw = decision_config.load(path)
    assert {v.name for v in config.variables} >= {"missense_class", "readthrough_feasible"}
    assert all(v.source for v in config.variables)
    assert isinstance(decision_config.todos(raw), list)
    json.dumps(raw)


def test_class_rows_expand_to_named_members_and_control_rows_drop() -> None:
    rows = [
        _row("proteasome inhibition (MG132; bortezomib)", "R1", "missense_unstable", 0.5, "n/a"),
        EvidenceRow("Untreated", "R1", "any", "negative control", 0.0, "failed", "s", "", "t"),
    ]
    aliases = {"proteasome inhibition (MG132; bortezomib)": {"MG132": 1.0, "BORTEZOMIB": 0.4}}
    kept, dropped = expand_aliases(rows, aliases, ["negative control"])
    assert [(r.drug_name, r.evidence_strength) for r in kept] == [
        ("MG132", 0.5),
        ("BORTEZOMIB", pytest.approx(0.2)),
    ]
    assert [r.drug_name for r, _ in dropped] == ["Untreated"]


def test_not_applicable_control_takes_its_own_factor() -> None:
    control = {"policy": "penalty", "failed_factor": 0.5, "unknown_factor": 0.5, "na_factor": 0.8}
    table = build_table(
        _config(control=control), [_row("X", "r", "any", 0.5, "not_applicable")], {}
    )
    assert table.utility[1][0] == pytest.approx(0.5 * 0.8 * 0.6)


def test_unflagged_without_any_label_is_unassessed(tmp_path: Path) -> None:
    path = tmp_path / "s.tsv"
    path.write_text(
        "drug\tcombined_flag\tlabels_total\n"
        "a\tunflagged by these two sources (not evidence of safety)\t0\n"
        "b\tunflagged by these two sources (not evidence of safety)\t12\n"
    )
    assert read_safety(path) == {"A": "unassessed", "B": "unflagged"}


def test_threshold_crossing_counts_pairs_that_reach_the_threshold(tmp_path: Path) -> None:
    table = tmp_path / "dose.tsv"
    table.write_text(
        "scenario\tdrug\ttotal\tgain\tanchor\tanchor_pct\n"
        "child now, a\tnone\t12\t0\tcliff\t13\n"
        "child now, b\tnone\t5\t0\tother\t4\n"
        "child now, c\tnone\t20\t0\tother\t4\n"
        "child + x (real)\tx\t12.5\t0.5\tcliff\t13\n"
        "child + y (bound)\ty\t14\t2\tcliff\t13\n"
    )
    spec = {
        "table": str(table),
        "threshold": {"column": "anchor_pct", "where_column": "anchor", "where_contains": "cliff"},
        "start": {"drug_column": "drug", "drug_value": "none", "scenario_column": "scenario",
                  "scenario_prefix": "child now"},
        "total_column": "total",
        "gain_column": "gain",
        "gains": {"strict": ["(real)"], "lenient": ["(real)", "(bound)"]},
    }  # fmt: skip
    out = decision_priors.threshold_crossing(spec)
    assert out["threshold"] == 13.0
    assert sorted(out["starts"].values()) == [5.0, 12.0]  # 20 is already above
    assert out["strict"]["prior_yes"] == 0.0  # 12 + 0.5 < 13
    assert out["lenient"]["prior_yes"] == pytest.approx(1 / 4)  # only 12 + 2


def test_avoid_rules_check_their_source_and_the_lowest_factor_wins(tmp_path: Path) -> None:
    source = tmp_path / "exposures.tsv"
    source.write_text("drug\toutcome\nvincristine\tauthors advise avoiding antimitotics\n")
    rule = {"drugs": ["vincristine"], "level": "avoid", "reason": "r", "source": "PMID:1",
            "source_file": str(source), "must_contain": ["advise avoiding"]}  # fmt: skip
    rows = decision_avoid.build({"rules": [rule]})
    factors = decision_config.parse(RAW).safety
    assert decision_avoid.merge({"VINCRISTINE": "unflagged"}, rows, factors) == {
        "VINCRISTINE": "avoid"
    }
    with pytest.raises(ValueError, match="lacks"):
        decision_avoid.build({"rules": [{**rule, "must_contain": ["not in the file"]}]})
