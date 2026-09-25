#!/usr/bin/env python3
"""Iteration 5, route R3 — quote-verified literature extraction, end to end.

Stages (each reads what the previous one wrote; every stage is re-runnable offline from the
caches under ``build/it5/r3/``):

``corpus``     topic queries → Europe PMC → ``build/it5/r3/docs/<pmid>.<kind>.txt`` +
               ``ressources/track2/it5/litmine_corpus.tsv``
``screen``     lexical screen → reading packs ``build/it5/r3/reading/*.md`` (for the reader)
``verify``     the model's rows (``litmine_extraction.tsv``, ``litmine_exposure_extraction.tsv``)
               → quote gate → ``litmine_interventions.tsv`` / ``litmine_mva_exposures.tsv`` /
               ``litmine_rejected.tsv``
``translate``  kept rows → ChEMBL → ``literature_candidates.tsv``
``all``        the four, in order

Usage::

    uv run python tools/it5_litmine.py all
    uv run python tools/it5_litmine.py verify          # offline: re-run the gate only
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from it5_litmine_params import (
    ANALOGUES,
    BRANCH_BY_EFFECT,
    CONTROLS,
    DESIRED,
    DISEASE_MARKERS,
    EXPOSURE_LEXICON,
    EXTRACTOR,
    INTERVENTION_LEXICON,
    SPEC,
)
from mva.drugs import provenance
from mva.drugs.cache import Fetcher
from mva.drugs.litmine_corpus import (
    EPMC,
    TextCache,
    build_queries,
    run_queries,
    save_documents,
)
from mva.drugs.litmine_screen import load_texts, screen_corpus, write_reading_pack
from mva.drugs.litmine_translate import candidates, control_recall, translate
from mva.drugs.litmine_verify import (
    EXPOSURE_ENUMS,
    INTERVENTION_ENUMS,
    INTERVENTION_FIELDS,
    verify_rows,
)

SCRIPT = "tools/it5_litmine.py"
ENTRY = (
    "docs/iteration5/step-1/methodology/"
    "160-every-bubr1-intervention-in-the-literature-with-a-verified-quote.md"
)
BUILD = Path("build/it5/r3")
DOCS = BUILD / "docs"
OUT = Path("ressources/track2/it5")
EXPOSURE_FIELDS = (
    "patient_gene",
    "tumour",
    "drug_or_regimen",
    "outcome_kind",
    "outcome",
    "hpo_overlap",
    "pmid",
    "quote",
)


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_tsv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=columns, delimiter="\t", extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    return path


def manifest(table: Path, rows: int, *, inputs: list[dict[str, Any]], **fields: Any) -> None:
    doc = provenance.envelope(table.name, SCRIPT)
    doc.update({"entry": ENTRY, "tool": SCRIPT, "inputs": inputs, "rows": rows})
    doc.update(fields)
    doc["outputs"] = [provenance.output(table, rows)]
    provenance.write(doc, table.with_suffix(".provenance.json"))


def file_input(path: Path) -> dict[str, Any]:
    return {"file": provenance.repo_relative(path), "sha256": provenance.digest(path)[0]}


# ── stages ───────────────────────────────────────────────────────────────────────────────


def stage_corpus(refresh: bool) -> None:
    fetcher = Fetcher(source="europepmc", cache_dir=BUILD / "cache", refresh=refresh)
    queries = build_queries(SPEC)
    docs, log = run_queries(fetcher, queries, max_records=SPEC.max_records)
    texts = TextCache(BUILD / "fulltext-xml")
    rows = save_documents(docs, DOCS, texts, fulltext_for=set(docs))
    (BUILD / "query_log.json").write_text(json.dumps(log, indent=1) + "\n", encoding="utf-8")
    stats = {
        "papers_retrieved": len(docs),
        "papers_with_text": len({r["pmid"] for r in rows}),
        "texts_cached": len(rows),
        "fulltext_cached": sum(r["text_kind"] == "fulltext" for r in rows),
        "fulltext_failed": len(texts.failures),
    }
    (BUILD / "corpus_stats.json").write_text(json.dumps(stats, indent=1) + "\n", encoding="utf-8")
    table = write_tsv(
        OUT / "litmine_corpus.tsv",
        rows,
        ["pmid", "title", "year", "source", "text_kind", "text_sha256", "queries"],
    )
    fulltext = stats["fulltext_cached"]
    manifest(
        table,
        len(rows),
        inputs=[
            provenance.api_input(
                "Europe PMC search",
                f"{EPMC}/search",
                role="corpus metadata + abstracts",
                fetcher=fetcher,
                queries=[q.term for q in queries],
            ),
            {
                "name": "Europe PMC full text",
                "url": f"{EPMC}/{{PMCID}}/fullTextXML",
                "role": "open-access full text (JATS XML), cached under build/it5/r3/fulltext-xml",
                "live_calls": texts.live_calls,
                "failed_after_retries": texts.failures,
            },
        ],
        parameters={
            "gene": SPEC.gene,
            "aliases": list(SPEC.aliases),
            "topics": {k: list(v) for k, v in SPEC.topics.items()},
            "disease_phrases": list(SPEC.disease_phrases),
            "max_records_per_query": SPEC.max_records,
            "query_log": log,
        },
        columns={
            "text_kind": "abstract = title + abstract from the search record; fulltext = "
            "JATS abstract + body prose (tables and reference lists dropped)",
            "text_sha256": "sha256 of the UTF-8 text file build/it5/r3/docs/<pmid>.<kind>.txt "
            "the quote verifier reads",
            "queries": "the query ids that retrieved the paper",
        },
        sources={
            "literature": "Europe PMC (MEDLINE records, SRC:MED)",
            "clinical": "none",
            "genomic": "none: the queries name the gene, never a variant or position",
        },
        assumptions="title+abstract matching finds the papers whose main subject is the gene",
        limitations="one page (<=1000 records) per query; full text only when open access; "
        "the cached text files stay in build/ (copyright), only their digests are committed",
        validation="positive control: the three control PMIDs must be retrieved "
        "(recall reported by the verify stage)",
        documents=len({r["pmid"] for r in rows}),
        fulltext_documents=fulltext,
    )
    print(f"corpus: {len(docs)} papers, {len(rows)} texts ({fulltext} full text)")
    for pmid in CONTROLS:
        print(f"  control {pmid}: {'retrieved' if pmid in docs else 'MISSING'}")


def stage_screen() -> None:
    texts = load_texts(DOCS)
    titles = {r["pmid"]: r["title"] for r in read_tsv(OUT / "litmine_corpus.tsv")}
    phrases = [p.lower() for p in (*SPEC.disease_phrases, *DISEASE_MARKERS)]
    disease = {
        pmid
        for pmid, kinds in texts.items()
        if any(p in text.lower() for text in kinds.values() for p in phrases)
    }
    hits = screen_corpus(texts, INTERVENTION_LEXICON)
    write_reading_pack(hits, titles, BUILD / "reading" / "interventions.md")
    exposure = screen_corpus(texts, EXPOSURE_LEXICON, only=disease)
    write_reading_pack(exposure, titles, BUILD / "reading" / "exposures.md")
    stats = {
        "intervention_sentences": len(hits),
        "intervention_papers": len({h["pmid"] for h in hits}),
        "exposure_sentences": len(exposure),
        "exposure_papers": len({h["pmid"] for h in exposure}),
        "disease_papers_screened": len(disease),
    }
    (BUILD / "screen_stats.json").write_text(json.dumps(stats, indent=1) + "\n", encoding="utf-8")
    print("screen:", stats)


def stage_verify() -> None:
    texts = load_texts(DOCS)
    raw = read_tsv(OUT / "litmine_extraction.tsv")
    kept, rejected = verify_rows(raw, texts, required=INTERVENTION_FIELDS, enums=INTERVENTION_ENUMS)
    raw_exp = read_tsv(OUT / "litmine_exposure_extraction.tsv")
    kept_exp, rejected_exp = verify_rows(
        raw_exp, texts, required=EXPOSURE_FIELDS, enums=EXPOSURE_ENUMS
    )
    recall = control_recall(kept, CONTROLS, texts)
    cols = [*INTERVENTION_FIELDS, "verified_in", "note"]
    t1 = write_tsv(OUT / "litmine_interventions.tsv", kept, cols)
    t2 = write_tsv(OUT / "litmine_mva_exposures.tsv", kept_exp, [*EXPOSURE_FIELDS, "verified_in"])
    all_rejected = [{**r, "table": "interventions"} for r in rejected] + [
        {**r, "table": "exposures"} for r in rejected_exp
    ]
    t3 = write_tsv(
        OUT / "litmine_rejected.tsv",
        all_rejected,
        ["table", "pmid", "intervention", "drug_or_regimen", "reject_reason", "quote"],
    )
    ins = [
        file_input(OUT / "litmine_corpus.tsv"),
        file_input(OUT / "litmine_extraction.tsv"),
        file_input(OUT / "litmine_exposure_extraction.tsv"),
    ]
    common = {
        "extractor": EXTRACTOR,
        "gate": "mva.drugs.litmine_verify.verify_rows: NFKC + quote/dash folding + whitespace "
        "collapse, case kept, min 30 characters, verbatim substring of the cached text of the "
        "cited PMID; a failing row is rejected, never repaired",
        "positive_control": recall,
        "sources": {
            "literature": "the cached corpus texts (litmine_corpus.tsv digests)",
            "clinical": "hpo_overlap names the child's HPO terms (exposures table)",
            "genomic": "none",
        },
        "limitations": "the reader saw screened sentences, not whole papers; a verified quote "
        "proves the sentence exists, not that the row reads it correctly",
    }
    manifest(t1, len(kept), inputs=ins, **common, rejected=len(rejected))
    manifest(t2, len(kept_exp), inputs=ins, **common, rejected=len(rejected_exp))
    manifest(t3, len(all_rejected), inputs=ins, **common)
    print(
        f"verify: interventions kept {len(kept)} rejected {len(rejected)}; "
        f"exposures kept {len(kept_exp)} rejected {len(rejected_exp)}"
    )
    print("positive control:", json.dumps(recall))


def stage_translate(refresh: bool) -> None:
    kept = read_tsv(OUT / "litmine_interventions.tsv")
    recall = json.loads((OUT / "litmine_interventions.provenance.json").read_text())[
        "positive_control"
    ]
    fetcher = Fetcher(source="chembl", cache_dir=Path("build/track2-cache"), refresh=refresh)
    mapped = translate(kept, fetcher, desired=DESIRED, analogues=ANALOGUES)
    (BUILD / "translation.json").write_text(json.dumps(mapped, indent=1) + "\n", encoding="utf-8")
    rows = candidates(mapped, branch_by_effect=BRANCH_BY_EFFECT, control_passed=recall["passed"])
    cols = [
        "drug_name",
        "route",
        "branch",
        "evidence_kind",
        "evidence_strength",
        "positive_control_passed",
        "source",
        "notes",
    ]
    table = write_tsv(OUT / "literature_candidates.tsv", rows, cols)
    manifest(
        table,
        len(rows),
        inputs=[
            file_input(OUT / "litmine_interventions.tsv"),
            provenance.api_input(
                "ChEMBL",
                "https://www.ebi.ac.uk/chembl/api/data",
                role="drug names → molecules, targets → mechanisms",
                fetcher=fetcher,
            ),
        ],
        parameters={
            "desired_direction": DESIRED,
            "branch_by_effect": BRANCH_BY_EFFECT,
            "analogues": ANALOGUES,
        },
        rubric="evidence_strength = model × directness × replication × translation; "
        "see the entry's rubric table",
        positive_control=recall,
        extractor=EXTRACTOR,
        clinical_framing="research exercise; no row advises for or against giving any drug",
        sources={
            "literature": "litmine_interventions.tsv (quote-verified)",
            "clinical": "none directly; the branch column is the allele question",
            "genomic": "the branch names the child's two allele classes, not positions",
        },
        limitations="a candidate is a literature lead, not an efficacy claim; strength is a "
        "stated heuristic, not a calibrated probability",
    )
    print(f"translate: {len(mapped)} intervention groups → {len(rows)} candidate rows")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("stage", choices=["corpus", "screen", "verify", "translate", "all"])
    parser.add_argument("--refresh", action="store_true", help="bypass the API caches")
    args = parser.parse_args()
    if args.stage in ("corpus", "all"):
        stage_corpus(args.refresh)
    if args.stage in ("screen", "all"):
        stage_screen()
    if args.stage in ("verify", "all"):
        stage_verify()
    if args.stage in ("translate", "all"):
        stage_translate(args.refresh)


if __name__ == "__main__":
    main()
