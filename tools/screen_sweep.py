#!/usr/bin/env python3
"""Step 10, S1 — the screen-wide PRISM sweep (generator G3), entry 154, claim H093 (P4-28).

This file is the **configuration**; the machinery is :mod:`mva.drugs.screen_sweep` (the
sweep and its family), ``_prism`` (PRISM's Launched label, the join key), ``_report``
(tables, calibration, generator list) and ``_run`` (the order of the run). Entry 151's
statistics are reused unchanged from :mod:`mva.drugs.screen_replication`.

Question: over **every** Launched compound PRISM measured well enough, is any one selective
for both high-aneuploidy lines and rhabdomyosarcoma (RMS) lines, after paying for testing
all of them?

**The plan, fixed 2026-09-25 before the first p value of this sweep was computed.** H093 in
``docs/science-register.json`` is binding; these are the choices it leaves open. Coverage
counts (how many compounds, how many lines) were looked at before this was written; no
contrast result was.

1. Screen and metric: PRISM Repurposing 24Q2 extended primary, log fold change (5 d,
   2.5 uM), lower = more sensitive — entry 151's primary metric. No secondary release: the
   claim is about 24Q2.
2. Launched: the compound's core BRD id is ``Launched`` in the 20Q2 **primary or
   secondary** treatment-info (PRISM's copy of the Repurposing Hub phase). The 24Q2 list
   has no phase column. Entry 151 used the secondary file alone (597 Launched rows) for its
   control universe; the primary file (2,175 Launched rows) is the wider copy of the same
   label and is fetched here. 24Q2 compounds absent from both files cannot be called
   Launched and are counted, not guessed.
3. Groups: RMS = ``Model.csv`` 24Q4 ``OncotreeCode`` in RMS/ERMS/ARMS/PLRMS/SCRMS/SRMS vs
   every other screened line; aneuploidy = ``OmicsSignatures.csv`` 24Q4 ``Aneuploidy``,
   strict median split over screened lines with a score, ties dropped. Entry 151's builders.
4. Eligibility (from H093): a copy is measured on >= 3 RMS lines and >= 20 lines in each
   aneuploidy arm (the RMS comparison arm is >= 3, entry 151's floor). A drug is eligible
   when any copy is.
5. Test: one-sided Mann-Whitney U "in-group more sensitive"; Cliff's delta from the same
   U; 95 % percentile bootstrap CI, 2,000 resamples; seed 20260924 + the copy's index in
   the sorted eligible list. Entry 151's ``contrast_item``, unchanged.
6. One drug, one test: copies are grouped by the join key (``prism_join_key``) and by
   shared core BRD id. (The key was first "hyphen to space between two letters"; it was
   changed to step 10's shared rule ``base_name(name.replace("-", " "))`` at the
   convergence join's request after the first run — an interface fix, recorded in entry
   154, re-run in full;) entry 151's ``representative`` rule (the copy measured on most
   in-group lines) picks one per contrast; only it enters the family.
7. Multiplicity: Benjamini-Hochberg over every eligible drug's representative, within each
   contrast. **H093 holds iff >= 1 drug has q < 0.10 in both contrasts.**
8. Rank and percentile: rank by one-sided p, ties by larger delta; percentile = share of
   the family with delta <= the drug's delta (entry 151's convention).
9. Generator G3: union of the top 0.5 % (``ceil``) of the family on each contrast by rank;
   ``direction_hint`` D4 for an RMS hit, D2 for an aneuploidy hit (``D4|D2`` for both);
   ``approval_evidence`` ``PRISM Launched``; universe = every eligible drug.
10. Controls (context, outside the claim): entry 151's negative band re-drawn from the
    eligible set (200 seeded compounds, MOA exclusion list unchanged) and the family's
    raw-p calibration; the positive control as a **sweep** (skin lines vs rest, every
    Launched compound with >= 3 lines each side, BH over the family, RAF/MEK ranks); the RMS
    lines' generic fragility and which RMS lines the 3-line compounds were measured on;
    a within-line rank-normalised repeat of the RMS contrast for every copy (raw p).
11. Retrospective, reported only: entry 151 put dasatinib at the 99.4th percentile of all
    compounds on the aneuploidy contrast. Its place in this family is reported; no rule
    reads it.

Usage::

    uv run python tools/screen_sweep.py fetch   # the one new file (1.3 MB) + its manifest
    uv run python tools/screen_sweep.py run     # minutes on a laptop, all CPU cores

Reads entry 151's raw files (digests verified against
``ressources/track2/prism_replication.provenance.json``; the run refuses on a mismatch).
Writes ``ressources/track2/it4/prism_sweep.tsv`` + ``.provenance.json``,
``ressources/track2/it4/generators/prism{,.universe}.tsv`` + ``prism.provenance.json`` and
``build/it4/track2-s1/controls.json``. No patient data is read.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from mva.drugs.screen_replication_plan import SourceFile, fetch_files
from mva.drugs.screen_replication_prism import RMS_ONCOTREE_CODES
from mva.drugs.screen_sweep_plan import SweepPlan
from mva.drugs.screen_sweep_run import execute

ENTRY = "docs/iteration4/step-10/methodology/154-screen-wide-prism-sweep.md"
E4_RAW = Path("build/it4/track2-e4/raw")
E4_MANIFEST = Path("ressources/track2/prism_replication.provenance.json")


def _figshare(role: str, name: str, file_id: str, release: str) -> SourceFile:
    return SourceFile(
        role=role,
        name=name,
        url=f"https://ndownloader.figshare.com/files/{file_id}",
        release=release,
    )


#: Entry 151's downloads this sweep reads (the 20Q2 dose-response file is not needed).
REUSED = (
    _figshare(
        "primary_matrix",
        "PRISM_24Q2_Extended_Primary_Data_Matrix.csv",
        "46630984",
        "PRISM Repurposing 24Q2 (figshare article 25917643)",
    ),
    _figshare(
        "primary_compounds",
        "PRISM_24Q2_Extended_Primary_Compound_List.csv",
        "46630981",
        "PRISM Repurposing 24Q2",
    ),
    _figshare("models", "Model_24Q4.csv", "51065297", "DepMap 24Q4 (figshare.plus 27993248)"),
    _figshare("signatures", "OmicsSignatures_24Q4.csv", "51065726", "DepMap 24Q4"),
    _figshare(
        "secondary_compounds",
        "PRISM_20Q2_secondary_treatment_info.csv",
        "36794619",
        "PRISM Repurposing 20Q2 secondary",
    ),
)
OWN = (
    _figshare(
        "primary_treatment_info",
        "PRISM_20Q2_primary_treatment_info.csv",
        "36794583",
        "PRISM Repurposing 20Q2 primary (figshare article 20564034; "
        "prism-repurposing-20q2-primary-screen-replicate-collapsed-treatment-info.csv)",
    ),
)

#: Entry 151's negative-control exclusion list, unchanged.
CONTROL_EXCLUDE = (
    "HMGCR",
    "PROTEASOME",
    "AUTOPHAGY",
    "LYSOSOM",
    "NAD ",
    "AMPK",
    "MTOR",
    "HDAC",
    "AURORA",
    "SPINDLE",
    "TUBULIN",
    "KINESIN",
    "PLK",
    "HSP90",
    "ANTIMALARIAL",
)


def plan(args: argparse.Namespace) -> SweepPlan:
    return SweepPlan(
        reused=REUSED,
        reused_dir=E4_RAW,
        reused_manifest=E4_MANIFEST,
        own=OWN,
        own_dir=args.raw_dir,
        build_dir=args.build_dir,
        out=args.out,
        generator_dir=args.generator_dir,
        generator="prism",
        entry=ENTRY,
        in_group_codes=RMS_ONCOTREE_CODES,
        annotation_column="Aneuploidy",
        min_in_group=3,
        min_arm=20,
        alpha=0.10,
        top_fraction=0.005,
        hints={"rms": "D4", "aneuploidy": "D2"},
        control_exclude=CONTROL_EXCLUDE,
        positive_control_drugs=("DABRAFENIB", "VEMURAFENIB", "PLX-4720", "SELUMETINIB"),
        positive_control_lineage="Skin",
        report_drugs=("DASATINIB",),
        seed=args.seed,
        resamples=args.resamples,
        workers=args.workers,
        patient_data=(
            "none. Public cell-line screens and public line annotations only. The clinical "
            "terms enter at one remove: HP:0002859 (rhabdomyosarcoma) is why the lineage "
            "contrast is RMS. No patient sequence, position or allele is read."
        ),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("command", choices=["fetch", "run"])
    parser.add_argument("--raw-dir", type=Path, default=Path("build/it4/track2-s1/raw"))
    parser.add_argument("--build-dir", type=Path, default=Path("build/it4/track2-s1"))
    parser.add_argument("--out", type=Path, default=Path("ressources/track2/it4/prism_sweep.tsv"))
    parser.add_argument(
        "--generator-dir", type=Path, default=Path("ressources/track2/it4/generators")
    )
    parser.add_argument("--seed", type=int, default=20260924)
    parser.add_argument("--resamples", type=int, default=2000)
    parser.add_argument("--workers", type=int, default=None)
    args = parser.parse_args(argv)
    built = plan(args)
    if args.command == "fetch":
        return fetch_files(built.own, built.own_dir, source_note="figshare mirror")
    return execute(built)


if __name__ == "__main__":
    raise SystemExit(main())
