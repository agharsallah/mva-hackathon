"""The three tables route R1 emits, and the manifest shape they share.

One function per table, each taking already-computed records and writing a tab-separated file
with a fixed header. Keeping the writers here rather than in the driver means the column
contract is one importable thing: a second case reuses it unchanged, and a test can assert the
header without running a pipeline.

The candidate table's columns are pinned by the iteration-5 plan so that four independent
routes produce one concatenable file.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mva.drugs import provenance
from mva.drugs.readthrough import ControlResult, Prediction
from mva.drugs.readthrough_dosage import ScenarioResult, Threshold

__all__ = [
    "CANDIDATE_COLUMNS",
    "Candidate",
    "manifest",
    "write_candidates",
    "write_dosage",
    "write_readthrough",
]

#: Pinned by ``docs/iteration5/plan.md`` - every route writes exactly these, in this order.
CANDIDATE_COLUMNS = (
    "drug_name",
    "route",
    "branch",
    "evidence_kind",
    "evidence_strength",
    "positive_control_passed",
    "source",
    "notes",
)

BRANCHES = frozenset({"stop_allele", "missense_unstable", "missense_inactive", "any"})


@dataclass(frozen=True)
class Candidate:
    """One therapeutic option, tied to the allele branch it could act on."""

    drug_name: str
    route: str
    branch: str
    evidence_kind: str
    evidence_strength: float
    positive_control_passed: str
    source: str
    notes: str

    def __post_init__(self) -> None:
        if self.branch not in BRANCHES:
            raise ValueError(f"{self.drug_name}: branch {self.branch!r} not in {sorted(BRANCHES)}")
        if not 0.0 <= self.evidence_strength <= 1.0:
            raise ValueError(f"{self.drug_name}: evidence_strength outside [0, 1]")

    def row(self) -> dict[str, Any]:
        return {
            "drug_name": self.drug_name,
            "route": self.route,
            "branch": self.branch,
            "evidence_kind": self.evidence_kind,
            "evidence_strength": f"{self.evidence_strength:.2f}",
            "positive_control_passed": self.positive_control_passed,
            "source": self.source,
            "notes": self.notes,
        }


def _write(path: Path, columns: Sequence[str], rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(columns), delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
            written += 1
    return written


READTHROUGH_COLUMNS = (
    "drug_name",
    "stop_codon",
    "plus4",
    "minus1",
    "predicted_readthrough",
    "unit",
    "evidence_level",
    "rows_behind_it",
    "contexts_behind_it",
    "control_passed",
    "control_spearman",
    "control_pair_accuracy",
    "control_contexts",
    "source",
)


def write_readthrough(
    path: Path,
    predictions: Sequence[tuple[Prediction, ControlResult | None, str]],
) -> int:
    """One row per drug: what the model predicts for this stop, and whether it may be believed."""

    def rows() -> Iterable[dict[str, Any]]:
        for prediction, control, source in predictions:
            yield {
                "drug_name": prediction.drug,
                "stop_codon": prediction.stop,
                "plus4": prediction.plus4,
                "minus1": prediction.minus1,
                "predicted_readthrough": (
                    "" if prediction.value is None else f"{prediction.value:.3f}"
                ),
                "unit": prediction.unit,
                "evidence_level": prediction.level,
                "rows_behind_it": prediction.rows,
                "contexts_behind_it": ";".join(prediction.contexts),
                "control_passed": "" if control is None else str(control.passed).lower(),
                "control_spearman": (
                    "" if control is None or control.spearman is None else f"{control.spearman:.3f}"
                ),
                "control_pair_accuracy": (
                    ""
                    if control is None or control.pair_accuracy is None
                    else f"{control.pair_accuracy:.3f}"
                ),
                "control_contexts": "" if control is None else control.contexts,
                "source": source,
            }

    return _write(path, READTHROUGH_COLUMNS, rows())


DOSAGE_COLUMNS = (
    "scenario",
    "drug",
    "stop_allele_output_pct",
    "missense_allele_output_pct",
    "total_pct_of_wild_type",
    "gain_pct_points",
    "nearest_published_genotype",
    "nearest_genotype_pct",
    "nearest_genotype_phenotype",
    "nearest_genotype_source",
    "note",
)


def write_dosage(path: Path, results: Sequence[tuple[ScenarioResult, Threshold | None]]) -> int:
    """One row per dosage scenario, with the published genotype it lands nearest."""

    def rows() -> Iterable[dict[str, Any]]:
        for result, threshold in results:
            per = dict(result.per_allele)
            yield {
                "scenario": result.label,
                "drug": result.drug,
                "stop_allele_output_pct": f"{100 * per.get('stop', 0.0):.3f}",
                "missense_allele_output_pct": f"{100 * per.get('missense', 0.0):.3f}",
                "total_pct_of_wild_type": f"{result.percent:.2f}",
                "gain_pct_points": f"{100 * result.gain:.3f}",
                "nearest_published_genotype": "" if threshold is None else threshold.label,
                "nearest_genotype_pct": "" if threshold is None else f"{threshold.percent:.1f}",
                "nearest_genotype_phenotype": "" if threshold is None else threshold.phenotype,
                "nearest_genotype_source": "" if threshold is None else threshold.source,
                "note": result.note,
            }

    return _write(path, DOSAGE_COLUMNS, rows())


def write_candidates(path: Path, candidates: Sequence[Candidate]) -> int:
    """The pinned candidate table, sorted strongest evidence first."""
    ordered = sorted(candidates, key=lambda c: (-c.evidence_strength, c.branch, c.drug_name))
    return _write(path, CANDIDATE_COLUMNS, (c.row() for c in ordered))


def manifest(
    *,
    name: str,
    built_by: str,
    entry: str,
    output_path: Path,
    rows: int,
    inputs: list[dict[str, Any]],
    parameters: dict[str, Any],
    assumptions: str,
    limitations: str,
    validation: str,
    sources: dict[str, str],
    columns: dict[str, str],
) -> dict[str, Any]:
    """The manifest shape ``ressources/track2/it4/*.provenance.json`` established."""
    envelope = provenance.envelope(name, built_by)
    envelope.update(
        {
            "entry": entry,
            "inputs": inputs,
            "output": provenance.output(output_path, rows),
            "rows": rows,
            "parameters": parameters,
            "assumptions": assumptions,
            "limitations": limitations,
            "validation": validation,
            "sources": sources,
            "columns": columns,
            "clinical_framing": (
                "research exercise; no row advises for or against giving any drug to any patient"
            ),
            "patient_data": (
                "none in this file. Sequence-derived facts are stated as codon identity, exon "
                "index, counts and fractions; no genomic position and no run of patient "
                "sequence appears"
            ),
        }
    )
    return envelope
