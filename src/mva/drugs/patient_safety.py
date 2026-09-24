"""Is a candidate drug safe *for this patient* — asked of two sources that share nothing.

Track 2's shortlist is built from mechanism. This module asks the question a treating team
would ask next, and asks it twice over inputs with no common ancestor:

* **the patient's own genome** — pharmacogenomic gene calls (PharmCAT/CPIC), read here as
  *actionability words* ("normal function", "decreased function", "no call"), never as a
  diplotype or a position;
* **the patient's own clinical terms** — HPO terms mapped to label adverse-effect terms
  (MedDRA), counted over regulatory labels and compared with a matched set of other drugs.

A drug flagged by both is the strongest statement this step can make. A drug flagged by
neither is **not** "safe": it is *unflagged by these two sources*, and
:data:`UNFLAGGED_WORDING` is the only phrase this module will emit for that state, so no
caller can accidentally promote silence into reassurance.

Nothing here advises for or against giving any drug to any patient. A row is a question
for a treating team, with its evidence attached.

**Case-agnostic by construction.** The drug list, the gene→drug map, the HPO→MedDRA
mapping and the label table all arrive as arguments. Swap them and the same code answers
for another patient, another disease and another shortlist.
"""

from __future__ import annotations

import csv
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

#: The only phrase allowed for "neither source flagged it". Spelled out once so that a
#: report, a figure legend and a table cell cannot drift into "safe".
UNFLAGGED_WORDING = "unflagged by these two sources (not evidence of safety)"

#: Actionability words a gene call may carry. `no call` is a *result* -- it says the data
#: could not answer -- and is never silently treated as "normal".
NO_CALL = "no call"
NORMAL = "normal"

#: Phenotype words that count as "would change prescribing if confirmed". Matched
#: case-insensitively as substrings, so "Intermediate Metabolizer" and "Decreased
#: Function" both land.
ACTIONABLE_WORDS: tuple[str, ...] = (
    "poor",
    "intermediate",
    "rapid",
    "ultrarapid",
    "decreased",
    "increased",
    "possible",
    "uncertain",
    "indeterminate",
    "deficient",
    "malignant hyperthermia",
)


@dataclass(frozen=True)
class GeneCall:
    """One pharmacogene, as far as this patient's callset could answer.

    ``phenotype`` is the actionability word (e.g. ``"Poor Metabolizer"``). ``observed`` is
    ``True`` only when the call rests on positions that were genotyped; a call produced by
    assuming absent positions are reference is ``observed=False`` and must be reported as
    an assumption everywhere it appears.
    """

    gene: str
    phenotype: str
    observed: bool
    positions_total: int = 0
    positions_called: int = 0
    note: str = ""
    assumed_phenotype: str = ""

    @property
    def callable_fraction(self) -> float:
        """Share of this gene's definition positions that the callset could answer."""
        return self.positions_called / self.positions_total if self.positions_total else 0.0

    @property
    def is_no_call(self) -> bool:
        """True when the gene has no usable phenotype at all."""
        p = self.phenotype.strip().lower()
        return not p or p in {NO_CALL, "no result", "indeterminate/no result", "n/a"}

    @property
    def is_actionable(self) -> bool:
        """True when the phenotype word is one that would change prescribing."""
        if self.is_no_call:
            return False
        p = self.phenotype.lower()
        return any(word in p for word in ACTIONABLE_WORDS)


@dataclass(frozen=True)
class LabelMatch:
    """How often a drug's labels carry an adverse effect matching the patient's terms."""

    drug: str
    labels_total: int
    labels_matched: int
    effects: tuple[str, ...] = ()
    per_term: Mapping[str, int] = field(default_factory=dict)

    @property
    def rate(self) -> float:
        """Share of this drug's labels carrying at least one matching effect."""
        return self.labels_matched / self.labels_total if self.labels_total else 0.0


@dataclass(frozen=True)
class SafetyRow:
    """One candidate, with what each source said and what the two together say."""

    drug: str
    direction: str
    genes: tuple[str, ...]
    genome_call: str
    genome_flag: bool
    cpic_recommendation: str
    label_effects: str
    labels_matched: int
    labels_total: int
    comparison_rate: float
    phenotype_flag: bool
    faers_signal: str
    combined_flag: str
    sources: str
    phenotype_flag_reason: str = ""

    def as_row(self) -> dict[str, str]:
        """The TSV shape: every field a string, no coordinate, no diplotype."""
        return {
            "drug": self.drug,
            "direction": self.direction,
            "pgx_genes": "|".join(self.genes),
            "genome_call": self.genome_call,
            "genome_flag": "yes" if self.genome_flag else "no",
            "cpic_recommendation": self.cpic_recommendation,
            "phenotype_matched_effects": self.label_effects,
            "labels_matched": str(self.labels_matched),
            "labels_total": str(self.labels_total),
            "shortlist_label_rate": f"{(self.labels_matched / self.labels_total):.3f}"
            if self.labels_total
            else "NA",
            "comparison_set_rate": f"{self.comparison_rate:.3f}",
            "phenotype_flag": "yes" if self.phenotype_flag else "no",
            "phenotype_flag_reason": self.phenotype_flag_reason,
            "faers_paediatric_signal": self.faers_signal,
            "combined_flag": self.combined_flag,
            "sources": self.sources,
        }


#: Column order of ``candidate_safety.tsv``.
COLUMNS: tuple[str, ...] = (
    "drug",
    "direction",
    "pgx_genes",
    "genome_call",
    "genome_flag",
    "cpic_recommendation",
    "phenotype_matched_effects",
    "labels_matched",
    "labels_total",
    "shortlist_label_rate",
    "comparison_set_rate",
    "phenotype_flag",
    "phenotype_flag_reason",
    "faers_paediatric_signal",
    "combined_flag",
    "sources",
)


def wilson_interval(successes: int, trials: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion.

    Wilson rather than the normal approximation because several drugs here have single-digit
    label counts, where the normal interval runs past 0 and 1 and stops meaning anything.
    """
    if trials <= 0:
        return (0.0, 0.0)
    p = successes / trials
    denom = 1.0 + z * z / trials
    centre = (p + z * z / (2 * trials)) / denom
    half = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def combined_flag(genome_flag: bool, phenotype_flag: bool) -> str:
    """The two-source verdict, in words that cannot be misread as clinical advice."""
    if genome_flag and phenotype_flag:
        return "both sources flag a question"
    if genome_flag:
        return "genome flags a question"
    if phenotype_flag:
        return "phenotype flags a question"
    return UNFLAGGED_WORDING


def genes_for_drug(drug: str, drug_genes: Mapping[str, Sequence[str]]) -> tuple[str, ...]:
    """The pharmacogenes tied to ``drug``, matched case-insensitively."""
    lowered = {k.lower(): tuple(v) for k, v in drug_genes.items()}
    return lowered.get(drug.lower(), ())


def describe_genome(genes: Sequence[str], calls: Mapping[str, GeneCall]) -> tuple[str, bool, str]:
    """Collapse a drug's gene calls into one phrase, a flag, and a caveat.

    The flag is raised by an **actionable phenotype**, and separately by a **no call on a
    gene that has a guideline** — because "we could not tell" is itself a question for a
    treating team, and is the honest reading of a variant-only callset.
    """
    if not genes:
        return ("no pharmacogene tied to this drug", False, "")
    parts: list[str] = []
    flag = False
    caveats: list[str] = []
    for gene in genes:
        call = calls.get(gene)
        if call is None:
            parts.append(f"{gene}: not covered by the caller")
            flag = True
            caveats.append(f"{gene} is outside the caller's gene set; needs direct genotyping")
            continue
        if call.is_no_call:
            assumed = call.assumed_phenotype or "nothing"
            parts.append(f"{gene}: no call (absent-to-ref would give: {assumed})")
            flag = True
            caveats.append(f"{gene} {call.note}" if call.note else f"{gene} uncallable")
            continue
        parts.append(f"{gene}: {call.phenotype}")
        if call.is_actionable:
            flag = True
    return ("; ".join(parts), flag, "; ".join(caveats))


def build_rows(
    drugs: Sequence[tuple[str, str]],
    drug_genes: Mapping[str, Sequence[str]],
    calls: Mapping[str, GeneCall],
    matches: Mapping[str, LabelMatch],
    recommendations: Mapping[str, str],
    comparison_rate: float,
    faers: Mapping[str, str] | None = None,
    sources: str = "",
    exact_effects: Sequence[str] = (),
) -> list[SafetyRow]:
    """Assemble one row per candidate. Pure: every input is already resolved.

    The phenotype flag has two independent triggers, and the row says which fired:

    * **rate** — the drug's share of labels carrying a mapped effect exceeds the matched
      comparison set's. This is the pre-registered test (H091);
    * **exact term** — the drug's label carries a term that *is* one of the patient's own
      phenotypes (tier ``exact`` in the mapping), at any rate. Added after the furosemide
      positive control showed the rate test misses a rare but exactly-matching effect:
      5 of 164 furosemide labels name nephrocalcinosis, a rate far below any base rate,
      and it is the one published drug–phenotype collision for this patient (PMID 35348900).
    """
    faers = faers or {}
    exact = {e.lower() for e in exact_effects}
    rows: list[SafetyRow] = []
    for drug, direction in drugs:
        genes = genes_for_drug(drug, drug_genes)
        phrase, genome_flag, caveat = describe_genome(genes, calls)
        match = matches.get(drug.lower())
        if match is None:
            match = LabelMatch(drug=drug, labels_total=0, labels_matched=0)
        by_rate = match.labels_matched > 0 and match.rate > comparison_rate
        hit_exact = sorted({e for e in match.effects if e.lower() in exact})
        phenotype_flag = by_rate or bool(hit_exact)
        reason = "; ".join(
            part
            for part in (
                f"label rate {match.rate:.2f} > comparison {comparison_rate:.2f}"
                if by_rate
                else "",
                "exact phenotype term on label: " + ", ".join(hit_exact) if hit_exact else "",
            )
            if part
        )
        rows.append(
            SafetyRow(
                drug=drug,
                direction=direction,
                genes=genes,
                genome_call=phrase + (f" [{caveat}]" if caveat else ""),
                genome_flag=genome_flag,
                cpic_recommendation=recommendations.get(drug.lower(), "no CPIC guideline"),
                label_effects="|".join(match.effects) if match.effects else "none",
                labels_matched=match.labels_matched,
                labels_total=match.labels_total,
                comparison_rate=comparison_rate,
                phenotype_flag=phenotype_flag,
                faers_signal=faers.get(drug.lower(), "not queried"),
                combined_flag=combined_flag(genome_flag, phenotype_flag),
                sources=sources,
                phenotype_flag_reason=reason,
            )
        )
    return rows


def write_table(rows: Iterable[SafetyRow], path: Path) -> int:
    """Write ``candidate_safety.tsv``; returns the number of rows written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(COLUMNS), delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow(row.as_row())
            written += 1
    return written


def read_mapping(path: Path) -> list[dict[str, str]]:
    """Read ``hpo_to_adverse_terms.tsv``. Every row, including the excluded ones."""
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def active_terms(mapping: Sequence[Mapping[str, str]]) -> dict[str, tuple[str, str]]:
    """The MedDRA ids actually used for the flag → (term name, the HPO label it serves)."""
    return {
        row["meddra_id"]: (row["meddra_name"], row["hpo_label"])
        for row in mapping
        if row.get("used_for_flag") == "yes" and row.get("meddra_id") not in (None, "", "NA")
    }
