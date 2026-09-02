"""The :class:`~mva.pipeline.annotation.Annotator` port, backed by Ensembl VEP REST.

``docs/notes/annotation-as-a-port.md`` left the backend open deliberately: an offline VEP
cache is right for a genome-wide run and wrong for annotating a few hundred panel alleles
today. This is the *today* backend — no multi-gigabyte download, no container, one HTTPS
call per 200 alleles against the same VEP the offline cache is built from.

The class is a swap, not a rewrite: it satisfies the existing protocol, so ranking code
written against ``DictAnnotator`` runs unchanged.

Three properties are load-bearing and each is tested without a network:

* **Nothing raises.** The protocol says an annotator returns ``UNKNOWN`` rather than
  failing, because a run that dies on one bad allele loses every good one before it.
  :meth:`VepRestAnnotator.annotate` honours that; :meth:`annotate_many` is the batch form
  and reports the misses as empty records.
* **The server's rate limit is obeyed, not raced.** A ``429`` carries ``Retry-After`` and
  is respected verbatim; a ``5xx`` or a timeout backs off exponentially; both are bounded.
* **The HTTP client is injected.** Tests hand in an ``httpx.MockTransport``; the sleep
  function is injected too, so a retry test costs no wall-clock.
"""

import time
from collections.abc import Iterable, Sequence

import httpx

from .annotation import UNKNOWN, Annotation
from .variant import Variant
from .vep_response import VepRecord, parse, query_line

#: The public Ensembl REST server. It serves GRCh38 by default — confirmed live, not
#: assumed: ``/info/assembly/homo_sapiens`` reports ``default_coord_system_version:
#: GRCh38``. GRCh37 lives on a *different host* (``grch37.rest.ensembl.org``), so there is
#: no assembly parameter to get wrong here, only a URL.
DEFAULT_BASE_URL = "https://rest.ensembl.org"

#: The region endpoint's documented POST ceiling. Exceeding it is rejected wholesale, so
#: the batcher clamps rather than trusting the caller.
MAX_BATCH = 200

#: Response fields we ask for beyond the default. ``af_gnomadg``/``af_gnomade`` are what
#: put a population frequency in the reply at all — without them ``colocated_variants``
#: carries identifiers and no numbers, and the ranker's rarity signal is empty.
QUERY_PARAMS = {
    "af_gnomadg": 1,  # gnomAD genomes AF, per genetic-ancestry group
    "af_gnomade": 1,  # gnomAD exomes AF, the fallback where genomes are absent
    "variant_class": 1,  # SNV / deletion / insertion, for reading the record back
    "canonical": 1,  # marks the representative transcript, used to break ties
    "hgvs": 1,  # protein-level notation, the form a clinician recognises
}

#: How long to wait when a 429 arrives without a ``Retry-After`` header.
DEFAULT_COOLDOWN = 2.0


class VepError(RuntimeError):
    """The REST server refused a request in a way retrying cannot fix."""


def batches(items: Sequence, size: int = MAX_BATCH) -> list[Sequence]:
    """Split ``items`` into chunks of at most ``size``, clamped to :data:`MAX_BATCH`."""
    if size < 1:
        raise ValueError(f"batch size must be positive; got {size}")
    step = min(size, MAX_BATCH)
    return [items[start : start + step] for start in range(0, len(items), step)]


class VepRestAnnotator:
    """Annotate variants through Ensembl's VEP REST service.

    ``genes`` is the panel's symbol set, used only to break ties where a position falls in
    two overlapping genes. Leaving it empty is valid and costs nothing but tie quality.
    """

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        genes: Iterable[str] = (),
        client: httpx.Client | None = None,
        batch_size: int = MAX_BATCH,
        timeout: float = 60.0,
        max_attempts: int = 5,
        backoff: float = 1.0,
        sleep=time.sleep,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.genes = frozenset(genes)
        self.batch_size = min(batch_size, MAX_BATCH)
        self.max_attempts = max_attempts
        self.backoff = backoff
        self.sleep = sleep
        self._owns_client = client is None
        self.client = client or httpx.Client(timeout=timeout)
        self._cache: dict[Variant, Annotation] = {}
        self.requests = 0

    # ── the port ─────────────────────────────────────────────────────────────────────

    def annotate(self, variant: Variant) -> Annotation:
        """Describe one variant, returning ``UNKNOWN`` rather than raising."""
        if variant not in self._cache:
            try:
                found = self.annotate_many([variant])
            except (VepError, httpx.HTTPError):
                return UNKNOWN
            self._cache[variant] = found[0].annotation if found else UNKNOWN
        return self._cache[variant]

    def annotate_many(self, variants: Sequence[Variant]) -> list[VepRecord]:
        """Annotate a whole list, one request per :data:`MAX_BATCH` alleles.

        Returns one record per input, in input order. An allele the server had nothing to
        say about comes back as an empty :class:`~mva.pipeline.vep_response.VepRecord`
        rather than being dropped, so the caller's row count never silently shrinks.
        """
        found: dict[str, dict] = {}
        for chunk in batches(list(variants), self.batch_size):
            for item in self._post_batch(chunk):
                key = item.get("input")
                if key:
                    found[key] = item
        records = []
        for variant in variants:
            match = found.get(query_line(variant))
            records.append(
                parse(match, variant, self.genes) if match else VepRecord(variant=variant)
            )
        return records

    # ── transport ────────────────────────────────────────────────────────────────────

    def version(self) -> dict[str, str]:
        """What produced the annotations: the Ensembl release and the assembly.

        Read from the server rather than hard-coded, because it is the one fact that
        makes a stored annotation reproducible — the same query against release 117 can
        legitimately return a different frequency.
        """
        software = self._get("/info/software") or {}
        assembly = self._get("/info/assembly/homo_sapiens") or {}
        return {
            "release": str(software.get("release", "unknown")),
            "assembly": str(assembly.get("default_coord_system_version", "unknown")),
            "accession": str(assembly.get("assembly_accession", "")),
        }

    def _post_batch(self, chunk: Sequence[Variant]) -> list[dict]:
        payload = {"variants": [query_line(variant) for variant in chunk], **QUERY_PARAMS}
        body = self._request("POST", "/vep/homo_sapiens/region", json=payload)
        # A single-variant error reply is a dict, not a list. Treating it as a list would
        # iterate its keys and parse strings as results.
        return body if isinstance(body, list) else []

    def _get(self, path: str):
        return self._request("GET", path)

    def _request(self, method: str, path: str, json: dict | None = None):
        """One REST call with the retry policy applied. Raises :class:`VepError` if spent."""
        url = f"{self.base_url}{path}"
        headers = {"Accept": "application/json"}
        last = ""
        for attempt in range(self.max_attempts):
            try:
                self.requests += 1
                response = self.client.request(method, url, json=json, headers=headers)
            except httpx.HTTPError as error:  # timeout, DNS, connection reset
                last = f"{type(error).__name__}: {error}"
                self.sleep(self._backoff(attempt))
                continue
            if response.status_code == 200:
                return response.json()
            if response.status_code == 429:
                # The server tells us exactly how long to wait; guessing shorter is how a
                # client gets its key throttled for the rest of the hour.
                self.sleep(_retry_after(response, self._backoff(attempt)))
                last = "429 rate limited"
                continue
            if response.status_code >= 500:
                self.sleep(self._backoff(attempt))
                last = f"{response.status_code} server error"
                continue
            raise VepError(f"{method} {url} -> {response.status_code}: {response.text[:200]}")
        raise VepError(f"{method} {url} gave up after {self.max_attempts} attempts ({last})")

    def _backoff(self, attempt: int) -> float:
        return self.backoff * (2**attempt)

    def close(self) -> None:
        """Close the HTTP client, but only the one we created."""
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> "VepRestAnnotator":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def _retry_after(response: httpx.Response, fallback: float) -> float:
    """Seconds to wait, from the header if the server sent a usable one."""
    raw = response.headers.get("Retry-After", "")
    try:
        return max(0.0, float(raw))
    except ValueError:
        return fallback
