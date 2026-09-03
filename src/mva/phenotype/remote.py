"""Two hosted phenotype rankers, used as independent second opinions.

The local ranking in :mod:`mva.phenotype.prioritise` is ours: our parse of the ontology,
our information content, our rollup. That makes it inspectable and it makes it *ours to
get wrong*. Two public services answer the same question by different routes, and running
all three turns one number into a concordance:

**Monarch semsim** (``api-v3.monarchinitiative.org``) is the closest thing to a hosted
Exomiser. It exposes ``phenodigm_score`` - the same PhenoDigm measure hiPHIVE is built on -
over the Phenio ontology, and Exomiser's own 2406+ phenotype bundles are generated with the
same semsimian engine. It is the same lineage, not a lookalike. Agreement here says our
information content and rollup are sound.

**Phen2Gene** (``phen2gene.wglab.org``) is a genuinely different algorithm - a
skewness-weighted aggregation over its own knowledge base rather than a graph similarity.
Agreement here says the *answer* is robust to the method, which is the stronger claim.

A third, AMELIE, is deliberately absent: every request to it timed out during research.
Adding a dependency that does not answer would make the agreement figure quietly
two-source while claiming three.

Every property that made :class:`mva.pipeline.annotate_vep.VepRestAnnotator` testable is
reproduced here on purpose, because it is the same problem:

* **Nothing raises.** A cross-check is corroboration, not the critical path. A service that
  is down, rate-limited or has changed its schema must cost the run its second opinion and
  nothing else, so every failure returns an empty :class:`RemoteRanking` carrying the
  reason. A run that died because a third-party API was rebooting would be the worst
  possible trade.
* **The rate limit is obeyed, not raced.** ``Retry-After`` is honoured verbatim; ``5xx``
  and timeouts back off exponentially; both are bounded.
* **The HTTP client and the clock are injected.** Tests hand in an
  ``httpx.MockTransport`` and a recording sleep, so retry and rate-limit paths are covered
  without a network and without wall-clock.

These services see only HPO term ids and gene symbols - public vocabulary, never a
genotype, never a coordinate, nothing derived from the delivered files. That is what makes
sending anything at all acceptable under the data agreement.
"""

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

import httpx

#: Monarch's semantic-similarity service.
MONARCH_BASE_URL = "https://api-v3.monarchinitiative.org"

#: Phen2Gene's public endpoint.
PHEN2GENE_BASE_URL = "https://phen2gene.wglab.org"

#: Phen2Gene's default weighting model: skewness-based, the one its paper benchmarks.
DEFAULT_WEIGHT_MODEL = "sk"

#: The semsim group to search. The service also carries mouse, rat, zebrafish and worm
#: genes; human-only is chosen deliberately, for the same reason the local ranking is
#: human-only - the published optimisation study measures 82.8% top-10 for human
#: associations against 66.6% for the cross-species default.
HUMAN_GENES = "Human Genes"

#: The result ceiling ``/search`` enforces. Asking for more silently returns this many, so
#: it is clamped here and the caller is told the ranking is a window, not a full list.
MONARCH_MAX_RESULTS = 50

#: Seconds to wait on a 429 that arrives without a usable ``Retry-After``.
DEFAULT_COOLDOWN = 2.0


@dataclass(frozen=True)
class RemoteGene:
    """One gene as a hosted service ranked it."""

    symbol: str
    rank: int
    score: float


@dataclass(frozen=True)
class RemoteRanking:
    """What one service said, or why it said nothing.

    ``error`` being set is a normal outcome, not an exception path. The report prints it
    next to the missing column so a blank cross-check reads as "the service was
    unreachable" rather than as "the service disagreed".
    """

    source: str
    genes: tuple[RemoteGene, ...] = ()
    error: str | None = None
    #: Echoed back so a stored result names the exact query that produced it.
    terms: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return self.error is None

    def __len__(self) -> int:
        return len(self.genes)

    def rank_of(self, symbol: str) -> int | None:
        """Where this service placed a gene, or ``None`` if it did not return it."""
        wanted = symbol.upper()
        return next((gene.rank for gene in self.genes if gene.symbol == wanted), None)


class RemoteClient:
    """Shared transport: retries, backoff, an injected clock, and no exceptions escaping."""

    def __init__(
        self,
        *,
        base_url: str,
        client: httpx.Client | None = None,
        timeout: float = 30.0,
        max_attempts: int = 4,
        backoff: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.max_attempts = max_attempts
        self.backoff = backoff
        self.sleep = sleep
        self._owns_client = client is None
        self.client = client or httpx.Client(timeout=timeout)
        self.requests = 0

    def request(self, method: str, path: str, **kwargs: Any) -> tuple[Any | None, str | None]:
        """One call. Returns ``(payload, error)`` - never both, never an exception."""
        url = f"{self.base_url}{path}"
        headers = {"Accept": "application/json"}
        last = "no attempt was made"
        for attempt in range(self.max_attempts):
            try:
                self.requests += 1
                response = self.client.request(method, url, headers=headers, **kwargs)
            except httpx.HTTPError as error:  # timeout, DNS, connection reset
                last = f"{type(error).__name__}: {error}"
                self.sleep(self._backoff(attempt))
                continue
            if response.status_code == 200:
                try:
                    return response.json(), None
                except ValueError as error:
                    # A 200 carrying HTML is what a captive portal or an error page looks
                    # like. Retrying cannot fix it, so report rather than spin.
                    return None, f"{url} returned unparseable JSON: {error}"
            if response.status_code == 429:
                self.sleep(_retry_after(response, self._backoff(attempt)))
                last = "429 rate limited"
                continue
            if response.status_code >= 500:
                self.sleep(self._backoff(attempt))
                last = f"{response.status_code} server error"
                continue
            return None, f"{method} {url} -> {response.status_code}: {response.text[:200]}"
        return None, f"{method} {url} gave up after {self.max_attempts} attempts ({last})"

    def _backoff(self, attempt: int) -> float:
        return self.backoff * float(2**attempt)

    def close(self) -> None:
        """Close the HTTP client, but only the one we created."""
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> "RemoteClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def phen2gene(
    terms: Sequence[str],
    *,
    client: RemoteClient | None = None,
    weight_model: str = DEFAULT_WEIGHT_MODEL,
    limit: int | None = None,
) -> RemoteRanking:
    """Rank genes through Phen2Gene's public API.

    The service takes the term list as one semicolon-joined query parameter and answers
    with ``{"results": [{"Gene", "Rank", "Score", "Status"}, ...], "errors": [...]}``.
    Rank and score arrive as **strings**; they are converted here so no caller has to
    remember that a rank is not a number until it is parsed.
    """
    owned = client is None
    transport = client or RemoteClient(base_url=PHEN2GENE_BASE_URL)
    try:
        payload, error = transport.request(
            "GET",
            "/api",
            params={"HPO_list": ";".join(terms), "weight_model": weight_model},
        )
    finally:
        if owned:
            transport.close()

    if error is not None:
        return RemoteRanking("phen2gene", error=error, terms=tuple(terms))
    if not isinstance(payload, dict):
        return RemoteRanking("phen2gene", error="reply was not an object", terms=tuple(terms))

    genes: list[RemoteGene] = []
    for item in payload.get("results") or ():
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("Gene") or "").upper()
        if not symbol:
            continue
        genes.append(
            RemoteGene(
                symbol, _as_int(item.get("Rank"), len(genes) + 1), _as_float(item.get("Score"))
            )
        )
    if limit is not None:
        genes = genes[:limit]
    return RemoteRanking("phen2gene", tuple(genes), None, tuple(terms))


def monarch_semsim(
    terms: Sequence[str],
    *,
    client: RemoteClient | None = None,
    limit: int = MONARCH_MAX_RESULTS,
    group: str = HUMAN_GENES,
) -> RemoteRanking:
    """Rank human genes through Monarch's semantic-similarity search.

    ``POST /v3/api/semsim/search`` with a termset and a group, which is the endpoint that
    actually answers. Its sibling ``multicompare`` looks like the better fit - it would take
    our own candidate list rather than searching the whole corpus - but it requires each
    object set to carry its own phenotype list, which is precisely the thing we are asking
    the service for, and it answers 500 when handed empty ones.

    The service caps results, so this is a **top-N** ranking rather than a full one. A gene
    it does not return has not been placed last; it simply fell outside the window, which
    is why :meth:`RemoteRanking.rank_of` answers ``None`` rather than a large number.

    Scores are Phenodigm-derived and unnormalised, so they are comparable **within** one
    reply and meaningless across services. Only the ordering is used.
    """
    owned = client is None
    transport = client or RemoteClient(base_url=MONARCH_BASE_URL)
    try:
        payload, error = transport.request(
            "POST",
            "/v3/api/semsim/search",
            json={
                "termset": list(terms),
                "group": group,
                "limit": min(limit, MONARCH_MAX_RESULTS),
            },
        )
    finally:
        if owned:
            transport.close()

    if error is not None:
        return RemoteRanking("monarch-semsim", error=error, terms=tuple(terms))

    scored = _monarch_scores(payload)
    genes = tuple(
        RemoteGene(symbol, index, score) for index, (symbol, score) in enumerate(scored, start=1)
    )
    return RemoteRanking("monarch-semsim", genes, None, tuple(terms))


def _monarch_scores(payload: Any) -> list[tuple[str, float]]:
    """Pull ``(symbol, score)`` pairs out of a semsim reply, in the order it returned them.

    The service answers with a bare list of ``{subject: {...}, score}`` objects, but has
    also been seen wrapping it under ``items``. Both are accepted rather than pinned,
    because a cross-check that breaks on a minor schema change costs a second opinion for
    no safety gain. The order is the service's own ranking and is preserved - re-sorting on
    a score whose scale we do not own would be inventing a ranking rather than reading one.
    """
    if isinstance(payload, dict):
        for key in ("items", "results", "matches"):
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break
    if not isinstance(payload, list):
        return []

    out: list[tuple[str, float]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        subject = item.get("subject")
        symbol = ""
        if isinstance(subject, dict):
            symbol = str(subject.get("symbol") or subject.get("name") or "")
        symbol = symbol or str(item.get("symbol") or "")
        if not symbol:
            continue
        out.append((symbol.upper(), _as_float(item.get("score"))))
    return out


def _retry_after(response: httpx.Response, fallback: float) -> float:
    """Seconds to wait, from the header when the server sent a usable one."""
    raw = response.headers.get("Retry-After", "")
    try:
        return max(0.0, float(raw))
    except ValueError:
        return fallback


def _as_int(value: object, fallback: int) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return fallback


def _as_float(value: object) -> float:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return 0.0
