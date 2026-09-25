"""K2, the child's own safety: entry 152's two-source method, re-run on a new drug set.

*Plain words.* Entry 152 asks two independent sources about each drug: the **genome**
(PharmCAT, a pharmacogenomics caller, reading the child's callset against CPIC guidelines)
and the **phenotype** (OnSIDES label adverse effects matched to the child's own HPO terms).
A drug is a K2 ``fail`` only when **both** flag it - the same rule as entry 152. One source
flagging is a ``caution``; neither is ``pass``, which means *these two sources are silent*,
never *safe*.

This module does not re-implement that method. It builds the command lines for
``tools/patient_safety.py`` (``labels``, ``faers``, ``table``) and reads the table it writes.
The PharmCAT result is reused as is: the caller never re-runs PharmCAT.

The FAERS pairs (paediatric spontaneous-report counts, informational, not part of the flag)
are chosen by a rule, never by hand: every drug in scope x every MedDRA term the HPO mapping
marks ``used_for_flag = yes``.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .checks import Check

__all__ = [
    "BOTH_FLAG",
    "SafetyPlan",
    "faers_pairs",
    "k2_from_table",
    "mapped_terms",
]

#: ``mva.drugs.patient_safety.combined_flag``'s wording when both sources flag.
BOTH_FLAG = "both sources flag a question"


def mapped_terms(mapping: Sequence[Mapping[str, str]]) -> list[str]:
    """The MedDRA preferred terms the mapping uses for the flag, upper-case, first-seen order."""
    out: list[str] = []
    for row in mapping:
        name = (row.get("meddra_name") or "").strip()
        if row.get("used_for_flag") == "yes" and name and name != "NA" and name.upper() not in out:
            out.append(name.upper())
    return out


def faers_pairs(drugs: Iterable[str], terms: Sequence[str]) -> list[str]:
    """``drug=TERM`` for every drug x every term, in the ``--pair`` syntax of ``faers``."""
    return [f"{drug.lower()}={term}" for drug in drugs for term in terms]


@dataclass(frozen=True)
class SafetyPlan:
    """The three ``tools/patient_safety.py`` invocations, as argv tails (no interpreter)."""

    work: Path
    drug_table: str
    onsides: Path
    mapping: Path
    out: Path
    entry: str
    sources: str
    faers: tuple[str, ...]
    aliases: tuple[str, ...] = ()
    extra_genes: tuple[str, ...] = ()
    per_candidate: int = 5

    def labels(self) -> list[str]:
        argv = ["--work", str(self.work), "labels", "--onsides", str(self.onsides)]
        argv += ["--mapping", str(self.mapping), "--drug-table", self.drug_table]
        argv += ["--per-candidate", str(self.per_candidate)]
        for alias in self.aliases:
            argv += ["--alias", alias]
        return argv

    def faers_argv(self) -> list[str]:
        argv = ["--work", str(self.work), "faers"]
        for pair in self.faers:
            argv += ["--pair", pair]
        return argv

    def table(self) -> list[str]:
        argv = ["--work", str(self.work), "table", "--drug-table", self.drug_table]
        argv += ["--mapping", str(self.mapping), "--out", str(self.out)]
        argv += ["--entry", self.entry, "--sources", self.sources]
        for gene in self.extra_genes:
            argv += ["--extra-gene", gene]
        return argv


def k2_from_table(path: Path) -> dict[str, Check]:
    """``{query name: K2 check}`` from a ``candidate_safety.tsv`` written by ``table``."""
    out: dict[str, Check] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            flag = row["combined_flag"]
            total = int(row.get("labels_total") or 0)
            silent = "" if total else "; OnSIDES holds no label for this name"
            phenotype = row["phenotype_flag_reason"] or "none"
            detail = f"{flag} (genome: {row['genome_call']}; phenotype: {phenotype}{silent})"
            if flag == BOTH_FLAG:
                out[row["drug"].lower()] = Check("fail", detail)
            elif row["genome_flag"] == "yes" or row["phenotype_flag"] == "yes":
                out[row["drug"].lower()] = Check("caution", detail)
            else:
                out[row["drug"].lower()] = Check("pass", detail)
    return out
