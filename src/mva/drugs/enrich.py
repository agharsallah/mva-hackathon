"""Step 7's enrichment pass, as a pipeline: snapshot tables in, a graded shortlist out.

Six stages, each a pure function over rows except the three that ask a public API:

1. **mechanism literature** - per approved drug, PubMed counts with the mechanism and with
   the tumour context (:mod:`mva.drugs.mechlit`);
2. **paediatric trials** - per approved drug, registered studies admitting children
   (:mod:`mva.drugs.pediatric`);
3. **labels** - each drug's openFDA label re-read for its paediatric section (cache-warm);
4. **the ladder** - every (drug, direction) on a rung (:mod:`mva.drugs.ladder`);
5. **shortlist and do-not** (:mod:`mva.drugs.shortlist`);
6. **decoy comparison** - the real directions against each decoy card under ``decoys/``
   (:mod:`mva.drugs.compare`).

Every table is written with a provenance manifest in the snapshot's own shape, and an
``analysis.json`` carries the numbers the methodology entry and the figures quote. Case-
agnostic by the same rule as the snapshot: everything is read off the card and the tables.
"""

from __future__ import annotations

import csv
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import compare, ladder, mechlit, pediatric, provenance, shortlist, tables
from .cache import DEFAULT_CACHE_DIR, Fetcher
from .mechanism import DEFAULT_CARD, MechanismCard, load
from .names import base_name
from .snapshot import DEFAULT_OUT_DIR, ENDPOINTS, build_fetchers
from .sources import openfda

# A registry study can list hundreds of conditions; the default 128 KiB field limit
# would make such a row unreadable, and an unreadable row is a silent data loss.
csv.field_size_limit(sys.maxsize)

__all__ = ["BUILT_BY", "DEFAULT_ANALYSIS", "Enrichment", "read_tsv", "run"]

BUILT_BY = "tools/track2_enrich.py"
DEFAULT_ANALYSIS = Path("build/track2/analysis.json")

#: Methods, as the manifests print them. One place, so the manifest and the docs agree.
METHODS = {
    "drug_mechanism_literature": (
        "two PubMed questions per approved drug, derived from the card: the drug AND the "
        "mechanism (gene, protein, pathway head, disease anchor), and the drug AND the tumour "
        "context; hits is the PubMed record count, pmids a head of at most 10"
    ),
    "pediatric_trials": (
        "ClinicalTrials.gov v2, query.intr=<drug> with aggFilters=ages:child, first page of "
        "100, any indication; a study that admits children, not proof one enrolled any"
    ),
    "evidence_ladder": (
        "one row per (approved drug, direction): automated rung from approval, tumour-context "
        "trial and paediatric evidence (5 = approved AND context trial AND paediatric "
        "label-or-study; 4 = context trial; else 1), curated rung from evidence.tsv (a PMID "
        "read by a person, rung 2 cell / 3 in vivo); rung = max of the two, both printed; "
        "flags name anti-directions (card moa_pattern), standard of care, curated-only and "
        "unverified approval"
    ),
    "shortlist": (
        "ladder rows at rung >= 2 that are neither standard of care nor anti-direction nor "
        "pathway-only, ranked: rung, molecule-level before proxy evidence, paediatric "
        "evidence, mechanism literature"
    ),
    "do_not": (
        "every ladder drug carrying an anti-direction flag (with the card's status for it) or "
        "the standard-of-care flag, once each"
    ),
    "decoy_comparison": (
        "per real direction and per decoy card: Jaccard between the approved drug sets (base "
        "names), the shared drugs, and the decoy's own automated flags; automated stages only"
    ),
    "evidence": (
        "curated by a person: one cited PubMed result per row, rung 2 (cell) or 3 (in vivo), "
        "proxy=true when the result is for a same-axis compound named in proxy_of; every PMID "
        "was resolved against PubMed E-utilities before the row was written"
    ),
}


def read_tsv(path: Path) -> list[dict[str, str]]:
    """One TSV as a list of string rows."""
    # The writer never quotes and a title may start with a double quote; the default dialect
    # would read that quote as the start of a multi-line field and swallow the rows after it.
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream, delimiter="\t", quoting=csv.QUOTE_NONE))


@dataclass
class Enrichment:
    """What one run produced, in memory."""

    card: MechanismCard
    drugs: list[str]
    mechlit: list[dict[str, Any]] = field(default_factory=list)
    mechlit_log: list[dict[str, Any]] = field(default_factory=list)
    pediatric: list[dict[str, Any]] = field(default_factory=list)
    labels: dict[str, dict[str, Any]] = field(default_factory=dict)
    ladder: list[dict[str, Any]] = field(default_factory=list)
    shortlist: list[dict[str, Any]] = field(default_factory=list)
    do_not: list[dict[str, Any]] = field(default_factory=list)
    comparison: list[dict[str, Any]] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    analysis: dict[str, Any] = field(default_factory=dict)


def _drug_names(candidates: list[dict[str, str]], evidence: list[dict[str, str]]) -> list[str]:
    approved = {base_name(r["drug_name"]) for r in candidates if r["approved"] == "true"}
    return sorted(approved | {base_name(r["drug_name"]) for r in evidence})


def _live(
    result: Enrichment, fetchers: dict[str, Fetcher], out_dir: Path, say: Callable[[str], None]
) -> None:
    say("stage 1/3  drug x mechanism literature")
    result.mechlit, result.mechlit_log = mechlit.survey(
        fetchers["pubmed"], result.card, result.drugs, progress=say
    )
    say("stage 2/3  paediatric trials")
    result.pediatric, _log = pediatric.survey(
        fetchers["clinicaltrials"], result.drugs, progress=say
    )
    say("stage 3/3  labels")
    for name in result.drugs:
        answer = openfda.label(fetchers["openfda"], name)
        result.labels[name] = {
            "has_label": answer["has_label"],
            "pediatric_use": answer["pediatric_use"],
        }
    (out_dir / "labels.json").write_text(
        json.dumps(result.labels, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )


def _from_disk(result: Enrichment, out_dir: Path) -> None:
    result.mechlit = [
        dict(r, hits=int(r["hits"])) for r in read_tsv(out_dir / "drug_mechanism_literature.tsv")
    ]
    result.pediatric = list(read_tsv(out_dir / "pediatric_trials.tsv"))
    result.labels = json.loads((out_dir / "labels.json").read_text(encoding="utf-8"))


def _decoys(out_dir: Path) -> list[Path]:
    return sorted(
        p for p in (out_dir / "decoys").glob("*") if (p / "drug_candidates.tsv").is_file()
    )


def _table_input(out_dir: Path, name: str) -> dict[str, Any]:
    path = out_dir / f"{name}.tsv"
    sha, size = provenance.digest(path)
    return {
        "name": f"track2.{name}",
        "path": provenance.repo_relative(path),
        "sha256": sha,
        "bytes": size,
    }


def _manifest(
    name: str, path: Path, rows: int, card: MechanismCard, inputs: list[dict[str, Any]]
) -> None:
    manifest = provenance.envelope(name, BUILT_BY) | {
        "method": METHODS[name],
        "card": {
            "path": provenance.repo_relative(card.path),
            "version": card.version,
            "gene": card.gene_symbol,
            "disease": card.disease_name,
        },
        "inputs": inputs,
        "outputs": [provenance.output(path, rows)],
        "patient_data": provenance.PATIENT_DATA,
    }
    provenance.write(manifest, path.with_name(f"{name}.provenance.json"))


def _write(
    result: Enrichment,
    out_dir: Path,
    fetchers: dict[str, Fetcher],
    decoys: list[Path],
    say: Callable[[str], None],
) -> None:
    def api(key: str, queries: list[str] | None = None) -> dict[str, Any]:
        url, role = ENDPOINTS[key]
        return provenance.api_input(key, url, role=role, fetcher=fetchers[key], queries=queries)

    asked = [f"{e['family']}: <drug> AND {e['term_body']}" for e in result.mechlit_log]

    def table_in(name: str) -> dict[str, Any]:
        return _table_input(out_dir, name)

    decoy_in = [
        {
            "name": f"decoy:{d.name}",
            "path": provenance.repo_relative(d / "drug_candidates.tsv"),
            "sha256": provenance.digest(d / "drug_candidates.tsv")[0],
        }
        for d in decoys
    ]
    # Inputs are thunks: a table's manifest hashes the tables written *before* it in this
    # plan, so the digest has to be taken after that write, not when the plan is declared.
    plan: list[
        tuple[str, tuple[str, ...], list[dict[str, Any]], Callable[[], list[dict[str, Any]]]]
    ] = [
        (
            "drug_mechanism_literature",
            tables.MECHLIT_COLUMNS,
            result.mechlit,
            lambda: [api("pubmed", asked or None), table_in("drug_candidates")],
        ),
        (
            "pediatric_trials",
            tables.PEDIATRIC_TRIAL_COLUMNS,
            result.pediatric,
            lambda: [api("clinicaltrials"), table_in("drug_candidates")],
        ),
        (
            "evidence_ladder",
            tables.LADDER_COLUMNS,
            result.ladder,
            lambda: [
                table_in("drug_candidates"),
                table_in("trials"),
                table_in("evidence"),
                table_in("drug_mechanism_literature"),
                table_in("pediatric_trials"),
                api("openfda"),
            ],
        ),
        (
            "shortlist",
            tables.SHORTLIST_COLUMNS,
            result.shortlist,
            lambda: [table_in("evidence_ladder")],
        ),
        ("do_not", tables.SHORTLIST_COLUMNS, result.do_not, lambda: [table_in("evidence_ladder")]),
        (
            "decoy_comparison",
            tables.DECOY_COMPARISON_COLUMNS,
            result.comparison,
            lambda: [table_in("drug_candidates"), *decoy_in],
        ),
    ]
    for name, columns, rows, inputs in plan:
        path = out_dir / f"{name}.tsv"
        result.counts[name] = tables.write_tsv(path, columns, rows)
        _manifest(name, path, result.counts[name], result.card, inputs())
        say(f"wrote {path}  {result.counts[name]:,} rows")
    evidence_path = out_dir / "evidence.tsv"
    _manifest(
        "evidence",
        evidence_path,
        len(read_tsv(evidence_path)),
        result.card,
        [{"name": "pubmed", "url": ENDPOINTS["pubmed"][0], "role": "PMID resolution"}],
    )


def _by_max_rung(rows: list[dict[str, Any]]) -> dict[str, int]:
    best: dict[str, int] = {}
    for r in rows:
        best[r["drug_name"]] = max(best.get(r["drug_name"], 0), int(r["rung"]))
    out: dict[int, int] = {}
    for rung in best.values():
        out[rung] = out.get(rung, 0) + 1
    return {str(k): v for k, v in sorted(out.items(), reverse=True)}


def _by_direction(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        entry = out.setdefault(
            r["direction_id"],
            {"direction_id": r["direction_id"], "drugs": 0, "rung_ge_2": 0, "rung_ge_3": 0},
        )
        entry["drugs"] += 1
        entry["rung_ge_2"] += int(r["rung"]) >= 2
        entry["rung_ge_3"] += int(r["rung"]) >= 3
    return sorted(out.values(), key=lambda e: e["direction_id"])


def _analysis(result: Enrichment, fetchers: dict[str, Fetcher]) -> dict[str, Any]:
    by_rung: dict[int, int] = {}
    for r in result.ladder:
        by_rung[int(r["rung"])] = by_rung.get(int(r["rung"]), 0) + 1
    return {
        "built_at": provenance.now(),
        "built_by": BUILT_BY,
        "code_version": provenance.code_version(),
        "card_version": result.card.version,
        "gene": result.card.gene_symbol,
        "drugs_graded": len(result.drugs),
        "rows": result.counts,
        "ladder_rows_by_rung": {str(k): v for k, v in sorted(by_rung.items(), reverse=True)},
        "ladder_drugs_by_max_rung": _by_max_rung(result.ladder),
        "direction_summary": _by_direction(result.ladder),
        "shortlist": result.shortlist,
        "do_not": result.do_not,
        "decoy_comparison": result.comparison,
        "ladder_top": [r for r in result.ladder if int(r["rung"]) >= 2],
        "mechlit_log": result.mechlit_log,
        "pediatric_summary": {
            "drugs_asked": len(result.drugs),
            "drugs_with_child_study": len({str(r["drug_name"]) for r in result.pediatric}),
            "drugs_with_pediatric_label": sum(
                1 for v in result.labels.values() if v.get("pediatric_use")
            ),
            "drugs_with_label": sum(1 for v in result.labels.values() if v.get("has_label")),
        },
        "requests": {
            k: {"replies": len(f.replies), "live": f.live_calls}
            for k, f in sorted(fetchers.items())
        },
    }


def run(
    card_path: Path = DEFAULT_CARD,
    out_dir: Path = DEFAULT_OUT_DIR,
    *,
    analysis_path: Path = DEFAULT_ANALYSIS,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    refresh: bool = False,
    skip_live: bool = False,
    progress: Callable[[str], None] | None = None,
) -> Enrichment:
    """Every stage, every file. Returns the enrichment with its counts and analysis."""
    say = progress or (lambda _line: None)
    card = load(card_path)
    candidates = read_tsv(out_dir / "drug_candidates.tsv")
    trials = read_tsv(out_dir / "trials.tsv")
    evidence = read_tsv(out_dir / "evidence.tsv")
    result = Enrichment(card, _drug_names(candidates, evidence))
    say(f"card v{card.version} {card.gene_symbol}: {len(result.drugs)} drugs to grade")

    fetchers = build_fetchers(cache_dir, refresh=refresh)
    try:
        if skip_live:
            _from_disk(result, out_dir)
        else:
            _live(result, fetchers, out_dir, say)
        result.ladder = ladder.assign(
            ladder.LadderInputs(
                card, candidates, trials, result.mechlit, result.pediatric, result.labels, evidence
            )
        )
        result.shortlist = shortlist.shortlist(result.ladder, card)
        result.do_not = shortlist.do_not_table(result.ladder, card)
        decoys = _decoys(out_dir)
        for decoy in decoys:
            result.comparison.extend(
                compare.compare(
                    card,
                    candidates,
                    decoy.name,
                    read_tsv(decoy / "drug_candidates.tsv"),
                    read_tsv(decoy / "trials.tsv"),
                )
            )
        _write(result, out_dir, fetchers, decoys, say)
        result.analysis = _analysis(result, fetchers)
    finally:
        for fetcher in fetchers.values():
            fetcher.close()
    analysis_path.parent.mkdir(parents=True, exist_ok=True)
    analysis_path.write_text(json.dumps(result.analysis, indent=2) + "\n", encoding="utf-8")
    say(f"wrote {analysis_path}")
    return result
