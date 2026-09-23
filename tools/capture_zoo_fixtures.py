"""Capture the dashboard's `/api/zoo/*` fixtures from a running `mva-viz-api`, reproducibly.

`app/src/fixtures/data/zoo-*.json` are what the zoo page draws when the API is down. They
were first captured by hand (2026-09-20, commit 89cf069); a run added two lanes after that
and the offline page kept showing four. This tool is the rebuild command: it `GET`s every
route, keeps the envelope's `data` verbatim, and writes the same wrapper the registry
unwraps — `_captured`, `captured_at`, the API's own `source`, and `_redacted` where a field
was removed.

**Which reports and genes.** The report keys are the lanes the latest run ranked (read from
`/api/zoo/ranks`) plus `merged`, so a new lane is captured without editing this file. The
genes are `--gene` (default: the case gene the API names, plus `NBPF3`, the gene the first
capture used for the disagreement view).

**The one redaction.** `hgvs_c` / `hgvs_p` in the gene payloads are the patient's own allele
spellings; they are nulled before writing, and the file says so. Run
`tools/check_coordinates.py` after a capture all the same.

Usage::

    uv run mva-viz-api --port 8911 &
    uv run python tools/capture_zoo_fixtures.py --api http://127.0.0.1:8911
    cd app && pnpm vitest run src/test/fixtures.test.ts   # read the new hashes, bless them
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

OUT = Path("app/src/fixtures/data")

#: Route → fixture file, for the routes that take no parameter.
PLAIN = {
    "/api/zoo/case": "zoo-case",
    "/api/zoo/models": "zoo-models",
    "/api/zoo/ranks": "zoo-ranks",
    "/api/zoo/merge": "zoo-merge",
    "/api/zoo/runs": "zoo-runs",
    "/api/zoo/lineage": "zoo-lineage",
}

#: Fields nulled in every gene record before a capture is written.
REDACT = ("hgvs_c", "hgvs_p")

#: The extra gene the disagreement view links to in the first capture.
EXTRA_GENES = ("NBPF3",)


def fetch(api: str, route: str) -> dict[str, Any]:
    """One envelope off the live route."""
    with urllib.request.urlopen(f"{api.rstrip('/')}{route}", timeout=300) as reply:
        envelope: dict[str, Any] = json.load(reply)
    return envelope


def wrap(envelope: dict[str, Any], payload: Any, redacted: list[str] | None = None) -> dict:
    """The wrapper `app/src/fixtures/registry/zoo.ts` unwraps."""
    out: dict[str, Any] = {
        "_captured": True,
        "captured_at": datetime.now(tz=UTC).date().isoformat(),
        "source": envelope.get("source", ""),
    }
    if redacted:
        out["_redacted"] = redacted
    out["payload"] = payload
    return out


def redact(gene: dict[str, Any]) -> dict[str, Any]:
    """The gene payload with the patient's allele spellings nulled."""
    for record in gene.get("records", []):
        for field in REDACT:
            if field in record:
                record[field] = None
    return gene


def write(name: str, data: dict) -> None:
    path = OUT / f"{name}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {path} ({path.stat().st_size:,} bytes)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--api", default="http://127.0.0.1:8900")
    parser.add_argument("--gene", action="append", default=[], help="gene symbol to capture")
    args = parser.parse_args(argv)

    envelopes = {name: fetch(args.api, route) for route, name in PLAIN.items()}
    for name, envelope in envelopes.items():
        write(name, wrap(envelope, envelope["data"]))

    lanes = [row["model"] for row in envelopes["zoo-ranks"]["data"]["per_model"]]
    reports: dict[str, Any] = {}
    source = ""
    # A lane ranked by a run whose reports were written elsewhere (step 8 writes its own under
    # docs/iteration4/step-8/reports/) has no report on this route; it is skipped and named.
    served = {row["key"] for row in fetch(args.api, "/api/zoo/reports")["data"]}
    missing = [key for key in lanes if key not in served]
    if missing:
        print(f"no served report for: {', '.join(missing)} (skipped)")
    for key in ["merged", *[lane for lane in lanes if lane in served]]:
        envelope = fetch(args.api, f"/api/zoo/reports/{key}")
        reports[key] = envelope["data"]
        source = source or envelope.get("source", "")
    write("zoo-reports", wrap({"source": source}, reports))

    # The first lane with an opinion on the pair names the gene; a lane that abstains has none.
    case_gene = next(
        row["confirmed"]["gene"]
        for row in envelopes["zoo-ranks"]["data"]["per_model"]
        if row.get("confirmed")
    )
    genes = args.gene or [case_gene, *EXTRA_GENES]
    captured: dict[str, Any] = {}
    gene_source = ""
    for symbol in genes:
        envelope = fetch(args.api, f"/api/zoo/scores/gene/{symbol}")
        captured[symbol] = redact(envelope["data"])
        gene_source = gene_source or envelope.get("source", "")
    write(
        "zoo-gene",
        wrap({"source": gene_source}, captured, [f"records[].{f}" for f in REDACT]),
    )
    print(f"report keys: {', '.join(reports)} · genes: {', '.join(captured)}")
    print("now: tools/check_coordinates.py, then bless the hashes fixtures.test.ts reports")
    return 0


if __name__ == "__main__":
    sys.exit(main())
