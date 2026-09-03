"""One candidate gene's folded protein, as an alpha-carbon trace, for the 3D exhibit.

The 1D exhibits — the exon track and the domain lollipop
(:mod:`mva.viz.genestructure`) — answer *which domain* an allele lands in. They cannot
answer the two questions that decide a compound heterozygote (two different broken copies
of one gene, one from each parent): are the two damaged residues **close in space**, and
does either sit on a **partner interface**. Sequence distance is a poor proxy for 3D
distance. This module fetches the folded model so the browser can answer both.

Four hops, each behind the same disk cache the gene-structure route uses:

1. panel BED → Ensembl gene id (``genestructure.panel_gene``), then
   ``/lookup/id/<ENSG>?expand=1`` → the canonical transcript and its translation
   (``genestructure.pick_transcript``). Reused, not reimplemented: the whole point is that
   the 3D residue axis is the *same* axis the lollipop's ``protein_pos`` indexes into.
2. ``/xrefs/id/<ENSP>?external_db=Uniprot/SWISSPROT`` → the **UniProt accession**, the id
   AlphaFold DB is keyed by. Never hardcoded: a wrong accession silently returns a
   different protein's fold, which no downstream assertion would catch.
3. ``https://alphafold.ebi.ac.uk/api/prediction/<accession>`` → the model's ``cifUrl`` and
   ``latestVersion``, both read from the reply. Hardcoding ``model_v4`` was the specific
   mistake the design note forbade; the live reply says ``v6`` today.
4. the mmCIF itself, parsed to one point per residue by :mod:`mva.viz.mmcif`.

**Why the server parses.** The browser draws a tube through the alpha carbons and paints
each residue; it never needs the ~8,000 side-chain atoms, and parsing mmCIF client-side
means shipping a second structure library next to three.js. Trimmed and rounded, BUB1B's
1,050 residues are ~70 kB of JSON against a ~1 MB coordinate file.

**Perimeter.** Everything here is public reference data — the model is the same for every
human, and the residue axis is an amino-acid index, not a genomic coordinate. Unlike the
locus cache, this payload is publishable as-is, which makes it the one patient-informative
figure whose screenshot can go straight into the report.

Live-verified facts (``docs/step-0/methodology/056``), not assumed:

* the AlphaFold prediction endpoint returns a **list**, one entry per isoform model
  (BUB1B: ``AF-O60566-F1``, ``-2-F1``, ``-3-F1``, at 1050 / 933 / 1064 residues). The
  entry is picked by matching its modelled **span** (``uniprotEnd - uniprotStart + 1``)
  against Ensembl's translation length, so the trace and the lollipop cannot end up on two
  different isoforms — and a fragment model, which does not start at residue 1, is matched
  on the same rule rather than being unreachable.
* ``B_iso_or_equiv`` in an AlphaFold file is **pLDDT**, and the files carry
  ``_struct_conf`` but no ``_struct_sheet_range``.
"""

from typing import Any

import httpx

from . import geneset, genestructure, mmcif
from .genestructure import ENSEMBL_BASE, EnsemblError

#: The public AlphaFold Protein Structure Database API. Keyless, like Ensembl REST.
ALPHAFOLD_BASE = "https://alphafold.ebi.ac.uk"

#: Ensembl external-database names to try, in order, for the UniProt accession.
#: Swiss-Prot is the manually reviewed half of UniProt and is what AlphaFold DB is built
#: over; TrEMBL is the automatic half and the fallback for a protein nobody curated.
UNIPROT_DATABASES = ("Uniprot/SWISSPROT", "Uniprot/SPTREMBL")

#: What the endpoint reports as its provenance.
SOURCE = (
    "ensembl rest /lookup/id + /xrefs/id, "
    "alphafold db /api/prediction + the model mmCIF, "
    "ressources/data-profile/mva_panel_grch38.bed, "
    "ressources/reference/structure_genes.tsv"
)


class ProteinModelError(RuntimeError):
    """No structure could be resolved or parsed. Never faked around — the route 502s."""


class NoProteinError(RuntimeError):
    """The gene makes no protein, so there is nothing to fold. The route answers **422**.

    Deliberately not a :class:`ProteinModelError`: that class means *an upstream failed*
    and maps to 502, "come back later". A lncRNA having no translation is not a failure and
    will never resolve — 422 ("this request cannot be answered for this gene") is the only
    status that tells the client to stop asking rather than retry.
    """


def structure(
    gene: str,
    _settings: Any = None,
    *,
    client: httpx.Client | None = None,
    base_url: str = ENSEMBL_BASE,
    alphafold_url: str = ALPHAFOLD_BASE,
    timeout: float = 60.0,
) -> dict:
    """Assemble one gene's alpha-carbon trace payload. ``LookupError`` if off-panel.

    ``_settings`` is accepted and ignored so the route can call this with the same
    signature as :func:`mva.viz.genestructure.structure`; this payload reads no warehouse
    table at all, which is exactly why it carries nothing patient-derived.

    The gene is resolved through :func:`mva.viz.geneset.resolve`, the same panel-BED-first
    resolution the gene-structure route uses, so the two exhibits can never end up on two
    different gene records. ``NoProteinError`` for a gene the set marks non-coding — and
    the check is repeated against the live reply, because the TSV is a snapshot and Ensembl
    is the authority on whether today's canonical transcript translates.
    """
    gene, ensembl_id, _in_panel = geneset.resolve(gene)
    _refuse_non_coding(gene)
    own = client is None
    client = client or httpx.Client(timeout=timeout, follow_redirects=True)
    try:
        lookup = _json(client, f"{base_url.rstrip('/')}/lookup/id/{ensembl_id}?expand=1")
        if not isinstance(lookup, dict):
            raise ProteinModelError(f"{gene}: /lookup/id/{ensembl_id} did not return an object")
        transcript = genestructure.pick_transcript(lookup)
        translation = transcript.get("Translation") or {}
        protein_id = translation.get("id")
        if not protein_id:
            raise NoProteinError(f"{gene} has no protein-coding canonical transcript")
        length = _int(translation.get("length"))
        accession = uniprot_accession(client, base_url, str(protein_id))
        if not accession:
            raise ProteinModelError(f"{gene}: no UniProt accession on {protein_id}")
        model = alphafold_model(client, alphafold_url, accession, length)
        text = _text(client, str(model["model_url"]))
    finally:
        if own:
            client.close()

    return trace(gene, str(protein_id), accession, model, text, length)


def trace(
    gene: str,
    protein_id: str,
    accession: str | None,
    model: dict,
    text: str,
    length: int | None,
) -> dict:
    """The contract payload, assembled from a fetched coordinate file.

    Split from the fetching so the parse is testable against a committed mmCIF with no
    transport at all, and so a future PDB path can reuse it by passing
    ``provenance="pdb"``.

    The parser also reports *which* chain, model and residue-numbering axis it read
    (``mmcif.ca_trace_detail`` → :class:`mva.viz.mmcif.Trace`). None of that reaches this
    payload, because the frozen client contract ``app/src/api/types/protein.ts`` has no
    field for it; a file that would need those fields to be understood — one mixing the
    label and auth numbering axes — is refused by the parser instead. The axis actually
    used for BUB1B is recorded in ``docs/step-0/methodology/058``.
    """
    provenance = str(model.get("provenance") or "alphafold")
    try:
        residues = mmcif.ca_trace(text, confidence=provenance == "alphafold")
        segments = mmcif.secondary(text)
    except mmcif.MmcifError as bad:
        raise ProteinModelError(f"{gene}: {model.get('model_url')}: {bad}") from bad
    return {
        "gene": gene,
        "protein": protein_id,
        "uniprot": accession,
        "provenance": provenance,
        "model_url": str(model.get("model_url") or ""),
        "version": model.get("version"),
        # Ensembl's translation length is the axis of record, because that is the axis
        # `GeneCandidate.protein_pos` was measured on. The model's own residue count is
        # only the fallback for a translation Ensembl reports no length for.
        "protein_length": length if length is not None else residues[-1]["n"],
        "residues": residues,
        "covered": mmcif.covered([residue["n"] for residue in residues]),
        "secondary": segments,
        # Phase 2: an experimental complex's other chains, for interface colouring.
        "partners": [],
    }


def uniprot_accession(client: httpx.Client, base_url: str, protein_id: str) -> str | None:
    """The UniProt accession cross-referenced to one Ensembl translation, or ``None``.

    Swiss-Prot first, TrEMBL second. Ensembl returns a *list* of xrefs and the reply
    carries ``ensembl_identity`` / ``xref_identity``; the highest-identity row wins so a
    partial-match xref cannot outrank the 100 % one that names the same protein.
    """
    for database in UNIPROT_DATABASES:
        rows = _json(client, f"{base_url.rstrip('/')}/xrefs/id/{protein_id}?external_db={database}")
        best = sorted(
            (
                row
                for row in (rows if isinstance(rows, list) else [])
                if isinstance(row, dict) and row.get("primary_id")
            ),
            key=lambda row: -(_int(row.get("xref_identity")) or 0),
        )
        if best:
            return str(best[0]["primary_id"])
    return None


def alphafold_model(
    client: httpx.Client, alphafold_url: str, accession: str, length: int | None
) -> dict:
    """``{model_url, version, provenance}`` for the AlphaFold entry matching ``length``.

    The endpoint answers with one entry per isoform model, so "the first one" is a coin
    flip on which isoform gets drawn. Preference order: an entry whose modelled **span**
    matches Ensembl's translation length, then the canonical ``AF-<acc>-F1`` id, then the
    first entry — with the version always read from the reply, never composed.

    The span is ``uniprotEnd - uniprotStart + 1``, not ``uniprotEnd``. Those two agree only
    for a model that starts at residue 1: a fragment entry (``F2`` of a protein too long
    for one model) starts partway in, so comparing the end position alone can never match
    it, and can match a *different* isoform whose end happens to equal the length.
    """
    entries = _json(client, f"{alphafold_url.rstrip('/')}/api/prediction/{accession}")
    usable = [
        entry
        for entry in (entries if isinstance(entries, list) else [])
        if isinstance(entry, dict) and entry.get("cifUrl")
    ]
    if not usable:
        raise ProteinModelError(f"AlphaFold DB has no model with a cifUrl for {accession}")
    chosen = usable[0]
    for entry in usable:
        if entry.get("entryId") == f"AF-{accession}-F1":
            chosen = entry
            break
    if length is not None:
        for entry in usable:
            if _span(entry) == length:
                chosen = entry
                break
    version = chosen.get("latestVersion")
    return {
        "model_url": chosen["cifUrl"],
        "version": None if version is None else str(version),
        "provenance": "alphafold",
        # Provenance only. `trace` does not read it and the frozen client contract
        # `app/src/api/types/protein.ts` has no field for it, so it never reaches the
        # payload; `tools/build_protein_fixture.py` records it in the fixture manifest,
        # which is the one place "which model release is this fold" can be answered.
        "created": chosen.get("modelCreatedDate"),
        "entry_id": chosen.get("entryId"),
    }


# ── internals ────────────────────────────────────────────────────────────────────────


def _refuse_non_coding(gene: str) -> None:
    """Refuse a gene the curated set already knows makes no protein, before any HTTP call.

    Saves two round trips per request for the lncRNAs in the set, and — more usefully —
    means the 422 does not depend on Ensembl being reachable: "this gene has no protein" is
    a fact the committed TSV holds, so it should not turn into a 502 during an outage.
    A gene absent from the set is *not* refused here; the live reply decides.
    """
    try:
        entry = geneset.lookup(gene)
    except LookupError:
        return
    if not entry["coding"]:
        raise NoProteinError(f"{gene} has no protein-coding canonical transcript")


def _json(client: httpx.Client, url: str) -> Any:
    """A GET whose reply must be JSON. Everything else becomes a stated failure."""
    body = _call(client, url, {"Accept": "application/json"})
    try:
        return body.json()
    except ValueError as bad:
        raise ProteinModelError(f"GET {url}: reply was not JSON") from bad


def _text(client: httpx.Client, url: str) -> str:
    """The coordinate file, as text."""
    return _call(client, url, {"Accept": "text/plain"}).text


def _call(client: httpx.Client, url: str, headers: dict[str, str]) -> httpx.Response:
    """One GET, with every failure turned into :class:`ProteinModelError`.

    No retry loop, for the reason ``genestructure._call`` states: this is a request-scoped
    fetch behind a disk cache, so the cheap recovery is ``?refresh=true``, and a retry
    only lengthens the wait on an outage the browser should be told about.
    """
    try:
        response = client.get(url, headers=headers)
    except httpx.HTTPError as error:
        raise ProteinModelError(f"GET {url}: {type(error).__name__}: {error}") from error
    if response.status_code != 200:
        raise ProteinModelError(f"GET {url} -> {response.status_code}: {response.text[:200]}")
    return response


def _span(entry: dict) -> int | None:
    """How many residues one AlphaFold entry models, inclusive of both ends.

    ``uniprotStart`` is absent on some entries; 1 is the only defensible default, and it
    is the value the field takes on every full-length model.
    """
    end = _int(entry.get("uniprotEnd"))
    if end is None:
        return None
    start = _int(entry.get("uniprotStart"))
    return end - (1 if start is None else start) + 1


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# Re-exported so the route can catch one class for "an upstream refused". Ensembl failures
# reach here through the reused `pick_transcript`, which raises its own error type.
UPSTREAM_ERRORS = (ProteinModelError, EnsemblError)
