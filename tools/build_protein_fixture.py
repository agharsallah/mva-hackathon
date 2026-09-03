"""Build the committed structure fixtures from the live public sources, one file per gene.

    uv run python tools/build_protein_fixture.py                     # the whole gene set
    uv run python tools/build_protein_fixture.py --gene BUB1B TP53   # just these
    uv run python tools/build_protein_fixture.py --dry-run           # fetch, report, write nothing
    uv run python tools/build_protein_fixture.py --manifest-only     # re-digest, no network

**Run order: ``tools/build_gene_set.py`` first, then this tool.** This tool reads
``ressources/reference/structure_genes.tsv`` — which symbols exist and which code — and
records that file's sha256 as an *input* in both fixture manifests. Rebuilding the TSV
afterwards leaves those two digests naming bytes that are no longer on disk, which is
exactly the defect ``docs/step-0/methodology/063`` records. If the TSV is rebuilt after a
fixture run, ``--manifest-only`` corrects the input digests without refetching 23 genes:
it re-digests the committed fixtures, keeps every per-gene upstream fact an earlier run
measured, and reuses the Ensembl release those runs recorded rather than inventing one.
``tests/test_viz_referencemanifest.py`` fails until it is run.

Two files per gene, both under ``app/src/fixtures/data/``:

* ``gene-structure/<SYMBOL>.json`` — the gene's **real** exons and protein domains from
  Ensembl (:func:`mva.viz.genestructure.anatomy`), plus **synthetic** candidate alleles for
  the panel genes only. Every field except ``candidates`` is measured.
* ``protein/<SYMBOL>.json`` — the gene's **real** AlphaFold alpha-carbon trace, produced by
  the same :mod:`mva.viz.proteinstructure` code the live route runs. Coding genes only: a
  lncRNA has no protein, and the live route answers 422 for it rather than inventing one.

**Why one file per gene.** The fixture loader imports each JSON as its own lazy chunk, so a
reader who opens BUB1B downloads BUB1B's fold and nothing else. It also removes the lie the
previous single-file fixture told: it handed *every* gene BUB1B's backbone with its own name
on it, which is invisible until two genes are put side by side and then reads as "these two
proteins are the same shape".

**Why real data is committable.** An AlphaFold model, an exon boundary and a Pfam domain are
public reference facts, identical for every human. Nothing patient-derived can ride on them:
the axis is an amino-acid index or a reference genome coordinate, never a proband record. The
one synthetic part — the candidate alleles — is invented precisely *because* the proband's
are never committed.

Reads three public keyless sources (Ensembl REST, the AlphaFold DB API, the model mmCIF). It
touches no warehouse table and no delivery object, so it runs on a bare checkout.
"""

import argparse
import json
import time
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any, TypeVar

import httpx

from mva.viz import (
    ensembl,
    fixturemanifest,
    fixturesynthetic,
    geneset,
    genestructure,
    proteinstructure,
)

PROTEIN_DIR = Path("app/src/fixtures/data/protein")
STRUCTURE_DIR = Path("app/src/fixtures/data/gene-structure")

#: The gene-set index fixture — the offline answer to ``GET /api/panel/structure-genes``.
#: Written from :func:`mva.viz.geneset.genes` so the offline list cannot drift from the
#: committed TSV, and only on a full build: a ``--gene`` subset would truncate the index.
INDEX_FILE = Path("app/src/fixtures/data/panel-structure-genes.json")

#: Above this many bytes a trace is re-rounded (see :func:`compact`). 60 kB is roughly
#: BUB1B at full precision, and the point past which a single lazy chunk stops being cheap.
COMPACT_ABOVE = 60_000

#: Attempts per gene, and the pause between them.
#:
#: The *routes* never retry, for the reason ``mva.viz.genestructure._call`` states. A batch
#: build over 23 genes and ~70 upstream calls is the opposite trade: observed live, Ensembl
#: answered ``/overlap/translation/ENSP00000317902`` with a 500 once and a 200 moments
#: later, and losing the whole run to that would be absurd. Bounded, and it re-raises.
ATTEMPTS, PAUSE = 6, 8.0

T = TypeVar("T")


def compact(payload: dict) -> dict:
    """Re-round a trace for size: coordinates to 1 decimal, pLDDT to a whole number.

    Lossy on purpose, and only in the *fixture*. 0.1 Å is far below the ~1 Å spread the
    prediction itself is uncertain by, and pLDDT is read against 50/70 thresholds, so a
    tenth of a point carries no meaning. The live route keeps the parser's 2 decimals,
    because there the file is fetched once and cached, not committed.
    """
    for residue in payload.get("residues") or []:
        residue["ca"] = [round(value, 1) for value in residue["ca"]]
        if residue.get("plddt") is not None:
            residue["plddt"] = round(residue["plddt"])
    return payload


def write_json(path: Path, payload: Any) -> int:
    """Write compact JSON and return the byte count."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, separators=(",", ":"), sort_keys=False) + "\n", encoding="utf-8"
    )
    return path.stat().st_size


def retrying(label: str, build: Callable[[], T]) -> T:
    """Run ``build``, retrying a transient upstream failure a bounded number of times."""
    for attempt in range(1, ATTEMPTS + 1):
        try:
            return build()
        except (*proteinstructure.UPSTREAM_ERRORS, httpx.HTTPError) as failed:
            if attempt == ATTEMPTS:
                raise
            print(f"    {label}: retry {attempt}/{ATTEMPTS - 1} after {failed}"[:200])
            time.sleep(PAUSE)
    raise AssertionError("unreachable")


def build_structure(client: httpx.Client, entry: dict) -> dict:
    """One gene's real anatomy plus, for a panel gene only, synthetic candidates."""
    symbol, ensembl_id, in_panel = geneset.resolve(entry["symbol"])
    payload = genestructure.anatomy(client, symbol, ensembl_id, in_panel)
    payload["candidates"] = (
        fixturesynthetic.candidates(payload["protein_length"], payload["transcript"])
        if in_panel
        else []
    )
    return payload


def build_protein(symbol: str) -> dict:
    """One gene's real AlphaFold trace, through the live route's own code path."""
    return proteinstructure.structure(symbol)


#: What each fixture directory's manifest calls itself, and whether AlphaFold is one of
#: its upstreams. Data rather than code, so adding a third fixture directory is one entry.
DIRECTORY_NOTES = {
    "structure_dir": (
        "gene-structure fixtures",
        (
            "One file per gene: real Ensembl exons and protein domains. The only invented "
            "field is candidates[], present for the eight annotated panel genes and empty "
            "for every other gene, because no annotation was ever run there."
        ),
        False,
    ),
    "protein_dir": (
        "protein-structure fixtures",
        (
            "One file per coding gene: that gene's own real AlphaFold alpha-carbon trace, "
            "public reference data identical for every human. Nothing here is invented; "
            "partners[] is empty because no experimental complex is fetched yet."
        ),
        True,
    ),
}


def record_skipped(args, manifests: dict[Path, dict[str, dict]], symbol: str) -> int:
    """Account for a gene whose files already existed, and return their byte count.

    A skipped gene keeps whatever an earlier manifest recorded about it. Only when no
    manifest describes it at all does it get a digest-only block, which says in its own
    ``note`` that its upstream is unrecorded — see :func:`mva.viz.fixturemanifest.disk_entry`.
    """
    total = 0
    for directory in (args.structure_dir, args.protein_dir):
        path = directory / f"{symbol}.json"
        if not path.exists():
            continue
        total += path.stat().st_size
        if symbol not in manifests[directory]:
            manifests[directory][symbol] = fixturemanifest.disk_entry(symbol, path)
    return total


def write_manifests(args, release: str | None, manifests: dict[Path, dict[str, dict]]) -> None:
    """Write one ``_provenance.json`` per fixture directory and report each."""
    for attribute, (name, note, alphafold) in DIRECTORY_NOTES.items():
        directory = getattr(args, attribute)
        written = fixturemanifest.write_manifest(
            directory,
            name,
            note,
            fixturemanifest.manifest_inputs(release, alphafold=alphafold),
            manifests[directory],
        )
        print(f"{written} — {len(manifests[directory])} genes")


def rewrite_index(args) -> None:
    """``--index-only``: rewrite the gene-set index fixture from the committed TSV.

    The offline half of a curation-only gene-set rebuild. Renaming or re-ranking a display
    group changes the index fixture and nothing else — no per-gene fold moves — so it must
    not require the ~70 upstream calls a full build spends.
    """
    catalogue = geneset.genes(args.tsv)
    if not catalogue:
        raise SystemExit(f"no gene set at {args.tsv or geneset.DEFAULT_TSV}")
    wrote = write_json(args.index, catalogue)
    print(f"{args.index} — {len(catalogue)} genes, {wrote:,} bytes")


def rewrite_manifests(args) -> None:
    """``--manifest-only``: re-digest the committed fixtures and rewrite both manifests.

    Every per-gene block keeps the upstream facts of the run that fetched it; only the
    digests, the byte counts and the ``inputs[]`` file digests are recomputed. Nothing is
    fetched, so nothing new can be claimed — see
    :func:`mva.viz.fixturemanifest.redigested` and
    :func:`mva.viz.fixturemanifest.recorded_release`.
    """
    manifests = {
        directory: fixturemanifest.redigested(directory)
        for directory in (args.structure_dir, args.protein_dir)
    }
    write_manifests(args, fixturemanifest.recorded_release(manifests.values()), manifests)


def parse_args() -> argparse.Namespace:
    """The command line. Split out of :func:`main` so that function stays readable."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gene", nargs="*", help="symbols to build (default: the whole set)")
    parser.add_argument(
        "--tsv", type=Path, default=None, help=f"gene set TSV (default: {geneset.DEFAULT_TSV})"
    )
    parser.add_argument("--index", type=Path, default=INDEX_FILE)
    parser.add_argument("--protein-dir", type=Path, default=PROTEIN_DIR)
    parser.add_argument("--structure-dir", type=Path, default=STRUCTURE_DIR)
    parser.add_argument(
        "--force", action="store_true", help="rebuild genes whose files already exist"
    )
    parser.add_argument("--dry-run", action="store_true", help="fetch and report, write nothing")
    parser.add_argument(
        "--index-only",
        action="store_true",
        help="rewrite the gene-set index fixture from the committed TSV; no network. Use it "
        "after a curation-only gene-set rebuild, which changes no per-gene fixture.",
    )
    parser.add_argument(
        "--manifest-only",
        action="store_true",
        help="rewrite both _provenance.json from the committed files; no network",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.index_only:
        rewrite_index(args)
        return

    if args.manifest_only:
        rewrite_manifests(args)
        return

    catalogue = geneset.genes(args.tsv)
    if not catalogue:
        raise SystemExit(f"no gene set at {args.tsv or geneset.DEFAULT_TSV}")
    wanted = [geneset.lookup(symbol, args.tsv) for symbol in args.gene] if args.gene else catalogue

    # Merged onto what earlier runs recorded, so a `--gene` subset updates one block
    # instead of erasing 22. See `mva.viz.fixturemanifest`.
    manifests = {
        args.structure_dir: fixturemanifest.existing_genes(args.structure_dir),
        args.protein_dir: fixturemanifest.existing_genes(args.protein_dir),
    }

    total = 0
    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        release = ensembl.release(client=client)
        print(
            f"ensembl release {release or 'unknown'} (GET {genestructure.ENSEMBL_BASE}/info/data)"
        )
        for entry in wanted:
            symbol = entry["symbol"]
            done = args.structure_dir / f"{symbol}.json"
            waiting = entry["coding"] and not (args.protein_dir / f"{symbol}.json").exists()
            if not args.force and not args.dry_run and done.exists() and not waiting:
                total += record_skipped(args, manifests, symbol)
                print(f"{symbol:<12} {entry['group']:<9} already built — skipped (--force to redo)")
                continue
            structure = retrying(symbol, partial(build_structure, client, entry))
            protein = retrying(symbol, partial(build_protein, symbol)) if entry["coding"] else None
            if args.dry_run:
                print(
                    f"{symbol:<12} {structure['ensembl_id']} exons={len(structure['exons']):<3} "
                    f"domains={len(structure['domains']):<3} "
                    f"candidates={len(structure['candidates'])} "
                    f"residues={len(protein['residues']) if protein else '—'}"
                )
                continue

            structure_path = args.structure_dir / f"{symbol}.json"
            wrote = write_json(structure_path, structure)
            total += wrote
            manifests[args.structure_dir][symbol] = fixturemanifest.structure_entry(
                structure, structure_path, release
            )
            line = (
                f"{symbol:<12} {entry['group']:<9} gene-structure {wrote / 1024:6.1f} kB "
                f"({len(structure['exons'])} exons, {len(structure['domains'])} domains, "
                f"{len(structure['candidates'])} synthetic candidates)"
            )
            if protein is None:
                print(f"{line} | protein: none — {entry['biotype']}, no translation")
                continue
            path = args.protein_dir / f"{symbol}.json"
            wrote = write_json(path, protein)
            if wrote > COMPACT_ABOVE:
                before = wrote
                wrote = write_json(path, compact(protein))
                print(f"{'':<12} {'':<9} compacted {before / 1024:.1f} → {wrote / 1024:.1f} kB")
            total += wrote
            model = retrying(
                symbol,
                partial(
                    proteinstructure.alphafold_model,
                    client,
                    proteinstructure.ALPHAFOLD_BASE,
                    str(protein["uniprot"]),
                    protein["protein_length"],
                ),
            )
            manifests[args.protein_dir][symbol] = fixturemanifest.protein_entry(
                protein, path, release, model
            )
            print(
                f"{line} | protein {wrote / 1024:6.1f} kB "
                f"({protein['protein']} / {protein['uniprot']} {protein['provenance']} "
                f"v{protein['version']}, {len(protein['residues'])} of "
                f"{protein['protein_length']} residues, covered {protein['covered']})"
            )

    if args.dry_run:
        return
    if not args.gene:
        total += write_json(args.index, catalogue)
        print(f"{args.index} — {len(catalogue)} genes")

    write_manifests(args, release, manifests)
    print(f"\n{len(wanted)} genes — {total:,} bytes total ({total / 1024:.1f} kB)")


if __name__ == "__main__":
    main()
