"""The provenance manifests for the committed structure fixtures, one per directory.

``app/src/fixtures/data/protein/`` and ``.../gene-structure/`` hold **real** upstream data
committed into the repository: AlphaFold alpha-carbon traces and Ensembl exon boundaries,
one JSON file per gene. That is the one case where "where did this come from" cannot be
answered by reading the file — an AlphaFold coordinate and an invented amino-acid position
are both just numbers, and a reader cannot tell them apart by looking.

So each directory carries a ``_provenance.json`` written by
``tools/build_protein_fixture.py`` on every run, and this module owns its shape. Per gene
it records which model at which version was parsed, which Ensembl release the gene record
came from, what the written file hashes to, and — **field by field** — which parts are
measured and which are synthetic. :mod:`mva.viz.refprovenance` is the reader that
normalises these onto the same row shape as the ``ressources/reference`` manifests.

Merged, not replaced: a ``--gene BUB1B`` run updates BUB1B's block and leaves the other 22
alone, and a skipped gene keeps the upstream facts of the run that actually fetched it.
Overwriting the whole file on a partial run would quietly replace 22 recorded builds with
nothing.

This module writes into the app's fixture tree and is called only by a build tool, never
by a route. It is in :mod:`mva.viz` because the payloads it describes are that package's
own — :mod:`mva.viz.genestructure` and :mod:`mva.viz.proteinstructure` produce them — and
the field-by-field REAL/SYNTHETIC map has to be maintained next to the code that fills
those fields or it silently goes stale.
"""

import json
from collections.abc import Iterable
from pathlib import Path

from . import geneset, genestructure, proteinstructure, refprovenance

#: Which top-level field of ``gene-structure/<SYMBOL>.json`` is measured and which is
#: invented. The map is committed *in the manifest*, per gene, because "this fixture is
#: real data" is not a thing a reader can check by looking at the JSON: an exon boundary
#: and an invented amino-acid position are both just numbers. ``candidates`` is the only
#: synthetic field in either payload, and the manifest is where that is stated per field
#: rather than in one prose sentence somewhere else.
STRUCTURE_FIELDS = {
    "gene": "REAL — the gene set's own spelling of the symbol",
    "ensembl_id": "REAL — Ensembl stable gene id",
    "chrom": "REAL — Ensembl seq_region_name",
    "start": "REAL — Ensembl gene start, GRCh38 reference coordinate (not a patient call)",
    "end": "REAL — Ensembl gene end, GRCh38 reference coordinate (not a patient call)",
    "strand": "REAL — Ensembl strand",
    "biotype": "REAL — Ensembl biotype",
    "transcript": "REAL — the canonical transcript id",
    "protein": "REAL — the canonical translation id, null for a non-coding gene",
    "protein_length": "REAL — Ensembl translation length",
    "exons": "REAL — Ensembl exon boundaries, renumbered in transcription order",
    "domains": "REAL — Ensembl /overlap/translation features, Pfam/SMART/etc only",
    "in_panel": "REAL — derived from ressources/data-profile/mva_panel_grch38.bed",
    "candidates": "SYNTHETIC",
}

#: The same map for ``protein/<SYMBOL>.json``. ``residues`` is real and ``partners`` is
#: empty rather than synthetic — an unfetched thing, not an invented one.
PROTEIN_FIELDS = {
    "gene": "REAL — the gene set's own spelling of the symbol",
    "protein": "REAL — the Ensembl translation id the residue axis belongs to",
    "uniprot": "REAL — the UniProt accession AlphaFold DB is keyed by",
    "provenance": "REAL — which structure database answered, always 'alphafold' today",
    "model_url": "REAL — the exact mmCIF that was parsed",
    "version": "REAL — the model's latestVersion, read from the API reply",
    "protein_length": "REAL — Ensembl's translation length, the axis of record",
    "residues": "REAL — alpha-carbon coordinates and pLDDT from the mmCIF, re-rounded",
    "covered": "REAL — which residue ranges the model actually contains",
    "secondary": "REAL — _struct_conf helix/strand segments from the mmCIF",
    "partners": "EMPTY — phase 2; no experimental complex is fetched, so it is always []",
}

#: What the synthetic-candidate line says for a gene that has none.
NO_CANDIDATES = "EMPTY — no annotation was ever run outside the panel, so there are none"

#: The synthetic-candidate line for a panel gene.
SYNTHETIC_CANDIDATES = (
    "SYNTHETIC — three invented alleles scaled to this protein's length, rsid "
    "synthetic-n, which is not the shape of a dbSNP accession and renders inside the "
    "label as its own disclaimer. NEVER the proband's alleles"
)


def manifest_inputs(release: str | None, *, alphafold: bool) -> list[dict]:
    """The upstreams a fixture directory was built from, in manifest row shape."""
    inputs = [
        {
            "name": "Ensembl REST",
            "url": genestructure.ENSEMBL_BASE,
            "release": release,
            "endpoints": ["/lookup/id/{ensembl_id}?expand=1", "/overlap/translation/{ensp}"],
            "sha256": None,
            "bytes": None,
        },
        _file_input(
            geneset.DEFAULT_TSV, "the curated gene set: which symbols exist and which code"
        ),
    ]
    if alphafold:
        inputs.insert(
            1,
            {
                "name": "AlphaFold Protein Structure Database",
                "url": f"{proteinstructure.ALPHAFOLD_BASE}/api/prediction/{{accession}}",
                "release": "per gene — see genes[].latest_version",
                "endpoints": ["/api/prediction/{accession}", "the model mmCIF at cifUrl"],
                "sha256": None,
                "bytes": None,
            },
        )
    return inputs


def _file_input(path: Path, role: str) -> dict:
    """One committed file as an input row, digested from disk."""
    sha, size = refprovenance.digest(path) if path.is_file() else (None, None)
    return {
        "name": path.as_posix(),
        "url": f"file://{path.as_posix()}",
        "release": None,
        "sha256": sha,
        "bytes": size,
        "role": role,
    }


def structure_entry(payload: dict, path: Path, release: str | None) -> dict:
    """One gene's block in ``gene-structure/_provenance.json``."""
    sha, size = refprovenance.digest(path)
    fields = dict(STRUCTURE_FIELDS)
    fields["candidates"] = SYNTHETIC_CANDIDATES if payload.get("in_panel") else NO_CANDIDATES
    return {
        "symbol": payload["gene"],
        "ensembl_id": payload.get("ensembl_id"),
        "ensembl_release": release,
        "transcript": payload.get("transcript"),
        # Null, not omitted: this directory holds no protein model, and saying so is a
        # different statement from a key that happens to be missing.
        "uniprot": None,
        "model_url": None,
        "latest_version": None,
        "model_created_date": None,
        "retrieved_at": refprovenance.now(),
        "path": path.as_posix(),
        "sha256": sha,
        "bytes": size,
        "counts": {
            "exons": len(payload.get("exons") or []),
            "domains": len(payload.get("domains") or []),
            "candidates": len(payload.get("candidates") or []),
        },
        "fields": fields,
    }


def protein_entry(payload: dict, path: Path, release: str | None, model: dict) -> dict:
    """One gene's block in ``protein/_provenance.json``.

    ``model`` is a second, cheap ``/api/prediction`` reply asked only for the manifest:
    the payload carries the model URL and version because the client needs them, but not
    ``modelCreatedDate`` or ``entryId``, and the frozen contract
    ``app/src/api/types/protein.ts`` has no field to put them in. Re-asking picks the same
    entry by the same span rule, so the two cannot disagree about which isoform was drawn.
    """
    sha, size = refprovenance.digest(path)
    return {
        "symbol": payload["gene"],
        # Read back off the committed set rather than left null: this payload does not
        # carry the gene id (its axis is an amino-acid index), but a manifest row that
        # cannot name the gene record is not traceable to the other half of the exhibit.
        "ensembl_id": _gene_id(payload["gene"]),
        "ensembl_release": release,
        "protein": payload.get("protein"),
        "uniprot": payload.get("uniprot"),
        "model_url": payload.get("model_url"),
        "latest_version": payload.get("version"),
        "alphafold_entry_id": model.get("entry_id"),
        "model_created_date": model.get("created"),
        "retrieved_at": refprovenance.now(),
        "path": path.as_posix(),
        "sha256": sha,
        "bytes": size,
        "counts": {
            "residues": len(payload.get("residues") or []),
            "protein_length": payload.get("protein_length"),
            "secondary": len(payload.get("secondary") or []),
        },
        "fields": dict(PROTEIN_FIELDS),
    }


def _gene_id(symbol: str) -> str | None:
    """The curated set's Ensembl gene id for ``symbol``, or ``None`` if it has none."""
    try:
        return str(geneset.lookup(symbol)["ensembl_id"]) or None
    except LookupError:
        return None


def disk_entry(symbol: str, path: Path) -> dict:
    """The block for a file this run did not fetch and no earlier manifest describes.

    Only the digest can be measured, so only the digest is claimed. ``ensembl_release``
    and the model facts stay null rather than being copied from today's other genes: this
    file was written by a run nobody recorded, and inventing its upstream would be exactly
    the lie the manifest exists to prevent. ``--force`` fixes it.
    """
    sha, size = refprovenance.digest(path)
    return {
        "symbol": symbol,
        "ensembl_release": None,
        "uniprot": None,
        "model_url": None,
        "latest_version": None,
        "model_created_date": None,
        "retrieved_at": None,
        "path": path.as_posix(),
        "sha256": sha,
        "bytes": size,
        "note": "digest measured from disk; this run did not rebuild it and no earlier "
        "manifest recorded its upstream. Rerun with --force to record it.",
    }


def write_manifest(
    directory: Path, name: str, note: str, inputs: list[dict], genes: dict[str, dict]
) -> Path:
    """Write one fixture directory's manifest, genes in symbol order for a stable diff."""
    ordered = {symbol: genes[symbol] for symbol in sorted(genes)}
    payload = {
        "name": name,
        "kind": "fixture",
        "built_at": refprovenance.now(),
        "built_by": "tools/build_protein_fixture.py",
        "code_version": refprovenance.code_version(),
        "code_version_note": (
            "the commit at build time, which precedes the commit that lands these files"
        ),
        "note": note,
        "patient_data": (
            "none. Reference coordinates and amino-acid indices only. The one invented "
            "part is gene-structure candidates[], which exists precisely because the "
            "proband's alleles are never committed."
        ),
        "inputs": inputs,
        "outputs": [
            {
                "path": entry["path"],
                "sha256": entry["sha256"],
                "bytes": entry["bytes"],
                "rows": (entry.get("counts") or {}).get("residues"),
            }
            for entry in ordered.values()
        ],
        "genes": ordered,
    }
    path = directory / refprovenance.FIXTURE_MANIFEST
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def existing_genes(directory: Path) -> dict[str, dict]:
    """The per-gene blocks an earlier run recorded, so a partial run does not erase them."""
    try:
        payload = json.loads(
            (directory / refprovenance.FIXTURE_MANIFEST).read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return {}
    genes = payload.get("genes") if isinstance(payload, dict) else None
    return (
        {str(k): v for k, v in genes.items() if isinstance(v, dict)}
        if isinstance(genes, dict)
        else {}
    )


def redigested(directory: Path) -> dict[str, dict]:
    """The directory's per-gene blocks with every digest and byte count recomputed.

    The ``--manifest-only`` pass of ``tools/build_protein_fixture.py``: it exists because
    a manifest's ``inputs[]`` can go stale without a single fixture byte changing —
    ``ressources/reference/structure_genes.tsv`` is rebuilt by ``tools/build_gene_set.py``
    *after* the fixture run recorded its sha256, and correcting that should not cost 23
    genes' worth of upstream calls (``docs/step-0/methodology/063``).

    Only what can be measured off disk is rewritten. Every upstream fact — which model at
    which version, which Ensembl release — is kept exactly as the run that fetched it
    recorded it, and a file no manifest describes still gets the digest-only
    :func:`disk_entry` block rather than a borrowed one.
    """
    blocks = existing_genes(directory)
    for path in sorted(directory.glob("*.json")):
        if path.name.startswith("_"):
            continue
        block = blocks.get(path.stem)
        if block is None:
            blocks[path.stem] = disk_entry(path.stem, path)
            continue
        block["sha256"], block["bytes"] = refprovenance.digest(path)
        block["path"] = path.as_posix()
    return blocks


def recorded_release(manifests: Iterable[dict[str, dict]]) -> str | None:
    """The Ensembl release the *fetching* runs recorded, for a ``--manifest-only`` pass.

    Read back rather than re-asked: that pass touches no network, so claiming today's
    ``/info/data`` reply would attribute a release to gene records fetched under whatever
    release was live then. ``None`` unless every block that names a release names the same
    one — a tree built across two releases cannot be summarised by one number, and saying
    so beats picking a side.
    """
    seen = {
        str(entry["ensembl_release"])
        for blocks in manifests
        for entry in blocks.values()
        if entry.get("ensembl_release")
    }
    return seen.pop() if len(seen) == 1 else None
