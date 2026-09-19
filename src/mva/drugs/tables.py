"""The five TSVs the snapshot writes: their columns, and how a row is serialised.

One place owns the column order and the scalar spelling, so the writer, the manifest and
any reader cannot drift. Three conventions, applied uniformly:

* a **list** field is joined with ``|`` — TSV has no nesting and a second delimiter is
  cheaper to split than a quoted JSON blob in a column;
* a **boolean** is ``true``/``false``;
* an **unknown** is the empty string, and it means *unknown*: ``fda_label`` empty is "not
  checked", not "no label". The manifest says so too.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

__all__ = [
    "CANDIDATE_COLUMNS",
    "DECOY_COMPARISON_COLUMNS",
    "EVIDENCE_COLUMNS",
    "LADDER_COLUMNS",
    "LITERATURE_COLUMNS",
    "MECHLIT_COLUMNS",
    "PATHWAY_COLUMNS",
    "PEDIATRIC_TRIAL_COLUMNS",
    "SHORTLIST_COLUMNS",
    "TARGET_COLUMNS",
    "TRANSFER_COMPARISON_COLUMNS",
    "TRIAL_COLUMNS",
    "cell",
    "write_tsv",
]

TARGET_COLUMNS = ("symbol", "role", "direction_ids", "pathways", "uniprot")

CANDIDATE_COLUMNS = (
    "drug_name",
    "drug_id",
    "target_symbol",
    "target_role",
    "direction_ids",
    "source",
    "interaction_or_moa",
    "action_type",
    "max_phase",
    "approved",
    "fda_label",
    "pmids",
    "first_approval",
    "atc",
)

#: ``query`` is this repository's addition to the contracted trial row: it names which of
#: the snapshot's queries returned the study, so a reader can tell a disease hit from a
#: per-drug hit without re-running anything.
TRIAL_COLUMNS = (
    "nct_id",
    "title",
    "phase",
    "overall_status",
    "conditions",
    "interventions",
    "start_date",
    "study_type",
    "query",
)

#: ``query`` likewise: which of the three literature query families found this paper.
LITERATURE_COLUMNS = ("pmid", "title", "journal", "year", "doi", "query")

PATHWAY_COLUMNS = ("st_id", "display_name", "matched", "n_participants")


def cell(value: Any) -> str:
    """One field, TSV-safe: lists joined with ``|``, booleans lower-case, ``None`` empty.

    Tabs, newlines and carriage returns inside a value are replaced by a space. A trial
    title carrying a newline would otherwise split one record into two, which no reader
    could detect after the fact.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple, set)):
        text = "|".join(cell(item) for item in value)
    else:
        text = str(value)
    for bad in ("\t", "\r\n", "\n", "\r"):
        text = text.replace(bad, " ")
    return text.strip()


def write_tsv(path: Path, columns: Sequence[str], rows: Iterable[dict[str, Any]]) -> int:
    """Write a header and one line per row. Returns the row count, header excluded."""
    path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write("\t".join(columns) + "\n")
        for row in rows:
            stream.write("\t".join(cell(row.get(name)) for name in columns) + "\n")
            written += 1
    return written


# ── step-7 enrichment tables (iteration 2) ───────────────────────────────────────────

#: Curated by a person, one cited result per row. ``proxy`` true means the cited result is
#: for a same-axis compound (``proxy_of``) rather than the approved molecule itself.
EVIDENCE_COLUMNS = (
    "drug_name",
    "direction_id",
    "rung",
    "model",
    "pmid",
    "target",
    "claim",
    "proxy",
    "proxy_of",
)

#: One PubMed question per approved drug per family: how much has been written about the
#: drug *and* this mechanism, and about the drug *and* the tumour context.
MECHLIT_COLUMNS = ("drug_name", "family", "term", "hits", "pmids")

#: A registered study of an approved drug that admits children, in any indication.
PEDIATRIC_TRIAL_COLUMNS = (
    "drug_name",
    "nct_id",
    "title",
    "phase",
    "overall_status",
    "conditions",
    "min_age",
    "max_age",
    "std_ages",
    "query",
)

#: One drug on one direction, its rung, and every test behind the rung - automated and
#: curated printed side by side, never merged silently.
LADDER_COLUMNS = (
    "drug_name",
    "direction_id",
    "rung",
    "rung_label",
    "automated_rung",
    "curated_rung",
    "approved",
    "fda_label",
    "pediatric_label",
    "trial_in_context",
    "pediatric_trial",
    "mechanism_hits",
    "context_hits",
    "curated_pmids",
    "proxy",
    "targets",
    "action_types",
    "flags",
)

#: The ranked shortlist and the do-not table share one shape; ``verdict`` tells them apart.
SHORTLIST_COLUMNS = (
    "rank",
    "drug_name",
    "direction_id",
    "rung",
    "verdict",
    "why",
    "pediatric_evidence",
    "curated_pmids",
    "targets",
    "flags",
)

#: One row per **case** in a transfer comparison: the real card, and the same pipeline run
#: unchanged on a different disease with its own gene, phenotype annotation and tumour.
#: Only the automated rungs are comparable - a transfer card carries no curated evidence,
#: which is why ``curated_rows`` is printed rather than folded into the rung counts.
TRANSFER_COMPARISON_COLUMNS = (
    "case",
    "role",
    "gene",
    "disease",
    "tumour_context",
    "card_version",
    "targets",
    "candidate_rows",
    "approved_drugs",
    "drugs_rung_5",
    "drugs_rung_4",
    "drugs_rung_3",
    "drugs_rung_2",
    "drugs_rung_1",
    "shortlist",
    "do_not",
    "curated_rows",
    "live_requests",
    "cached_replies",
    "wall_seconds",
    "warm_seconds",
)

#: The real card's directions against each decoy card's approved drug set.
DECOY_COMPARISON_COLUMNS = (
    "decoy",
    "direction_id",
    "direction_approved",
    "decoy_approved",
    "shared",
    "jaccard",
    "shared_drugs",
    "decoy_with_context_trial",
    "decoy_with_fda_label",
)
