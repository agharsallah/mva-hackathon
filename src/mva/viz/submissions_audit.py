"""The audit half of an iteration: what the oracle was asked, and what the register believes.

Two independent trails, deliberately kept beside each other on the page.

**Probes** are ``warehouse.probe_ledger`` — the append-only record of every upload spent
against a six-submission budget, with the reply and the score. Rows are matched to an
iteration by the ``rationale`` the logger wrote (``"iteration 1, see submissions/..."``, the
convention the folder README prescribes) or by a payload digest equal to the CSV's, if the
ledger carries one. The ledger is created on first write, exactly like the register tables,
so a project that has not uploaded yet has **no table**, and that is an empty list here
rather than an error.

**Register revisions** are ``docs/science-register.json`` — the exported research record —
filtered to the claims this iteration argues. It is read off disk rather than out of the
database on purpose: the export is what a judge reads, so the page and the judge see the
same bytes.

One honest limitation, stated because it changes what the field means: the export carries
the **current** state of each claim plus a count of how many revisions it has been through.
It does not carry the earlier revisions or the instant any of them was recorded. So one row
per claim is emitted, ``revision`` is that count (the number of the current one) and
``recorded_at`` is the empty string — not a fabricated timestamp.

No coordinate reaches here: a probe rationale, a claim statement and a verdict are all
forbidden from carrying one, by ``mva-science check`` on the way in.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..warehouse.settings import Postgres
from .queries import ledger as ledger_queries

#: Where the exported research record lives, relative to the repository root.
REGISTER_FILE = "docs/science-register.json"

#: Any column whose name mentions a digest. The ledger stores the payload itself today;
#: should it grow a ``payload_sha256``, matching on it is stronger than matching on prose,
#: so both are tried rather than the code being rewritten later.
DIGEST_COLUMN = re.compile(r"sha256", re.IGNORECASE)


def read_probes(settings: Postgres) -> list[dict[str, Any]]:
    """Every probe, or ``[]`` when the ledger has never been written.

    Bare :class:`Exception`: a missing table, missing credentials and an unreachable host
    all mean the same thing to this page — there is nothing to show — and the lineage
    block above it is already the place that reports *why* the warehouse is silent.
    """
    try:
        return ledger_queries.probe_ledger(settings)
    except Exception:
        return []


def probes_for(probes: list[dict[str, Any]], number: int, csv_sha256: str | None) -> list[dict]:
    """The probes belonging to one iteration: by rationale, or by payload digest."""
    needle = f"iteration {number}"
    matched = []
    for probe in probes:
        rationale = str(probe.get("rationale") or "").lower()
        if needle in rationale or _digest_matches(probe, csv_sha256):
            matched.append(probe)
    return matched


def _digest_matches(probe: dict[str, Any], csv_sha256: str | None) -> bool:
    if not csv_sha256:
        return False
    return any(
        DIGEST_COLUMN.search(column) and str(value or "") == csv_sha256
        for column, value in probe.items()
    )


def read_register(root: Path) -> list[dict[str, Any]]:
    """The exported research record's hypotheses, or ``[]`` when it has not been exported."""
    path = root / REGISTER_FILE
    try:
        exported = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    hypotheses = exported.get("hypotheses", [])
    return hypotheses if isinstance(hypotheses, list) else []


def revisions_for(hypotheses: list[dict[str, Any]], wanted: list[str]) -> list[dict[str, Any]]:
    """One ``RegisterRevision`` per claim this iteration argues, in claim-id order.

    See the module docstring for why this is one row per claim rather than its history:
    the export does not carry the history, and inventing it would be worse than saying so.
    """
    by_id = {str(entry.get("id")): entry for entry in hypotheses}
    rows = []
    for claim in sorted(set(wanted)):
        entry = by_id.get(claim)
        if entry is None:
            continue
        rows.append(
            {
                "hypothesis_id": claim,
                "revision": int(entry.get("revisions") or 1),
                "status": str(entry.get("status") or ""),
                "confidence": entry.get("confidence"),
                "reasoning": str(entry.get("reasoning") or ""),
                "recorded_at": "",
                "step": str(entry.get("step") or ""),
                "statement": str(entry.get("statement") or ""),
            }
        )
    return rows


def build(
    probes: list[dict[str, Any]],
    hypotheses: list[dict[str, Any]],
    number: int,
    csv_sha256: str | None,
    wanted: list[str],
) -> dict[str, Any]:
    """The ``audit`` object for one iteration."""
    return {
        "probes": probes_for(probes, number, csv_sha256),
        "register": revisions_for(hypotheses, wanted),
    }
