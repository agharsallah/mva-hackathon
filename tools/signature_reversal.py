#!/usr/bin/env python3
"""Step 9, E3 — is a BUB1B loss-of-function expression signature reversed by an approved drug?

This file is the **configuration**; the machinery is :mod:`mva.drugs.signature_reversal`
(signature, decoys, ranking), ``_approval`` (ChEMBL / openFDA), ``_tables`` (rows, the G4
list, the verdict inputs), ``_plan`` (the inputs) and ``_run`` (the order). Another gene,
another library or another cut is an edit to the constants below, not a new script.

**Why a loss-of-function signature** (iteration-4 evidence only): the child's BUB1B pair is
one ``stop_gained`` and one missense allele (oracle reply, entry 083); the missense is
predicted destabilising (entry 149); the closest mouse twin is a Bub1b hypomorph (entry 150).
So the child's cells are expected to carry less working BubR1, and a knockout / knockdown
signature is the matching query.

**The plan, fixed 2026-09-25 before any drug query.** H092 (P4-27) in the register fixes
the claim; these are the choices it leaves open:

1. Signature: SigCom LINCS holds 31 BUB1B CRISPR-knockout signatures, so the CRISPR branch
   of H092 applies (no shRNA, no GEO fallback). The **consensus** is the ``BUB1B`` row of
   the LINCS 2021 ``xpr_mean_coeff_mat`` (mean characteristic-direction coefficient over
   the knockout signatures, 12,327 genes). ``run`` checks it against the plain mean of the
   downloaded per-cell-line files.
2. Gene space: the 978 L1000 **landmark** genes (measured by the assay; the rest are
   inferred). iLINCS scores only landmark genes, so both engines then read the same 200
   genes. BUB1B itself is excluded (the edited gene, not a response).
3. Compound rank: each compound at its best reverser signature; SigCom by two-sided rank
   z-sum over the top 10,000 reverser signatures, iLINCS by concordance over its
   p < 0.05 rows. Names are joined on ChEMBL's preferred name where ChEMBL knows the
   name (so a research code meets its INN), else on ``base_name``.
4. Decoys: 20 random 100 + 100 draws from the same landmark space, seed 20260925, through
   SigCom ``l1000_cp`` with the same depth and aggregation.
5. Positive control: the real signature against SigCom ``l1000_xpr`` and ``l1000_shRNA``
   as mimickers, aggregated per perturbed gene, BUB1B excluded; pass = any of BUB1, BUB3,
   MAD2L1, MAD1L1, TTK in the top 5 % of genes in either library. The 20 decoys run the
   same control, to show how often chance passes it.

Usage::

    uv run python tools/signature_reversal.py fetch   # ~450 MB + library crawls, cached
    uv run python tools/signature_reversal.py run

Writes ``ressources/track2/it4/lincs_reversal.tsv`` (+ provenance), the G4 generator files
under ``ressources/track2/it4/generators/``, and the intermediates the figures read under
``build/it4/track2-e3/``. Only gene symbols and drug names leave the laptop.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from mva.drugs.screen_replication_plan import SourceFile
from mva.drugs.signature_reversal_plan import ReversalPlan, fetch_inputs
from mva.drugs.signature_reversal_run import execute

LINCS_S3 = "https://lincs-dcic.s3.amazonaws.com/LINCS-sigs-2021"

CONSENSUS = SourceFile(
    role="consensus signatures (CRISPR knockout, mean CD coefficient)",
    name="xpr_mean_coeff_mat.tsv.gz",
    url=f"{LINCS_S3}/means/xpr_mean_coeff_mat.tsv.gz",
    release="LINCS L1000 2021 (SigCom LINCS downloads; S3 Last-Modified 2023-09-05)",
    licence="LINCS data: public (no licence stated by SigCom)",
)

GENE_INFO = SourceFile(
    role="L1000 gene space (landmark / inferred)",
    name="geneinfo_beta.txt",
    url="https://s3.amazonaws.com/macchiato.clue.io/builds/LINCS2020/geneinfo_beta.txt",
    release="CMap LINCS 2020 beta",
    licence="CMap / LINCS: public",
)

CLAIM = (
    "H092 (P4-27): a BUB1B loss-of-function expression signature is reversed by at least "
    "one approved drug in two independent connectivity engines, and specifically to that "
    "signature"
)


def plan(args: argparse.Namespace) -> ReversalPlan:
    return ReversalPlan(
        perturbation="BUB1B",
        consensus=CONSENSUS,
        gene_info=GENE_INFO,
        per_signature_database="l1000_xpr",
        gene_space="landmark",
        size=100,
        decoys=20,
        seed=args.seed,
        top_n=100,
        decoy_max_hits=1,
        sigcom_limit=10_000,
        drug_database="l1000_cp",
        control_databases=("l1000_xpr", "l1000_shRNA"),
        control_genes=("BUB1", "BUB3", "MAD1L1", "MAD2L1", "TTK"),
        control_cut=0.05,
        raw_dir=args.raw_dir,
        build_dir=args.build_dir,
        out=args.out,
        generator_dir=args.generator_dir,
        entry="docs/iteration4/step-9/methodology/153-lincs-signature-reversal-of-bub1b-loss.md",
        claim=CLAIM,
        mechanism_note=(
            "loss-of-function query: stop_gained + destabilising missense (entries 083, 149); "
            "hypomorph phenotype twin (entry 150)"
        ),
        patient_data=(
            "none. Public LINCS signatures, gene symbols and drug names only. This experiment "
            "uses the genomic source (the mechanism class of the child's alleles) to choose "
            "the query; it reads no clinical (HPO) term."
        ),
        refresh=args.refresh,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("command", choices=["fetch", "run"])
    parser.add_argument("--raw-dir", type=Path, default=Path("build/it4/track2-e3/raw"))
    parser.add_argument("--build-dir", type=Path, default=Path("build/it4/track2-e3"))
    parser.add_argument(
        "--out", type=Path, default=Path("ressources/track2/it4/lincs_reversal.tsv")
    )
    parser.add_argument(
        "--generator-dir", type=Path, default=Path("ressources/track2/it4/generators")
    )
    parser.add_argument("--seed", type=int, default=20260925)
    parser.add_argument("--refresh", action="store_true", help="bypass the API cache")
    args = parser.parse_args(argv)
    built = plan(args)
    return fetch_inputs(built) if args.command == "fetch" else execute(built)


if __name__ == "__main__":
    raise SystemExit(main())
