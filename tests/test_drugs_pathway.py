"""The pathway expansion rule: which pathways are kept, and what a target row then says.

The rule under test, restated: seeds are the card's union in card order; a pathway is kept
when its ``displayName`` matches the pattern; every human gene product in a kept pathway
becomes a ``pathway`` target unless it is already a seed. The pattern is a *parameter*, so
one of these tests passes a different one and watches the target set change — that is what
"case-agnostic" has to mean to be worth claiming.
"""

from __future__ import annotations

import re

from mva.drugs import mechanism
from mva.drugs.pathway import PATHWAY_PATTERN, expand, rule_text
from test_drugs_support import FIXTURES, FakeFetcher, fixture

CARD = mechanism.load(FIXTURES / "card.json")


def fetcher() -> FakeFetcher:
    return (
        FakeFetcher()
        .route("/data/mapping/UniProt/", fixture("reactome_pathways"))
        .route("/referenceEntities", fixture("reactome_participants"))
    )


class TestSeeds:
    def test_seeds_are_the_card_union_in_card_order(self) -> None:
        result = expand(CARD, fetcher())
        assert [t.symbol for t in result.seeds] == ["GENEA", "GENEB", "GENEC"]

    def test_a_seed_carries_every_direction_that_named_it(self) -> None:
        result = expand(CARD, fetcher())
        by_symbol = {t.symbol: t for t in result.seeds}
        assert by_symbol["GENEB"].direction_ids == ("X1", "X2")
        assert by_symbol["GENEC"].direction_ids == ("X2",)

    def test_only_the_card_gene_carries_the_uniprot(self) -> None:
        result = expand(CARD, fetcher())
        by_symbol = {t.symbol: t for t in result.seeds}
        assert by_symbol["GENEA"].uniprot == "P00001"
        assert by_symbol["GENEB"].uniprot is None


class TestExpansion:
    def test_only_pathways_matching_the_pattern_are_walked(self) -> None:
        result = expand(CARD, fetcher())
        kept = [p.display_name for p in result.pathways if p.matched]
        dropped = [p.display_name for p in result.pathways if not p.matched]
        assert kept == [
            "Widget assembly checkpoint signalling",
            "Kinetochore attachment of widgets",
        ]
        assert dropped == ["Unrelated metabolism of sprockets"]

    def test_a_dropped_pathway_costs_no_participants_request(self) -> None:
        got = fetcher()
        expand(CARD, got)
        # one mapping call + one participants call per kept pathway
        assert len(got.calls) == 3

    def test_a_pathway_member_that_is_already_a_seed_keeps_role_seed(self) -> None:
        result = expand(CARD, fetcher())
        # GENEB participates in both kept pathways and is also a seed.
        roles = {t.symbol: t.role for t in result.targets}
        assert roles["GENEB"] == "seed"
        assert roles["GENED"] == "pathway"

    def test_a_pathway_member_records_every_pathway_it_came_from(self) -> None:
        result = expand(CARD, fetcher())
        gened = next(t for t in result.members if t.symbol == "GENED")
        assert gened.pathways == ("R-HSA-000001", "R-HSA-000003")
        assert gened.direction_ids == ()

    def test_the_pattern_is_a_parameter_not_a_constant(self) -> None:
        narrow = expand(CARD, fetcher(), pattern=re.compile(r"kinetochore", re.IGNORECASE))
        assert sum(1 for p in narrow.pathways if p.matched) == 1

        none = expand(CARD, fetcher(), pattern=re.compile(r"zzz-no-such-word"))
        assert none.members == []
        assert len(none.targets) == 3  # seeds only

    def test_a_card_with_no_uniprot_skips_the_walk_entirely(self, tmp_path) -> None:
        import json

        raw = json.loads((FIXTURES / "card.json").read_text(encoding="utf-8"))
        raw["gene"].pop("uniprot")
        path = tmp_path / "no-uniprot.json"
        path.write_text(json.dumps(raw), encoding="utf-8")

        got = fetcher()
        result = expand(mechanism.load(path), got)
        assert got.calls == []
        assert result.members == []
        assert len(result.seeds) == 3

    def test_progress_lines_are_emitted_when_a_callback_is_given(self) -> None:
        lines: list[str] = []
        expand(CARD, fetcher(), progress=lines.append)
        assert any("seeds 3" in line for line in lines)
        assert any("kept 2/3 pathways" in line for line in lines)


class TestRuleText:
    def test_the_rule_names_the_pattern_it_was_run_with(self) -> None:
        text = rule_text(PATHWAY_PATTERN)
        assert PATHWAY_PATTERN.pattern in text
        assert "/data/mapping/UniProt/" in text
        assert "parameter" in text
