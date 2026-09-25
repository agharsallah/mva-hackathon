"""Turn a published wide measurement table into :class:`~mva.drugs.readthrough.Measurement` rows.

Massively parallel readthrough experiments are published in one shape: one row per premature
stop codon, a few columns describing its sequence context, and then **one column per drug**
holding the measured readthrough. This module reshapes that (a *wide* table) into the long form
the model reads (one row per context x drug), and it is parameterised by column names so a
second dataset in the same shape needs a new :class:`WideSpec`, not new code.

Two details that would otherwise be silent errors:

* **Censored values.** An assay with a ceiling reports ``>3.2``. The value is kept as its
  numeric part and the row is flagged ``censored``, because a mean over lower bounds is itself a
  lower bound and the entry has to say so.
* **Context orientation.** ``downstream`` and ``upstream`` are both read 5'->3', so the +4 base
  is the *first* character of the downstream field and the -1 base is the *last* character of
  the upstream field. :func:`load_wide` takes that as the spec's contract; a dataset that
  reverses one of them needs its own spec flag, not a guess.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from mva.drugs.readthrough import Measurement

__all__ = ["TOLEDANO_2024", "WideSpec", "load_wide"]


@dataclass(frozen=True)
class WideSpec:
    """Which columns of a wide table mean what."""

    context_column: str
    stop_column: str
    downstream_column: str
    upstream_column: str
    drug_columns: tuple[str, ...]
    unit: str
    assay: str
    source: str
    censored_marks: tuple[str, ...] = (">", "<")
    upstream_is_5_to_3: bool = True


#: Toledano, Supek & Lehner, *Nat Genet* 56:1914-1924 (2024), PMID 39174735, supplementary
#: table 3: 5,837 pathogenic premature stop codons measured in a pooled HEK293T fluorescent
#: reporter, as **percent of the no-PTC control**, under eight compounds plus untreated.
TOLEDANO_2024 = WideSpec(
    context_column="mutation_identifier",
    stop_column="stop_type",
    downstream_column="down_123nt",
    upstream_column="up_123nt",
    drug_columns=(
        "Untreated",
        "Gentamicin",
        "G418",
        "Clitocine",
        "DAP",
        "SJ6986",
        "SRI",
        "CC90009",
        "FUr",
    ),
    unit="percent_of_no_ptc_control",
    assay="pooled fluorescent reporter (sort-seq), HEK293T, 144 nt of native context",
    source="PMID:39174735",
)


def _value(raw: str, marks: tuple[str, ...]) -> tuple[float, bool] | None:
    text = raw.strip()
    if not text:
        return None
    censored = text[:1] in marks
    try:
        return float(text.lstrip("".join(marks))), censored
    except ValueError:
        return None


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def load_wide(path: Path, spec: WideSpec) -> list[Measurement]:
    """Read a wide TSV and return one :class:`Measurement` per context x drug with a value.

    A context identifier that the table reuses for two different stop codons (one protein
    position reachable by two substitutions) is suffixed with its stop, so that holding out a
    context holds out exactly one sequence context.
    """
    rows = _rows(path)
    seen: dict[str, set[str]] = {}
    for row in rows:
        seen.setdefault(row[spec.context_column].strip(), set()).add(row[spec.stop_column].strip())
    ambiguous = {name for name, stops in seen.items() if len(stops) > 1}
    out: list[Measurement] = []
    for row in rows:
        stop = row[spec.stop_column].strip()
        context = row[spec.context_column].strip()
        downstream = row[spec.downstream_column].strip()
        upstream = row[spec.upstream_column].strip()
        if not context or not downstream:
            continue
        if context in ambiguous:
            context = f"{context}({stop})"
        minus1 = (upstream[-1] if spec.upstream_is_5_to_3 else upstream[0]) if upstream else ""
        for drug in spec.drug_columns:
            parsed = _value(row.get(drug, ""), spec.censored_marks)
            if parsed is None:
                continue
            value, censored = parsed
            out.append(
                Measurement(
                    context=context,
                    stop=stop,
                    plus4=downstream[0],
                    drug=drug,
                    value=value,
                    unit=spec.unit,
                    assay=spec.assay,
                    source=spec.source,
                    minus1=minus1,
                    censored=censored,
                )
            )
    return out
