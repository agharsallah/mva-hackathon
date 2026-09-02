"""The contract's vocabulary: what a check is called, what it powers, and how its result
is shaped — split out of :mod:`mva.viz.health_probes` so that module stays under the
400-line cap (`CLAUDE.md`'s module-size rule) and this one holds a single concern: the
static facts about the seven checks, and the small result-building vocabulary every probe
in :mod:`mva.viz.health_probes` uses instead of hand-rolling a dict.

A probe returns a *partial* result — ``{status, detail, remedy, endpoint}`` — via
:func:`up`, :func:`degraded`, :func:`down`, :func:`skipped` or :func:`failed`.
:mod:`mva.viz.health` fills in ``id``, ``name``, ``kind`` and ``powers`` from
:data:`REGISTRY`, and ``latency_ms`` from its own timer, so a probe never repeats its own
metadata or reinvents its own clock.
"""

from dataclasses import dataclass

#: The React app's page names, copied from ``app/src/app/modules/index.ts`` (nav order).
#: Used only for ``powers`` — which pages the front end shows as affected.
PAGES = (
    "Overview",
    "Genome",
    "Callset",
    "Panel",
    "Compare",
    "Reads",
    "Probes",
    "Science",
    "Provenance",
    "Catalog",
    "Search",
)

#: How much of a caught exception's message reaches the response body.
DETAIL_LIMIT = 200


@dataclass(frozen=True)
class Meta:
    """Static facts about one check — what the app calls it, and what breaks without it."""

    name: str
    kind: str  # "internal" | "upstream" | "third-party" | "snapshot"
    powers: tuple[str, ...]


#: One entry per check id in the contract, in the order the endpoint reports them.
REGISTRY: dict[str, Meta] = {
    "viz-api": Meta("Viz API", "internal", PAGES),
    "warehouse": Meta(
        "Postgres warehouse",
        "internal",
        (
            "Overview",
            "Genome",
            "Callset",
            "Panel",
            "Compare",
            "Catalog",
            "Provenance",
            "Science",
            "Search",
            "Probes",
        ),
    ),
    "object-store": Meta("Object store (MinIO/S3)", "internal", ("Reads",)),
    "parquet": Meta("Parquet read path", "internal", ("Reads",)),
    "reads-api": Meta("Reads API (mva-reads-api)", "upstream", ("Probes",)),
    "ensembl": Meta("Ensembl REST", "third-party", ("Panel",)),
    "reference-snapshots": Meta(
        "Reference snapshots (gnomAD, ClinVar)", "snapshot", ("Panel", "Compare")
    ),
}


def outcome(
    status: str, detail: str, remedy: str | None = None, endpoint: str | None = None
) -> dict:
    """The shape every probe returns. ``health.py`` adds the static metadata and timing."""
    return {"status": status, "detail": detail, "remedy": remedy, "endpoint": endpoint}


def up(detail: str, endpoint: str | None = None) -> dict:
    return outcome("up", detail, None, endpoint)


def degraded(detail: str, remedy: str, endpoint: str | None = None) -> dict:
    return outcome("degraded", detail, remedy, endpoint)


def down(detail: str, remedy: str, endpoint: str | None = None) -> dict:
    return outcome("down", detail, remedy, endpoint)


def skipped(detail: str, remedy: str | None = None, endpoint: str | None = None) -> dict:
    return outcome("skipped", detail, remedy, endpoint)


def redact(text: str, secrets: tuple[str, ...]) -> str:
    """Replace every occurrence of a non-empty secret with a marker, never the value.

    A defensive second line, not the only one: nothing in :mod:`mva.viz.health_probes` is
    *expected* to echo a password or access key back, but a driver's own exception text is
    not this project's code, and the hard rule ("no credential in any field") has to hold
    even if one someday does.
    """
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[redacted]")
    return text


def failed(
    error: Exception, remedy: str, endpoint: str | None = None, secrets: tuple[str, ...] = ()
) -> dict:
    """A caught exception, turned into a ``down`` result — never a stack trace."""
    text = str(error).splitlines()[0] if str(error) else type(error).__name__
    text, remedy = redact(text, secrets), redact(remedy, secrets)
    return down(text[:DETAIL_LIMIT], remedy, endpoint)
