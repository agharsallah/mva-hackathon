#!/usr/bin/env python3
"""Step 9, E4 — do the Track 2 leads survive a public screen nobody curated for this case?

This file is the **configuration**; the machinery is
:mod:`mva.drugs.screen_replication` (rank contrasts), ``_prism`` (readers),
``_report`` (rows, controls, provenance) and ``_plan`` (the order of the run). Pointing it
at another lineage, another line annotation or another screen is an edit to the constants
below, not a new script.

It reads the PRISM Repurposing screens and the DepMap line annotations (all CC BY 4.0,
from the figshare mirrors verified in ``docs/iteration4/step-9/research/data-sources.md``
§1) and asks, for each drug the Track 2 report argues:

* **RMS contrast** — are the child's tumour-context lines (rhabdomyosarcoma) more sensitive
  than the rest of the screen?  (H087 / P4-22, statins)
* **Aneuploidy contrast** — are lines with a high DepMap arm-level aneuploidy score more
  sensitive than low ones?  (H088 / P4-23, chloroquine and the D2 stress drugs)
* both, for the **D5** drugs read out of the phenotype twin's papers (H089 / P4-24)

**The plan, fixed before the run.** The pre-registration is H087-H089 in
``docs/science-register.json``; these are the analysis choices those claims leave open:

1. Response metric: 24Q2 extended primary **log fold change**, 5 days at 2.5 uM; lower =
   more sensitive. The 20Q2 secondary dose-response **AUC** is the sensitivity analysis —
   a different release *and* a different metric.
2. RMS membership: ``Model.csv`` 24Q4 ``OncotreeCode`` in RMS/ERMS/ARMS/PLRMS/SCRMS/SRMS.
3. Aneuploidy split: ``OmicsSignatures.csv`` 24Q4 ``Aneuploidy``, **strict median split**
   over the screened lines carrying a score, lines exactly at the median dropped (it is an
   integer arm count with many ties). A tertile split is a sensitivity analysis.
4. Test: Mann-Whitney U, one-sided "the in-group is more sensitive". Effect size Cliff's
   delta with a 2,000-resample percentile bootstrap CI.
5. Multiplicity: Benjamini-Hochberg **within each primary contrast, over the representative
   row of every candidate drug**. Controls, sensitivity contrasts and the background sweep
   are outside the family and carry raw p only.
6. Controls: a seeded 200-drug negative-control band of Launched compounds with no
   mechanistic tie to either contrast; a positive control with a textbook lineage
   dependency (RAF/MEK inhibitors in skin/melanoma lines); a literature direction check
   (Mps1 and Aurora inhibitors, where Cohen-Sharir 2021 PMID 33505028 reports aneuploid
   lines are *less* sensitive to short-term SAC inhibition).
7. Confounders: the RMS lines' overall median response versus the rest; their aneuploidy
   scores against the rest; and a within-line rank-normalised repeat of the RMS contrast,
   which removes any line-level "easy to kill" offset.

Usage::

    uv run python tools/screen_replication.py fetch     # ~365 MB, one manifest per file
    uv run python tools/screen_replication.py run       # ~3 min on a laptop

Writes ``ressources/track2/prism_replication.tsv`` + ``.provenance.json``, and the
intermediates the figures read under ``build/it4/track2-e4/``. No patient data is read and
no genomic position can appear in any output.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from mva.drugs.screen_replication_plan import ReplicationPlan, SourceFile, fetch_sources
from mva.drugs.screen_replication_prism import RMS_ONCOTREE_CODES
from mva.drugs.screen_replication_run import execute


def _figshare(role: str, name: str, file_id: str, release: str) -> SourceFile:
    return SourceFile(
        role=role,
        name=name,
        url=f"https://ndownloader.figshare.com/files/{file_id}",
        release=release,
    )


SOURCES = (
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
    _figshare(
        "primary_lines",
        "PRISM_24Q2_Cell_Line_Meta_Data.csv",
        "46630978",
        "PRISM Repurposing 24Q2",
    ),
    _figshare("models", "Model_24Q4.csv", "51065297", "DepMap 24Q4 (figshare.plus 27993248)"),
    _figshare("signatures", "OmicsSignatures_24Q4.csv", "51065726", "DepMap 24Q4"),
    _figshare(
        "secondary_auc",
        "PRISM_20Q2_secondary_dose_response_curve_parameters.csv",
        "36794595",
        "PRISM Repurposing 20Q2 secondary (figshare article 20564034)",
    ),
    _figshare(
        "secondary_compounds",
        "PRISM_20Q2_secondary_treatment_info.csv",
        "36794619",
        "PRISM Repurposing 20Q2 secondary",
    ),
)

#: MOA words that disqualify a drug from the negative-control band: anything touching
#: cholesterol synthesis, the proteasome, autophagy, NAD, AMPK, mTOR, HDAC or the mitotic
#: apparatus could plausibly be tied to one of the two contrasts.
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


def plan(args: argparse.Namespace) -> ReplicationPlan:
    return ReplicationPlan(
        sources=SOURCES,
        raw_dir=args.raw_dir,
        build_dir=args.build_dir,
        out=args.out,
        entry=("docs/iteration4/step-9/methodology/151-prism-replication-of-the-track2-leads.md"),
        candidate_tables=(args.shortlist, Path("ressources/track2/model_interventions.tsv")),
        shortlist=args.shortlist,
        shortlist_verdict="argue",
        in_group_codes=RMS_ONCOTREE_CODES,
        in_group_label="rhabdomyosarcoma lines",
        in_group_lineage="Soft Tissue",
        annotation_column="Aneuploidy",
        # D5 drugs E2 read out of the phenotype twin's papers; no shortlist row yet.
        extra_drugs=("DASATINIB", "QUERCETIN", "SIROLIMUS", "EVEROLIMUS", "TEMSIROLIMUS"),
        extra_drug_direction="D5",
        extra_drug_source="model_interventions.tsv (E2) nearest_approved_analogue",
        # Class completion for H087's "most statins point the same way".
        class_moa=(("HMGCR INHIBITOR", "D4"),),
        literature_moa=("MONOPOLAR SPINDLE 1 KINASE INHIBITOR", "AURORA KINASE INHIBITOR"),
        literature_note=(
            "Cohen-Sharir 2021 (PMID 33505028) reports aneuploid lines are LESS sensitive to "
            "short-term SAC-inhibitor exposure. These rows test that direction in the same "
            "5-day screen. A direction check, not a positive control: research/papers.md "
            "records that no drug-level aneuploidy-selectivity result is published to replicate"
        ),
        positive_control_drugs=("DABRAFENIB", "VEMURAFENIB", "PLX-4720", "SELUMETINIB"),
        positive_control_lineage="Skin",
        positive_control_note=(
            "RAF/MEK inhibitors against skin (melanoma) lines: BRAF V600E is mutated in about "
            "half of melanoma lines and dabrafenib/vemurafenib are licensed on that genotype, "
            "so a lineage contrast that cannot find them is broken. Same code path, same test, "
            "different group"
        ),
        control_exclude=CONTROL_EXCLUDE,
        seed=args.seed,
        resamples=args.resamples,
        negative_control_size=args.negative_control_size,
        source_note=(
            "figshare mirror; depmap.org/portal/api answers scripts with a Cloudflare "
            "challenge (research/data-sources.md §1)"
        ),
        patient_data=(
            "none. Public cell-line screens and public line annotations only. This experiment "
            "uses the genomic / public-screen source; it reads no clinical (HPO) term."
        ),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("command", choices=["fetch", "run"])
    parser.add_argument("--raw-dir", type=Path, default=Path("build/it4/track2-e4/raw"))
    parser.add_argument("--build-dir", type=Path, default=Path("build/it4/track2-e4"))
    parser.add_argument("--out", type=Path, default=Path("ressources/track2/prism_replication.tsv"))
    parser.add_argument("--shortlist", type=Path, default=Path("ressources/track2/shortlist.tsv"))
    parser.add_argument("--seed", type=int, default=20260924)
    parser.add_argument("--resamples", type=int, default=2000)
    parser.add_argument("--negative-control-size", type=int, default=200)
    args = parser.parse_args(argv)
    built = plan(args)
    return fetch_sources(built) if args.command == "fetch" else execute(built)


if __name__ == "__main__":
    raise SystemExit(main())
