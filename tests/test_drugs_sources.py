"""One class per public API adapter: does it parse the shape the API actually returns?

Every payload here is a trimmed *real* reply, recorded from the live endpoint on
2026-09-06 and cut down to the fields the adapter reads. The point of these tests is to
pin the schema deviations the adapters absorb — the Open Targets stage string, ChEMBL's
string ``max_phase``, DGIdb's ``interactionScore``, Reactome's mapping endpoint — so a
future schema move fails here rather than silently emptying a table.
"""

from __future__ import annotations

import pytest

from mva.drugs.cache import SourceError
from mva.drugs.sources import chembl, clinicaltrials, dgidb, openfda, opentargets, pubmed, reactome
from test_drugs_support import FakeFetcher, fixture


class TestOpenTargets:
    def fetcher(self) -> FakeFetcher:
        return (
            FakeFetcher()
            .route(opentargets.ENDPOINT, fixture("opentargets_search_target"), '"entity": "target"')
            .route(
                opentargets.ENDPOINT,
                fixture("opentargets_search_disease"),
                '"entity": "disease"',
            )
            .route(opentargets.ENDPOINT, fixture("opentargets_target"), "ensemblId")
        )

    def test_a_stage_string_maps_onto_the_integer_phase(self) -> None:
        assert opentargets.stage_to_phase("APPROVAL") == 4
        assert opentargets.stage_to_phase("PHASE_2_3") == 3
        assert opentargets.stage_to_phase("PHASE_1") == 1
        assert opentargets.stage_to_phase("NOT_A_STAGE") is None
        assert opentargets.stage_to_phase(None) is None

    def test_the_symbol_is_matched_exactly_not_taken_as_the_top_hit(self) -> None:
        # The recorded search puts the readthrough gene GENEA-PAKX first.
        record = opentargets.target_by_symbol(self.fetcher(), "GENEA")
        assert record is not None
        assert record["ensembl_id"] == "ENSG00000000001"
        assert record["approvedSymbol"] == "GENEA"

    def test_only_the_true_tractability_buckets_are_kept(self) -> None:
        record = opentargets.target_by_symbol(self.fetcher(), "GENEA")
        assert record is not None
        assert [t["label"] for t in record["tractability"]] == ["Approved Drug"]

    def test_an_unknown_symbol_is_none_not_an_error(self) -> None:
        record = opentargets.target_by_symbol(self.fetcher(), "NOSUCHGENE")
        assert record is None

    def test_one_row_per_candidate_disease_pair_with_the_phase_resolved(self) -> None:
        rows = opentargets.known_drugs(self.fetcher(), "ENSG00000000001")
        # WIDGETONE has two diseases, WOBBLIB has none (which still yields one row).
        assert len(rows) == 3
        approved = [r for r in rows if r["drug_name"] == "WIDGETONE"]
        assert {r["phase"] for r in approved} == {4}
        assert all(r["approved"] for r in approved)
        assert approved[0]["mechanism_of_action"] == "Widget kinase inhibitor"
        assert approved[0]["action_type"] == "INHIBITOR"
        assert approved[0]["status"] == "COMPLETED"

    def test_an_unmapped_disease_falls_back_to_the_source_text(self) -> None:
        rows = opentargets.known_drugs(self.fetcher(), "ENSG00000000001")
        unmapped = [r for r in rows if r["disease_id"] == ""]
        assert unmapped[0]["disease_name"] == "unmapped thing"

    def test_a_combined_stage_takes_its_upper_bound(self) -> None:
        rows = opentargets.known_drugs(self.fetcher(), "ENSG00000000001")
        wobblib = next(r for r in rows if r["drug_name"] == "WOBBLIB")
        assert wobblib["phase"] == 3
        assert wobblib["approved"] is False

    def test_disease_search_returns_efo_ids(self) -> None:
        hits = opentargets.disease_search(self.fetcher(), "fictional wobble syndrome")
        assert hits[0]["efo_id"] == "MONDO_0000123"

    def test_graphql_errors_raise_naming_the_endpoint(self) -> None:
        broken = FakeFetcher().route(opentargets.ENDPOINT, {"errors": [{"message": "boom"}]})
        with pytest.raises(SourceError) as caught:
            opentargets.disease_search(broken, "x")
        assert caught.value.url == opentargets.ENDPOINT


class TestChembl:
    def fetcher(self) -> FakeFetcher:
        return (
            FakeFetcher()
            .route("/target/search.json", fixture("chembl_target_search"))
            .route("/mechanism.json", fixture("chembl_mechanism"))
            .route("/molecule.json", fixture("chembl_molecule"))
        )

    def test_max_phase_arrives_as_a_string_and_is_parsed(self) -> None:
        assert chembl.phase("4.0") == 4
        assert chembl.phase(2) == 2
        assert chembl.phase(None) is None
        assert chembl.phase("") is None
        assert chembl.phase("not a phase") is None

    def test_only_human_targets_that_declare_the_symbol_are_kept(self) -> None:
        found = chembl.targets_for_gene(self.fetcher(), "GENEA")
        assert [t["target_chembl_id"] for t in found] == ["CHEMBL_T1"]
        assert found[0]["organism"] == "Homo sapiens"

    def test_a_symbol_no_component_declares_yields_nothing(self) -> None:
        assert chembl.targets_for_gene(self.fetcher(), "GENEZ") == []

    def test_mechanisms_keep_only_pubmed_references(self) -> None:
        rows = chembl.mechanisms_for_target(self.fetcher(), "CHEMBL_T1")
        assert [r["molecule_chembl_id"] for r in rows] == [
            "CHEMBL0001",
            "CHEMBL0003",
            "CHEMBL0004",
        ]
        assert rows[0]["pmids"] == ("90000333",)
        assert rows[0]["max_phase"] == 4
        assert rows[1]["max_phase"] is None

    def test_molecules_come_back_as_a_mapping_and_absence_is_not_phase_zero(self) -> None:
        facts = chembl.molecules(self.fetcher(), ["CHEMBL0001", "CHEMBL0003", "CHEMBL_NOPE"])
        assert facts["CHEMBL0001"]["max_phase"] == 4
        assert facts["CHEMBL0001"]["first_approval"] == 1999
        assert facts["CHEMBL0001"]["atc_classifications"] == ("L01EG04",)
        assert facts["CHEMBL0003"]["max_phase"] is None
        assert "CHEMBL_NOPE" not in facts

    def test_an_empty_id_list_makes_no_request(self) -> None:
        got = self.fetcher()
        assert chembl.molecules(got, []) == {}
        assert got.calls == []


class TestDgidb:
    def fetcher(self) -> FakeFetcher:
        return FakeFetcher().route(dgidb.ENDPOINT, fixture("dgidb_interactions"))

    def test_one_row_per_edge_with_the_renamed_score(self) -> None:
        rows = dgidb.interactions(self.fetcher(), ["GENEB", "GENEC"])
        assert len(rows) == 2
        assert rows[0]["gene"] == "GENEB"
        assert rows[0]["drug_name"] == "GADGETIB"
        assert rows[0]["score"] == pytest.approx(0.42)
        assert rows[0]["sources"] == ("ChEMBL", "TTD")
        assert rows[0]["pmids"] == ("90000444",)
        assert rows[0]["interaction_types"] == ("inhibitor",)

    def test_the_approved_flag_is_carried_through(self) -> None:
        rows = dgidb.interactions(self.fetcher(), ["GENEB"])
        assert [r["approved"] for r in rows] == [False, True]

    def test_a_gene_with_no_edges_contributes_nothing(self) -> None:
        rows = dgidb.interactions(self.fetcher(), ["GENEC"])
        assert all(r["gene"] != "GENEC" for r in rows)

    def test_an_empty_symbol_list_makes_no_request(self) -> None:
        got = self.fetcher()
        assert dgidb.interactions(got, []) == []
        assert got.calls == []

    def test_only_a_chembl_namespace_yields_a_chembl_id(self) -> None:
        assert dgidb.chembl_id("chembl:CHEMBL0003") == "CHEMBL0003"
        assert dgidb.chembl_id("ncit:C00001") is None
        assert dgidb.chembl_id("") is None


class TestReactome:
    def fetcher(self) -> FakeFetcher:
        return (
            FakeFetcher()
            .route("/data/mapping/UniProt/", fixture("reactome_pathways"))
            .route("/referenceEntities", fixture("reactome_participants"))
        )

    def test_pathways_come_from_the_mapping_endpoint_not_the_entity_one(self) -> None:
        got = self.fetcher()
        found = reactome.pathways_for_uniprot(got, "P00001")
        assert "/data/mapping/UniProt/P00001/pathways" in got.urls()[0]
        assert [p["stId"] for p in found] == ["R-HSA-000001", "R-HSA-000002", "R-HSA-000003"]

    def test_participants_keep_only_the_first_gene_name_of_a_gene_product(self) -> None:
        found = reactome.participants(self.fetcher(), "R-HSA-000001")
        # ALIAS is a synonym of GENEB, ATP is not a gene product, and the last entry
        # carries no geneName at all.
        assert found == ["GENEB", "GENED"]

    def test_a_404_body_is_an_empty_result_not_a_crash(self) -> None:
        got = FakeFetcher().route("/data/mapping/UniProt/", {"code": 404, "reason": "NOT_FOUND"})
        assert reactome.pathways_for_uniprot(got, "P99999") == []


class TestClinicalTrials:
    def test_the_nested_v2_shape_is_flattened(self) -> None:
        got = FakeFetcher().route(clinicaltrials.ENDPOINT, fixture("clinicaltrials_studies"))
        rows = clinicaltrials.studies(got, cond="testoma")
        assert len(rows) == 1
        row = rows[0]
        assert row["nct_id"] == "NCT00000001"
        assert row["phase"] == "PHASE2"
        assert row["overall_status"] == "RECRUITING"
        assert row["conditions"] == ("Testoma",)
        assert row["interventions"] == ("WIDGETONE",)
        assert row["start_date"] == "2024-01"
        assert row["study_type"] == "INTERVENTIONAL"

    def test_no_condition_and_no_intervention_makes_no_request(self) -> None:
        got = FakeFetcher()
        assert clinicaltrials.studies(got) == []
        assert got.calls == []

    def test_paging_stops_when_the_api_returns_no_token(self) -> None:
        got = FakeFetcher().route(clinicaltrials.ENDPOINT, fixture("clinicaltrials_studies"))
        clinicaltrials.studies(got, cond="testoma", max_pages=3)
        assert len(got.calls) == 1

    def test_an_empty_result_set_is_a_finding_not_an_error(self) -> None:
        got = FakeFetcher().route(clinicaltrials.ENDPOINT, {"studies": []})
        assert clinicaltrials.studies(got, cond="a disease nobody studies") == []


class TestPubmed:
    def fetcher(self) -> FakeFetcher:
        return (
            FakeFetcher()
            .route("/esearch.fcgi", fixture("pubmed_esearch"))
            .route("/esummary.fcgi", fixture("pubmed_esummary"))
        )

    def test_search_returns_pmids_and_count_returns_the_total(self) -> None:
        got = self.fetcher()
        assert pubmed.search(got, "widgets", retmax=2) == ["90000111", "90000222"]
        assert pubmed.count(got, "widgets") == 165

    def test_an_empty_term_makes_no_request(self) -> None:
        got = self.fetcher()
        assert pubmed.search(got, "   ") == []
        assert pubmed.count(got, "") == 0
        assert got.calls == []

    def test_summaries_carry_the_year_the_journal_and_the_doi(self) -> None:
        rows = pubmed.summaries(self.fetcher(), ["90000111", "90000222"])
        assert rows[0] == {
            "pmid": "90000111",
            "title": "A paper about widgets",
            "journal": "J Widget",
            "year": "2019",
            "doi": "10.1/x",
        }
        assert rows[1]["doi"] == ""

    def test_summaries_keep_the_order_asked(self) -> None:
        rows = pubmed.summaries(self.fetcher(), ["90000222", "90000111"])
        assert [r["pmid"] for r in rows] == ["90000222", "90000111"]


class TestOpenFda:
    def test_a_label_is_flattened(self) -> None:
        got = FakeFetcher().route(openfda.ENDPOINT, fixture("openfda_label"))
        found = openfda.label(got, "WIDGETONE")
        assert found["has_label"] is True
        assert found["brand_names"] == ("Widgex",)
        assert found["application_numbers"] == ("ANDA000001",)
        assert found["routes"] == ("ORAL",)

    def test_a_404_body_means_no_label_not_a_failure(self) -> None:
        got = FakeFetcher().route(openfda.ENDPOINT, fixture("openfda_404"))
        found = openfda.label(got, "NOTADRUG")
        assert found["has_label"] is False
        assert found["brand_names"] == ()

    def test_the_name_is_sent_as_a_quoted_phrase(self) -> None:
        got = FakeFetcher().route(openfda.ENDPOINT, fixture("openfda_label"))
        openfda.label(got, "two words")
        _method, _url, params = got.calls[0]
        assert params["search"] == 'openfda.generic_name:"two words"'

    def test_an_empty_name_makes_no_request(self) -> None:
        got = FakeFetcher()
        assert openfda.label(got, "  ")["has_label"] is False
        assert got.calls == []
