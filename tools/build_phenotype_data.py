#!/usr/bin/env python3
"""Build the committable phenotype reference tables in `ressources/reference/`.

Two public sources, no patient data anywhere in this script:

  hp.obo                   the Human Phenotype Ontology graph
  genes_to_phenotype.txt   which genes are curated to cause which features

Both download to a scratch directory (default `build/reference-scratch/`, gitignored) and
only the small derived TSVs enter the repository — the same shape as
`build_reference_data.py`, which this sits beside rather than inside because that file is
already near the 400-line module cap.

Outputs:

  hpo_term_ic.tsv      one row per term: name, depth, how many genes carry it, and its
                       information content. The measured rarity of every clinical feature.
  hpo_gene_scores.tsv  one row per (term set, gene): where the gene ranked against the
                       child's features, and which feature drove it.

Nothing here reads the callset, the panel, or a variant. That independence is the point:
the ranking must not be able to inherit the candidate panel's bias.

Usage:
  uv run tools/build_phenotype_data.py            [--scratch DIR] [--out-dir DIR]
  uv run tools/build_phenotype_data.py --top 50   # also print the leaderboard
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from mva.phenotype import (  # noqa: E402  - needs the sys.path line above
    associations,
    ontology,
    prioritise,
    terms,
)

DEFAULT_SCRATCH = REPO / "build" / "reference-scratch"
REFERENCE = REPO / "ressources" / "reference"

#: HPO publishes monthly. These PURLs always serve the current release, so the release the
#: run actually used is read out of the file's own ``data-version`` and recorded in the
#: output — pinning a URL to a date would go stale silently, and not recording the version
#: would make a number impossible to reproduce.
OBO_URL = "https://purl.obolibrary.org/obo/hp.obo"
GENES_URL = "https://purl.obolibrary.org/obo/hp/hpoa/genes_to_phenotype.txt"


def fetch(url: str, dest: Path) -> Path:
    """Download `url` to `dest` unless a non-empty file is already there."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        print(f"cached  {dest}  ({dest.stat().st_size:,} bytes)", file=sys.stderr)
        return dest
    print(f"fetch   {url}", file=sys.stderr)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url) as response, tmp.open("wb") as handle:
        shutil.copyfileobj(response, handle, length=1 << 20)
    tmp.replace(dest)
    print(f"wrote   {dest}  ({dest.stat().st_size:,} bytes)", file=sys.stderr)
    return dest


#: The provenance sidecar. Written beside the tables it describes, and read back by
#: :mod:`mva.warehouse.reference` to build the lineage edges.
#:
#: It exists because HPO's PURLs always serve the **current** monthly release. Hard-coding
#: a release and a digest in the lineage spec therefore goes stale the moment anyone
#: re-runs this script, silently, while still looking authoritative. Deriving the spec
#: from a manifest the same run produced makes that impossible.
#:
#: JSON rather than TSV on purpose: it is metadata *about* the reference tables, not one of
#: them, and `ressources/reference/*.tsv` is asserted by test to be exactly the set of
#: staged tables.
PROVENANCE_FILE = "hpo_provenance.json"


def sha256(path: Path) -> str:
    """The file's digest, streamed - these inputs are tens of megabytes."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def code_version() -> str:
    """The commit this ranking was computed by, or ``unknown`` outside a git checkout.

    A score is a function of three things: the ontology, the annotation corpus, and **our
    algorithm**. The first two are digested above; this is the third. It is the commit at
    build time, so it necessarily predates the commit that lands the output - close enough
    to find the code, which is the point, and the caveat is recorded in the manifest.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return result.stdout.strip() or "unknown"


def write_provenance(path: Path, inputs: list[dict], outputs: dict[str, int], release: str) -> None:
    """Record what produced these tables, in enough detail to reproduce or refute them."""
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "release": release,
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "built_by": "tools/build_phenotype_data.py",
        "code_version": code_version(),
        "code_version_note": (
            "the commit at build time, which precedes the commit that lands these files"
        ),
        "method": (
            "Resnik similarity over the most informative common ancestor, rolled up "
            "best-match-average in both directions and normalised by the query set's "
            "self-score. Human associations only - no mouse, no zebrafish, no "
            "protein-interaction random walk. This is a reimplementation of hiPHIVE's "
            "human-only path and is not Exomiser output."
        ),
        "method_citation": "Genome Medicine vol 17 art 127 (2025), PMID 41121346",
        "inputs": inputs,
        "outputs": outputs,
        "licence": "HPO is CC BY 4.0; cite PMID 33264411",
        "patient_data": (
            "none. Inputs are public ontology files; the query is the eight HPO terms "
            "owned by src/mva/phenotype/terms.py. No genomic coordinate is involved."
        ),
    }
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def read_release(path: Path) -> str:
    """The ontology's own ``data-version``, so a stored score names the release it used."""
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("data-version:"):
                return line.partition(":")[2].strip()
            if line.startswith("["):
                break
    return "unknown"


def write_term_ic(path: Path, graph: ontology.Ontology, counts: dict[str, int]) -> int:
    """One row per term: how many genes carry it, and how surprising that makes it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["hpo_id", "name", "depth", "gene_count", "information_content"])
        rows = 0
        for hpo_id in sorted(graph.concepts):
            concept = graph.concepts[hpo_id]
            if concept.obsolete:
                continue
            writer.writerow(
                [
                    hpo_id,
                    concept.name,
                    graph.depth(hpo_id),
                    counts.get(hpo_id, 0),
                    f"{graph.ic(hpo_id):.6f}",
                ]
            )
            rows += 1
    return rows


def write_gene_scores(path: Path, rankings: list[prioritise.Ranking]) -> int:
    """One row per (term set, gene). Both term sets share a file so the delta is a join.

    ``genes_considered`` is constant within a term set and repeated on every row on
    purpose. Genes that scored zero are not written - ordering zeroes against each other
    would be ordering noise - so the row count understates the population a rank is quoted
    against, and inferring it from the highest rank present would silently understate it
    too. Carrying it makes the file self-describing.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(
            [
                "term_set",
                "genes_considered",
                "gene_symbol",
                "entrez_id",
                "rank",
                "score",
                "forward",
                "reverse",
                "curated_terms",
                "best_term",
                "best_common_ancestor",
                "best_ic",
            ]
        )
        rows = 0
        for ranking in rankings:
            for score in ranking.scores:
                best = score.similarity.best
                writer.writerow(
                    [
                        ranking.term_set.name,
                        ranking.considered,
                        score.symbol,
                        score.entrez_id or "",
                        score.rank,
                        f"{score.score:.6f}",
                        f"{score.similarity.forward:.6f}",
                        f"{score.similarity.reverse:.6f}",
                        score.term_count,
                        best.query_term if best else "",
                        best.common_ancestor if best else "",
                        f"{best.ic:.6f}" if best else "",
                    ]
                )
                rows += 1
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--scratch", type=Path, default=DEFAULT_SCRATCH)
    parser.add_argument("--out-dir", type=Path, default=REFERENCE)
    parser.add_argument("--top", type=int, default=0, help="also print this many top genes")
    args = parser.parse_args(argv)

    obo = fetch(OBO_URL, args.scratch / "hp.obo")
    genes = fetch(GENES_URL, args.scratch / "genes_to_phenotype.txt")

    release = read_release(obo)
    graph = ontology.parse_obo(obo)
    corpus = associations.parse_genes_to_phenotype(genes, graph)
    counts = corpus.closure_counts(graph)
    graph.with_frequencies(counts, total=len(corpus))
    print(
        f"release {release}  {len(graph):,} terms  {len(corpus):,} annotated genes",
        file=sys.stderr,
    )

    rankings = [prioritise.rank_genes(term_set, corpus, graph) for term_set in terms.TERM_SETS]

    term_rows = write_term_ic(args.out_dir / "hpo_term_ic.tsv", graph, counts)
    score_rows = write_gene_scores(args.out_dir / "hpo_gene_scores.tsv", rankings)
    print(f"wrote   hpo_term_ic.tsv      {term_rows:,} rows", file=sys.stderr)
    print(f"wrote   hpo_gene_scores.tsv  {score_rows:,} rows", file=sys.stderr)

    write_provenance(
        args.out_dir / PROVENANCE_FILE,
        inputs=[
            {
                "name": "hp.obo",
                "url": OBO_URL,
                "sha256": sha256(obo),
                "bytes": obo.stat().st_size,
                "release": release,
                "terms": len(graph),
                "role": "the ontology graph: ancestor closure and term labels",
            },
            {
                "name": "genes_to_phenotype.txt",
                "url": GENES_URL,
                "sha256": sha256(genes),
                "bytes": genes.stat().st_size,
                "release": release,
                "annotated_genes": len(corpus),
                "role": "gene to clinical feature, and the frequencies the information "
                "content is computed from",
                "known_defect": (
                    "rows whose gene symbol is a placeholder are dropped at parse time; "
                    "in this release that is 375 rows spanning 7 distinct NCBI gene ids, "
                    "which would otherwise fuse into one fabricated gene"
                ),
            },
        ],
        outputs={"hpo_term_ic.tsv": term_rows, "hpo_gene_scores.tsv": score_rows},
        release=release,
    )
    print(f"wrote   {PROVENANCE_FILE}", file=sys.stderr)

    for ranking in rankings:
        if ranking.unresolved:
            print(
                f"WARNING {ranking.term_set.name}: unplaceable terms "
                f"{', '.join(ranking.unresolved)}",
                file=sys.stderr,
            )
        if args.top:
            print(f"\n{ranking.term_set.name} - top {args.top} of {ranking.considered:,}:")
            for score in ranking.top(args.top):
                print(f"  {score.rank:3d}. {score.symbol:12s} {score.score:.4f}  {score.summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
