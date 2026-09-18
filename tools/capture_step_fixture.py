#!/usr/bin/env python3
"""Capture one step's API payload into the app's offline fixture, reproducibly.

`app/src/fixtures/data/steps-step-<n>.json` is a committed file that the dashboard serves
when the API is down, and `app/src/test/fixtureHashes.json` pins its content. Until now each
one was captured by hand, which makes it the only artifact in the repository with no rebuild
command — so a reader could not tell a stale fixture from a deliberate one.

This writes the fixture from the same `payload()` function the route serves, so the offline
copy and the live reply cannot drift for any reason but time.

**The blessing is deliberately not automatic.** A changed fixture is either a new result or a
bug in the loading layer, and the test that fails is the only thing that distinguishes them.
After running this, run the app's fixture test, read the hash it reports, and put it in
`fixtureHashes.json` on purpose.

Usage::

    uv run python tools/capture_step_fixture.py --step step-4
    cd app && pnpm vitest run src/test/fixtures.test.ts   # read the new hash, then bless it
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mva.warehouse.settings import Postgres

#: Step slug → the module whose ``payload(settings)`` the route serves. Listed rather than
#: derived, because a slug is not a module name and guessing one would be a silent failure.
MODULES = {
    "step-2": "mva.viz.steps_it2",
    "step-3": "mva.viz.steps_it2_step3",
    "step-4": "mva.viz.steps_it2_step4",
    "step-5": "mva.viz.steps_it2_step5",
    "step-6": "mva.viz.steps_it2_step6",
    "step-8": "mva.viz.steps_it2_step8",
}

DEFAULT_ROOT = Path("app/src/fixtures/data")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--step", choices=sorted(MODULES), required=True)
    parser.add_argument("--out", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args(argv)

    settings = Postgres.from_env()
    if settings.missing:
        print("missing settings: " + ", ".join(settings.missing))
        return 1

    module = importlib.import_module(MODULES[args.step])
    data = module.payload(settings)

    path = args.out / f"steps-{args.step}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )
    filled = [name for name, value in data.items() if value]
    print(
        f"wrote {path} ({path.stat().st_size:,} bytes, {len(filled)} of {len(data)} blocks filled)"
    )
    print("now: cd app && pnpm vitest run src/test/fixtures.test.ts, and bless the hash it reports")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
