"""Signature reversal (step 9, E3): the pure logic behind entry 153, on synthetic data.

No network: the engines' replies are hand-built in the shapes verified live on 2026-09-25
(``mva.drugs.sources.sigcom`` / ``ilincs`` docstrings). Every gene, drug and id is invented,
so a passing test cannot rest on this case's real values.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

import pytest

from mva.drugs.signature_reversal import (
    Hit,
    Ranked,
    Signature,
    decoy_signatures,
    ilincs_reverser_hits,
    pick_signature,
    rank_by_label,
    read_consensus_row,
    sigcom_hits,
    top_keys,
)
from mva.drugs.signature_reversal_approval import (
    Approval,
    approve,
    canonical,
    chembl_phase4_index,
    looks_like_code,
)
from mva.drugs.signature_reversal_tables import (
    GENERATOR_COLUMNS,
    compound_rows,
    control_result,
    generator_rows,
    verdict_inputs,
    write_tsv,
)
from mva.drugs.sources import ilincs, sigcom
from test_drugs_support import FakeFetcher

SPACE = frozenset(f"G{i:02d}" for i in range(20))


class TestConsensusRow:
    LINES = ("\tGA\tGB\tGC\n", "KO1\t0.1\t0.2\t0.3\n", "KO2\t-1\t0\t2\n")

    def test_the_named_row_is_read_against_the_header(self) -> None:
        assert read_consensus_row(self.LINES, "KO2") == {"GA": -1.0, "GB": 0.0, "GC": 2.0}

    def test_an_absent_row_raises_rather_than_returning_empty(self) -> None:
        with pytest.raises(ValueError, match="not a row"):
            read_consensus_row(self.LINES, "KO3")

    def test_a_ragged_row_raises(self) -> None:
        with pytest.raises(ValueError, match="values"):
            read_consensus_row(("\tGA\tGB\n", "KO1\t1\n"), "KO1")


class TestPickSignature:
    COEFFS = {f"G{i:02d}": float(i - 10) for i in range(20)} | {"OUTSIDE": 99.0}

    def pick(self, size: int = 3, exclude: tuple[str, ...] = ()) -> Signature:
        return pick_signature(
            self.COEFFS, space=SPACE, size=size, exclude=exclude, name="t", source="s"
        )

    def test_the_extremes_inside_the_space_are_kept(self) -> None:
        picked = self.pick()
        assert picked.up == ("G19", "G18", "G17")
        assert picked.down == ("G00", "G01", "G02")
        assert "OUTSIDE" not in picked.genes()

    def test_an_excluded_gene_is_never_in_the_query(self) -> None:
        assert "G19" not in self.pick(exclude=("G19",)).genes()

    def test_a_size_that_would_label_a_lowered_gene_raised_is_refused(self) -> None:
        # 9 genes are > 0; asking for 10 raised genes would include G10 (= 0).
        with pytest.raises(ValueError, match="too few"):
            self.pick(size=10)


class TestDecoys:
    def test_seeded_size_matched_and_disjoint_within_each_decoy(self) -> None:
        first = decoy_signatures(SPACE, n_up=4, n_down=4, count=5, seed=7, exclude=("G00",))
        again = decoy_signatures(SPACE, n_up=4, n_down=4, count=5, seed=7, exclude=("G00",))
        assert first == again
        for decoy in first:
            assert len(decoy.up) == len(decoy.down) == 4
            assert not set(decoy.up) & set(decoy.down)
            assert decoy.genes() <= SPACE - {"G00"}
        assert len({decoy.genes() for decoy in first}) == 5

    def test_a_space_too_small_raises(self) -> None:
        with pytest.raises(ValueError):
            decoy_signatures(SPACE, n_up=15, n_down=15, count=1, seed=1)


class TestEngineReplies:
    SIGCOM: ClassVar[dict[str, Any]] = {
        "maxRank": 10,
        "results": [
            {"type": "mimickers", "uuid": "m1", "rank": 0, "z-sum": 5.0},
            {"type": "reversers", "uuid": "r1", "rank": 9, "z-sum": -6.0},
            {"type": "reversers", "uuid": "r2", "rank": 8, "z-sum": -5.0},
            {"type": "reversers", "uuid": "unknown", "rank": 7, "z-sum": -4.0},
        ],
    }

    def test_a_sigcom_reverser_position_counts_from_the_bottom_of_the_library(self) -> None:
        hits = sigcom_hits(self.SIGCOM, {"r1": "a", "r2": "b"}, direction="reversers")
        assert [(h.signature_id, h.position) for h in hits] == [("r1", 1), ("r2", 2)]
        assert sigcom.reverser_position({"rank": 9}, 10) == 1

    def test_a_mimicker_position_is_one_based_and_unnamed_signatures_drop(self) -> None:
        hits = sigcom_hits(self.SIGCOM, {"m1": "x"}, direction="mimickers")
        assert [(h.label, h.position) for h in hits] == [("x", 1)]

    def test_ilincs_keeps_negative_concordance_most_negative_first(self) -> None:
        rows = [
            {"signatureID": "S1", "similarity": 0.9, "pValue": 0.01, "compound": "up"},
            {"signatureID": "S2", "similarity": -0.5, "pValue": 0.02, "compound": "b"},
            {"signatureID": "S3", "similarity": -0.8, "pValue": 0.03, "compound": "a"},
        ]
        hits = ilincs_reverser_hits(rows)
        assert [(h.label, h.position) for h in hits] == [("a", 1), ("b", 2)]

    def test_a_reply_without_a_table_raises(self) -> None:
        fake = FakeFetcher().route("findConcordancesSC", {"Remark": ["error"]})
        with pytest.raises(ValueError, match="concordanceTable"):
            ilincs.concordance(fake, ["A"], ["B"])

    def test_a_crawl_shorter_than_the_library_count_raises(self) -> None:
        fake = FakeFetcher().route("signatures/find", [{"id": "a"}, {"id": "b"}])
        with pytest.raises(ValueError, match="expected 3"):
            sigcom.crawl_library(fake, "lib", page=10, expected=3)


def _hit(label: str, position: int, sid: str = "") -> Hit:
    return Hit(
        signature_id=sid or f"{label}-{position}", position=position, score=-1.0, label=label
    )


class TestRankByLabel:
    def test_one_compound_many_signatures_is_ranked_by_its_best(self) -> None:
        hits = [_hit("Drug A Hydrochloride", 5), _hit("DRUG B", 2), _hit("drug a", 1)]
        ranked = rank_by_label(hits, key=lambda s: s.upper().removesuffix(" HYDROCHLORIDE"))
        assert [(r.key, r.rank, r.best_position, r.signatures) for r in ranked] == [
            ("DRUG A", 1, 1, 2),
            ("DRUG B", 2, 2, 1),
        ]
        assert top_keys(ranked, 1) == {"DRUG A"}

    def test_an_excluded_key_is_left_out_before_ranking(self) -> None:
        ranked = rank_by_label([_hit("SELF", 1), _hit("OTHER", 2)], key=str, exclude=("SELF",))
        assert [(r.key, r.rank) for r in ranked] == [("OTHER", 1)]


class TestApproval:
    CHEMBL: ClassVar[dict[str, Any]] = {
        "molecules": [
            {
                "molecule_chembl_id": "CHEMBL9",
                "pref_name": "WIDGETINIB",
                "max_phase": "4.0",
                "molecule_synonyms": [
                    {"molecule_synonym": "WX-4032", "syn_type": "RESEARCH_CODE"},
                    {"molecule_synonym": "Brandex", "syn_type": "TRADE_NAME"},
                ],
            }
        ]
    }

    def test_codes_are_told_from_drug_names(self) -> None:
        assert looks_like_code("BRD-K12345678")
        assert looks_like_code("PD-0325901")
        assert looks_like_code("38194-50-2")
        assert not looks_like_code("SIROLIMUS")

    def test_a_research_code_meets_its_inn_and_a_trade_name_is_not_a_key(self) -> None:
        index = chembl_phase4_index(FakeFetcher().route("molecule.json", self.CHEMBL))
        assert canonical("wx-4032", index) == "WIDGETINIB"
        assert canonical("Widgetinib Hydrochloride", index) == "WIDGETINIB"
        assert "BRANDEX" not in index

    def test_evidence_names_each_source_it_rests_on(self) -> None:
        got = approve(["A", "B", "C"], {"A": ("CHEMBL1", "A")}, {"A": "NDA1", "B": "ANDA2"})
        assert got["A"].evidence == "ChEMBL max_phase 4 (CHEMBL1); openFDA NDA1"
        assert got["B"].approved and not got["C"].approved


def _ranked(keys: list[str]) -> list[Ranked]:
    return rank_by_label([_hit(k, i) for i, k in enumerate(keys, start=1)], key=str)


class TestVerdict:
    def rows(self, decoy_tops: list[set[str]], approved: set[str]) -> list[dict[str, Any]]:
        return compound_rows(
            _ranked(["A", "B", "C"]),
            _ranked(["B", "A", "D"]),
            sigcom_universe={"A", "B", "C"},
            ilincs_universe={"A", "B", "D"},
            approvals={k: Approval(approved=True, evidence="e") for k in approved},
            decoy_tops=decoy_tops,
            top_n=2,
            decoy_max_hits=1,
        )

    def test_supported_needs_both_tops_approval_specificity_and_the_control(self) -> None:
        rows = self.rows([{"A"}, set(), set()], approved={"A"})
        listed = [r["drug"] for r in rows if r["listed"]]
        assert listed == ["A"]
        good = control_result("lib", _ranked(["BUB"]), ["BUB"], universe=100, cut=0.05)
        assert verdict_inputs(rows, [good], decoy_max_hits=1)["status"] == "supported"

    def test_a_drug_in_two_decoys_tops_is_not_specific_and_refutes(self) -> None:
        rows = self.rows([{"A"}, {"A"}, set()], approved={"A"})
        good = control_result("lib", _ranked(["BUB"]), ["BUB"], universe=100, cut=0.05)
        got = verdict_inputs(rows, [good], decoy_max_hits=1)
        assert got["status"] == "refuted" and got["listed_drugs"] == ["A"]

    def test_a_failed_control_is_uninterpretable_never_support(self) -> None:
        rows = self.rows([set()], approved={"A", "B"})
        beyond = control_result("lib", [], ["BUB"], universe=100, cut=0.05)
        tenth = _ranked([f"N{i}" for i in range(9)] + ["BUB"])
        late = control_result("lib", tenth, ["BUB"], universe=100, cut=0.05)
        assert not beyond.passed and not late.passed
        assert verdict_inputs(rows, [beyond, late], decoy_max_hits=1)["status"] == (
            "uninterpretable"
        )

    def test_an_empty_list_still_writes_the_contract_header(self, tmp_path: Path) -> None:
        rows = self.rows([set()], approved=set())
        generator = generator_rows(rows, entry="e")
        assert generator == []
        path = write_tsv(tmp_path / "lincs.tsv", generator, GENERATOR_COLUMNS)
        assert path.read_text().splitlines() == ["\t".join(GENERATOR_COLUMNS)]


def test_the_step10_join_key_folds_hyphens_before_salts() -> None:
    from mva.drugs.signature_reversal_tables import join_key

    assert join_key("valproic-acid sodium") == "VALPROIC ACID"


def test_engine_overlap_counts_only_inside_the_shared_universe() -> None:
    from mva.drugs.signature_reversal_tables import engine_overlap

    assert engine_overlap([{"A", "B", "X"}, {"C"}], {"A", "X", "C"}, {"A", "B", "C"}) == [1, 1]
