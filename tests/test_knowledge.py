"""The knowledge route, and the two measurements that decide whether it is one.

No sockets. The adapters are exercised against trimmed real payloads through the same
``FakeFetcher`` the Track 2 adapters use, and the statistics are exercised against hand-
built orderings whose answer can be worked out on paper.

The tests that matter most here are the *negative* ones. A literature route is easy to
make look good, so the suite pins the cases where the code has to say "this route
measures nothing": an allele nobody could have looked up, a ranking identical to a
citation count, and a decoy set the score cannot be told apart from.
"""

from __future__ import annotations

from typing import ClassVar

import pytest

from mva.drugs.cache import SourceError
from mva.knowledge import anchors, baselines, catalogue, protein, sources
from test_drugs_support import FakeFetcher

LITVAR_PUBS = {"pmids": [27397505, 31853058, 31658756], "pmcids": []}
LITVAR_NONE: dict[str, list[int]] = {"pmids": []}

PUBTATOR_HIT = {
    "count": 131,
    "page_size": 10,
    "results": [
        {
            "pmid": 15475955,
            "title": "Constitutional aneuploidy and cancer predisposition",
            "journal": "Nat Genet",
            "meta_date_publication": "2004",
            "score": 271.4,
        }
    ],
}
PUBTATOR_EMPTY: dict[str, object] = {"count": 0, "results": []}

UNIPROT = {
    "results": [{"primaryAccession": "X99999", "sequence": {"length": 1000}}],
}
INTERPRO = {
    "results": [
        {
            "metadata": {"accession": "IPR000001", "name": "Kinase domain", "type": "domain"},
            "proteins": [
                {"entry_protein_locations": [{"fragments": [{"start": 700, "end": 900}]}]}
            ],
        },
        {
            "metadata": {
                "accession": "IPR000002",
                "name": "Kinase-like superfamily",
                "type": "homologous_superfamily",
            },
            "proteins": [{"entry_protein_locations": [{"fragments": [{"start": 1, "end": 1000}]}]}],
        },
    ]
}
PREDICTION = [{"plddtDocUrl": "https://alphafold.ebi.ac.uk/files/AF-X99999-F1-confidence_v6.json"}]
CONFIDENCE = {
    "residueNumber": [10, 800, 810],
    "confidenceScore": [41.0, 92.5, 68.0],
}


class TestSources:
    def test_a_litvar_identifier_carries_its_trailing_hashes(self) -> None:
        assert sources.litvar_id("rs1801376") == "litvar@rs1801376##"

    def test_the_identifier_is_percent_encoded_inside_a_url_path(self) -> None:
        # Unencoded, the trailing ## is read as a url fragment, the client sends a
        # truncated identifier, LitVar answers "Variant not found" — and every variant
        # comes back with zero publications. A wrong headline, not a failed request.
        assert sources.litvar_path("rs1801376") == "litvar%40rs1801376%23%23"
        assert "#" not in sources.litvar_path("rs1801376")

    def test_publications_come_back_as_strings(self) -> None:
        fetcher = FakeFetcher().route(sources.LITVAR, LITVAR_PUBS, "")
        assert sources.publications_for_rsid(fetcher, "rs1801376")[0] == "27397505"

    def test_an_allele_nobody_published_about_is_an_empty_list_not_an_error(self) -> None:
        fetcher = FakeFetcher().route(sources.LITVAR, LITVAR_NONE, "")
        assert sources.publications_for_rsid(fetcher, "rs999") == []

    def test_litvars_400_variant_not_found_reads_as_nobody_published(self) -> None:
        # Measured live: LitVar answers an unknown variant with HTTP 400 and a detail
        # string, not 404 and not an empty list.
        fetcher = FakeFetcher().route(sources.LITVAR, {"detail": "Variant not found: x"}, "")
        assert sources.publications_for_rsid(fetcher, "rs999") == []

    def test_any_other_400_is_still_a_failure(self) -> None:
        fetcher = FakeFetcher().route(sources.LITVAR, {"detail": "Rate limit exceeded"}, "")
        with pytest.raises(SourceError):
            sources.publications_for_rsid(fetcher, "rs999")

    def test_a_blank_identifier_is_never_sent_to_the_network(self) -> None:
        fetcher = FakeFetcher()
        assert sources.publications_for_rsid(fetcher, "  ") == []
        assert fetcher.calls == []

    def test_the_search_reports_the_total_not_the_page(self) -> None:
        fetcher = FakeFetcher().route(sources.PUBTATOR, PUBTATOR_HIT, "")
        reply = sources.search_papers(fetcher, "GENEA AND Feature")
        assert reply["count"] == 131
        assert reply["papers"][0]["pmid"] == "15475955"
        assert reply["papers"][0]["year"] == "2004"

    def test_a_query_is_spelled_the_same_way_every_time(self) -> None:
        assert sources.gene_query(" GENEA ", " Short stature ") == "GENEA AND Short stature"
        assert sources.gene_query("GENEA", "  ") == "GENEA"


class TestCatalogue:
    def rows(self) -> list[dict[str, object]]:
        return [
            {"gene": "GENEA", "rsid": "rs1", "consequence_class": "missense"},
            {"gene": "GENEA", "rsid": "", "consequence_class": "truncating"},
            {
                "gene": "GENEB",
                "rsid": "rs2",
                "consequence_class": "missense",
                "clin_sig": "pathogenic",
                "child_call": "het",
                "child_posterior": 0.99,
            },
        ]

    def test_an_allele_with_no_identifier_is_unqueryable_not_unpublished(self) -> None:
        fetcher = FakeFetcher().route(sources.LITVAR, LITVAR_NONE, "")
        built = catalogue.build(fetcher, self.rows())
        blank = next(row for row in built if row.rsid == "")
        assert blank.pmid_count == catalogue.NOT_ASKED
        assert not blank.queryable
        assert not blank.described

    def test_the_summary_keeps_all_three_counts_apart(self) -> None:
        fetcher = FakeFetcher().route(sources.LITVAR, LITVAR_PUBS, "")
        summary = catalogue.summarise(catalogue.build(fetcher, self.rows()))
        assert summary.alleles == 3
        assert summary.queryable == 2
        assert summary.unqueryable == 1
        assert summary.described == 2

    def test_a_carried_pathogenic_allele_needs_both_halves(self) -> None:
        fetcher = FakeFetcher().route(sources.LITVAR, LITVAR_PUBS, "")
        built = catalogue.build(fetcher, self.rows())
        carried = [row for row in built if row.carried_pathogenic]
        assert [row.gene for row in carried] == ["GENEB"]

    def test_litvar_is_asked_once_per_distinct_identifier(self) -> None:
        duplicated = [*self.rows(), {"gene": "GENEC", "rsid": "rs1"}]
        fetcher = FakeFetcher().route(sources.LITVAR, LITVAR_PUBS, "")
        catalogue.build(fetcher, duplicated)
        assert len(fetcher.calls) == 2


class TestAnchors:
    def test_a_paper_returned_by_two_term_searches_matches_two_terms(self) -> None:
        fetcher = FakeFetcher().route(sources.PUBTATOR, PUBTATOR_HIT, "")
        result = anchors.for_gene(fetcher, "GENEA", ["Feature one", "Feature two"])
        assert result.best == 2
        assert result.anchors[0].matched_terms == ("Feature one", "Feature two")
        assert result.anchors[0].terms_total == 2

    def test_a_gene_the_literature_never_pairs_with_a_feature_scores_zero(self) -> None:
        fetcher = FakeFetcher().route(sources.PUBTATOR, PUBTATOR_EMPTY, "")
        result = anchors.for_gene(fetcher, "GENEZ", ["Feature one", "Feature two"])
        assert result.best == 0
        assert result.terms_with_any_paper == 0
        assert result.anchors == []

    def test_the_ranking_never_breaks_a_tie_on_citation_volume(self) -> None:
        # Two genes with the same best paper must tie on the printed statistics alone.
        one = anchors.GeneAnchors("GENEB", [], {"t": 500})
        two = anchors.GeneAnchors("GENEA", [], {"t": 1})
        assert [row[0] for row in anchors.rank([one, two])] == ["GENEA", "GENEB"]


class TestProtein:
    def context(self) -> protein.ProteinContext:
        fetcher = (
            FakeFetcher()
            .route(protein.UNIPROT, UNIPROT, "")
            .route("interpro", INTERPRO, "")
            .route("api/prediction", PREDICTION, "")
            .route("confidence_v6.json", CONFIDENCE, "")
        )
        return protein.context_for_gene(fetcher, "GENEA")

    def test_a_superfamily_covering_the_whole_protein_does_not_count_as_a_domain(self) -> None:
        # IPR000002 spans 1-1000, so a residue outside the real domain must still fail
        # the domain test — while the superfamily column records that it was covered.
        answer = protein.verdict(self.context(), 10)
        assert not answer.in_domain
        assert answer.in_superfamily

    def test_a_residue_inside_a_domain_at_high_confidence_supports_the_claim(self) -> None:
        answer = protein.verdict(self.context(), 800)
        assert answer.in_domain and answer.confident and answer.structural_support
        assert answer.domain_accession == "IPR000001"

    def test_low_confidence_refuses_support_even_inside_a_domain(self) -> None:
        answer = protein.verdict(self.context(), 810)
        assert answer.in_domain
        assert not answer.confident
        assert not answer.structural_support

    def test_the_figure_track_carries_fractions_and_never_a_residue(self) -> None:
        tracks = protein.tracks(self.context())
        assert tracks[0]["start_fraction"] == 0.001
        assert all(0.0 <= row["end_fraction"] <= 1.0 for row in tracks)
        assert all("start" not in row for row in tracks)


class TestBaselines:
    KNOWLEDGE: ClassVar[list[tuple[str, float]]] = [
        ("A", 5.0),
        ("B", 4.0),
        ("C", 3.0),
        ("D", 2.0),
        ("E", 1.0),
        ("F", 0.0),
    ]

    def test_ties_share_a_midrank_rather_than_being_broken_alphabetically(self) -> None:
        assert baselines.ranks([("A", 1.0), ("B", 1.0), ("C", 0.0)]) == {
            "A": 1.5,
            "B": 1.5,
            "C": 3.0,
        }

    def test_an_ordering_identical_to_the_citation_count_does_not_reorder(self) -> None:
        agreement = baselines.agreement(self.KNOWLEDGE, self.KNOWLEDGE)
        assert agreement.rho == 1.0
        assert agreement.overlap == agreement.k
        assert not agreement.reorders
        assert "citation volume" in agreement.verdict

    def test_a_reversed_baseline_reorders(self) -> None:
        reversed_scores = [(name, -score) for name, score in self.KNOWLEDGE]
        assert baselines.agreement(self.KNOWLEDGE, reversed_scores).reorders

    def test_a_top_k_cut_out_of_a_tie_says_how_wide_the_tie_was(self) -> None:
        flat = [("A", 1.0), ("B", 1.0), ("C", 1.0), ("D", 1.0), ("E", 1.0), ("F", 1.0)]
        assert baselines.tied_at(flat, 5) == 6
        assert baselines.agreement(flat, flat).tied_at_k == 6
        # A score with no tie at the boundary reports one.
        assert baselines.tied_at(self.KNOWLEDGE, 5) == 1

    def test_a_correlation_over_fewer_than_three_shared_names_is_not_reported(self) -> None:
        assert baselines.spearman([("A", 1.0), ("B", 2.0)], [("A", 1.0), ("B", 2.0)]) == 0.0

    def test_a_route_that_separates_but_adds_nothing_is_not_a_ranking_route(self) -> None:
        weight = baselines.weigh(
            target_scores=[5.0] * 40 + [4.0] * 40,
            decoy_scores=[1.0] * 80,
            knowledge=self.KNOWLEDGE,
            citations=self.KNOWLEDGE,
        )
        assert weight.separation.separates
        assert not weight.ranking_route
        assert "adds nothing to the citation count" in weight.verdict

    def test_a_route_that_reorders_but_cannot_beat_its_decoys_is_not_one_either(self) -> None:
        weight = baselines.weigh(
            target_scores=[1.0, 2.0, 3.0, 4.0] * 20,
            decoy_scores=[1.0, 2.0, 3.0, 4.0] * 20,
            knowledge=self.KNOWLEDGE,
            citations=[(name, -score) for name, score in self.KNOWLEDGE],
        )
        assert not weight.separation.separates
        assert not weight.ranking_route
        assert "no measured separation" in weight.verdict
