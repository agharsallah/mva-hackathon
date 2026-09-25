"""One provenance manifest per table route R1 writes.

The driver's job is to run stages; deciding what a manifest must name — which inputs with which
digests, which parameters, which assumptions and limitations — is a separate concern and lives
here, so that the three manifests stay consistent with each other and a review of what is
recorded is a review of one file.

Every function returns a plain dict; :func:`mva.drugs.provenance.write` puts it on disk.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mva.drugs import provenance
from mva.drugs import readthrough_notes as notes
from mva.drugs.readthrough_tables import manifest

__all__ = [
    "candidates_manifest",
    "dosage_manifest",
    "external_check_manifest",
    "readthrough_manifest",
]


def _file(path: str | Path, role: str, **extra: Any) -> dict[str, Any]:
    """One input row: repo-relative path, digest, and what it was read for."""
    path = Path(path)
    row: dict[str, Any] = {"file": path.as_posix(), "role": role}
    if path.is_file():
        row["sha256"] = provenance.digest(path)[0]
    row.update(extra)
    return row


def readthrough_manifest(
    *,
    entry: str,
    output_path: Path,
    rows: int,
    workbook: Path,
    workbook_url: str,
    stop_facts: Path,
    parameters: dict[str, Any],
    case_notes: Any = None,
) -> dict[str, Any]:
    """The predicted-readthrough table: a public measurement set plus this case's stop context.

    ``case_notes`` is the case card's prose block (same attribute names as
    :mod:`mva.drugs.readthrough_notes`); ``None`` keeps this repo's first case.
    """
    n = case_notes or notes
    return manifest(
        name="readthrough",
        built_by="tools/it5_readthrough.py predict",
        entry=entry,
        output_path=output_path,
        rows=rows,
        inputs=[
            _file(
                workbook,
                (
                    "Toledano et al., Nat Genet 56:1914-1924 (2024), PMID 39174735, "
                    "supplementary table 3: 5,837 measured premature stop codons x 8 compounds, "
                    "as percent of the no-PTC control. Gitignored under build/: a rebuildable "
                    "download, not a source file"
                ),
                url=workbook_url,
                citation="PMID:39174735",
            ),
            _file(
                stop_facts,
                (
                    "the case's stop codon, its +4 and -1 bases and its NMD verdict (gitignored: "
                    "the file holds transcript offsets)"
                ),
            ),
        ],
        parameters=parameters,
        assumptions=n.READTHROUGH_ASSUMPTIONS,
        limitations=n.READTHROUGH_LIMITATIONS,
        validation=(
            "every drug's row carries its own held-out control, on a benchmark panel named "
            "before the run and on a random fifth of contexts; a row whose control failed is "
            "not interpretable as a prediction. The dataset's own untreated column runs through "
            "the identical pipeline as a negative control and must fail"
        ),
        sources=n.SOURCES,
        columns=n.READTHROUGH_COLUMN_NOTES,
    )


def dosage_manifest(
    *,
    entry: str,
    output_path: Path,
    rows: int,
    stop_facts: Path,
    readthrough_table: Path,
    published_alleles: Path,
    parameters: dict[str, Any],
    case_notes: Any = None,
) -> dict[str, Any]:
    """The dosage-scenario table: what each allele contributes and what a drug could add."""
    n = case_notes or notes
    return manifest(
        name="allele_dosage",
        built_by="tools/it5_readthrough.py dosage",
        entry=entry,
        output_path=output_path,
        rows=rows,
        inputs=[
            _file(
                stop_facts, "the NMD verdict and truncation, which set the stop allele's factors"
            ),
            _file(
                readthrough_table,
                "the readthrough fraction used in the treated scenarios; only rows whose "
                "positive control passed are read",
            ),
            _file(
                published_alleles,
                "the published MVA missense alleles behind the unstable/inactive branches",
                citation="PMID:20516114",
            ),
        ],
        parameters=parameters,
        assumptions=n.DOSAGE_ASSUMPTIONS,
        limitations=n.DOSAGE_LIMITATIONS,
        validation=n.DOSAGE_VALIDATION,
        sources=n.SOURCES,
        columns=n.DOSAGE_COLUMN_NOTES,
    )


def candidates_manifest(
    *,
    entry: str,
    output_path: Path,
    rows: int,
    readthrough_table: Path,
    hpo_map: Path,
    route: str = "R1",
) -> dict[str, Any]:
    """The pinned candidate table: model rows, literature rows, and the child's own terms."""
    return manifest(
        name="readthrough_candidates",
        built_by="tools/it5_readthrough.py dosage",
        entry=entry,
        output_path=output_path,
        rows=rows,
        inputs=[
            _file(
                readthrough_table,
                "which compounds have a prediction for this stop context and a passing control",
            ),
            _file(
                hpo_map,
                "the child's clinical terms as the adverse-effect axes they map to, used to "
                "decide which candidates collide with this child's own phenotype",
            ),
        ],
        parameters={"rubric": notes.STRENGTH_RUBRIC, "route": route},
        assumptions=notes.CANDIDATE_ASSUMPTIONS,
        limitations=notes.CANDIDATE_LIMITATIONS,
        validation=(
            "positive_control_passed repeats the held-out control of the method behind the row; "
            "'n/a' marks a literature statement, which no model produced"
        ),
        sources=notes.SOURCES,
        columns=notes.CANDIDATE_COLUMN_NOTES,
    )


def external_check_manifest(
    *,
    entry: str,
    output_path: Path,
    rows: int,
    measurements: Path,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    """The external check: a published measurement of the case's own allele, held out."""
    return manifest(
        name="readthrough_external_check",
        built_by="tools/it5_readthrough.py holdout",
        entry=entry,
        output_path=output_path,
        rows=rows,
        inputs=[
            _file(
                measurements,
                (
                    "Toledano et al., Nat Genet 56:1914-1924 (2024), PMID 39174735: measured "
                    "readthrough. The held-out context's rows are removed from the fit and "
                    "used only as the answer"
                ),
                citation="PMID:39174735",
            )
        ],
        parameters=parameters,
        assumptions=(
            "the reporter assay's percent-of-no-PTC scale is comparable across contexts, so a "
            "prediction learned on other contexts is on the same scale as this one"
        ),
        limitations=(
            "one context per row group and a handful of compounds; a rank correlation over so "
            "few points is weak evidence, and censored (>) measurements are lower bounds"
        ),
        validation=(
            "the context is removed from the model entirely before it is predicted, so nothing "
            "about it can leak into its own prediction"
        ),
        sources={
            "literature": "PMID:39174735 supplementary table 3",
            "clinical": "none",
            "genomic": "none: a published allele of another person's gene",
        },
        columns={
            "predicted": "group mean from every other context, same compound",
            "measured": "the held-out measurement",
            "backoff_level": "which key answered: stop+4-1, stop+4, stop or drug",
        },
    )
