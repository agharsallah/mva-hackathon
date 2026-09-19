"""Transfer cards: the case is swapped, nothing of the template's case leaks, and the
comparison arithmetic is the arithmetic the manifest claims.

Every value here is invented. The template is ``tests/fixtures/track2/card.json`` (an
already-synthetic case) with the three case-agnostic blocks bolted on, and the spec is a
second invented disease with invented identifiers. A test that passed only because the
code hard-coded this repository's real case or its real second case would fail here.

Offline by construction: no fetcher, no socket, no sleep. The phenotype reader is given a
handful of hand-written ``phenotype.hpoa`` lines in ``tmp_path``.

No genomic position appears: genes, made-up HPO ids, drug names and counts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from mva.drugs import enrich, mechanism, transfer
from test_drugs_support import FIXTURES

# ── the doubles ──────────────────────────────────────────────────────────────────────

ANTI = [{"id": "A1", "name": "invented anti-direction", "moa_pattern": "widget"}]
LADDER = {"purpose": "invented", "rungs": [{"rung": 5, "label": "invented top rung"}]}
CONSTRAINTS = {"eligibility": "invented", "public_sources_only": True}

SPEC: dict[str, Any] = {
    "picked_by": "an invented second case, chosen for this test",
    "gene": {"symbol": "GENEZ", "uniprot": "P00099", "protein": "Sprocket ATPase"},
    "case": {
        "disease": "Fictional sprocket syndrome 9 (FSS9)",
        "omim_phenotype": "999999",
        "mondo": "MONDO:9999999",
        "tumour_context": "sprocketoma (HP:9999001), an invented malignancy",
        "context_standard_of_care": {"drugs": ["MADEUPICIN"], "source": "invented"},
    },
    "mechanism": {"class": "loss-of-function", "pathway": "sprocket assembly checkpoint"},
    "repurposing_directions": [
        {"id": "D1", "name": "d one", "rationale": "made up", "seed_targets": ["GENEZ"]},
        {"id": "D2", "name": "d two", "rationale": "made up", "seed_targets": ["GENEY"]},
        {"id": "D3", "name": "d three", "rationale": "made up", "seed_targets": ["GENEX"]},
        {
            "id": "D4",
            "name": "d four",
            "rationale": "made up",
            "seed_targets": ["GENEW"],
            "context": True,
        },
    ],
}

HPOA = "\n".join(
    [
        '#description: "invented"',
        "#version: 2099-12-31",
        "database_id\tdisease_name\tqualifier\thpo_id\treference\tevidence",
        "OMIM:999999\tFictional sprocket syndrome 9\t\tHP:9999001\tPMID:1\tPCS",
        "OMIM:999999\tFictional sprocket syndrome 9\tNOT\tHP:9999002\tPMID:1\tPCS",
        "OMIM:999999\tFictional sprocket syndrome 9\t\tHP:9999003\tPMID:1\tPCS",
        "OMIM:999999\tFictional sprocket syndrome 9\t\tHP:9999001\tPMID:2\tPCS",
        "OMIM:888888\tSomething else entirely\t\tHP:9999004\tPMID:3\tPCS",
        "",
    ]
)


@pytest.fixture
def template(tmp_path: Path) -> mechanism.MechanismCard:
    """The synthetic card, plus the three blocks a transfer card copies."""
    raw = json.loads((FIXTURES / "card.json").read_text(encoding="utf-8"))
    raw |= {"anti_directions": ANTI, "evidence_ladder": LADDER, "constraints": CONSTRAINTS}
    path = tmp_path / "template.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return mechanism.load(path)


@pytest.fixture
def spec(tmp_path: Path) -> transfer.TransferSpec:
    path = tmp_path / "transfer_spec.json"
    path.write_text(json.dumps(SPEC), encoding="utf-8")
    return transfer.load_spec(path)


# ── the phenotype reader ─────────────────────────────────────────────────────────────


class TestHpoAnnotation:
    def test_terms_are_read_deduped_and_not_qualified_rows_are_skipped(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "phenotype.hpoa"
        path.write_text(HPOA, encoding="utf-8")
        found = transfer.hpo_annotation(path, "OMIM:999999")
        assert found.terms == ("HP:9999001", "HP:9999003")
        assert found.excluded == ("HP:9999002",)
        assert found.rows == 4
        assert found.disease_name == "Fictional sprocket syndrome 9"

    def test_the_files_own_version_line_travels_with_the_terms(self, tmp_path: Path) -> None:
        path = tmp_path / "phenotype.hpoa"
        path.write_text(HPOA, encoding="utf-8")
        found = transfer.hpo_annotation(path, "OMIM:999999")
        assert found.version == "2099-12-31"
        assert "2099-12-31" in found.provenance
        assert "1 NOT-qualified row(s) skipped" in found.provenance

    def test_a_disease_with_no_rows_raises_rather_than_returning_nothing(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "phenotype.hpoa"
        path.write_text(HPOA, encoding="utf-8")
        with pytest.raises(LookupError):
            transfer.hpo_annotation(path, "OMIM:000000")


# ── the card ─────────────────────────────────────────────────────────────────────────


class TestTransferCard:
    def test_the_case_is_the_specs_and_the_templates_case_does_not_leak(
        self, template: mechanism.MechanismCard, spec: transfer.TransferSpec
    ) -> None:
        card = transfer.transfer_card(template, spec, today="2099-01-01")
        assert card["case"]["disease"] == "Fictional sprocket syndrome 9 (FSS9)"
        assert "proband_id" not in card["case"]
        # the template's gene is named on purpose in `transfer` and `_standing` (that is
        # the provenance); it must appear nowhere in the blocks the pipeline queries from.
        queried = json.dumps(
            {key: card[key] for key in ("case", "gene", "mechanism", "repurposing_directions")}
        )
        for leaked in ("TESTPROBAND", "Fictional wobble syndrome 3", "testoma", "GENEA"):
            assert leaked not in queried, f"{leaked} leaked from the template's case"
        assert card["transfer"]["template_gene"] == "GENEA"

    def test_it_asserts_no_allele_and_says_what_it_is_in_its_first_words(
        self, template: mechanism.MechanismCard, spec: transfer.TransferSpec
    ) -> None:
        card = transfer.transfer_card(template, spec, today="2099-01-01")
        assert card["alleles"] == []
        assert card["_standing"].startswith("TRANSFER CARD")
        assert "not a finding for the proband" in card["_standing"]

    def test_only_the_case_agnostic_blocks_are_copied_and_the_card_says_so(
        self, template: mechanism.MechanismCard, spec: transfer.TransferSpec
    ) -> None:
        card = transfer.transfer_card(template, spec, today="2099-01-01")
        assert card["anti_directions"] == ANTI
        assert card["evidence_ladder"] == LADDER
        assert card["constraints"] == CONSTRAINTS
        assert card["transfer"]["copied_from_template"]["blocks"] == [
            "anti_directions",
            "evidence_ladder",
            "constraints",
        ]
        assert card["transfer"]["inherited_from_template_case"] == "nothing"
        # a deep copy: mutating the card must not reach back into the template
        card["anti_directions"][0]["id"] = "MUTATED"
        assert template.raw["anti_directions"][0]["id"] == "A1"

    def test_the_context_flag_is_on_the_tumour_direction_alone(
        self, template: mechanism.MechanismCard, spec: transfer.TransferSpec
    ) -> None:
        card = transfer.transfer_card(template, spec, today="2099-01-01")
        flags = [(d["id"], d["context"]) for d in card["repurposing_directions"]]
        assert flags == [("D1", False), ("D2", False), ("D3", False), ("D4", True)]

    @pytest.mark.parametrize(
        ("mutate", "why"),
        [
            (lambda ds: [d | {"context": False} for d in ds], "no direction is the tumour one"),
            (lambda ds: [d | {"context": True} for d in ds], "every direction claims to be"),
            (lambda ds: ds[:3], "only three directions"),
            (lambda ds: [ds[0] | {"id": "X9"}, *ds[1:]], "an id outside D1-D4"),
        ],
    )
    def test_a_card_that_could_grade_wrongly_raises_instead(
        self,
        template: mechanism.MechanismCard,
        tmp_path: Path,
        mutate,
        why: str,
    ) -> None:
        payload = dict(SPEC)
        payload["repurposing_directions"] = mutate(SPEC["repurposing_directions"])
        path = tmp_path / "bad_spec.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(ValueError):
            transfer.transfer_card(template, transfer.load_spec(path)), why

    def test_the_card_round_trips_through_the_ordinary_loader(
        self, template: mechanism.MechanismCard, spec: transfer.TransferSpec, tmp_path: Path
    ) -> None:
        card = transfer.transfer_card(template, spec, today="2099-01-01")
        path = tmp_path / "mechanism.json"
        path.write_text(json.dumps(card), encoding="utf-8")
        parsed = mechanism.load(path)
        assert parsed.gene_symbol == "GENEZ"
        assert parsed.disease_query == "Fictional sprocket syndrome 9"
        assert parsed.tumour_context == "sprocketoma"
        assert parsed.pathway == "sprocket assembly checkpoint"
        assert [d.id for d in parsed.directions] == ["D1", "D2", "D3", "D4"]
        assert parsed.seed_targets == ("GENEZ", "GENEY", "GENEX", "GENEW")

    def test_the_phenotype_is_read_into_the_case_never_typed(
        self, template: mechanism.MechanismCard, spec: transfer.TransferSpec, tmp_path: Path
    ) -> None:
        path = tmp_path / "phenotype.hpoa"
        path.write_text(HPOA, encoding="utf-8")
        annotation = transfer.hpo_annotation(path, spec.disease_id)
        card = transfer.transfer_card(template, spec.with_phenotype(annotation))
        assert card["case"]["hpo_terms"] == ["HP:9999001", "HP:9999003"]
        assert card["case"]["hpo_terms_excluded"] == ["HP:9999002"]
        assert card["transfer"]["hpo_source"]["version"] == "2099-12-31"
        assert card["transfer"]["hpo_source"]["excluded"] == 1


# ── the comparison ───────────────────────────────────────────────────────────────────

SNAPSHOT = {
    "card": {"gene": "GENEZ", "disease": "FSS9", "tumour_context": "sprocketoma", "version": 1},
    "rows": {"drug_candidates": 40},
    "targets": {"total": 11},
    "candidates": {"distinct_approved_drugs": 7},
    "requests": {"chembl": {"replies": 10, "live": 4}, "pubmed": {"replies": 5, "live": 0}},
}
ANALYSIS = {
    "rows": {"shortlist": 3, "do_not": 2},
    "ladder_drugs_by_max_rung": {"5": 2, "4": 1, "1": 4},
    "requests": {"pubmed": {"replies": 8, "live": 6}},
}


class TestComparison:
    def test_cache_hits_are_replies_minus_live_summed_over_both_stages(self) -> None:
        live, cached = transfer.request_totals(SNAPSHOT["requests"], ANALYSIS["requests"])
        assert live == 10  # 4 + 0 + 6
        assert cached == 13  # (10-4) + (5-0) + (8-6)

    def test_a_missing_or_malformed_requests_block_contributes_nothing(self) -> None:
        assert transfer.request_totals(None, {}, {"x": "not a dict"}) == (0, 0)

    def test_one_row_per_case_with_every_rung_present_even_at_zero(self) -> None:
        run = transfer.CaseRun(
            label="GENEZ / FSS9",
            role="transfer case",
            snapshot=SNAPSHOT,
            analysis=ANALYSIS,
            curated_rows=0,
            wall_seconds=12.34,
        )
        row = transfer.comparison_row(run)
        assert row["case"] == "GENEZ / FSS9"
        assert row["gene"] == "GENEZ"
        assert row["targets"] == 11
        assert row["candidate_rows"] == 40
        assert row["approved_drugs"] == 7
        assert (row["drugs_rung_5"], row["drugs_rung_4"]) == (2, 1)
        assert (row["drugs_rung_3"], row["drugs_rung_2"]) == (0, 0)
        assert row["drugs_rung_1"] == 4
        assert (row["shortlist"], row["do_not"], row["curated_rows"]) == (3, 2, 0)
        assert (row["live_requests"], row["cached_replies"]) == (10, 13)
        assert row["wall_seconds"] == 12.3

    def test_a_case_this_run_did_not_execute_has_no_wall_clock(self) -> None:
        row = transfer.comparison_row(
            transfer.CaseRun("real", "real case", SNAPSHOT, ANALYSIS, curated_rows=5)
        )
        assert row["wall_seconds"] is None
        assert row["curated_rows"] == 5

    def test_rows_keep_the_order_they_were_given(self) -> None:
        runs = [
            transfer.CaseRun("first", "real case", SNAPSHOT, ANALYSIS),
            transfer.CaseRun("second", "transfer case", SNAPSHOT, ANALYSIS),
        ]
        assert [row["case"] for row in transfer.comparison_rows(runs)] == ["first", "second"]


# ── an uncurated card through the enrichment ─────────────────────────────────────────

CANDIDATES = (
    "drug_name\tdrug_id\ttarget_symbol\ttarget_role\tdirection_ids\tsource\t"
    "interaction_or_moa\taction_type\tmax_phase\tapproved\tfda_label\tpmids\t"
    "first_approval\tatc\n"
    "MADEUPICIN\tCHEMBL1\tGENEZ\tseed\tD1\tchembl\twidget binder\tINHIBITOR\t4\ttrue\t"
    "true\t\t1999\tX01\n"
)
TRIALS = (
    "nct_id\ttitle\tphase\toverall_status\tconditions\tinterventions\tstart_date\t"
    "study_type\tquery\n"
)
MECHLIT = "drug_name\tfamily\tterm\thits\tpmids\nMADEUPICIN\tmechanism\tinvented\t3\t\n"
PEDIATRIC = (
    "drug_name\tnct_id\ttitle\tphase\toverall_status\tconditions\tmin_age\tmax_age\t"
    "std_ages\tquery\n"
)


class TestUncuratedEnrichment:
    """A folder with no ``evidence.tsv`` and no ``decoys/`` grades on the automated rungs."""

    @pytest.fixture
    def folder(
        self, template: mechanism.MechanismCard, spec: transfer.TransferSpec, tmp_path: Path
    ) -> Path:
        out = tmp_path / "case"
        out.mkdir()
        card = transfer.transfer_card(template, spec, today="2099-01-01")
        (out / "mechanism.json").write_text(json.dumps(card), encoding="utf-8")
        (out / "drug_candidates.tsv").write_text(CANDIDATES, encoding="utf-8")
        (out / "trials.tsv").write_text(TRIALS, encoding="utf-8")
        (out / "drug_mechanism_literature.tsv").write_text(MECHLIT, encoding="utf-8")
        (out / "pediatric_trials.tsv").write_text(PEDIATRIC, encoding="utf-8")
        (out / "labels.json").write_text(
            json.dumps({"MADEUPICIN": {"has_label": True, "pediatric_use": False}}),
            encoding="utf-8",
        )
        return out

    def test_a_missing_evidence_file_reads_as_no_curated_rows(
        self, folder: Path, tmp_path: Path
    ) -> None:
        assert enrich.read_optional_tsv(folder / "evidence.tsv") == []
        result = enrich.run(
            folder / "mechanism.json",
            folder,
            analysis_path=tmp_path / "analysis.json",
            cache_dir=tmp_path / "cache",
            skip_live=True,
        )
        assert result.curated == 0
        assert result.analysis["curated_rows"] == 0
        assert (folder / "evidence_ladder.tsv").is_file()
        assert [row["curated_rung"] for row in result.ladder] == [None]
        assert [row["rung"] for row in result.ladder] == [1]

    def test_no_manifest_and_no_table_is_written_for_what_is_not_there(
        self, folder: Path, tmp_path: Path
    ) -> None:
        enrich.run(
            folder / "mechanism.json",
            folder,
            analysis_path=tmp_path / "analysis.json",
            cache_dir=tmp_path / "cache",
            skip_live=True,
        )
        assert not (folder / "evidence.provenance.json").exists()
        assert not (folder / "decoy_comparison.tsv").exists()
        manifest = json.loads((folder / "evidence_ladder.provenance.json").read_text())
        named = {entry.get("name") for entry in manifest["inputs"]}
        assert "track2.evidence" not in named
        assert "track2.drug_candidates" in named
