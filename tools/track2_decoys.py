#!/usr/bin/env python3
"""Run the Track 2 pipeline on a decoy gene, unchanged, as a specificity control.

    uv run python tools/track2_decoys.py --symbol XDH --uniprot P47989 \\
        --protein "xanthine dehydrogenase/oxidase" --pattern purine \\
        --picked-by "an unrelated, well-drugged metabolic enzyme, chosen before the run"

Writes ``ressources/track2/decoys/<symbol>/mechanism.json`` (a decoy card built from the real
card's clinical side by :func:`mva.drugs.decoy.decoy_card`) and then runs ``mva-drugs snapshot``
into the same folder: the five TSVs, their provenance manifests and ``snapshot.json``, exactly
as for the real card. The comparison against the real card is ``tools/track2_enrich.py``'s
job; this script only produces the material.

The pathway pattern is the one case-specific choice, and it is printed into every manifest by
the snapshot's own ``rule_text``: a decoy expanded under ``.*`` would pull in Reactome's
top-level pathways and thousands of targets, which is a different experiment.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mva.drugs.decoy import DecoySpec, decoy_card
from mva.drugs.mechanism import DEFAULT_CARD, load
from mva.drugs.snapshot import write_snapshot

DEFAULT_ROOT = Path("ressources/track2/decoys")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--uniprot", required=True)
    parser.add_argument("--protein", required=True)
    parser.add_argument("--pattern", required=True, help="regex over Reactome pathway names")
    parser.add_argument("--picked-by", required=True, help="the rule that chose this gene")
    parser.add_argument("--ensembl-gene-id", default=None)
    parser.add_argument("--template", type=Path, default=DEFAULT_CARD)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--refresh", action="store_true", help="bypass the HTTP cache")
    parser.add_argument("--card-only", action="store_true", help="write the card, run nothing")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    template = load(args.template)
    spec = DecoySpec(
        args.symbol,
        args.uniprot,
        args.protein,
        args.pattern,
        args.picked_by,
        ensembl_gene_id=args.ensembl_gene_id,
    )
    out_dir = args.root / args.symbol
    out_dir.mkdir(parents=True, exist_ok=True)
    card_path = out_dir / "mechanism.json"
    card_path.write_text(
        json.dumps(decoy_card(template, spec), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {card_path}")
    if args.card_only:
        return 0
    snapshot = write_snapshot(
        card_path,
        out_dir,
        refresh=args.refresh,
        pattern=re.compile(args.pattern, re.IGNORECASE),
        progress=print,
    )
    counts = snapshot.counts
    print(
        json.dumps(
            {
                "rows": counts.get("rows"),
                "targets": counts.get("targets"),
                "candidates": counts.get("candidates"),
            },
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
