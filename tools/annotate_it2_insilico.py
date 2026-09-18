#!/usr/bin/env python3
"""Ask Ensembl VEP for the in-silico lanes step 4's likelihood ratio scores alleles with.

Every distinct coding allele in the callset (38,087 of them) goes back through VEP REST,
this time asking for ``AlphaMissense``, ``SpliceAI`` and ``numbers`` — the missense lane,
the splice lane, and the exon numbering a LOFTEE-style nonsense-mediated-decay rule needs.
The answers land in ``warehouse.it2_insilico_annotations``, a sibling of
``coding_annotations`` on the same four-key join, so iteration 1's table is left untouched.

The loop, the checkpointing and the lineage edge are
:mod:`mva.warehouse.annotate_coding`'s. This script only says which alleles, which table
and which writer — and prints the coverage gate: how many alleles each lane could score at
all, which is the number the step reports rather than assumes.

Usage::

    uv run python tools/annotate_it2_insilico.py --dry-run
    uv run python tools/annotate_it2_insilico.py --workers 4
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mva.pipeline.annotate_vep import UNAVAILABLE_PARAMS
from mva.warehouse import annotate_coding, annotate_insilico
from mva.warehouse.postgres import ALIAS, attached, safe_identifier
from mva.warehouse.settings import Postgres

DEFAULT_OUT = Path("build/it2/step-4")


def coverage(settings: Postgres) -> dict[str, int]:
    """How many alleles each lane could score at all — the gate this stage is judged by."""
    table = f"{ALIAS}.{safe_identifier(settings.schema)}.{annotate_insilico.INSILICO_TABLE}"
    with attached(settings, read_only=True) as connection:
        row = connection.execute(f"""
            SELECT count(*)                                        AS alleles,
                   count(consequence)                              AS with_consequence,
                   count(am_pathogenicity)                         AS with_alphamissense,
                   count(spliceai_ds_max)                          AS with_spliceai,
                   count(exon_total)                               AS with_exon_numbering,
                   count(gnomad_af)                                AS with_gnomad_af,
                   count(NULLIF(clin_sig, ''))                     AS with_clinvar,
                   count(DISTINCT gene)                            AS genes
            FROM {table}
        """).fetchone()
        names = (
            "alleles",
            "with_consequence",
            "with_alphamissense",
            "with_spliceai",
            "with_exon_numbering",
            "with_gnomad_af",
            "with_clinvar",
            "genes",
        )
    return {name: int(value or 0) for name, value in zip(names, row, strict=True)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="smaller than the 200 a plain annotation uses: AlphaMissense and SpliceAI add "
        "two lookups per allele and a 200-allele batch times out",
    )
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=300.0, help="seconds per request")
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=annotate_insilico.CHECKPOINT,
        help="resumable, gitignored",
    )
    parser.add_argument("--dry-run", action="store_true", help="say what would be asked")
    args = parser.parse_args(argv)

    settings = Postgres.from_env()
    if args.dry_run:
        print(
            json.dumps(annotate_coding.plan(settings, args.batch_size, args.checkpoint), indent=2)
        )
        return 0

    summary = annotate_coding.run(
        settings,
        batch_size=args.batch_size,
        checkpoint=args.checkpoint,
        workers=args.workers,
        timeout=args.timeout,
        progress=lambda line: print(line, flush=True),
        table=annotate_insilico.INSILICO_TABLE,
        transform=annotate_insilico.TRANSFORM,
        source_note=(
            "every distinct coding allele, re-asked with AlphaMissense, SpliceAI and exon "
            f"numbering; {'/'.join(UNAVAILABLE_PARAMS)} are not served by this endpoint"
        ),
        writer=annotate_insilico.write,
    )
    summary["coverage"] = coverage(settings)
    summary["unavailable_plugins"] = list(UNAVAILABLE_PARAMS)

    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / "insilico-coverage.json"
    path.write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(summary["coverage"], indent=2))
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
