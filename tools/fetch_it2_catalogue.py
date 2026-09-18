#!/usr/bin/env python3
"""Has anyone published about the alleles this child actually carries?

*Plain words.* Take every allele the genome-wide ranking scored in a gene of the step-5
gene set, and ask LitVar 2.0 — NCBI's index of variants mentioned in the literature — how
many papers discuss that exact variant. Then add the other half of the question from a
completely different instrument: the public ClinVar pathogenic alleles that step 3 found
present in the reads, by k-mer count, with no aligner and no caller.

**The direction is the design.** "Every published allele of gene X" is somebody else's
alleles and tells you only how famous the gene is. "Which of *this* child's alleles has
been written about" has a complete denominator and a meaningful zero.

**An allele with no dbSNP identifier is counted, not dropped.** LitVar is keyed on dbSNP,
so a private allele cannot be looked up at all. Its ``pmid_count`` is -1 (*not asked*) and
it is counted as ``unqueryable``. Reporting one "coverage" percentage would merge two
different absences — nobody indexed it, and nobody wrote about it — and only the second
says anything.

Writes ``build/it2/step-5/tables/it2_pub_alleles.tsv`` and ``catalogue.json``.
Every reply is cached under ``build/track2-cache/`` by the shared fetcher, so a second run
costs no requests and the provenance manifest names the exact bytes that were parsed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import it2_step5_common as common
from mva.drugs import provenance
from mva.drugs.cache import Fetcher
from mva.knowledge import catalogue, sources

COLUMNS = (
    "gene",
    "origin",
    "rsid",
    "consequence_class",
    "pmid_count",
    "top_pmid",
    "clin_sig",
    "child_call",
    "child_posterior",
    "is_target",
    "is_decoy",
    "in_top_leaders",
)

#: Rows coming from the ranking: alleles the callset carries and the ranker scored.
RANKED = "ranked"

#: Rows coming from step 3: public ClinVar pathogenic alleles typed directly in the reads.
CLINVAR_KMER = "clinvar-kmer"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, default=common.DEFAULT_OUT)
    parser.add_argument("--refresh", action="store_true", help="bypass the cache for this run")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="build the table without asking LitVar; every count is 'not asked'",
    )
    args = parser.parse_args(argv)

    scored = common.alleles()
    print(f"alleles the ranking scored in the step-5 gene set: {len(scored):,}")
    fetcher = Fetcher(source="litvar2", refresh=args.refresh)
    rows = catalogue.build(fetcher, scored, ask_literature=not args.offline)
    summary = catalogue.summarise(rows)

    table = [
        {
            "gene": row.gene,
            "origin": RANKED,
            "rsid": row.rsid,
            "consequence_class": row.consequence_class,
            "pmid_count": row.pmid_count,
            "top_pmid": row.top_pmid,
            "clin_sig": row.clin_sig,
            "child_call": "",
            "child_posterior": "",
            "is_target": row.is_target,
            "is_decoy": row.is_decoy,
            "in_top_leaders": row.in_top_leaders,
        }
        for row in rows
    ]

    # The second instrument. These rows carry no rsID on purpose: step 3 typed them by
    # k-mer against the public ClinVar catalogue, and what it reports is a multiplicity in
    # this child, not a literature identifier.
    membership = {row["gene"]: row for row in common.genes()}
    carried = common.clinvar_carried()
    for row in carried:
        flags = membership.get(row["gene"], {})
        table.append(
            {
                "gene": row["gene"],
                "origin": CLINVAR_KMER,
                "rsid": "",
                "consequence_class": "clinvar-pathogenic",
                "pmid_count": catalogue.NOT_ASKED,
                "top_pmid": "",
                "clin_sig": "pathogenic/likely pathogenic (ClinVar)",
                "child_call": row["child_call"],
                "child_posterior": row["child_posterior"],
                "is_target": bool(flags.get("is_target")),
                "is_decoy": bool(flags.get("is_decoy")),
                "in_top_leaders": bool(flags.get("in_top_leaders")),
            }
        )

    written = common.write_tsv(args.out / "tables" / "it2_pub_alleles.tsv", table, COLUMNS)
    payload = {
        "genes": summary.genes,
        "alleles": summary.alleles,
        "queryable": summary.queryable,
        "unqueryable": summary.unqueryable,
        "described": summary.described,
        "clinvar_carried": len(carried),
        "clinvar_carried_genes": sorted({row["gene"] for row in carried}),
        "rows_written": written,
        "asked_litvar": not args.offline,
        "source": sources.LITVAR,
    }
    common.write_json(args.out / "catalogue.json", payload)

    print(f"  queryable (has a dbSNP identifier) : {summary.queryable:,}")
    print(f"  unqueryable (private allele)       : {summary.unqueryable:,}")
    print(f"  described (>= 1 publication)       : {summary.described:,}")
    print(f"  ClinVar pathogenic, carried        : {len(carried):,}")
    print(f"\n  wrote {written:,} rows -> {args.out / 'tables' / 'it2_pub_alleles.tsv'}")

    manifest = provenance.envelope("it2-step5-catalogue", built_by=Path(__file__).name)
    manifest["inputs"] = [
        provenance.api_input(
            "litvar2", sources.LITVAR, role="published-allele index", fetcher=fetcher
        )
    ]
    manifest["outputs"] = [provenance.output(args.out / "tables" / "it2_pub_alleles.tsv", written)]
    provenance.write(manifest, args.out / "catalogue.provenance.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
