"""Run every stage once and land five tables, five manifests and one index.

``write_snapshot`` is the whole Track 2 data layer as one function: card in, and out come

``targets.tsv``          the seed + pathway target set, with why each gene is in it
``drug_candidates.tsv``  every drug any source ties to any of those targets
``trials.tsv``           the trial activity behind the approved ones
``literature.tsv``       the publications behind the gene, the pathway and each direction
``pathways.tsv``         every Reactome pathway the expansion walked, kept or not
``snapshot.json``        the counts, per table and per source, plus the card version

Each TSV gets a ``<name>.provenance.json`` beside it in the manifest shape the repository
already uses for reference tables. Nothing here is committed to git by this function; the
caller decides. The HTTP cache is under ``build/`` and is gitignored.

Every source gets its **own** fetcher so a manifest can attribute replies to the API they
came from, and so each API's politeness interval is its own — NCBI's 3 requests/second is
not ClinicalTrials.gov's problem.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import provenance, queries, tables
from .cache import DEFAULT_CACHE_DIR, Fetcher
from .candidates import Candidate, Sources, gather
from .mechanism import DEFAULT_CARD, MechanismCard, load
from .pathway import PATHWAY_PATTERN, Expansion, expand, rule_text
from .sources import chembl, clinicaltrials, dgidb, openfda, opentargets, pubmed

__all__ = ["DEFAULT_OUT_DIR", "Snapshot", "build_fetchers", "write_snapshot"]

#: Where the committed Track 2 tables live, beside the card that produced them.
DEFAULT_OUT_DIR = Path("ressources/track2")

BUILT_BY = "mva-drugs snapshot"

#: Politeness interval per API, in seconds between *live* calls. NCBI documents 3/s
#: without a key; openFDA documents 240/min; the rest state no published limit and get a
#: conservative default rather than an assumed allowance.
INTERVALS: dict[str, float] = {
    "opentargets": 0.20,
    "chembl": 0.25,
    "dgidb": 0.50,
    "reactome": 0.25,
    "clinicaltrials": 0.25,
    "pubmed": 0.34,
    "openfda": 0.30,
}

#: The endpoint and one-line role each source plays, for the manifest input rows.
ENDPOINTS: dict[str, tuple[str, str]] = {
    "opentargets": (opentargets.ENDPOINT, "integrated target-drug-disease rows and clinical stage"),
    "chembl": (chembl.BASE, "mechanism of action, clinical phase, first approval, ATC class"),
    "dgidb": (dgidb.ENDPOINT, "aggregated drug-gene interaction edges over ~40 curated sources"),
    "reactome": ("https://reactome.org/ContentService", "pathway membership, for target expansion"),
    "clinicaltrials": (clinicaltrials.ENDPOINT, "registered trial activity per disease and drug"),
    "pubmed": (pubmed.BASE, "the literature behind the gene, the pathway and each direction"),
    "openfda": (openfda.ENDPOINT, "current US drug labelling, the second evidence of approval"),
}


@dataclass
class Snapshot:
    """What one run produced: the tables in memory, plus the paths and counts written."""

    card: MechanismCard
    expansion: Expansion
    candidates: list[Candidate]
    trials: list[dict[str, Any]] = field(default_factory=list)
    literature: list[dict[str, Any]] = field(default_factory=list)
    trial_log: list[dict[str, Any]] = field(default_factory=list)
    literature_log: list[dict[str, Any]] = field(default_factory=list)
    counts: dict[str, Any] = field(default_factory=dict)
    written: list[str] = field(default_factory=list)

    @property
    def approved(self) -> list[Candidate]:
        return [c for c in self.candidates if c.approved]


def build_fetchers(
    cache_dir: Path = DEFAULT_CACHE_DIR, *, refresh: bool = False
) -> dict[str, Fetcher]:
    """One :class:`~mva.drugs.cache.Fetcher` per source, each with its own interval."""
    return {
        name: Fetcher(source=name, cache_dir=cache_dir, min_interval_s=interval, refresh=refresh)
        for name, interval in INTERVALS.items()
    }


def write_snapshot(
    card_path: Path = DEFAULT_CARD,
    out_dir: Path = DEFAULT_OUT_DIR,
    *,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    refresh: bool = False,
    pattern: re.Pattern[str] = PATHWAY_PATTERN,
    progress: Callable[[str], None] | None = None,
) -> Snapshot:
    """Run every stage and write every file. Returns the snapshot with its counts."""
    say = progress or (lambda _line: None)
    card = load(card_path)
    fetchers = build_fetchers(cache_dir, refresh=refresh)
    try:
        say(f"card {card.path} v{card.version}: {card.gene_symbol} / {card.disease_query}")
        say("stage 1/4  target set")
        expansion = expand(card, fetchers["reactome"], pattern=pattern, progress=say)

        say("stage 2/4  drug candidates")
        found = gather(
            expansion.targets,
            Sources(
                opentargets=fetchers["opentargets"],
                chembl=fetchers["chembl"],
                dgidb=fetchers["dgidb"],
                openfda=fetchers["openfda"],
            ),
            progress=say,
        )
        snapshot = Snapshot(card=card, expansion=expansion, candidates=found)

        say("stage 3/4  trials")
        snapshot.trials, snapshot.trial_log = queries.trials(
            fetchers["clinicaltrials"], card, snapshot.approved, progress=say
        )

        say("stage 4/4  literature")
        snapshot.literature, snapshot.literature_log = queries.literature(
            fetchers["pubmed"], card, progress=say
        )
    finally:
        for fetcher in fetchers.values():
            fetcher.close()

    _write_tables(snapshot, out_dir, fetchers, pattern, say)
    return snapshot


# ── writing ─────────────────────────────────────────────────────────────────────────


def _write_tables(
    snapshot: Snapshot,
    out_dir: Path,
    fetchers: dict[str, Fetcher],
    pattern: re.Pattern[str],
    say: Callable[[str], None],
) -> None:
    card = snapshot.card
    out_dir.mkdir(parents=True, exist_ok=True)

    target_rows = [
        {
            "symbol": t.symbol,
            "role": t.role,
            "direction_ids": t.direction_ids,
            "pathways": t.pathways,
            "uniprot": t.uniprot,
        }
        for t in snapshot.expansion.targets
    ]
    candidate_rows = [
        {
            "drug_name": c.drug_name,
            "drug_id": c.drug_id,
            "target_symbol": c.target_symbol,
            "target_role": c.target_role,
            "direction_ids": c.direction_ids,
            "source": c.source,
            "interaction_or_moa": c.interaction_or_moa,
            "action_type": c.action_type,
            "max_phase": c.max_phase,
            "approved": c.approved,
            "fda_label": c.fda_label,
            "pmids": c.pmids,
            "first_approval": c.first_approval,
            "atc": c.atc,
        }
        for c in snapshot.candidates
    ]
    pathway_rows = [
        {
            "st_id": p.st_id,
            "display_name": p.display_name,
            "matched": p.matched,
            "n_participants": p.n_participants,
        }
        for p in snapshot.expansion.pathways
    ]

    plan: list[tuple[str, tuple[str, ...], list[dict[str, Any]], tuple[str, ...], str]] = [
        (
            "targets",
            tables.TARGET_COLUMNS,
            target_rows,
            ("reactome",),
            rule_text(pattern),
        ),
        (
            "drug_candidates",
            tables.CANDIDATE_COLUMNS,
            candidate_rows,
            ("opentargets", "chembl", "dgidb", "openfda"),
            _candidate_method(),
        ),
        ("trials", tables.TRIAL_COLUMNS, snapshot.trials, ("clinicaltrials",), _trial_method()),
        (
            "literature",
            tables.LITERATURE_COLUMNS,
            snapshot.literature,
            ("pubmed",),
            _literature_method(),
        ),
        ("pathways", tables.PATHWAY_COLUMNS, pathway_rows, ("reactome",), rule_text(pattern)),
    ]

    counts: dict[str, int] = {}
    for name, columns, rows, sources, method in plan:
        path = out_dir / f"{name}.tsv"
        written = tables.write_tsv(path, columns, rows)
        counts[name] = written
        manifest = provenance.envelope(name, BUILT_BY) | {
            "method": method,
            "card": {
                "path": provenance.repo_relative(card.path),
                "version": card.version,
                "gene": card.gene_symbol,
                "disease": card.disease_name,
            },
            "inputs": [_input(key, fetchers[key], snapshot) for key in sources],
            "outputs": [provenance.output(path, written)],
            "licence": _LICENCE,
            "patient_data": provenance.PATIENT_DATA,
        }
        provenance.write(manifest, out_dir / f"{name}.provenance.json")
        snapshot.written.append(provenance.repo_relative(path))
        say(f"wrote {path}  {written:,} rows")

    snapshot.counts = _index(snapshot, counts, fetchers, pattern)
    index = out_dir / "snapshot.json"
    index.write_text(json.dumps(snapshot.counts, indent=2) + "\n", encoding="utf-8")
    snapshot.written.append(provenance.repo_relative(index))
    say(f"wrote {index}")


def _input(key: str, fetcher: Fetcher, snapshot: Snapshot) -> dict[str, Any]:
    url, role = ENDPOINTS[key]
    asked: list[str] | None = None
    if key == "clinicaltrials":
        asked = [entry["query"] for entry in snapshot.trial_log]
    elif key == "pubmed":
        asked = [entry["query"] for entry in snapshot.literature_log]
    return provenance.api_input(key, url, role=role, fetcher=fetcher, queries=asked)


def _index(
    snapshot: Snapshot,
    counts: dict[str, int],
    fetchers: dict[str, Fetcher],
    pattern: re.Pattern[str],
) -> dict[str, Any]:
    card = snapshot.card
    by_source: dict[str, int] = {}
    for candidate in snapshot.candidates:
        for source in candidate.source:
            by_source[source] = by_source.get(source, 0) + 1
    windows = {name: f.window for name, f in fetchers.items() if f.window}
    stamps = sorted(v for window in windows.values() for v in window)
    return {
        "built_at": provenance.now(),
        "built_by": BUILT_BY,
        "code_version": provenance.code_version(),
        "card": {
            "path": provenance.repo_relative(card.path),
            "version": card.version,
            "gene": card.gene_symbol,
            "uniprot": card.uniprot,
            "disease": card.disease_name,
            "tumour_context": card.tumour_context,
            "pathway": card.pathway,
            "directions": [
                {"id": d.id, "name": d.name, "seed_targets": len(d.seed_targets)}
                for d in card.directions
            ],
        },
        "retrieved_at": {"from": stamps[0], "to": stamps[-1]} if stamps else None,
        "rows": counts,
        "targets": {
            "seed": len(snapshot.expansion.seeds),
            "pathway": len(snapshot.expansion.members),
            "total": len(snapshot.expansion.targets),
        },
        "pathways": {
            "walked": len(snapshot.expansion.pathways),
            "matched": sum(1 for p in snapshot.expansion.pathways if p.matched),
            "pattern": pattern.pattern,
        },
        "candidates": {
            "total": len(snapshot.candidates),
            "approved": len(snapshot.approved),
            "with_fda_label": sum(1 for c in snapshot.candidates if c.fda_label),
            "by_source": dict(sorted(by_source.items())),
            "distinct_drugs": len({c.drug_name.lower() for c in snapshot.candidates}),
            "distinct_approved_drugs": len({c.drug_name.lower() for c in snapshot.approved}),
        },
        "requests": {
            name: {"replies": len(f.replies), "live": f.live_calls}
            for name, f in sorted(fetchers.items())
        },
        "trial_queries": snapshot.trial_log,
        "literature_queries": snapshot.literature_log,
    }


_LICENCE = (
    "Every row is derived from a public API: Open Targets Platform (CC0), ChEMBL "
    "(CC BY-SA 3.0), DGIdb (MIT, aggregating sources under their own terms), Reactome "
    "(CC0), ClinicalTrials.gov (US public domain), PubMed/NCBI (US public domain) and "
    "openFDA (US public domain). No licensed resource is queried; DrugBank is named by "
    "the challenge form but requires a licence for programmatic access and was not used."
)


def _candidate_method() -> str:
    return (
        "For every target in targets.tsv: Open Targets drugAndClinicalCandidates (a "
        "search for the exact approved symbol, then the target), ChEMBL mechanisms for "
        "every human target whose components declare that gene symbol, and one batched "
        "DGIdb interactions query over the whole symbol list. Rows are deduped on "
        "(drug_name.lower(), target_symbol); a row merged from several sources lists all "
        "of them in `source`. max_phase, first_approval and atc are then filled from one "
        "batched ChEMBL molecule lookup over every ChEMBL id any source produced, which "
        "also replaces a bare ChEMBL id with the preferred name. `approved` is the "
        "disjunction of ChEMBL max_phase == 4, an Open Targets clinical stage of "
        "APPROVAL, and DGIdb's own approved flag. openFDA is then queried once per "
        "approved drug name; `fda_label` is empty for a row that was never checked, which "
        "is not the same statement as false."
    )


def _trial_method() -> str:
    return (
        "Two query families, both derived from the card: one cond= query for the card's "
        "disease name with any parenthetical gloss stripped, and one intr=<drug> "
        "cond=<tumour context> query per approved candidate drug name. The disease query "
        "walks up to 3 pages of 100; the per-drug queries take the first page only. A "
        "study matching two queries appears once per query, tagged in the `query` column. "
        "Every query and its hit count, including the zeros, is listed in snapshot.json."
    )


def _literature_method() -> str:
    return (
        "Four query families over PubMed E-utilities: <gene> AND (repurposing OR "
        "inhibitor OR <anchor>); <pathway head phrase> AND drug; per direction, the "
        "direction name with its slash-separated segments OR'd, AND <anchor>; and the "
        "PMIDs the card itself cites. <anchor> is the last alphabetic word of the card's "
        "disease name. The direction family is the weak one: a long descriptive name "
        "becomes a long AND-chain and can match nothing. Those zeros are recorded in "
        "snapshot.json rather than papered over with a looser query."
    )
