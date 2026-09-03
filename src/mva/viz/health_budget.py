"""How long each dependency probe is allowed to take, and where that number comes from.

``GET /api/health/dependencies`` used to give all seven probes the same 2-second budget.
That is right for the cheap ones — this process answering itself, a ``/health`` ping on a
neighbouring service — and wrong for the ones that do real work against a remote host:

* the **warehouse** probe opens a Postgres connection over the network and issues two
  round trips (``SELECT 1``, then an ``information_schema`` lookup); on a cold pool
  against a hosted database that alone can exceed 2 s and be reported as ``down`` while
  the database is merely slow to greet;
* the **reference snapshots** probe adds two ``count(*)`` reads on top of that, over
  tables with millions of rows;
* the **object store** and **parquet** probes cross an SSH tunnel or a WAN hop to MinIO,
  and the parquet one additionally decodes a footer through DuckDB ``httpfs``.

A false ``down`` is worse than a slow page: it sends a developer to fix a service that
was never broken. So the budget is per check, defaults are set from what each probe
actually does, and both the default and the per-check values are configurable from the
environment — a tunnel adds latency this repo cannot predict.

Two knobs, resolved by :func:`mva.warehouse.settings.setting` (real environment first,
then the nearest ``.env``):

``MVA_HEALTH_TIMEOUT``
    A floor, in seconds, applied to every check. One knob for the common case — "this
    deployment is behind a slow tunnel, give everything at least 20 s" — without naming
    seven ids. It only ever raises a budget, never lowers one.

``MVA_HEALTH_TIMEOUTS``
    Exact per-check values, ``id=seconds`` separated by commas — e.g.
    ``warehouse=20,object-store=12``. Ids are the contract's check ids. A value here wins
    over both the default and the floor, in either direction.

A malformed value raises rather than being ignored. A timeout typo would otherwise show
up as a mysteriously flapping health card weeks later; failing at app construction with
the offending token named is the cheaper failure.
"""

from ..warehouse.settings import setting
from .health_results import REGISTRY

#: Budget for a check with no entry in :data:`BUDGETS` — i.e. one the API reports that this
#: table does not know about yet.
DEFAULT_TIMEOUT = 2.0

#: Per-check defaults, in seconds, keyed by the contract's check id. Set from what the
#: probe does, not from taste: a two-round-trip database greet, an S3 hop and a Parquet
#: footer decode are not the same cost as pinging a process on localhost.
BUDGETS: dict[str, float] = {
    "viz-api": 2.0,  # this process; it has already answered by the time we time it
    "warehouse": 12.0,  # connect + SELECT 1 + information_schema, over the network
    "object-store": 10.0,  # one capped listing, possibly through an SSH tunnel
    "parquet": 15.0,  # the listing's cost plus an httpfs byte-range read and a decode
    "reads-api": 4.0,  # GET /health on a neighbouring process
    "ensembl": 6.0,  # a third party we do not run and cannot tune
    "reference-snapshots": 15.0,  # table lookup plus two count(*) over millions of rows
}

#: Nothing may sit on the request path longer than this, whatever the environment says.
#: The board fetches on page load; a 10-minute "budget" would hang the page, not measure it.
MAX_TIMEOUT = 60.0

#: The two environment knobs. See the module docstring for their syntax.
ENV_DEFAULT = "MVA_HEALTH_TIMEOUT"
ENV_OVERRIDES = "MVA_HEALTH_TIMEOUTS"

#: How much of a check's budget is left for the probe's *own* client timeout. A probe that
#: times out itself returns a `down` result with its own remedy ("start mva-reads-api");
#: the orchestrator's generic net returns "timed out after Ns" with no advice. So the inner
#: client is given slightly less than the outer wait, and the useful message wins the race.
INNER_SLACK = 0.25


def parse_seconds(key: str, text: str) -> float:
    """One positive, finite number of seconds, or a :class:`ValueError` naming the key."""
    try:
        value = float(text)
    except ValueError:
        raise ValueError(f"{key}: {text!r} is not a number of seconds") from None
    if not 0 < value <= MAX_TIMEOUT:
        raise ValueError(f"{key}: {value} s is outside (0, {MAX_TIMEOUT}] s")
    return value


def parse_overrides(text: str) -> dict[str, float]:
    """``"warehouse=20,object-store=12"`` → ``{"warehouse": 20.0, "object-store": 12.0}``.

    Unknown ids raise: silently dropping ``warehosue=20`` would leave the operator
    believing they had raised a budget they had not.
    """
    overrides: dict[str, float] = {}
    for token in (part.strip() for part in text.split(",")):
        if not token:
            continue
        check_id, _, raw = token.partition("=")
        check_id = check_id.strip()
        if not _:
            raise ValueError(f"{ENV_OVERRIDES}: {token!r} is not `id=seconds`")
        if check_id not in REGISTRY:
            raise ValueError(
                f"{ENV_OVERRIDES}: unknown check id {check_id!r} — valid ids: {', '.join(REGISTRY)}"
            )
        overrides[check_id] = parse_seconds(f"{ENV_OVERRIDES}[{check_id}]", raw)
    return overrides


def budgets() -> dict[str, float]:
    """Every check's timeout in seconds, environment applied, one entry per check id.

    Precedence, narrowest first: an ``MVA_HEALTH_TIMEOUTS`` entry for that id, else the
    :data:`BUDGETS` default raised to the ``MVA_HEALTH_TIMEOUT`` floor if one is set.
    """
    configured_floor = setting(ENV_DEFAULT)
    floor = parse_seconds(ENV_DEFAULT, configured_floor) if configured_floor else 0.0
    overrides = parse_overrides(setting(ENV_OVERRIDES))
    resolved: dict[str, float] = {}
    for check_id in REGISTRY:
        default = max(BUDGETS.get(check_id, DEFAULT_TIMEOUT), floor)
        resolved[check_id] = overrides.get(check_id, default)
    return resolved


def timeout_for(check_id: str, resolved: dict[str, float]) -> float:
    """One check's budget out of :func:`budgets`, with a default for an unknown id.

    ``run_check`` is called with ids from the registry, but a caller assembling a subset
    (a per-service re-probe) must never crash on an id this table has not heard of.
    """
    return resolved.get(check_id, DEFAULT_TIMEOUT)


def inner_timeout(budget: float) -> float:
    """The client timeout a probe should use inside a check whose budget is ``budget``."""
    return max(budget - INNER_SLACK, INNER_SLACK)
