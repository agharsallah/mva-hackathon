"""Pinning bytes that are never held: ``HEAD``, redirects, and small downloads.

The half of the tabix subset that talks to the network but moves almost nothing. A 37 GB
score file cannot be hashed here, so what stands in for its digest is this: its size and
``ETag`` from a ``HEAD``, the sha256 of the index that *was* downloaded, and — from the
caller — the sha256 of the subset that came back. Together they say which bytes answered.

Split from :mod:`mva.zoo.tabix_subset` so the fan-out module stays about the fan-out.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

__all__ = ["digest", "download", "resolve_url", "upstream_head"]


def resolve_url(url: str) -> str:
    """Follow the redirects once and return the final URL.

    Hugging Face answers ``/resolve/main/<file>`` with a redirect to a signed CDN URL.
    Resolving it once is a measured 25 % faster per seek, and the workers are **not** given
    the result: the signature expires in hours and the first real fan-out ran 3 h 13 m before
    every worker died on it at once. What this is for is the provenance line — the host the
    bytes actually came from — which is worth one ``HEAD`` and no risk.
    """
    import httpx

    with httpx.Client(follow_redirects=True, timeout=60.0) as client:
        reply = client.head(url)
        reply.raise_for_status()
        return str(reply.url)


def upstream_head(url: str) -> tuple[int | None, str]:
    """``(size in bytes, ETag)`` of the remote file, from a ``HEAD`` — no body is fetched."""
    import httpx

    with httpx.Client(follow_redirects=True, timeout=60.0) as client:
        reply = client.head(url)
        reply.raise_for_status()
        raw = reply.headers.get("content-length") or reply.headers.get("x-linked-size")
        size = int(raw) if raw and raw.isdigit() else None
        etag = reply.headers.get("etag", "") or reply.headers.get("x-linked-etag", "")
        return size, etag.strip('"')


def download(url: str, dest: Path) -> str:
    """Stream a small file (the index) to disk and return its sha256."""
    import httpx

    dest.parent.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256()
    with httpx.stream("GET", url, follow_redirects=True, timeout=120.0) as reply:
        reply.raise_for_status()
        with dest.open("wb") as handle:
            for chunk in reply.iter_bytes(1 << 20):
                handle.write(chunk)
                sha.update(chunk)
    return sha.hexdigest()


def digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            sha.update(block)
    return sha.hexdigest()
