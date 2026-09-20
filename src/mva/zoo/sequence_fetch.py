"""Fetching protein sequences from Ensembl, cached one file per accession.

Split out of :mod:`mva.zoo.record_window` (module-size gate) — that module builds windows
from sequences this one fetches and caches. See its docstring for why a window needs a
sequence at all.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Any

__all__ = [
    "DEFAULT_BATCH",
    "DEFAULT_CACHE",
    "ENSEMBL_SEQUENCE",
    "PAUSE_SECONDS",
    "RETRYABLE",
    "Fetcher",
    "SequenceCache",
    "ensembl_sequences",
    "fetch_sequences",
]

#: Ensembl's documented POST ceiling for ``/sequence/id`` is 50 ids per request.
DEFAULT_BATCH = 50

#: One file per accession. Gitignored, and it holds protein sequence, so it stays here.
DEFAULT_CACHE = Path("build/it4/protein-seq")

#: The REST endpoint. Public, no key, ~15 requests/second fair-use.
ENSEMBL_SEQUENCE = "https://rest.ensembl.org/sequence/id"


class SequenceCache:
    """One protein per file — the cheapest resumable cache there is.

    ``build/<prefix>/protein-seq/ENSP00000287598.json`` holds ``{"id": …, "seq": …}``. A
    re-run reads what is there and asks Ensembl only for the rest, so a dropped connection
    at accession 8,000 of 8,947 costs one batch.
    """

    def __init__(self, directory: Path | str = DEFAULT_CACHE) -> None:
        self.directory = Path(directory)

    def path(self, accession: str) -> Path:
        return self.directory / f"{accession}.json"

    def read(self, accession: str) -> str | None:
        target = self.path(accession)
        if not target.exists():
            return None
        try:
            return str(json.loads(target.read_text())["seq"])
        except (ValueError, KeyError):
            return None

    def write(self, accession: str, sequence: str) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        target = self.path(accession)
        target.write_text(json.dumps({"id": accession, "seq": sequence}))
        return target

    def load(self, accessions: Iterable[str]) -> dict[str, str]:
        found: dict[str, str] = {}
        for accession in accessions:
            sequence = self.read(accession)
            if sequence:
                found[accession] = sequence
        return found


#: What a fetcher looks like: a batch of accessions in, ``{accession: sequence}`` out.
Fetcher = Callable[[Sequence[str]], dict[str, str]]


#: Ensembl's documented fair-use ceiling is 15 requests/second per client. This pass is
#: nowhere near it, but the server answers 429/503 under *its own* load too, so a courteous
#: floor between requests costs nothing and keeps the pass off the rate limiter.
PAUSE_SECONDS = 0.2

#: Status codes that are worth waiting out rather than believing. 429 and 503 are the rate
#: limiter and Ensembl sends ``Retry-After`` with them. **500 is on this list too, and that
#: is a measured decision, not laziness**: the endpoint returns 500 both for a POST carrying
#: one unknown accession *and* when it is simply busy — three accessions that failed
#: individually mid-run answered fine on a hand-run request a minute later (2026-09-20). So
#: 500 is retried first and only bisected once it survives :func:`ensembl_sequences`'s
#: attempts, which is what separates "this id is bad" from "the server was busy".
RETRYABLE = (429, 500, 502, 503, 504)


def ensembl_sequences(
    accessions: Sequence[str], *, timeout: float = 60.0, attempts: int = 4
) -> dict[str, str]:
    """One POST to Ensembl's ``/sequence/id`` for up to :data:`DEFAULT_BATCH` accessions.

    The reply is a list of ``{"id", "seq", …}``; ids come back without the version suffix,
    which is the spelling this module keys on.

    A :data:`RETRYABLE` status is waited out, honouring ``Retry-After`` — it means the server
    is busy, and the caller's bisection would otherwise *double* the load that caused it.
    Anything else raises, and the caller bisects to find the one bad accession.
    """
    import httpx

    for attempt in range(attempts):
        time.sleep(PAUSE_SECONDS)
        reply = httpx.post(
            ENSEMBL_SEQUENCE,
            params={"type": "protein"},
            json={"ids": list(accessions)},
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=timeout,
        )
        if reply.status_code in RETRYABLE and attempt < attempts - 1:
            wait = reply.headers.get("Retry-After")
            time.sleep(float(wait) if wait and wait.replace(".", "").isdigit() else 2**attempt)
            continue
        reply.raise_for_status()
        payload = reply.json()
        rows = payload if isinstance(payload, list) else [payload]
        return {
            str(row["id"]).split(".")[0]: str(row["seq"])
            for row in rows
            if isinstance(row, dict) and row.get("seq")
        }
    raise RuntimeError(f"Ensembl stayed busy for {attempts} attempts on {len(accessions)} ids")


def fetch_sequences(
    accessions: Sequence[str],
    *,
    cache: SequenceCache | None = None,
    fetcher: Fetcher = ensembl_sequences,
    batch: int = DEFAULT_BATCH,
    progress: Any = None,
) -> dict[str, str]:
    """Every accession's sequence, from the cache first and the network only for the rest.

    A batch that raises is **bisected**, not abandoned. Ensembl's POST endpoint answers HTTP
    500 for the whole request when one id in it is unknown — measured 2026-09-20 on a batch
    of 50, where two ids apart the same batch succeeds — so one bad accession would otherwise
    cost the 49 beside it. Halving until the failure is a single id isolates it in
    ``log2(batch)`` extra requests and leaves that one accession simply unanswered, which is
    the honest outcome: the record it belongs to is reported as ``sequence_missing``.
    """
    store = cache or SequenceCache()
    known = store.load(accessions)
    missing = [key for key in dict.fromkeys(accessions) if key not in known]
    for start in range(0, len(missing), batch):
        chunk = missing[start : start + batch]
        answered = _fetch_bisecting(chunk, fetcher, progress)
        for accession, sequence in answered.items():
            store.write(accession, sequence)
        known.update(answered)
        if progress:
            progress(f"    {min(start + batch, len(missing)):,}/{len(missing):,} accessions")
    return known


def _fetch_bisecting(
    chunk: Sequence[str], fetcher: Fetcher, progress: Any = None
) -> dict[str, str]:
    """Ask for a batch; on any failure, split it in half and ask for each half."""
    if not chunk:
        return {}
    try:
        return fetcher(chunk)
    except Exception as failure:  # any transport or server error bisects — that is the point
        if len(chunk) == 1:
            if progress:
                progress(f"    no sequence for {chunk[0]}: {type(failure).__name__}")
            return {}
    middle = len(chunk) // 2
    left = _fetch_bisecting(chunk[:middle], fetcher, progress)
    return {**left, **_fetch_bisecting(chunk[middle:], fetcher, progress)}
