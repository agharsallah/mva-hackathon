#!/usr/bin/env python3
"""Where does a leading missense allele sit in the protein, and is the model sure about it?

*Plain words.* A missense allele swaps one amino acid for another at one position. Three
public resources say whether that position matters, and none of them is a pathogenicity
score we trained:

* **Ensembl VEP** turns the allele into a residue number on the canonical transcript.
* **InterPro** says whether that residue falls inside an annotated *domain* — a stretch
  that folds and works as a unit, like a kinase's catalytic core.
* **AlphaFold DB** gives the per-residue confidence (**pLDDT**) of its predicted structure
  there. Low pLDDT means the model has no confident opinion, which is a real answer.

The fourth opinion, **AlphaMissense**, is already in the warehouse from step 4 and is not
re-fetched; the claim asks whether it agrees with the structural picture.

**ESM1b is deliberately absent.** It needs `torch` and a 2.5 GB checkpoint to score a
handful of residues, and AlphaMissense is the calibrated missense score the ranking
actually used. The cut is recorded in the step README rather than made silently.

**The residue never leaves ``build/``.** The table written here carries the domain name,
the InterPro accession, the pLDDT and the position as a *fraction* of protein length.

Writes ``build/it2/step-5/tables/it2_protein_residues.tsv``,
``it2_protein_domains.tsv`` and ``protein.json``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import it2_step5_common as common
from mva.drugs import provenance
from mva.drugs.cache import Fetcher, SourceError
from mva.knowledge import protein
from mva.viz.queries.access import fetch
from mva.warehouse.postgres import ALIAS

ENSEMBL = "https://rest.ensembl.org"

RESIDUE_COLUMNS = (
    "gene",
    "uniprot",
    "rsid",
    "consequence_class",
    "gene_rank",
    "in_domain",
    "in_superfamily",
    "domain_accession",
    "domain_name",
    "plddt",
    "confident",
    "fraction",
    "am_class",
    "am_agrees",
    "note",
)

DOMAIN_COLUMNS = (
    "gene",
    "uniprot",
    "protein_length",
    "interpro",
    "domain_name",
    "entry_type",
    "start_fraction",
    "end_fraction",
)

#: How many genes off the top of the ranking are scored. The claim is about the leading
#: pair; the neighbours are carried so the leader can be read against them.
DEFAULT_GENES = 20

#: Missense alleles scored **per gene**, strongest AlphaMissense class first.
#:
#: Not a convenience. The claim is about the allele the step-4 AlphaMissense lane scored
#: for a gene, which is the one with the highest pathogenicity; the next two are carried so
#: that allele can be read against its neighbours. Scoring every missense allele of the top
#: 20 genes means 306 of them, most in the HLA loci where a gene carries dozens, and
#: Ensembl throttles long before that finishes — a cost paid entirely on alleles no claim
#: is about.
DEFAULT_PER_GENE = 3

#: The AlphaMissense class the claim asks the structure to agree with.
DAMAGING = "likely_pathogenic"


def leading_missense(limit: int, per_gene: int = DEFAULT_PER_GENE) -> list[dict[str, Any]]:
    """The missense alleles of the top-ranked genes, strongest AlphaMissense class first.

    The coordinates come from ``warehouse.it2_insilico_annotations`` and are used only to
    ask VEP for a residue; they are never written to a table. ``is_lane_allele`` marks the
    allele the step-4 AlphaMissense lane actually scored for that gene — the one with the
    highest pathogenicity — because that is the allele the claim is about.
    """
    sql = f"""
    WITH leaders AS (
        SELECT gene, gene_rank FROM {ALIAS}.results.it2_lr_top_pairs WHERE gene_rank <= {limit}
    ),
    ranked AS (
        SELECT l.gene,
               l.gene_rank,
               n.chrom,
               n.pos,
               n.ref,
               n.alt,
               coalesce(n.rsid, '')     AS rsid,
               coalesce(n.am_class, '') AS am_class,
               n.am_pathogenicity,
               row_number() OVER (
                   PARTITION BY l.gene ORDER BY n.am_pathogenicity DESC NULLS LAST, n.pos
               ) AS within_gene
        FROM leaders l
        JOIN {ALIAS}.warehouse.it2_insilico_annotations n ON n.gene = l.gene
        WHERE n.consequence LIKE '%missense%'
    )
    SELECT gene, gene_rank, chrom, pos, ref, alt, rsid, am_class, am_pathogenicity,
           within_gene = 1 AS is_lane_allele
    FROM ranked
    WHERE within_gene <= {per_gene}
    ORDER BY gene_rank, within_gene
    """
    return fetch(common.settings(), sql)


def residue_of(fetcher: Fetcher, row: dict[str, Any]) -> tuple[int, str]:
    """The residue this allele changes on the canonical transcript, via Ensembl VEP.

    Returns ``(0, reason)`` when VEP has no canonical protein consequence for the gene —
    a real outcome for an allele on a transcript nobody made canonical, and one the table
    records rather than skipping.
    """
    region = f"{row['chrom']}:{row['pos']}-{row['pos']}"
    try:
        payload = fetcher.get_json(
            f"{ENSEMBL}/vep/human/region/{region}/{row['alt']}",
            {"hgvs": 1, "canonical": 1, "content-type": "application/json"},
            allow_status=(400, 404),
        )
    except SourceError as error:
        return 0, f"VEP refused the allele: {error.detail[:80]}"
    entries = payload if isinstance(payload, list) else []
    for entry in entries:
        for consequence in entry.get("transcript_consequences") or []:
            if consequence.get("gene_symbol") != row["gene"]:
                continue
            if not consequence.get("canonical"):
                continue
            start = consequence.get("protein_start")
            if start:
                return int(start), ""
    return 0, "no canonical protein consequence"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, default=common.DEFAULT_OUT)
    parser.add_argument("--genes", type=int, default=DEFAULT_GENES)
    parser.add_argument("--per-gene", type=int, default=DEFAULT_PER_GENE)
    parser.add_argument("--refresh", action="store_true", help="bypass the cache")
    args = parser.parse_args(argv)

    alleles = leading_missense(args.genes, args.per_gene)
    genes = sorted({row["gene"] for row in alleles})
    print(f"{len(alleles)} missense alleles across {len(genes)} leading genes")

    ensembl = Fetcher(source="ensembl-vep", refresh=args.refresh)
    ebi = Fetcher(source="protein-context", refresh=args.refresh)

    contexts = {}
    for gene in genes:
        contexts[gene] = protein.context_for_gene(ebi, gene)
        context = contexts[gene]
        print(
            f"  {gene:<12} {context.accession or '-':<10} "
            f"{len(context.domains):>3} interpro rows  "
            f"{len(context.plddt):>5} residues  {context.note}"
        )

    residue_rows = []
    for row in alleles:
        context = contexts[row["gene"]]
        residue, why = residue_of(ensembl, row)
        answer = protein.verdict(context, residue) if residue else None
        am_class = row["am_class"]
        residue_rows.append(
            {
                "gene": row["gene"],
                "uniprot": context.accession,
                "rsid": row["rsid"],
                "consequence_class": "missense",
                "gene_rank": row["gene_rank"],
                "in_domain": bool(answer and answer.in_domain),
                "in_superfamily": bool(answer and answer.in_superfamily),
                "domain_accession": answer.domain_accession if answer else "",
                "domain_name": answer.domain_name if answer else "",
                "plddt": round(answer.plddt, 2) if answer else "",
                "confident": bool(answer and answer.confident),
                "fraction": round(answer.fraction, 5) if answer else "",
                "am_class": am_class,
                "am_agrees": am_class == DAMAGING,
                "note": why or context.note,
            }
        )

    domain_rows = [
        {
            "gene": gene,
            "uniprot": context.accession,
            "protein_length": context.length,
            "interpro": track["accession"],
            "domain_name": track["name"],
            "entry_type": track["type"],
            "start_fraction": round(track["start_fraction"], 5),
            "end_fraction": round(track["end_fraction"], 5),
        }
        for gene, context in contexts.items()
        for track in protein.tracks(context)
    ]

    tables = args.out / "tables"
    common.write_tsv(tables / "it2_protein_residues.tsv", residue_rows, RESIDUE_COLUMNS)
    common.write_tsv(tables / "it2_protein_domains.tsv", domain_rows, DOMAIN_COLUMNS)

    lane = [
        row for row, source in zip(residue_rows, alleles, strict=True) if source["is_lane_allele"]
    ]
    payload = {
        "genes": len(genes),
        "alleles": len(residue_rows),
        "lane_alleles": len(lane),
        "resolved_residue": sum(1 for row in residue_rows if row["fraction"] != ""),
        "in_domain": sum(1 for row in residue_rows if row["in_domain"]),
        "in_superfamily": sum(1 for row in residue_rows if row["in_superfamily"]),
        "confident": sum(1 for row in residue_rows if row["confident"]),
        "all_three": sum(
            1 for row in residue_rows if row["in_domain"] and row["confident"] and row["am_agrees"]
        ),
        "leader": lane[0] if lane else None,
        "confident_plddt": protein.CONFIDENT_PLDDT,
        "esm1b": "cut - see docs/iteration2/step-5/README.md; AlphaMissense is the missense score",
        **protein.summarise(list(contexts.values())),
    }
    common.write_json(args.out / "protein.json", payload)
    print(f"\n  residue resolved: {payload['resolved_residue']}/{len(residue_rows)}")
    print(f"  inside a domain : {payload['in_domain']}")
    print(f"  pLDDT >= {protein.CONFIDENT_PLDDT:.0f}   : {payload['confident']}")
    if lane:
        print(f"  leader          : {lane[0]}")

    manifest = provenance.envelope("it2-step5-protein", built_by=Path(__file__).name)
    manifest["inputs"] = [
        provenance.api_input("ensembl-vep", ENSEMBL, role="allele -> residue", fetcher=ensembl),
        provenance.api_input(
            "uniprot-interpro-alphafold",
            protein.ALPHAFOLD,
            role="domain map and per-residue confidence",
            fetcher=ebi,
        ),
    ]
    manifest["outputs"] = [
        provenance.output(tables / "it2_protein_residues.tsv", len(residue_rows)),
        provenance.output(tables / "it2_protein_domains.tsv", len(domain_rows)),
    ]
    provenance.write(manifest, args.out / "protein.provenance.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
