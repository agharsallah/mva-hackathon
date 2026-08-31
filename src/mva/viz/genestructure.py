"""One candidate gene's anatomy, assembled from Ensembl REST for the locus explorer.

The locus tracks plot patient records against a bare number line. That number line means
nothing on its own: whether a record sits in an **exon** (a stretch that ends up in the
protein) or an **intron** (a stretch spliced out before translation) is the difference
between "changes the protein" and "probably nothing". This module fetches that anatomy so
the chart can draw it under the existing tracks, and fetches the **protein domains** (the
functional sub-units of the folded protein, as Pfam/SMART/… annotate them) so a
protein-altering allele can be placed against the part of the machine it breaks.

**The browser never calls Ensembl.** Three reasons, in order: the public REST server sets
no CORS header a Vite dev origin can use, an API key discipline belongs on one server not
in every tab, and the third call sends the proband's alleles — which must not leave a
process we control the logging of.

Three live-verified facts about the API shape drove the code, not assumed:

* ``/lookup/id/<ENSG>?expand=1`` returns every transcript with its ``Exon`` list **in
  transcript order** — descending coordinates on the minus strand. The exons are
  re-sorted here anyway, so the numbering survives an API that ever stops doing that.
* ``canonical_transcript`` is **versioned** (``ENST00000287598.11``) while the transcript
  objects' ``id`` is not, so the match is on the part before the dot.
* ``/overlap/translation/<ENSP>`` returns far more than domains: PDB cross-references
  (``sifts``), an AlphaFold model, low-complexity (``Seg``), disorder (``MobiDBLite``) and
  coiled-coil (``ncoils``) predictions. Those are not domains and are filtered out.
  ``PANTHER`` is filtered out too — it is a whole-protein *family* assignment (21–1036 of
  1050 aa for BUB1B), which as a bar would read as "the entire protein is one domain".

Everything in the payload is **public reference data plus derived protein offsets** — no
patient genomic coordinate is emitted, which is why this cache entry, unlike the locus
one, holds nothing that could not be published.
"""

from typing import Any, Iterable

import httpx

from ..pipeline.variant import Variant
from ..pipeline.vep_response import query_line
from . import panelbed, queries

#: The public Ensembl REST server. Same host the panel annotation ran against.
ENSEMBL_BASE = "https://rest.ensembl.org"

#: Feature sources that describe a *domain* — a conserved, independently folding part of
#: the protein. Matched case-insensitively because Ensembl spells them ``Smart``,
#: ``SuperFamily``, ``Prosite_profiles``. Everything else the endpoint returns is a
#: prediction or a cross-reference and is dropped; see the module docstring.
DOMAIN_SOURCES = frozenset({
    "pfam", "smart", "prosite_profiles", "prosite_patterns", "superfamily",
    "gene3d", "cdd", "prints", "pirsf", "tigrfam", "hamap",
})

#: What the endpoint reports as its provenance.
SOURCE = ("ensembl rest /lookup/id + /overlap/translation + /vep/homo_sapiens/region, "
          "pg.results.panel_candidates, ressources/data-profile/mva_panel_grch38.bed")

#: Consequence suffix stripped when building a short human label.
_SUFFIX = "_variant"


class EnsemblError(RuntimeError):
    """Ensembl REST could not be reached or refused a request. Never faked around."""


def structure(gene: str, settings: Any, *, client: httpx.Client | None = None,
              base_url: str = ENSEMBL_BASE, timeout: float = 30.0) -> dict:
    """Assemble one gene's exon/domain/candidate payload. ``LookupError`` if off-panel."""
    ensembl_id = panel_gene(gene)
    own = client is None
    client = client or httpx.Client(timeout=timeout)
    try:
        lookup = _get(client, base_url, f"/lookup/id/{ensembl_id}?expand=1")
        transcript = pick_transcript(lookup)
        translation = transcript.get("Translation") or {}
        protein_id = translation.get("id")
        domains = fetch_domains(client, base_url, protein_id) if protein_id else []
        rows = protein_altering(settings, gene)
        placed, failure = protein_positions(client, base_url, rows, transcript.get("id"))
    finally:
        if own:
            client.close()

    return {
        "gene": gene,
        "ensembl_id": ensembl_id,
        "chrom": str(lookup.get("seq_region_name") or ""),
        "start": _int(lookup.get("start")),
        "end": _int(lookup.get("end")),
        "strand": _int(lookup.get("strand")) or 1,
        "biotype": lookup.get("biotype"),
        "transcript": transcript.get("id"),
        "protein": protein_id,
        "protein_length": _int(translation.get("length")),
        "exons": exons(transcript, _int(lookup.get("strand")) or 1),
        "domains": domains,
        "candidates": [candidate(row, placed, failure, transcript.get("id"))
                       for row in rows],
    }


def panel_gene(gene: str) -> str:
    """The panel BED's Ensembl gene id for ``gene``, or ``LookupError``.

    Validated against the committed BED rather than the warehouse copy of it: the BED is
    the panel's source of truth *and* it is the only place the stable gene id survives
    (staging keeps the four standard BED columns). One file read, no database round trip.
    """
    entry = (panelbed.annotations() or {}).get(gene)
    if not entry or not entry.get("ensembl_id"):
        raise LookupError(gene)
    return str(entry["ensembl_id"])


def pick_transcript(lookup: dict) -> dict:
    """The canonical transcript object out of an expanded ``/lookup/id`` reply.

    Canonical first — it is the one every downstream tool (VEP's ``canonical``, gnomAD's
    constraint row) reports against, so picking anything else would put the domains and
    the variants' protein positions on two different coordinate systems.
    """
    transcripts = lookup.get("Transcript") or []
    if not transcripts:
        raise EnsemblError(f"no transcripts for {lookup.get('id')!r}")
    wanted = str(lookup.get("canonical_transcript") or "").split(".")[0]
    for entry in transcripts:
        if wanted and entry.get("id") == wanted:
            return entry
    for entry in transcripts:
        if entry.get("is_canonical"):
            return entry
    # No canonical flag at all: prefer something that translates, so the domain track has
    # a protein to hang off, rather than the first transcript the API happened to list.
    coding = [e for e in transcripts if e.get("Translation")]
    return (coding or transcripts)[0]


def exons(transcript: dict, strand: int) -> list[dict]:
    """The transcript's exons, numbered 1..n **in transcript order**.

    On the minus strand transcription runs from high coordinate to low, so exon 1 is the
    rightmost box on a coordinate axis. Numbering by coordinate instead would disagree
    with every clinical report, which says "exon 11" meaning the eleventh one *read*.
    """
    found = [
        {"start": _int(e.get("start")), "end": _int(e.get("end")), "id": e.get("id")}
        for e in transcript.get("Exon") or []
        if e.get("start") is not None and e.get("end") is not None
    ]
    found.sort(key=lambda e: e["start"], reverse=strand < 0)
    for number, exon in enumerate(found, start=1):
        exon["n"] = number
    return found


def fetch_domains(client: httpx.Client, base_url: str, protein_id: str) -> list[dict]:
    """Domain features on one translation, filtered to :data:`DOMAIN_SOURCES`."""
    features = _get(client, base_url, f"/overlap/translation/{protein_id}")
    if not isinstance(features, list):
        return []
    out = []
    for feature in features:
        source = str(feature.get("type") or "")
        if source.lower() not in DOMAIN_SOURCES:
            continue
        start, end = _int(feature.get("start")), _int(feature.get("end"))
        if start is None or end is None:
            continue
        accession = feature.get("id")
        out.append({
            "source": source,
            "accession": accession,
            # An empty description is common on structural sources (Gene3D), where the
            # accession *is* the name people quote.
            "name": (feature.get("description") or "").strip() or accession,
            "start_aa": start,
            "end_aa": end,
            "interpro": feature.get("interpro") or None,
        })
    out.sort(key=lambda d: (d["start_aa"], d["end_aa"], d["source"]))
    return out


def protein_altering(settings: Any, gene: str) -> list[dict]:
    """The gene's protein-altering annotated alleles, rarest first.

    ``panel_annotations`` stores gene, consequence and impact — **no protein position** —
    so rarity and severity are all this query can supply; the amino-acid offset has to be
    asked of VEP separately (:func:`protein_positions`).

    The filter is ``is_protein_altering`` rather than *rare and* protein-altering: only
    one panel gene has a rare protein-altering allele at all, so the stricter filter would
    hand seven of eight genes an empty exhibit. Rarity is kept as the ``rare`` flag and
    marked in the plot instead of silently deciding what the reader may see.
    """
    rows = queries.panel_candidates(settings, gene)
    return sorted((row for row in rows if row.get("is_protein_altering")),
                  key=lambda row: (not row.get("is_rare_recessive"),
                                   row.get("pos") or 0, row.get("alt") or ""))


def protein_positions(client: httpx.Client, base_url: str, rows: Iterable[dict],
                      transcript_id: str | None) -> tuple[dict[str, int], str | None]:
    """Amino-acid offsets for ``rows``, keyed by VEP query line, plus a failure reason.

    One POST to VEP's region endpoint for the whole (single-digit) list. It is the only
    call in this module that transmits patient coordinates, and it is justified the same
    way ``docs/step-0/methodology/031`` justified the annotation run: VEP is the authority
    on the transcript's reading frame, and re-deriving a codon offset from exon bounds
    locally would be a second, untested implementation of it.

    Never raises: a VEP outage leaves every candidate unplaced *with a stated reason*,
    which is a weaker exhibit but a true one.
    """
    lines = [query_line(Variant.from_vcf(row["chrom"], row["pos"], row["ref"], row["alt"]))
             for row in rows if _has_allele(row)]
    if not lines:
        return {}, None
    try:
        body = _post(client, base_url, "/vep/homo_sapiens/region",
                     {"variants": lines, "canonical": 1})
    except EnsemblError as failed:
        return {}, str(failed)
    found: dict[str, int] = {}
    for item in body if isinstance(body, list) else []:
        key = item.get("input")
        start = _protein_start(item, transcript_id)
        if key and start is not None:
            found[key] = start
    return found, None


def candidate(row: dict, placed: dict[str, int], failure: str | None,
              transcript_id: str | None) -> dict:
    """One allele as the chart needs it: no genomic coordinate, ever.

    ``protein_pos`` is null whenever VEP put no amino-acid offset on the canonical
    transcript — a splice-region or UTR consequence has none — and ``reason`` says which
    of the two causes applies, so the frontend can list it rather than drop it.
    """
    key = (query_line(Variant.from_vcf(row["chrom"], row["pos"], row["ref"], row["alt"]))
           if _has_allele(row) else None)
    position = placed.get(key) if key else None
    consequence = row.get("consequence") or "unknown consequence"
    return {
        "consequence": consequence,
        "impact": row.get("impact"),
        "rsid": row.get("rsid"),
        "rare": bool(row.get("is_rare_recessive")),
        "clin_sig": row.get("clin_sig"),
        "gt": row.get("gt"),
        "filter": row.get("filter"),
        "label": label(consequence, row.get("rsid")),
        "protein_pos": position,
        "reason": None if position is not None else _reason(failure, consequence,
                                                            transcript_id),
    }


def label(consequence: str, rsid: str | None) -> str:
    """A short human handle: ``"missense · rs1801516"``, or the consequence alone."""
    short = consequence.removesuffix(_SUFFIX).replace("_", " ")
    return f"{short} · {rsid}" if rsid else short


# ── internals ────────────────────────────────────────────────────────────────────────


def _reason(failure: str | None, consequence: str, transcript_id: str | None) -> str:
    if failure:
        return f"protein position not resolved — VEP call failed: {failure}"
    return (f"VEP reports no amino-acid position for a {consequence} on "
            f"{transcript_id or 'the canonical transcript'}")


def _has_allele(row: dict) -> bool:
    return all(row.get(field) not in (None, "") for field in ("chrom", "pos", "ref", "alt"))


def _protein_start(item: dict, transcript_id: str | None) -> int | None:
    """``protein_start`` from the canonical transcript's consequence block.

    Matched on the transcript id we drew the domains from, not on VEP's own ``canonical``
    flag: the two agree today, and if they ever stopped, a lollipop drawn against a
    different transcript's numbering would be silently wrong rather than absent.
    """
    for entry in item.get("transcript_consequences") or []:
        if transcript_id and entry.get("transcript_id") != transcript_id:
            continue
        start = _int(entry.get("protein_start"))
        if start is not None:
            return start
    return None


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _get(client: httpx.Client, base_url: str, path: str) -> Any:
    return _call(client, "GET", base_url, path, None)


def _post(client: httpx.Client, base_url: str, path: str, payload: dict) -> Any:
    return _call(client, "POST", base_url, path, payload)


def _call(client: httpx.Client, method: str, base_url: str, path: str,
          payload: dict | None) -> Any:
    """One REST call, with every failure turned into :class:`EnsemblError`.

    No retry loop here on purpose: this is a request-scoped fetch behind a disk cache, so
    the cheap recovery is the caller pressing refresh, and a retry would only lengthen the
    time the browser spends waiting on an outage it should be told about.
    """
    url = f"{base_url.rstrip('/')}{path}"
    try:
        response = client.request(method, url, json=payload,
                                  headers={"Accept": "application/json"})
    except httpx.HTTPError as error:
        raise EnsemblError(f"{method} {url}: {type(error).__name__}: {error}") from error
    if response.status_code != 200:
        raise EnsemblError(f"{method} {url} -> {response.status_code}: "
                           f"{response.text[:200]}")
    try:
        return response.json()
    except ValueError as bad:
        raise EnsemblError(f"{method} {url}: reply was not JSON") from bad
