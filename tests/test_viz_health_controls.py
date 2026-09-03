"""The Status page's three controls, on the API side.

`test_viz_health.py` owns the seven probes and the overall rule. This module owns what
was added so a developer can *drive* the board instead of only reading it:

* **per-check timeout budgets** (`mva.viz.health_budget`) — the defaults, the
  `MVA_HEALTH_TIMEOUT` floor, the `MVA_HEALTH_TIMEOUTS` per-check overrides, and the
  refusal to accept a value that would silently do nothing;
* **`only=<id>`** — re-probe one service and serve the other six from cache, which is
  what the per-card re-probe button costs;
* **the per-check cache** — each row carries its own `checked_at`, so a partial re-probe
  never has to pretend the rows it did not touch were measured just now.

The fakes come from `test_viz_health` rather than being written twice: these tests are
about orchestration, and orchestration has to be observed through the same seams.
"""

import pytest

from mva.viz import health, health_budget, health_probes
from mva.viz.health_results import REGISTRY
from test_viz_health import SETTINGS, STORE, Fake, client, healthy_fetch

CHECK_IDS = list(REGISTRY)


def counting(monkeypatch, name: str, result: dict) -> list[int]:
    """Replace one probe with a counter, so "was it re-probed" is a number, not a guess."""
    calls = [0]

    def probe(*args, **kwargs):
        calls[0] += 1
        return result

    monkeypatch.setattr(health_probes, name, probe)
    return calls


def board(running, **params) -> dict:
    response = running.get("/api/health/dependencies", params=params)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def by_id(data: dict) -> dict:
    return {check["id"]: check for check in data["checks"]}


# ── budgets ──────────────────────────────────────────────────────────────────────────


def test_the_slow_probes_get_a_bigger_budget_than_the_cheap_ones():
    """The point of the change: a WAN Postgres greet is not a localhost ping."""
    resolved = health_budget.budgets()
    assert set(resolved) == set(CHECK_IDS)
    for slow in ("warehouse", "object-store", "parquet", "reference-snapshots"):
        assert resolved[slow] > resolved["viz-api"], slow


def test_the_floor_raises_every_budget_but_never_lowers_one(monkeypatch):
    monkeypatch.setenv("MVA_HEALTH_TIMEOUT", "5")
    monkeypatch.delenv("MVA_HEALTH_TIMEOUTS", raising=False)
    resolved = health_budget.budgets()
    assert resolved["viz-api"] == 5.0  # raised from its 2 s default
    assert resolved["parquet"] == health_budget.BUDGETS["parquet"]  # already above the floor


def test_a_per_check_override_wins_over_the_default_and_the_floor(monkeypatch):
    monkeypatch.setenv("MVA_HEALTH_TIMEOUT", "20")
    monkeypatch.setenv("MVA_HEALTH_TIMEOUTS", "warehouse=30,ensembl=3")
    resolved = health_budget.budgets()
    assert resolved["warehouse"] == 30.0
    assert resolved["ensembl"] == 3.0  # below the floor, on purpose, because it was named


@pytest.mark.parametrize(
    "value",
    ["warehouse=abc", "warehouse", "warehosue=20", "warehouse=0", "warehouse=99999"],
)
def test_a_malformed_or_useless_timeout_setting_is_refused_not_ignored(value):
    """A typo that quietly changed nothing would surface weeks later as a flapping card."""
    with pytest.raises(ValueError):
        health_budget.parse_overrides(value)


def test_the_inner_client_timeout_stays_under_the_outer_budget():
    """So the probe's own specific remedy wins the race against the generic timeout."""
    assert health_budget.inner_timeout(4.0) < 4.0
    assert health_budget.inner_timeout(0.1) > 0


def test_every_row_reports_the_budget_it_was_measured_against(tmp_path, monkeypatch):
    checks = by_id(board(client(tmp_path, monkeypatch)))
    for check_id, check in checks.items():
        assert check["timeout_ms"] == round(health_budget.BUDGETS[check_id] * 1000), check_id


# ── only=<id> ────────────────────────────────────────────────────────────────────────


def test_only_reprobes_the_named_check_and_leaves_the_others_alone(tmp_path, monkeypatch):
    running = client(tmp_path, monkeypatch)
    ensembl = counting(monkeypatch, "probe_ensembl", health_probes.up("ping"))
    warehouse = counting(monkeypatch, "probe_warehouse", health_probes.up("SELECT 1 answered"))

    board(running)  # first load probes everything once
    assert (warehouse[0], ensembl[0]) == (1, 1)

    data = board(running, only="warehouse", refresh="true")
    assert (warehouse[0], ensembl[0]) == (2, 1)  # only the warehouse was probed again
    assert [c["id"] for c in data["checks"]] == CHECK_IDS  # the whole board still comes back


def test_only_accepts_both_repeated_and_comma_separated_ids(tmp_path, monkeypatch):
    running = client(tmp_path, monkeypatch)
    warehouse = counting(monkeypatch, "probe_warehouse", health_probes.up("ok"))
    ensembl = counting(monkeypatch, "probe_ensembl", health_probes.up("ping"))
    board(running)

    running.get("/api/health/dependencies?only=warehouse&only=ensembl&refresh=true")
    assert (warehouse[0], ensembl[0]) == (2, 2)

    running.get("/api/health/dependencies?only=warehouse,ensembl&refresh=true")
    assert (warehouse[0], ensembl[0]) == (3, 3)


def test_an_unknown_check_id_is_a_400_that_names_the_valid_ids(tmp_path, monkeypatch):
    """A bad request is the caller's fault — the only 4xx on an endpoint that never 5xxs."""
    response = client(tmp_path, monkeypatch).get("/api/health/dependencies?only=warehosue")
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "warehosue" in detail
    assert "warehouse" in detail


def test_the_first_request_of_all_can_name_only_and_still_get_every_check(tmp_path, monkeypatch):
    """Nothing is cached yet, so the board must probe the rest rather than omit them."""
    data = board(client(tmp_path, monkeypatch), only="warehouse")
    assert [c["id"] for c in data["checks"]] == CHECK_IDS
    assert data["overall"] == "up"


def test_a_partial_reprobe_recomputes_overall_from_the_whole_board(tmp_path, monkeypatch):
    """Re-probing a healthy check must not erase a down one measured a minute ago."""
    running = client(tmp_path, monkeypatch, upstream=Fake(503, {"detail": "starting up"}))
    assert board(running)["overall"] == "degraded"
    data = board(running, only="warehouse", refresh="true")
    assert by_id(data)["reads-api"]["status"] == "down"
    assert data["overall"] == "degraded"


# ── the per-check cache ──────────────────────────────────────────────────────────────


def test_a_second_load_inside_the_ttl_reprobes_nothing(tmp_path, monkeypatch):
    running = client(tmp_path, monkeypatch)
    warehouse = counting(monkeypatch, "probe_warehouse", health_probes.up("ok"))
    board(running)
    board(running)
    assert warehouse[0] == 1


def test_refresh_bypasses_the_cache_for_every_check(tmp_path, monkeypatch):
    running = client(tmp_path, monkeypatch)
    warehouse = counting(monkeypatch, "probe_warehouse", health_probes.up("ok"))
    board(running)
    board(running, refresh="true")
    assert warehouse[0] == 2


def test_each_row_carries_its_own_checked_at(tmp_path, monkeypatch):
    """The reason the cache is per check: staleness is per row, so it is stated per row."""
    checks = by_id(board(client(tmp_path, monkeypatch)))
    for check_id, check in checks.items():
        assert check["checked_at"], check_id


def test_probe_all_ignores_any_cache_and_measures_everything(monkeypatch):
    monkeypatch.setattr(health_probes, "fetch", healthy_fetch)
    monkeypatch.setattr(health_probes.objects_mod, "listing", lambda store, prefix="": ["a"])
    warehouse = counting(monkeypatch, "probe_warehouse", health_probes.up("ok"))
    parquet = counting(monkeypatch, "probe_parquet", health_probes.up("ok"))
    ensembl = counting(monkeypatch, "probe_ensembl", health_probes.up("ping"))
    import asyncio

    data = asyncio.run(health.probe_all(SETTINGS, STORE, Fake(200, {"ok": True})))
    assert [c["id"] for c in data["checks"]] == CHECK_IDS
    assert (warehouse[0], parquet[0], ensembl[0]) == (1, 1, 1)
