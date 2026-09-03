"""The seven dependency probes behind ``GET /api/health/dependencies``.

Each function here answers one question — "is this backend actually usable right now" —
by doing the cheapest real thing that proves it (a `SELECT 1`, a capped listing, one
Parquet row, a `/health` ping) and never raises: a failure becomes a `down` (or
`skipped`) result, not an exception. That is what lets :mod:`mva.viz.health` run all
seven concurrently, each under its own timeout budget (:mod:`mva.viz.health_budget`),
without a single misbehaving probe taking the whole response down with it.

The result vocabulary (:func:`~mva.viz.health_results.up` and friends), the per-check
metadata (:data:`~mva.viz.health_results.REGISTRY`) and the app's page names live in
:mod:`mva.viz.health_results` — split out purely to keep this module under the 400-line
cap, since it is otherwise one concern: seven independent probes.

Nothing here writes a secret into a result. ``endpoint`` strings are built by hand from
non-secret fields (host, port, database, bucket, URL) rather than by printing a settings
object whose ``__repr__`` was written for a human terminal, not a browser response.
"""

import httpx

from ..reads import access as reads_access
from ..warehouse import objects as objects_mod
from ..warehouse.objects import ObjectStore
from ..warehouse.postgres import ALIAS
from ..warehouse.reference import LINEAGE
from ..warehouse.settings import Postgres
from .health_results import DETAIL_LIMIT, degraded, down, failed, redact, skipped, up
from .proxy import UnreachableError as UpstreamUnreachableError
from .proxy import Upstream, base_url
from .queries.access import fetch

#: The two committed reference tables staged by ``mva.warehouse.reference`` — gnomAD
#: constraint and the ClinVar panel slice. Ingested once, never fetched live.
REFERENCE_TABLES = ("gnomad_constraint", "clinvar_panel")

#: Ensembl's own liveness endpoint — the one ``genestructure.py`` and
#: ``mva.pipeline.annotate_vep`` both depend on being reachable.
ENSEMBL_PING = "https://rest.ensembl.org/info/ping?content-type=application/json"


def _warehouse_remedy(settings: Postgres) -> str:
    if settings.missing:
        return f"Set {', '.join(settings.missing)} in .env (see .env.example), then retry."
    return (
        f"Check that PostgreSQL is reachable at {settings.host}:{settings.port} and that "
        f"{settings.database} accepts connections from this machine."
    )


# ── 1. viz-api ───────────────────────────────────────────────────────────────────────


def probe_viz_api(service: str, version: str) -> dict:
    """This process. Always up — the endpoint could not otherwise have answered."""
    return up(f"{service} v{version} answered this request")


# ── 2. warehouse ─────────────────────────────────────────────────────────────────────


def probe_warehouse(settings: Postgres) -> dict:
    """``SELECT 1``, then confirm both configured schemas actually exist.

    Two round trips through :func:`~mva.viz.queries.access.fetch` — the one seam every
    other viz test already replaces — rather than one hand-opened connection, so this
    check can be faked in tests exactly like the rest of the API's Postgres reads.
    """
    endpoint = settings.describe()  # already redacts the password
    try:
        fetch(settings, "SELECT 1")
        found = {
            row["schema_name"]
            for row in fetch(
                settings,
                f"SELECT schema_name FROM {ALIAS}.information_schema.schemata "
                "WHERE schema_name IN (?, ?)",
                [settings.schema, settings.result_schema],
            )
        }
    except Exception as error:
        return failed(error, _warehouse_remedy(settings), endpoint, secrets=(settings.password,))

    missing = [name for name in (settings.schema, settings.result_schema) if name not in found]
    if missing:
        return degraded(
            f"SELECT 1 answered; schema(s) missing: {', '.join(missing)}",
            f"Run the ingest that creates {', '.join(missing)} "
            "(`mva-warehouse vcf-ingest` / `stage`) against this database.",
            endpoint,
        )
    return up(
        f"SELECT 1 answered; schemas {settings.schema} + {settings.result_schema} present",
        endpoint,
    )


# ── 3. object-store ──────────────────────────────────────────────────────────────────


def _store_endpoint(store: ObjectStore) -> str:
    """``scheme://host/bucket`` — no access key, no secret."""
    scheme = "https" if store.use_ssl else "http"
    return f"{scheme}://{store.endpoint}/{store.bucket}"


def _reads_prefix(store: ObjectStore) -> str:
    """The read store's key prefix under ``store``'s bucket, e.g. ``reads``."""
    return reads_access.s3_root(store).removeprefix(f"s3://{store.bucket}/")


def probe_object_store(store: ObjectStore) -> dict:
    """List one capped prefix — never the whole bucket — through ``objects.listing``.

    ``objects.diagnose`` already turns the transport failure into cause-specific advice
    (tunnel vs. container vs. TLS mismatch); this reuses that text verbatim rather than
    writing a second version of it.
    """
    if store.missing:
        return skipped(
            f"S3 credentials not configured ({', '.join(store.missing)})",
            "Set S3_ENDPOINT, S3_ACCESS_KEY and S3_SECRET_KEY in .env to enable object "
            "storage checks.",
        )
    endpoint = _store_endpoint(store)
    prefix = _reads_prefix(store)
    secrets = (store.secret_key, store.access_key)
    try:
        keys = objects_mod.listing(store, prefix=prefix)
    except objects_mod.UnreachableError as error:
        text = redact(str(error), secrets)
        return down(text.splitlines()[0], text, endpoint)
    except Exception as error:
        return failed(
            error, "Unexpected object-store failure; check server logs.", endpoint, secrets
        )
    if not keys:
        return degraded(
            f"reached {endpoint} but found 0 objects under {prefix}/",
            f"Confirm S3_BUCKET and the read store's prefix ({prefix}) are correct — an "
            "empty listing on a live bucket usually means the wrong bucket or prefix.",
            endpoint,
        )
    return up(f"{len(keys)} object(s) listed under {prefix}/", endpoint)


# ── 4. parquet ───────────────────────────────────────────────────────────────────────


def probe_parquet(store: ObjectStore) -> dict:
    """Read one tiny, known-good Parquet object end to end through DuckDB ``httpfs``.

    Distinct from the object-store check: that one proves the bucket answers a listing.
    This one proves credentials, ``httpfs`` and the Parquet format actually decode — a
    listing can succeed on a session that a byte-range read then rejects. Always the
    8-row ``reads.runs`` dimension table, never the 272-shard read store or the
    5,012,204-row callset.
    """
    if store.missing:
        return skipped(
            f"S3 credentials not configured ({', '.join(store.missing)})",
            "Set S3_ENDPOINT, S3_ACCESS_KEY and S3_SECRET_KEY in .env to enable the "
            "Parquet read-path check.",
        )
    key = f"{_reads_prefix(store)}/runs.parquet"
    url = store.url(key)
    endpoint = url
    try:
        result = objects_mod.query(store, f"SELECT count(*) AS n FROM read_parquet('{url}')")
    except Exception as error:
        text = redact(objects_mod.diagnose(store, error), (store.secret_key, store.access_key))
        return down(text.splitlines()[0], text, endpoint)
    n = result.rows[0][0] if result.rows else 0
    return up(f"read {n} row(s) from {key} through httpfs", endpoint)


# ── 5. reads-api ─────────────────────────────────────────────────────────────────────


async def probe_reads_api(upstream: Upstream, timeout: float = 2.0) -> dict:  # noqa: ASYNC109
    """``GET /health`` on ``mva-reads-api``, through the same client the real proxy uses.

    No token: its ``/health`` needs none. Down here is never fatal to the rest of the
    app — only the Probes page's job monitor and ledger depend on it.

    ``timeout`` is this check's own budget, passed in by :mod:`mva.viz.health` so raising
    it in the environment actually gives the request longer. The caller's own
    ``asyncio.wait_for`` is the outer net; this is the client-level one, which is the only
    one that can come back with a *specific* remedy instead of "timed out".
    """
    endpoint = f"{base_url()}/health"
    try:
        reply = await upstream.request("GET", "/health", timeout=timeout)
    except UpstreamUnreachableError as error:
        return down(str(error), "Start `mva-reads-api` or check MVA_READS_API_URL.", endpoint)
    except Exception as error:
        return failed(error, "Unexpected reads-API failure; check server logs.", endpoint)
    if reply.status == 200:
        return up(f"GET /health -> 200 {reply.body}"[:DETAIL_LIMIT], endpoint)
    return down(
        f"GET /health -> {reply.status}",
        "mva-reads-api is reachable but unhealthy; check its own logs.",
        endpoint,
    )


# ── 6. ensembl ───────────────────────────────────────────────────────────────────────


def probe_ensembl(timeout: float = 2.0) -> dict:
    """Ensembl's own liveness ping, under this check's own budget.

    Down here costs only the gene-structure track and any new VEP annotation — nothing
    already resolved and stored in the warehouse depends on Ensembl being up right now.
    Ensembl is also the one dependency whose latency this project cannot tune, which is
    why its default budget is looser than a probe against our own machinery.
    """
    try:
        response = httpx.get(ENSEMBL_PING, timeout=timeout)
    except httpx.HTTPError as error:
        return down(
            str(error).splitlines()[0][:DETAIL_LIMIT],
            "Ensembl REST is unreachable from here; retry later or check network egress. "
            "Gene-structure tracks and new VEP annotation are unavailable until it recovers.",
            ENSEMBL_PING,
        )
    if response.status_code == 200:
        return up(f"GET /info/ping -> 200 {response.text.strip()}"[:DETAIL_LIMIT], ENSEMBL_PING)
    return down(
        f"GET /info/ping -> {response.status_code}",
        "Ensembl REST answered but not healthily; retry later.",
        ENSEMBL_PING,
    )


# ── 7. reference-snapshots ───────────────────────────────────────────────────────────


def _release(table: str) -> str:
    return LINEAGE.get(table, {}).get("source_version", "release unrecorded")


def probe_reference_snapshots(settings: Postgres) -> dict:
    """Not a live dependency: gnomAD and ClinVar were ingested, never fetched live here.

    Confirms the two committed reference tables exist and are non-empty, and states the
    release each was pulled from (:data:`mva.warehouse.reference.LINEAGE`) — no NCBI or
    Google Storage request is made.
    """
    schema = settings.schema
    endpoint = " + ".join(f"pg.{schema}.{table}" for table in REFERENCE_TABLES)
    try:
        present = {
            row["table_name"]
            for row in fetch(
                settings,
                f"SELECT table_name FROM {ALIAS}.information_schema.tables "
                "WHERE table_schema = ? AND table_name IN (?, ?)",
                [schema, *REFERENCE_TABLES],
            )
        }
    except Exception as error:
        return failed(error, _warehouse_remedy(settings), endpoint, secrets=(settings.password,))

    missing = [table for table in REFERENCE_TABLES if table not in present]
    if missing:
        return degraded(
            f"table(s) not ingested: {', '.join(missing)}",
            "Run `tools/build_reference_data.py` then `mva-warehouse stage`/`ingest` — see "
            "ressources/reference/README.md.",
            endpoint,
        )

    counts: dict[str, int] = {}
    for table in REFERENCE_TABLES:
        try:
            found = fetch(settings, f"SELECT count(*) AS n FROM {ALIAS}.{schema}.{table}")
        except Exception as error:
            return failed(
                error, _warehouse_remedy(settings), endpoint, secrets=(settings.password,)
            )
        counts[table] = int(found[0]["n"]) if found else 0

    empty = [table for table, n in counts.items() if not n]
    detail = "; ".join(
        f"{table} {counts[table]:,} rows ({_release(table)})" for table in REFERENCE_TABLES
    )
    if empty:
        return degraded(
            f"{detail} — empty: {', '.join(empty)}",
            f"Re-run ingestion for {', '.join(empty)}: a 0-row reference table usually means "
            "staging ran but ingest did not, or ran against the wrong file.",
            endpoint,
        )
    return up(detail, endpoint)


# ── endpoint, independent of outcome ─────────────────────────────────────────────────


def static_endpoint(check_id: str, settings: Postgres, store: ObjectStore) -> str | None:
    """Where a check targets, computed without running it.

    A probe only fills in ``endpoint`` on its own success/failure paths; a timeout or an
    exception :mod:`mva.viz.health`'s ``run_check`` catches on its behalf never reaches
    that code, and would otherwise report ``endpoint: null`` for a dependency whose
    address we knew perfectly well before we tried it. This is the fallback that keeps
    "timed out" as useful as "down": it still says *where* nothing answered.
    """
    if check_id == "warehouse":
        return settings.describe()
    if check_id == "object-store":
        return _store_endpoint(store)
    if check_id == "parquet":
        return store.url(f"{_reads_prefix(store)}/runs.parquet")
    if check_id == "reads-api":
        return f"{base_url()}/health"
    if check_id == "ensembl":
        return ENSEMBL_PING
    if check_id == "reference-snapshots":
        return " + ".join(f"pg.{settings.schema}.{table}" for table in REFERENCE_TABLES)
    return None  # viz-api probes nothing external
