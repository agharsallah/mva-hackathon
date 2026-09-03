"""One Ensembl REST call, with every failure stated rather than guessed around.

Extracted from :mod:`mva.viz.genestructure` when that module outgrew the project's
400-line limit. It is a bounded concern in its own right: *how this service talks to the
public Ensembl REST server, and what it does when the server says no*. Three callers share
it — the exon/domain fetch, the VEP position POST, and the gene-set builder's
symbol resolution — and each would otherwise repeat the same five failure branches.

**No retry loop here, on purpose.** These are request-scoped fetches behind a disk cache,
so the cheap recovery is the reader pressing refresh (or `?refresh=true`), and a retry only
lengthens the wait on an outage the browser should be *told* about. The batch **build
tools** are the deliberate exception and retry with their own bounded backoff, because one
transient 503 halfway through 23 genes would throw away 22 good replies; both sites say so.
Ensembl REST does answer 500 and 503 intermittently — observed live, recorded in
``docs/step-0/methodology/060``.
"""

from typing import Any

import httpx

#: The public Ensembl REST server. Keyless. The same host the panel annotation ran against.
ENSEMBL_BASE = "https://rest.ensembl.org"


class EnsemblError(RuntimeError):
    """Ensembl REST could not be reached or refused a request. Never faked around."""


def get(client: httpx.Client, base_url: str, path: str) -> Any:
    """A GET whose reply must be JSON."""
    return call(client, "GET", base_url, path, None)


def post(client: httpx.Client, base_url: str, path: str, payload: dict) -> Any:
    """A POST whose reply must be JSON."""
    return call(client, "POST", base_url, path, payload)


def call(client: httpx.Client, method: str, base_url: str, path: str, payload: dict | None) -> Any:
    """One REST call. Every failure becomes an :class:`EnsemblError` naming the URL.

    The URL is in the message because these paths are composed from ids the caller
    resolved, and "Ensembl said 400" without the path is unactionable.
    """
    url = f"{base_url.rstrip('/')}{path}"
    try:
        response = client.request(method, url, json=payload, headers={"Accept": "application/json"})
    except httpx.HTTPError as error:
        raise EnsemblError(f"{method} {url}: {type(error).__name__}: {error}") from error
    if response.status_code != 200:
        raise EnsemblError(f"{method} {url} -> {response.status_code}: {response.text[:200]}")
    try:
        return response.json()
    except ValueError as bad:
        raise EnsemblError(f"{method} {url}: reply was not JSON") from bad


def as_int(value: Any) -> int | None:
    """``int(value)`` or ``None`` — for a reply field that may be absent or a string.

    Ensembl returns coordinates and lengths as numbers today and has returned them as
    strings; a payload field typed ``number | null`` in the client contract must never
    carry ``"1050"``.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


#: Which Ensembl release each base URL last reported, so ``/info/data`` is asked once per
#: process and never on a cache hit. Ensembl cuts a release roughly quarterly, so a value
#: memoised for the lifetime of a server process cannot go meaningfully stale — and the
#: alternative, asking on every reply, would put an extra round trip on a route whose
#: whole point is that its answer is already on disk.
_RELEASES: dict[str, str | None] = {}


def release(base_url: str = ENSEMBL_BASE, *, client: httpx.Client | None = None) -> str | None:
    """The Ensembl release number ``GET /info/data`` reports, or ``None``.

    Recorded into the ``source`` line of every reply built from Ensembl, because "the gene
    record came from Ensembl" is not a provenance statement — Ensembl re-annotates, and an
    exon boundary from release 115 is a different fact from the same boundary in 116.

    A failure is ``None``, not an exception: not knowing the release must never turn a
    working payload into a 502. The reply is ``{"releases": [116]}`` — a list, because the
    server can host more than one; the highest is the one the other endpoints answer from.
    """
    if base_url in _RELEASES:
        return _RELEASES[base_url]
    own = client is None
    client = client or httpx.Client(timeout=10.0, follow_redirects=True)
    try:
        body = get(client, base_url, "/info/data")
        numbers = [str(value) for value in (body.get("releases") or []) if value is not None]
        found = max(numbers, key=lambda text: (len(text), text)) if numbers else None
    except (EnsemblError, AttributeError, TypeError):
        found = None
    finally:
        if own:
            client.close()
    _RELEASES[base_url] = found
    return found
