"""The roster parses, the four MVP lanes are on, and a bad card fails at load time.

The registry is the part of the zoo that transfers to the next case, so these tests pin its
behaviour rather than its content: the shipped ``models.toml`` is checked for the invariants
the plan depends on (four enabled MVP lanes, one catalogue-adjacent lane, no typed digests),
and the merge rules are checked against small rosters written into ``tmp_path``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mva.zoo import registry
from mva.zoo.types import Coverage

MVP_LANES = {"alphamissense", "spliceai", "esm1b", "revel"}

MINIMAL = """
[models.demo]
name = "Demo"
key = "demo"
version = "demo-1"
tier = 1
input_class = "missense"
source = "warehouse-column"
adapter = "warehouse_column"
params = { table = "t", column = "c" }
licence = "MIT"
licence_url = "https://example.invalid/licence"
non_commercial = false
catalogue_adjacent = false
pmid = ""
scope = "opt-a"
enabled = true
notes = "a fixture, not a model"
"""


def _roster(tmp_path: Path, body: str = MINIMAL) -> Path:
    path = tmp_path / "models.toml"
    path.write_text(body)
    return path


def _fragments(tmp_path: Path, **files: str) -> Path:
    directory = tmp_path / "models.d"
    directory.mkdir(exist_ok=True)
    for name, body in files.items():
        (directory / f"{name}.toml").write_text(body)
    return directory


# --- the shipped roster ----------------------------------------------------------------


def test_shipped_roster_loads() -> None:
    cards = registry.load()
    assert cards, "the shipped models.toml declares no models"
    for key, card in cards.items():
        assert card.key == key
        assert card.tier in (1, 2, 3)
        assert card.adapter in registry.ADAPTER_FOR_SOURCE[card.source]


def test_four_mvp_lanes_are_enabled() -> None:
    cards = registry.load()
    assert set(registry.enabled(cards)) == MVP_LANES
    assert set(registry.mvp(cards)) >= MVP_LANES


def test_enabled_lanes_cover_three_sources_and_one_adjacent() -> None:
    """The MVP is an agreement matrix, so the four lanes must not be one instrument."""
    enabled = registry.enabled(registry.load())
    assert {card.source for card in enabled.values()} == {"warehouse-column", "table", "vep-rest"}
    adjacent = [key for key, card in enabled.items() if card.catalogue_adjacent]
    assert adjacent == ["revel"], "exactly one catalogue-adjacent lane runs in the MVP"


def test_no_digest_is_typed_into_the_shared_roster() -> None:
    """A digest is measured by `tools/fetch_zoo_tables.py`, never written by hand."""
    cards = registry.load(registry.DEFAULT_MODELS_TOML, fragments_dir=None)
    for card in cards.values():
        assert not card.params.get("sha256"), f"{card.key}: models.toml carries a typed digest"


def test_every_card_round_trips_as_json() -> None:
    for card in registry.load().values():
        payload = json.loads(json.dumps(card.as_dict()))
        assert payload["key"] == card.key
        assert payload["ships"] == registry.SHIPS[card.source]
        assert set(payload) >= {"licence", "licence_url", "non_commercial", "tier", "params"}


# --- fragments -------------------------------------------------------------------------


def test_fragment_overrides_one_field_and_merges_params(tmp_path: Path) -> None:
    fragment = '[models.demo]\nenabled = false\nparams = { sha256 = "deadbeef" }\n'
    cards = registry.load(_roster(tmp_path), _fragments(tmp_path, demo=fragment))
    demo = cards["demo"]
    assert demo.enabled is False
    assert demo.params["sha256"] == "deadbeef"
    assert demo.params["table"] == "t", "params merge by key; the fragment must not wipe them"
    assert demo.name == "Demo"


def test_fragment_adds_a_new_model(tmp_path: Path) -> None:
    added = MINIMAL.replace("demo", "extra").replace("Demo", "Extra")
    cards = registry.load(_roster(tmp_path), _fragments(tmp_path, extra=added))
    assert set(cards) == {"demo", "extra"}


def test_two_fragments_claiming_one_key_is_an_error(tmp_path: Path) -> None:
    body = "[models.demo]\nenabled = false\n"
    fragments = _fragments(tmp_path, a_first=body, b_second=body)
    with pytest.raises(registry.RegistryError, match="two fragments"):
        registry.load(_roster(tmp_path), fragments)


def test_missing_fragments_dir_is_not_an_error(tmp_path: Path) -> None:
    cards = registry.load(_roster(tmp_path), tmp_path / "absent")
    assert set(cards) == {"demo"}


# --- validation ------------------------------------------------------------------------


def test_enabled_lane_without_a_required_param_is_rejected(tmp_path: Path) -> None:
    broken = MINIMAL.replace('params = { table = "t", column = "c" }', 'params = { table = "t" }')
    with pytest.raises(registry.RegistryError, match="column"):
        registry.load(_roster(tmp_path, broken), None)


def test_disabled_lane_may_be_a_stub(tmp_path: Path) -> None:
    stub = MINIMAL.replace('params = { table = "t", column = "c" }', "params = { }").replace(
        "enabled = true", "enabled = false"
    )
    assert registry.load(_roster(tmp_path, stub), None)["demo"].params == {}


def test_bad_tier_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(registry.RegistryError, match="tier"):
        registry.load(_roster(tmp_path, MINIMAL.replace("tier = 1", "tier = 4")), None)


def test_adapter_must_match_source(tmp_path: Path) -> None:
    mismatch = MINIMAL.replace('adapter = "warehouse_column"', 'adapter = "vep_rest"')
    with pytest.raises(registry.RegistryError, match="served by"):
        registry.load(_roster(tmp_path, mismatch), None)


def test_missing_field_names_itself(tmp_path: Path) -> None:
    without = MINIMAL.replace('licence = "MIT"\n', "")
    with pytest.raises(registry.RegistryError, match="licence"):
        registry.load(_roster(tmp_path, without), None)


def test_non_numeric_pmid_is_rejected(tmp_path: Path) -> None:
    faked = MINIMAL.replace('pmid = ""', 'pmid = "PMID: 123"')
    with pytest.raises(registry.RegistryError, match="pmid"):
        registry.load(_roster(tmp_path, faked), None)


def test_unknown_scope_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(registry.RegistryError, match="scope"):
        registry.load(
            _roster(tmp_path, MINIMAL.replace('scope = "opt-a"', 'scope = "later"')), None
        )


# --- generated artefacts ---------------------------------------------------------------


def test_write_cards_writes_one_json_per_model_plus_the_manifest(tmp_path: Path) -> None:
    cards = registry.load()
    written = registry.write_cards(cards, tmp_path / "cards")
    assert len(written) == len(cards) + 1
    for key in cards:
        payload = json.loads((tmp_path / "cards" / f"{key}.json").read_text())
        assert payload["key"] == key


def test_licence_manifest_lists_every_model() -> None:
    cards = registry.load()
    manifest = registry.licence_manifest(cards)
    for card in cards.values():
        assert card.name in manifest
        assert card.licence_url in manifest
        assert registry.SHIPS[card.source] in manifest
    assert f"{len(cards)} models declared" in manifest


def test_committed_cards_are_fresh(tmp_path: Path) -> None:
    """`docs/iteration4/cards/` is generated; a roster edit without a regenerate fails here."""
    committed = Path(__file__).resolve().parents[1] / "docs" / "iteration4" / "cards"
    cards = registry.load()
    registry.write_cards(cards, tmp_path / "cards")
    for name in [f"{key}.json" for key in cards] + ["licences.md"]:
        expected = (tmp_path / "cards" / name).read_text()
        assert (committed / name).read_text() == expected, (
            f'{name} is stale — rerun: uv run python -c "from mva.zoo import registry as r; '
            "r.write_cards(r.load(), 'docs/iteration4/cards')\""
        )


def test_card_with_coverage_attaches_the_measured_numbers() -> None:
    card = registry.load()["alphamissense"]
    coverage = Coverage(
        model="alphamissense",
        scored=9,
        total=20,
        by_consequence={"missense_variant": (9, 10), "stop_gained": (0, 10)},
    )
    payload = registry.card_with_coverage(card, coverage)
    assert payload["key"] == "alphamissense"
    assert payload["coverage"]["fraction"] == pytest.approx(0.45)
    assert payload["coverage"]["by_consequence"]["stop_gained"] == {"scored": 0, "total": 10}
    assert json.loads(json.dumps(payload))["coverage"]["scored"] == 9


def test_with_digest_does_not_mutate_the_card() -> None:
    card = registry.load()["esm1b"]
    before = card.params.get("sha256", "")
    stamped = registry.with_digest(card, "a" * 64)
    assert stamped.params["sha256"] == "a" * 64
    # The point is that stamping copies: the card the registry handed out is untouched,
    # whether it already carried a measured digest (it does once the fetch has run) or not.
    assert card.params.get("sha256", "") == before
    assert before != "a" * 64
    assert stamped.params["url"] == card.params["url"]
