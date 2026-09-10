"""Build the blind target set and its matched decoy set — iteration 2, step 1.

Reads the child's HPO terms and two public files, and writes the gene lists steps 2 and 3
will bait reads for. **No genomic data is read**: that is the whole point of step 1, and
the provenance manifest written beside the tables says so.

What it produces, under ``--out`` (gitignored; the tables carry no patient sequence but
they are derived, and derived tables live under ``build/``):

``targets.tsv``     one row per target gene: tier, pure symptom-score rank, score, how it
                    got in, and which term sets nominated it.
``decoys.tsv``      one shape-matched decoy per target — the read route's null.
``summary.json``    the gate numbers of plan §4b: tier counts, the uncurated blind spot,
                    and the mechanism-term rows listed by name.
``provenance.json`` inputs with their sha256 and release, the seed, the parameters, and
                    the code version — everything needed to rebuild these exact files.

Case-agnostic: the term sets come from :mod:`mva.phenotype.terms`, the thresholds are
flags, and nothing here names a gene.

Usage::

    uv run python tools/build_it2_targets.py
    uv run python tools/build_it2_targets.py --core-n 50 --target-n 300 --seed 20260910
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from collections import defaultdict
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mva.phenotype import targets as targets_module
from mva.phenotype import terms as terms_module
from mva.phenotype.associations import Corpus, parse_genes_to_phenotype
from mva.phenotype.ontology import Ontology, parse_obo
from mva.phenotype.prioritise import Ranking, rank_genes

DEFAULT_SCRATCH = Path("build/reference-scratch")
DEFAULT_OUT = Path("build/it2/step-1")
DEFAULT_CODING = Path("ressources/reference/coding_regions.tsv")

#: The draw is made once from this seed and never edited — the plan's rule for the decoys.
DEFAULT_SEED = 20260910


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def code_version() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def read_release(path: Path) -> str:
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[:40]:
        if line.startswith("data-version:"):
            return line.split(":", 1)[1].strip()
    return "unknown"


def gene_features(path: Path) -> tuple[targets_module.GeneFeature, ...]:
    """Coding length and exon count per gene, from the Ensembl-derived coding regions.

    The rows are merged coding intervals, so the exon count is the row count and the
    coding length is their total span. Both are gene *shape*, which is what a decoy is
    matched on; neither says anything about the patient.
    """
    spans: dict[str, int] = defaultdict(int)
    exons: dict[str, int] = defaultdict(int)
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            gene = (row.get("gene") or "").strip()
            if not gene:
                continue
            spans[gene] += max(0, int(row["end"]) - int(row["start"]))
            exons[gene] += 1
    return tuple(
        targets_module.GeneFeature(symbol=gene, coding_length=spans[gene], exon_count=exons[gene])
        for gene in sorted(spans)
    )


def phenotype_matched(corpus: Corpus, ontology: Ontology, term_ids: frozenset[str]) -> set[str]:
    """Every gene annotated with any of the case's terms, anywhere in its closure.

    Excluded from the decoy draw: a decoy that shares the child's phenotype is not a null.
    """
    return {
        annotation.symbol
        for annotation in corpus.genes.values()
        if term_ids & ontology.closure_of(annotation.terms)
    }


def rankings(ontology: Ontology, corpus: Corpus) -> tuple[Ranking, ...]:
    """Both term sets, ranked. Co-primary: their target sets are unioned, never chosen
    between, so neither reading of the parental term can hide a gene."""
    return tuple(
        rank_genes(term_set, corpus, ontology)
        for term_set in (terms_module.PROBAND_ONLY, terms_module.WITH_PARENTAL)
    )


def write_tsv(path: Path, rows, columns: tuple[str, ...]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(columns)
        for row in rows:
            record = asdict(row)
            writer.writerow(
                [
                    ""
                    if record[c] is None
                    else ";".join(record[c])
                    if isinstance(record[c], tuple)
                    else record[c]
                    for c in columns
                ]
            )
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch", type=Path, default=DEFAULT_SCRATCH)
    parser.add_argument("--coding-regions", type=Path, default=DEFAULT_CODING)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--core-n", type=int, default=targets_module.CORE_N)
    parser.add_argument("--target-n", type=int, default=targets_module.TARGET_N)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args(argv)

    obo = args.scratch / "hp.obo"
    annotations = args.scratch / "genes_to_phenotype.txt"
    for path in (obo, annotations, args.coding_regions):
        if not path.exists():
            raise SystemExit(
                f"missing {path}\nRun: uv run tools/build_phenotype_data.py "
                f"--scratch {args.scratch}"
            )

    ontology = parse_obo(obo)
    corpus = parse_genes_to_phenotype(annotations, ontology)
    corpus.apply_to(ontology)

    scored = rankings(ontology, corpus)
    mechanism = targets_module.mechanism_genes(corpus, ontology)
    rows = targets_module.build(
        scored, mechanism=mechanism, core_n=args.core_n, target_n=args.target_n
    )

    features = gene_features(args.coding_regions)
    protein_coding = [f.symbol for f in features]
    uncurated, total = targets_module.uncurated_count(corpus, protein_coding)
    excluded = phenotype_matched(corpus, ontology, terms_module.WITH_PARENTAL.id_set)
    decoys = targets_module.draw_decoys(rows, features, seed=args.seed, excluded=excluded)

    written_targets = write_tsv(
        args.out / "targets.tsv",
        rows,
        ("symbol", "tier", "score_rank", "score", "entered_by", "term_sets"),
    )
    written_decoys = write_tsv(
        args.out / "decoys.tsv",
        decoys,
        ("symbol", "matched_to", "coding_length", "exon_count"),
    )

    by_tier: dict[str, int] = defaultdict(int)
    for row in rows:
        by_tier[row.tier] += 1
    mechanism_rows = [r.symbol for r in rows if r.entered_by == targets_module.BY_MECHANISM]
    summary = {
        "targets": written_targets,
        "decoys": written_decoys,
        "by_tier": dict(sorted(by_tier.items())),
        "core_n": args.core_n,
        "target_n": args.target_n,
        "genes_scored": {r.term_set.name: len(r.scores) for r in scored},
        "genes_considered": {r.term_set.name: r.considered for r in scored},
        "mechanism_term_genes_in_corpus": len(mechanism),
        "mechanism_term_rows": sorted(mechanism_rows),
        "earned_by_score": sum(1 for r in rows if r.earned_its_place),
        "uncurated_protein_coding": uncurated,
        "protein_coding_total": total,
        "uncurated_fraction": round(uncurated / total, 4) if total else None,
        "decoy_exclusions": len(excluded),
    }
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "built_by": "tools/build_it2_targets.py",
        "code_version": code_version(),
        "step": "docs/iteration2/step-1",
        "method": (
            "Genes ranked against the child's HPO terms by the human-only Resnik ranker "
            "(entry 067), tiered into core / net / mechanism-term, unioned across both "
            "term sets on best rank. Mechanism-term rows are every gene the corpus "
            "annotates at or under HP:0002916 or HP:0003220, read through the ancestor "
            "closure. Decoys are shape-matched on coding length and exon count, drawn "
            "once from the recorded seed, excluding every gene annotated with any of "
            "the case's terms."
        ),
        "inputs": [
            {
                "name": path.name,
                "path": str(path),
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
                "role": role,
            }
            for path, role in (
                (obo, "the ontology graph: ancestor closure and term labels"),
                (annotations, "gene-to-phenotype curation: the corpus that is ranked"),
                (args.coding_regions, "gene shape: coding length and exon count for matching"),
            )
        ],
        "hpo_release": read_release(obo),
        "clinical_input": {
            "source": "ressources/hackathon-rules/Challenge_Clinical_Phenotype_1.md",
            "term_sets": {
                terms_module.PROBAND_ONLY.name: list(terms_module.PROBAND_ONLY.ids),
                terms_module.WITH_PARENTAL.name: list(terms_module.WITH_PARENTAL.ids),
            },
        },
        "parameters": {"core_n": args.core_n, "target_n": args.target_n, "seed": args.seed},
        "outputs": {"targets.tsv": written_targets, "decoys.tsv": written_decoys},
        "genomic_data_read": (
            "none. Step 1 chooses the target set with the DNA never read; the only "
            "genomic file touched is the reference gene model, which is public and "
            "carries no patient information."
        ),
    }
    (args.out / "provenance.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    print(f"targets: {written_targets} rows -> {args.out / 'targets.tsv'}")
    for tier, count in sorted(by_tier.items()):
        print(f"  {tier:<16} {count}")
    print(f"decoys:  {written_decoys} rows -> {args.out / 'decoys.tsv'}")
    print(
        f"uncurated protein-coding genes: {uncurated}/{total} ({summary['uncurated_fraction']:.1%})"
        if total
        else "uncurated: unknown"
    )
    print(f"mechanism-term rows: {len(mechanism_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
