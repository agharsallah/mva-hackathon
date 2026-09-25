"""Step 10 S2: the generator join, the permutation null, the generator rules and the checks.

Synthetic generator tables only; no network, no PrimeKG, no patient data.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from mva.drugs import convergence
from mva.drugs.checks import K3Rule, Measurement, k1, k3
from mva.drugs.checks_safety import BOTH_FLAG, faers_pairs, k2_from_table, mapped_terms
from mva.drugs.checks_sources import load_moa_index
from mva.drugs.convergence_candidates import CandidateChecks, candidate_rows
from mva.drugs.convergence_generators import (
    WalkCandidate,
    approved_analogues,
    twin_rows,
    walk_rows,
)
from mva.drugs.convergence_tables import (
    GeneratorList,
    GeneratorRow,
    read_generator,
    write_generator,
)


def _row(
    generator: str, rank: int, drug: str, approved: bool = True, hint: str = "none"
) -> GeneratorRow:
    return GeneratorRow(generator, rank, drug, drug.lower(), approved, "test", "1", "s", hint, "e")


def _write(tmp: Path, gen: str, drugs: list[str], universe: list[str]) -> None:
    rows = [_row(gen, i + 1, d) for i, d in enumerate(drugs)]
    write_generator(tmp, gen, rows, universe)


def _lists(tmp: Path, specs: dict[str, tuple[list[str], list[str]]]) -> list[GeneratorList]:
    for gen, (drugs, universe) in specs.items():
        _write(tmp, gen, drugs, universe)
    return [read_generator(tmp, gen) for gen in specs]


# --- the join key -----------------------------------------------------------------------


def test_join_folds_salts_and_case(tmp_path: Path) -> None:
    lists = _lists(
        tmp_path,
        {
            "a": (["Metformin Hydrochloride", "Lovastatin"], ["METFORMIN", "LOVASTATIN"]),
            "b": (["metformin"], ["METFORMIN"]),
        },
    )
    assert convergence.converging(lists) == ["METFORMIN"]


def test_unapproved_rows_do_not_vote_and_list_joins_its_universe(tmp_path: Path) -> None:
    write_generator(tmp_path, "a", [_row("a", 1, "X"), _row("a", 2, "Y", approved=False)], ["Z"])
    item = read_generator(tmp_path, "a")
    assert item.drugs == {"X"}
    assert item.outside_universe == ("X",)
    assert item.universe == {"X", "Z"}


# --- the permutation null ---------------------------------------------------------------


def test_null_detects_a_planted_overlap(tmp_path: Path) -> None:
    universe = [f"D{i:03d}" for i in range(300)]
    shared = universe[:8]
    lists = _lists(
        tmp_path,
        {"a": (shared + universe[100:102], universe), "b": (shared + universe[200:202], universe)},
    )
    result, counts = convergence.run(lists, label="planted", draws=2000, seed=1)
    assert result.observed == 8
    assert result.p_value < 0.01
    assert result.beats_p95
    assert len(counts) == 2000


def test_null_does_not_fire_on_chance_overlap(tmp_path: Path) -> None:
    universe = [f"D{i:02d}" for i in range(20)]
    lists = _lists(tmp_path, {"a": (universe[:10], universe), "b": (universe[5:15], universe)})
    result, _ = convergence.run(lists, label="chance", draws=2000, seed=1)
    # 10 of 20 twice: the expected overlap is 5, so an observed 5 is unremarkable.
    assert result.observed == 5
    assert result.p_value > 0.3


def test_p_value_is_never_zero_and_seeded(tmp_path: Path) -> None:
    universe = [f"D{i:03d}" for i in range(500)]
    lists = _lists(tmp_path, {"a": (universe[:5], universe), "b": (universe[:5], universe)})
    first, _ = convergence.run(lists, label="x", draws=500, seed=7)
    again, _ = convergence.run(lists, label="x", draws=500, seed=7)
    assert first.p_value == pytest.approx(1 / 501)
    assert first == again


def test_exclusion_leaves_lists_and_universes(tmp_path: Path) -> None:
    universe = [f"D{i:02d}" for i in range(30)]
    lists = _lists(tmp_path, {"a": (universe[:3], universe), "b": (universe[:3], universe)})
    result, _ = convergence.run(lists, label="w/o", draws=100, seed=0, exclude=["D00"])
    assert result.observed == 2
    assert result.sizes == {"a": 2, "b": 2}
    assert result.universe_sizes == {"a": 29, "b": 29}


# --- the generator rules ----------------------------------------------------------------


def test_approved_analogues_reads_the_status_literally() -> None:
    assert approved_analogues(
        "dasatinib (+ quercetin)", "dasatinib approved; senolytic use off-label"
    ) == ["dasatinib"]
    assert (
        approved_analogues(
            "x; navitoclax is the analogue but not approved", "navitoclax not approved"
        )
        == []
    )
    assert approved_analogues("sirolimus / everolimus (mTORC1)", "approved (transplant)") == [
        "sirolimus",
        "everolimus",
    ]
    assert approved_analogues("none (investigational)", "none approved") == []


def test_twin_votes_only_on_supporting_rows() -> None:
    keys = ("supports_direction", "nearest_approved_analogue", "analogue_status", "direction")
    table = [
        dict(zip(keys, ("supports", "dasatinib", "dasatinib approved", "D5"), strict=True)),
        dict(zip(keys, ("hypothesis only", "sirolimus", "approved", "D5"), strict=True)),
    ]
    table[0].update(intervention="a", pmid="1", twin_rank_phenodigm="9")
    rows, skipped = twin_rows(table)
    assert [(r.drug, r.direction_hint) for r in rows] == [("DASATINIB", "D5")]
    assert skipped[0]["reason"].startswith("supports_direction")


def test_walk_keeps_distinct_labelled_drugs_in_order() -> None:
    def cand(name: str, rank: int, labelled: bool | None) -> WalkCandidate:
        return WalkCandidate(name, "DB0", 1.0 / rank, rank, labelled, "", (), "")

    items = [
        cand("A", 1, False),
        cand("B sodium", 2, True),
        cand("B", 3, True),
        cand("C", 4, None),
        cand("D", 5, True),
    ]
    rows = walk_rows(items, top=2)
    assert [(r.rank, r.drug) for r in rows] == [(1, "B"), (2, "D")]


# --- K1, K3 -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("moa", "targets", "status"),
    [
        ("AURORA KINASE INHIBITOR", (), "fail"),
        ("Monopolar spindle 1 kinase inhibitor", (), "fail"),
        ("TUBULIN POLYMERIZATION INHIBITOR", (), "caution"),
        ("SYK INHIBITOR", ("SYK",), "pass"),
        ("SYK INHIBITOR", ("SYK", "AURKB"), "caution"),
        (None, (), "caution"),
    ],
)
def test_k1_rule(moa: str | None, targets: tuple[str, ...], status: str) -> None:
    assert k1(moa, targets).status == status


def test_k1_annotation_index_reads_both_hub_layouts(tmp_path: Path) -> None:
    first = tmp_path / "list.csv"
    first.write_text(
        'Drug.Name,MOA,repurposing_target\nVALPROIC-ACID,HDAC INHIBITOR,"HDAC1, HDAC2"\n'
    )
    second = tmp_path / "info.csv"
    second.write_text(
        "name,moa,target\nvalproic-acid,other,X\nbarasertib,Aurora kinase inhibitor,AURKB\n"
    )
    index = load_moa_index([first, second])
    assert index["VALPROIC ACID"].moa == "HDAC INHIBITOR"
    assert index["VALPROIC ACID"].targets == ("HDAC1", "HDAC2")
    assert k1(index["BARASERTIB"].moa).status == "fail"


def test_k3_contrary_only_on_the_mapped_contrast() -> None:
    rule = K3Rule(direction_contrasts={"D2": ("aneuploidy",), "D4": ("rms",)})
    contrary = [Measurement("rms", -0.4, 0.01), Measurement("aneuploidy", 0.1, 0.9)]
    assert k3(["D2"], contrary, rule).status == "pass"
    assert k3(["D4"], contrary, rule).status == "fail"
    assert k3(["D5"], contrary, rule).reason.startswith("not applicable")
    assert k3(["D4"], [Measurement("rms", -0.4, 0.2)], rule).status == "pass"


# --- K2 plumbing and the survivor rule --------------------------------------------------


def test_faers_pairs_follow_the_mapping() -> None:
    mapping = [
        {"meddra_name": "Myopathy", "used_for_flag": "yes"},
        {"meddra_name": "Foetal growth restriction", "used_for_flag": "no"},
        {"meddra_name": "NA", "used_for_flag": "yes"},
    ]
    assert faers_pairs(["Dasatinib"], mapped_terms(mapping)) == ["dasatinib=MYOPATHY"]


def test_k2_fails_only_when_both_sources_flag(tmp_path: Path) -> None:
    path = tmp_path / "safety.tsv"
    fields = [
        "drug",
        "genome_call",
        "genome_flag",
        "phenotype_flag",
        "phenotype_flag_reason",
        "labels_total",
        "combined_flag",
    ]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        writer.writerow(
            dict(zip(fields, ["a", "g", "yes", "yes", "rate", "3", BOTH_FLAG], strict=True))
        )
        writer.writerow(
            dict(
                zip(
                    fields, ["b", "g", "yes", "no", "", "0", "genome flags a question"], strict=True
                )
            )
        )
        writer.writerow(
            dict(zip(fields, ["c", "g", "no", "no", "", "2", "unflagged"], strict=True))
        )
    got = {d: c.status for d, c in k2_from_table(path).items()}
    assert got == {"a": "fail", "b": "caution", "c": "pass"}


def test_survivor_needs_convergence_and_no_failed_check(tmp_path: Path) -> None:
    from mva.drugs.checks import Check

    lists = _lists(tmp_path, {"a": (["X", "Y", "Z"], []), "b": (["X", "Y"], [])})
    ok, bad = Check("pass", ""), Check("fail", "")
    checks = {
        "X": CandidateChecks(ok, Check("caution", ""), ok),
        "Y": CandidateChecks(bad, ok, ok),
        "Z": CandidateChecks(ok, ok, ok),
    }
    rows = {r["drug"]: r for r in candidate_rows(lists, checks)}
    assert rows["X"]["survivor"] == "true"
    assert rows["Y"]["survivor_reason"] == "fails k1"
    assert rows["Z"]["survivor"] == "false"
    assert rows["X"]["rank_a"] == "1" and rows["Z"]["rank_b"] == ""


def test_query_name_prefers_a_spelling_the_label_source_lists(tmp_path: Path) -> None:
    from mva.drugs.convergence_candidates import query_names

    rows = [_row("a", 1, "PYRIDOXAL"), _row("a", 2, "ADENOSINE")]
    rows = [
        GeneratorRow(**{**r.__dict__, "drug_label": label})
        for r, label in zip(rows, ["Pyridoxal phosphate", "Adenosine phosphate"], strict=True)
    ]
    write_generator(tmp_path, "a", rows, [])
    lists = [read_generator(tmp_path, "a")]
    names = query_names(lists, {"pyridoxal phosphate", "adenosine"})
    assert names == {"PYRIDOXAL": "pyridoxal phosphate", "ADENOSINE": "adenosine"}
    assert query_names(lists)["ADENOSINE"] == "adenosine phosphate"


def test_sweep_keeps_only_representative_rows(tmp_path: Path) -> None:
    from mva.drugs.checks_sources import SweepColumns, load_sweep

    path = tmp_path / "sweep.tsv"
    path.write_text(
        "drug\tcontrast\tcliffs_delta\tp_raw\tp_opposite\trepresentative\n"
        "X\trms\t-0.5\t0.99\t0.01\tfalse\n"
        "X\trms\t0.2\t0.10\t0.90\ttrue\n"
        "Y-Z\taneuploidy\tNA\tNA\tNA\ttrue\n"
    )
    cols = SweepColumns(p_opposite="p_opposite", only_column="representative")
    sweep = load_sweep(path, cols)
    assert [(m.delta, m.p_opposite) for m in sweep["X"]] == [(0.2, 0.9)]
    assert "Y Z" not in sweep  # an untestable row carries no measurement
