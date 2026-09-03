"""The build manifest for ``ressources/reference/structure_genes.tsv``.

``tools/build_gene_set.py`` resolves a curated list of gene symbols against Ensembl REST
and writes the TSV. This module owns the JSON manifest it writes beside it: what was
fetched, from which server at which release, which committed files were read and what they
hashed to, what the output hashed to, and every OMIM phenotype number and PubMed id the
curated notes cite.

Written by the tool on every run, never maintained by hand — which is the whole point. A
manifest a human edits is a claim, and a claim about provenance is exactly the thing that
must not be one. :func:`mva.viz.geneset.provenance` is the reader that pulls the release
and the digest back out for the ``/panel/structure-genes`` envelope, and
:mod:`mva.viz.refprovenance` normalises the file onto the row shape
``GET /api/provenance/reference`` returns.

The shape mirrors ``ressources/reference/hpo_provenance.json`` so neither needs
special-casing. The one structural difference is deliberate: ``outputs`` here is a *list*
carrying the digest measured at build time, where the HPO manifest maps file name to row
count and records no digest, so a digest for it can only be computed later off disk — a
weaker statement, and the reader says so.

This module writes no genomic coordinate and cannot: it records gene symbols, stable ids,
file digests and citations. That is the perimeter rule for every manifest in the
repository, and ``tests/test_viz_refprovenance.py`` asserts it over the committed files.
"""

import re
from collections.abc import Sequence
from pathlib import Path

from . import refprovenance

#: The Ensembl endpoints this tool calls, recorded in the manifest. Written out rather
#: than inferred, because "we called Ensembl" is not a provenance statement: ``/lookup``
#: and ``/xrefs`` answer different questions and only one of them resolves a retired
#: symbol, which is the fact this whole tool turned on.
ENDPOINTS = (
    "/info/data",
    "/lookup/symbol/homo_sapiens/{symbol}?expand=1",
    "/xrefs/symbol/homo_sapiens/{symbol}",
)

#: One paragraph saying what the output *is*, for a reader who has only the manifest.
METHOD = (
    "Every symbol in the editable spec TSV is resolved against the live Ensembl REST "
    "server: /lookup/symbol for the gene record, and /xrefs/symbol to confirm an alias "
    "names the same gene id (membership in the xref list, not a single match, because a "
    "gene present on a patch scaffold legitimately matches twice). The stable gene id, "
    "the biotype and the coding flag are read from the reply and never hand-written; "
    "coding means the canonical transcript carries a Translation, not that the biotype "
    "string says protein_coding, because those two disagree and only the first decides "
    "whether a protein exhibit can be drawn. The canonical transcript is matched on the "
    "unversioned id, the same rule mva.viz.genestructure.pick_transcript applies, so the "
    "flag written here cannot disagree with what the live route finds. Every gene in the "
    "panel group is asserted to carry the panel BED's own gene id, and the build fails "
    "rather than preferring one side, because the BED's intervals are what the proband's "
    "callset was actually annotated against. The group and the note are curation, not "
    "measurement: a blank note for a panel gene is borrowed from the BED's sixth column "
    "so that fact keeps one owner."
)

#: How an OMIM phenotype number and a PubMed id are spelled in the curated notes.
CITATION = {"omim": re.compile(r"OMIM (\d{6})"), "pmid": re.compile(r"PMID (\d{6,9})")}


def literature(genes: Sequence[dict]) -> list[dict]:
    """Every OMIM phenotype number and PubMed id the curated notes cite, per gene.

    **Extracted, not retyped.** The notes in the spec TSV are the one place a citation is
    written; a hand-maintained second list beside them would drift, and a drifted citation
    is worse than none because it looks checked. A gene whose note cites nothing is
    omitted rather than listed empty — the absence of a citation is what its note says in
    words ("no documented MVA link found"), and repeating that as an empty array adds no
    fact.
    """
    out = []
    for entry in genes:
        note = str(entry.get("note") or "")
        cited = {name: sorted(set(pattern.findall(note))) for name, pattern in CITATION.items()}
        if not any(cited.values()):
            continue
        out.append(
            {
                "gene": entry["symbol"],
                "group": entry.get("group", ""),
                "omim": cited["omim"],
                "pmid": cited["pmid"],
                "claim": note,
            }
        )
    return out


def manifest(
    genes: Sequence[dict],
    out: Path,
    spec: Path | None,
    bed: Path,
    base_url: str,
    release: str | None,
) -> dict:
    """The build manifest: what was fetched, from where, at which release, into what.

    ``genes`` is one dict per resolved row, carrying at least ``symbol``, ``group`` and
    ``note`` — plain data rather than the tool's own dataclass, so the shape of this file
    is owned here and the tool cannot change it by refactoring a class.

    Written by the tool on every run rather than maintained by hand, for the reason the
    whole file exists: a manifest a human edits is a claim, and a claim about provenance
    is exactly the thing that must not be one. Mirrors ``hpo_provenance.json``'s shape so
    ``GET /api/provenance/reference`` can list both without special-casing either.

    ``code_version`` is the commit at *build* time, which precedes the commit that lands
    the built file — the same caveat ``hpo_provenance.json`` states.
    """
    sha, size = refprovenance.digest(out)
    inputs: list[dict] = [
        {
            "name": "Ensembl REST",
            "url": base_url,
            "release": release,
            "endpoints": list(ENDPOINTS),
            "sha256": None,
            "bytes": None,
            "role": "the gene id, the biotype and whether the canonical transcript translates",
        }
    ]
    for path, role in (
        (spec, "the editable input: symbol, display group, curated note"),
        (bed, "the panel's own gene ids, which the panel group is asserted against"),
    ):
        if path is None:
            continue
        digest, byte_count = refprovenance.digest(path) if path.is_file() else (None, None)
        inputs.append(
            {
                "name": path.as_posix(),
                "url": f"file://{path.as_posix()}",
                "release": None,
                "sha256": digest,
                "bytes": byte_count,
                "role": role,
            }
        )
    return {
        "name": "structure_genes",
        "built_at": refprovenance.now(),
        "built_by": "tools/build_gene_set.py",
        "code_version": refprovenance.code_version(),
        "code_version_note": (
            "the commit at build time, which precedes the commit that lands this file"
        ),
        "method": METHOD,
        "inputs": inputs,
        "outputs": [{"path": out.as_posix(), "sha256": sha, "bytes": size, "rows": len(genes)}],
        "literature": literature(genes),
        "licence": (
            "Ensembl is Apache 2.0 / no-restriction for the annotation; OMIM numbers and "
            "PubMed ids are citations, not redistributed content"
        ),
        "patient_data": (
            "none. A gene symbol, a stable gene id and a biotype are public reference "
            "facts. No genomic position of any kind is written to this file or the TSV."
        ),
        "note": (
            f"{len(genes)} curated genes resolved live against Ensembl REST "
            f"release {release or 'unknown'}; ids, biotypes and the coding flag come from "
            "the reply, groups and notes are curation."
        ),
    }
