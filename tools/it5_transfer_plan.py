"""Which files, tables and controls belong to each route of the iteration-5 transfer check.

Configuration, not code: it names the two cases' file sets so that
:mod:`tools.it5_transfer_summary` can count lines and read verdicts without knowing anything
about any route. A third case is a new entry here, not new code.

Each route declares three things that differ between routes and cannot be inferred:

* which files are **configuration** (a case card) and which are **shared code**;
* which added lines are a **new capability** rather than a portability cost, named by the
  function that holds them, so the split is auditable;
* which **kind of positive control** the route has — the three routes control themselves in
  three different ways, and the reader that understands each is named by ``control_kind``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["COLUMNS", "PLAN", "RoutePlan"]


@dataclass(frozen=True)
class RoutePlan:
    """One route's file sets and the artefacts that prove its transfer ran."""

    route: str
    name: str
    config_files: tuple[str, ...]
    code_files: tuple[str, ...]
    #: ``file -> (function name, what it adds)``: lines inside these functions are counted as
    #: a new capability rather than as a portability cost.
    new_capability: dict[str, tuple[str, str]] = field(default_factory=dict)
    #: Whole files that hold a new capability, counted in full rather than as a transfer cost.
    new_capability_files: tuple[str, ...] = ()
    #: Files created **only** to keep a module under the 400-line gate after the change:
    #: existing code moved, no behaviour added. Counted and named, never charged to the transfer.
    moved_files: tuple[str, ...] = ()
    #: The first case's tables, whose digests must not move.
    baseline_tables: tuple[str, ...] = ()
    #: The transferred case's tables, each read with its manifest.
    transfer_tables: tuple[str, ...] = ()
    control_from: str = ""
    #: Which reader in :data:`CONTROL_READERS` understands this route's control artefact.
    #: The three routes control themselves in three different ways, so the kind is declared.
    control_kind: str = "manifest_recall"


PLAN: tuple[RoutePlan, ...] = (
    RoutePlan(
        route="R1",
        name="readthrough context model + allele dosage",
        config_files=(
            "src/mva/drugs/readthrough_case_blm.py",
            "ressources/track2/it5/transfer/r1/blm_allele_note.md",
        ),
        code_files=(
            "tools/it5_readthrough.py",
            "src/mva/drugs/readthrough_manifests.py",
            "src/mva/drugs/readthrough_case.py",
            "src/mva/drugs/readthrough_dataset.py",
        ),
        new_capability_files=("src/mva/drugs/readthrough_external.py",),
        moved_files=("src/mva/drugs/readthrough_facts.py",),
        new_capability={
            "tools/it5_readthrough.py": (
                "holdout",
                "the external check: refit without a measured context, predict it, compare",
            )
        },
        baseline_tables=(
            "ressources/track2/it5/readthrough.tsv",
            "ressources/track2/it5/allele_dosage.tsv",
            "ressources/track2/it5/readthrough_candidates.tsv",
        ),
        transfer_tables=(
            "ressources/track2/it5/transfer/r1/readthrough.tsv",
            "ressources/track2/it5/transfer/r1/readthrough_external_check.tsv",
            "ressources/track2/it5/transfer/r1/allele_dosage.tsv",
        ),
        control_from="ressources/track2/it5/transfer/r1/readthrough.tsv",
        control_kind="held_out_per_drug",
    ),
    RoutePlan(
        route="R2",
        name="proliferation-corrected drug proteomics",
        config_files=(),
        code_files=("tools/it5_proteome.py",),
        moved_files=("src/mva/drugs/proteome_baseline.py",),
        baseline_tables=(
            "ressources/track2/it5/proteome_hits.tsv",
            "ressources/track2/it5/proteome_control.tsv",
            "ressources/track2/it5/protein_candidates.tsv",
        ),
        transfer_tables=(
            "ressources/track2/it5/transfer/r2/proteome_hits.tsv",
            "ressources/track2/it5/transfer/r2/proteome_control.tsv",
            "ressources/track2/it5/transfer/r2/protein_candidates.tsv",
        ),
        control_from="ressources/track2/it5/transfer/r2/proteome_hits.tsv",
        control_kind="dataset_interpretable",
    ),
    RoutePlan(
        route="R3",
        name="quote-verified literature mining",
        config_files=("tools/it5_litmine_params_blm.py",),
        code_files=(
            "tools/it5_litmine.py",
            "tools/it5_litmine_params.py",
            "src/mva/drugs/litmine_verify.py",
            "src/mva/drugs/litmine_translate.py",
        ),
        baseline_tables=(
            "ressources/track2/it5/litmine_interventions.tsv",
            "ressources/track2/it5/literature_candidates.tsv",
            "ressources/track2/it5/litmine_mva_exposures.tsv",
        ),
        transfer_tables=(
            "ressources/track2/it5/transfer/r3/litmine_corpus.tsv",
            "ressources/track2/it5/transfer/r3/litmine_interventions.tsv",
            "ressources/track2/it5/transfer/r3/litmine_mva_exposures.tsv",
            "ressources/track2/it5/transfer/r3/literature_candidates.tsv",
        ),
        control_from=("ressources/track2/it5/transfer/r3/litmine_interventions.provenance.json"),
    ),
)

COLUMNS = [
    "route",
    "name",
    "new_config_files",
    "config_lines",
    "shared_code_files_changed",
    "code_lines_added",
    "code_lines_removed",
    "portability_and_refactor_lines",
    "new_capability_lines_added",
    "moved_lines",
    "code_change_needed",
    "first_case_outputs_identical",
    "positive_control_passed",
    "positive_control",
    "transfer_output_rows",
    "wall_clock_s",
]
