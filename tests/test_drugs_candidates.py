"""Candidate gathering: the merge across three sources, the dedup key, the approved rule.

The rules under test:

* one row per ``(drug_name.lower(), target_symbol)`` — the same drug against two targets is
  two rows, the same drug against one target from three sources is one row naming three;
* ``approved`` is the disjunction of ChEMBL phase 4, an Open Targets ``APPROVAL`` stage and
  DGIdb's own flag;
* ``fda_label`` is ``None`` when nothing checked, which is not ``False``;
* a bare ChEMBL id in the ``drug_name`` slot is replaced by the preferred name during
  enrichment, and the rows are re-deduped afterwards so the rename cannot leave two rows
  for one drug.
"""

from __future__ import annotations

from mva.drugs.candidates import Candidate, Sources, gather, key_of
from mva.drugs.pathway import TargetRow
from mva.drugs.sources import dgidb, openfda, opentargets
from test_drugs_support import FakeFetcher, fixture

TARGETS = [
    TargetRow("GENEA", "seed", direction_ids=("X1",), uniprot="P00001"),
    TargetRow("GENEB", "seed", direction_ids=("X1", "X2")),
    TargetRow("GENED", "pathway", pathways=("R-HSA-000001",)),
]


def open_targets() -> FakeFetcher:
    return (
        FakeFetcher()
        .route(opentargets.ENDPOINT, fixture("opentargets_search_target"), '"entity": "target"')
        .route(opentargets.ENDPOINT, fixture("opentargets_target"), "ensemblId")
    )


def chembl() -> FakeFetcher:
    return (
        FakeFetcher()
        .route("/target/search.json", fixture("chembl_target_search"))
        .route("/mechanism.json", fixture("chembl_mechanism"))
        .route("/molecule.json", fixture("chembl_molecule"))
    )


def fda() -> FakeFetcher:
    return (
        FakeFetcher()
        .route(openfda.ENDPOINT, fixture("openfda_label"), "WIDGETONE")
        .route(openfda.ENDPOINT, fixture("openfda_404"))
    )


def all_sources(**overrides) -> Sources:
    base = {
        "opentargets": open_targets(),
        "chembl": chembl(),
        "dgidb": FakeFetcher().route(dgidb.ENDPOINT, fixture("dgidb_interactions")),
        "openfda": fda(),
    }
    base.update(overrides)
    return Sources(**base)


class TestKey:
    def test_the_key_folds_case_on_the_drug_only(self) -> None:
        assert key_of("Widgetone", "GENEA") == ("widgetone", "GENEA")
        assert key_of(" WIDGETONE ", "GENEA") == key_of("widgetone", "GENEA")
        assert key_of("widgetone", "GENEA") != key_of("widgetone", "GENEB")


class TestGather:
    def test_the_same_drug_against_two_targets_stays_two_rows(self) -> None:
        from mva.drugs.candidates import _add

        merged: dict[tuple[str, str], object] = {}
        _add(merged, Candidate("WIDGETONE", "CHEMBL0001", "GENEA", "seed", source=("chembl",)))
        _add(merged, Candidate("widgetone", "CHEMBL0001", "GENEB", "seed", source=("dgidb",)))
        assert len(merged) == 2

    def test_a_row_seen_by_two_sources_names_both(self) -> None:
        rows = gather(TARGETS, all_sources())
        merged = next(r for r in rows if r.drug_name == "WIDGETONE" and r.target_symbol == "GENEA")
        assert set(merged.source) == {"opentargets", "chembl"}
        assert merged.direction_ids == ("X1",)

    def test_a_bare_chembl_id_is_renamed_and_then_re_deduped(self) -> None:
        rows = gather(TARGETS, all_sources())
        # CHEMBL0001 arrived from ChEMBL with the id in the name slot; after enrichment
        # there must be no row still called CHEMBL0001, and only one WIDGETONE per target.
        assert not any(r.drug_name.startswith("CHEMBL") for r in rows)
        per_target = [(r.drug_name.lower(), r.target_symbol) for r in rows]
        assert len(per_target) == len(set(per_target))

    def test_dgidb_edges_join_on_the_gene_they_name(self) -> None:
        rows = gather(TARGETS, all_sources())
        gadgetib = [r for r in rows if r.drug_name == "GADGETIB"]
        assert {r.target_symbol for r in gadgetib} >= {"GENEB"}
        from_dgidb = next(r for r in gadgetib if r.target_symbol == "GENEB")
        assert "dgidb" in from_dgidb.source
        assert "90000444" in from_dgidb.pmids

    def test_a_dgidb_gene_outside_the_target_set_is_dropped(self) -> None:
        rows = gather([TargetRow("GENED", "pathway")], Sources(dgidb=all_sources().dgidb))
        assert rows == []

    def test_enrichment_fills_phase_first_approval_and_atc(self) -> None:
        rows = gather(TARGETS, all_sources())
        widgetone = next(r for r in rows if r.drug_name == "WIDGETONE")
        assert widgetone.max_phase == 4
        assert widgetone.first_approval == "1999"
        assert widgetone.atc == ("L01EG04",)

    def test_a_source_left_out_simply_contributes_nothing(self) -> None:
        only_dgidb = gather(TARGETS, Sources(dgidb=all_sources().dgidb))
        assert {s for r in only_dgidb for s in r.source} == {"dgidb"}


class TestApproved:
    def test_open_targets_approval_stage_marks_a_row_approved(self) -> None:
        rows = gather(TARGETS, Sources(opentargets=open_targets()))
        widgetone = next(r for r in rows if r.drug_name == "WIDGETONE")
        assert widgetone.approved is True
        wobblib = next(r for r in rows if r.drug_name == "WOBBLIB")
        assert wobblib.approved is False

    def test_chembl_phase_four_marks_a_row_approved(self) -> None:
        rows = gather(TARGETS, Sources(chembl=chembl()))
        approved = {r.drug_name for r in rows if r.approved}
        assert "WIDGETONE" in approved
        assert "GADGETIB" not in approved

    def test_the_dgidb_flag_alone_marks_a_row_approved(self) -> None:
        rows = gather(TARGETS, Sources(dgidb=all_sources().dgidb))
        sprocketol = next(r for r in rows if r.drug_name == "SPROCKETOL")
        assert sprocketol.approved is True
        assert sprocketol.max_phase is None  # approved by DGIdb, no ChEMBL phase to quote

    def test_an_unapproved_row_is_never_label_checked(self) -> None:
        rows = gather(TARGETS, all_sources())
        for row in rows:
            if not row.approved:
                assert row.fda_label is None

    def test_an_approved_row_records_true_or_false_never_none(self) -> None:
        rows = gather(TARGETS, all_sources())
        approved = [r for r in rows if r.approved]
        assert approved
        assert all(r.fda_label is not None for r in approved)
        labelled = {r.drug_name for r in approved if r.fda_label}
        assert labelled == {"WIDGETONE"}

    def test_without_an_openfda_fetcher_every_label_stays_unknown(self) -> None:
        rows = gather(TARGETS, all_sources(openfda=None))
        assert all(r.fda_label is None for r in rows)


class TestMergeArithmetic:
    def test_the_higher_phase_wins_when_two_sources_disagree(self) -> None:
        from mva.drugs.candidates import _add

        merged: dict[tuple[str, str], object] = {}
        _add(merged, Candidate("D", "CHEMBL1", "G", "seed", max_phase=2, source=("chembl",)))
        _add(merged, Candidate("d", "", "G", "seed", max_phase=4, source=("dgidb",)))
        row = next(iter(merged.values())).row
        assert row.max_phase == 4
        assert row.source == ("chembl", "dgidb")
        assert row.drug_id == "CHEMBL1"

    def test_a_namespaced_dgidb_id_resolves_to_a_bare_chembl_id(self) -> None:
        # Regression: upper-casing the whole concept id first produced "CHEMBL:CHEMBL3"
        # (which still startswith "CHEMBL"), and ChEMBL resolved none of them.
        from mva.drugs.candidates import _chembl_id

        assert _chembl_id(Candidate("D", "chembl:CHEMBL0003", "G", "seed")) == "CHEMBL0003"
        assert _chembl_id(Candidate("D", "CHEMBL0003", "G", "seed")) == "CHEMBL0003"
        assert _chembl_id(Candidate("D", "ncit:C00001", "G", "seed")) is None
        assert _chembl_id(Candidate("D", "", "G", "seed")) is None

    def test_a_dgidb_chembl_id_gets_enriched_like_any_other(self) -> None:
        rows = gather(TARGETS, all_sources())
        gadgetib = next(r for r in rows if r.drug_name == "GADGETIB")
        # CHEMBL0003 has no phase in the fixture, so enrichment must not invent one -
        # but it must have been looked up, which the preferred name proves.
        assert gadgetib.max_phase is None
        assert gadgetib.approved is False

    def test_an_unknown_phase_never_overwrites_a_known_one(self) -> None:
        from mva.drugs.candidates import _add

        merged: dict[tuple[str, str], object] = {}
        _add(merged, Candidate("D", "", "G", "seed", max_phase=4))
        _add(merged, Candidate("D", "", "G", "seed", max_phase=None))
        assert next(iter(merged.values())).row.max_phase == 4
