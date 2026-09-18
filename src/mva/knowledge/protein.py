"""Where a missense allele sits in the protein, and whether the model is sure about it.

*Plain words.* A missense allele swaps one amino acid for another at one position in a
protein. Two public resources say whether that position matters:

**InterPro** is a curated map of *domains* — stretches of a protein that fold and function
as a unit, like the kinase domain that does the enzymatic work. A swap inside a domain is
more likely to break something than a swap in a flexible linker between domains.

**AlphaFold DB** publishes a predicted 3D structure with a per-residue confidence called
**pLDDT** (predicted local distance difference test, 0-100). It is not a pathogenicity
score: it says how sure the model is about the shape *there*. Low pLDDT usually means the
region is genuinely disordered, so "the structure has no confident opinion" is a real
answer and is reported as one rather than as a weak yes.

**This deliberately does not run a protein language model.** The plan named ESM1b for a
zero-shot second opinion; it needs ``torch`` and a 2.5 GB checkpoint to score a handful of
residues, and AlphaMissense — already computed for every allele in the warehouse — is the
calibrated missense score the ranking actually uses. So the second opinion here is
*structural context*, over two REST APIs and no new dependency, and the ESM1b half is
recorded as a cut rather than quietly dropped.

**No coordinate leaves this module.** A residue index is a protein-relative offset, not a
genomic position, and the tables built from these rows carry the domain name, the
InterPro accession and the pLDDT — never the residue. The caller keeps the residue under
``build/``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from ..drugs.cache import Fetcher, SourceError

__all__ = [
    "ALPHAFOLD",
    "CONFIDENT_PLDDT",
    "Domain",
    "ProteinContext",
    "ResidueVerdict",
    "accession_for_gene",
    "context_for_gene",
    "domains_for_accession",
    "plddt_for_accession",
    "summarise",
    "tracks",
    "verdict",
]

ALPHAFOLD = "https://alphafold.ebi.ac.uk"
INTERPRO = "https://www.ebi.ac.uk/interpro/api"
UNIPROT = "https://rest.uniprot.org/uniprotkb/search"

#: The threshold the claim is pre-registered on. AlphaFold's own banding calls 70-90
#: "confident" and below 70 "low"; a residue under it gets no structural opinion here.
CONFIDENT_PLDDT = 70.0

#: InterPro entry types that describe a folded functional unit. Homologous superfamilies
#: and families are kept out of the "in a domain" test: they describe the whole protein's
#: ancestry, so almost every residue falls inside one and the test would always pass.
DOMAIN_TYPES = frozenset({"domain"})


@dataclass(frozen=True)
class Domain:
    """One InterPro annotation and the residue range it covers."""

    accession: str
    name: str
    entry_type: str
    start: int
    end: int

    def covers(self, residue: int) -> bool:
        return self.start <= residue <= self.end


@dataclass
class ProteinContext:
    """Everything the two APIs know about one protein, fetched once and reused."""

    gene: str
    accession: str = ""
    length: int = 0
    domains: list[Domain] = field(default_factory=list)
    #: pLDDT per residue, 1-indexed by position; empty when AlphaFold has no model.
    plddt: dict[int, float] = field(default_factory=dict)
    note: str = ""


@dataclass(frozen=True)
class ResidueVerdict:
    """The claim's three conditions, evaluated separately so a refutation names its half."""

    gene: str
    accession: str
    in_domain: bool
    #: Covered by *any* InterPro entry, including the family and superfamily rows that
    #: :data:`DOMAIN_TYPES` excludes from the domain test. Reported beside ``in_domain``
    #: because the two can disagree, and a residue outside every annotated domain but
    #: inside a superfamily is a different finding from one outside everything.
    in_superfamily: bool
    domain_accession: str
    domain_name: str
    plddt: float
    confident: bool
    #: Where the residue falls along the protein, 0.0-1.0. A fraction, never a position.
    fraction: float

    @property
    def structural_support(self) -> bool:
        """Inside an annotated domain *and* in a region the model is confident about."""
        return self.in_domain and self.confident


def accession_for_gene(fetcher: Fetcher, gene: str) -> tuple[str, int]:
    """The reviewed human UniProt accession for a gene symbol, and its length.

    Reviewed (Swiss-Prot) only, and an exact gene match: a fuzzy match would silently
    score the wrong protein, which is worse than returning nothing. An unmatched symbol
    returns ``("", 0)`` — a gene with no reviewed human entry is a fact about the gene.
    """
    payload = fetcher.get_json(
        UNIPROT,
        {
            "query": f"gene_exact:{gene} AND organism_id:9606 AND reviewed:true",
            "fields": "accession,length",
            "format": "json",
            "size": 1,
        },
    )
    results = (payload or {}).get("results") or []
    if not results:
        return "", 0
    first = results[0]
    return str(first.get("primaryAccession") or ""), int(
        ((first.get("sequence") or {}).get("length")) or 0
    )


def domains_for_accession(fetcher: Fetcher, accession: str) -> list[Domain]:
    """Every InterPro entry mapped onto one protein, with its residue ranges.

    All entry types are returned; :data:`DOMAIN_TYPES` decides which of them count as
    "in a domain" at verdict time, so the table keeps the superfamily rows a reader would
    otherwise wonder about.
    """
    if not accession:
        return []
    payload = fetcher.get_json(f"{INTERPRO}/entry/InterPro/protein/uniprot/{accession}/")
    domains: list[Domain] = []
    for entry in (payload or {}).get("results") or []:
        meta = entry.get("metadata") or {}
        for protein in entry.get("proteins") or []:
            for location in protein.get("entry_protein_locations") or []:
                domains.extend(
                    Domain(
                        accession=str(meta.get("accession") or ""),
                        name=str(meta.get("name") or ""),
                        entry_type=str(meta.get("type") or ""),
                        start=int(fragment.get("start") or 0),
                        end=int(fragment.get("end") or 0),
                    )
                    for fragment in location.get("fragments") or []
                )
    domains.sort(key=lambda domain: (domain.start, domain.end))
    return domains


def plddt_for_accession(fetcher: Fetcher, accession: str) -> dict[int, float]:
    """Per-residue pLDDT from AlphaFold DB's published confidence file.

    Two calls: the prediction record names the confidence file for the current model
    version, and the file carries one score per residue. A protein AlphaFold has no model
    for returns an empty mapping, which :func:`verdict` reads as "no structural opinion".
    """
    if not accession:
        return {}
    try:
        record = fetcher.get_json(f"{ALPHAFOLD}/api/prediction/{accession}", allow_status=(404,))
    except SourceError:
        return {}
    entries = record if isinstance(record, list) else []
    url = str((entries[0] if entries else {}).get("plddtDocUrl") or "")
    if not url:
        return {}
    payload = fetcher.get_json(url, allow_status=(404,))
    if not isinstance(payload, dict):
        return {}
    numbers = payload.get("residueNumber") or []
    scores = payload.get("confidenceScore") or []
    return {int(n): float(s) for n, s in zip(numbers, scores, strict=False)}


def context_for_gene(fetcher: Fetcher, gene: str) -> ProteinContext:
    """The three fetches for one gene, folded into one reusable record."""
    accession, length = accession_for_gene(fetcher, gene)
    if not accession:
        return ProteinContext(gene=gene, note="no reviewed human UniProt entry")
    domains = domains_for_accession(fetcher, accession)
    plddt = plddt_for_accession(fetcher, accession)
    note = "" if plddt else "no AlphaFold model"
    return ProteinContext(
        gene=gene, accession=accession, length=length, domains=domains, plddt=plddt, note=note
    )


def verdict(context: ProteinContext, residue: int) -> ResidueVerdict:
    """Evaluate one residue against the domain map and the confidence profile.

    The three conditions of the claim stay separate in the returned record — inside a
    domain, confident structure, and (supplied by the caller from the warehouse) the
    AlphaMissense class — so a refutation can say *which* of them failed rather than only
    that the claim did.
    """
    over = [domain for domain in context.domains if domain.covers(residue)]
    covering = [domain for domain in over if domain.entry_type in DOMAIN_TYPES]
    score = context.plddt.get(residue, 0.0)
    best = covering[0] if covering else (over[0] if over else None)
    return ResidueVerdict(
        gene=context.gene,
        accession=context.accession,
        in_domain=bool(covering),
        in_superfamily=bool(over),
        domain_accession=best.accession if best else "",
        domain_name=best.name if best else "",
        plddt=score,
        confident=score >= CONFIDENT_PLDDT,
        fraction=(residue / context.length) if context.length else 0.0,
    )


def tracks(context: ProteinContext) -> list[dict[str, Any]]:
    """The domain map as fractions of protein length, ready for a coordinate-free figure.

    A figure drawn from residue numbers would put protein positions into a committed SVG.
    Fractions carry the same shape and no position, which is the rule the whole repository
    runs on.
    """
    if not context.length:
        return []
    return [
        {
            "accession": domain.accession,
            "name": domain.name,
            "type": domain.entry_type,
            "start_fraction": domain.start / context.length,
            "end_fraction": domain.end / context.length,
        }
        for domain in context.domains
    ]


def summarise(contexts: Sequence[ProteinContext]) -> dict[str, int]:
    """How many proteins resolved, carried domains, and carried a structure."""
    return {
        "genes": len(contexts),
        "with_accession": sum(1 for c in contexts if c.accession),
        "with_domains": sum(1 for c in contexts if c.domains),
        "with_structure": sum(1 for c in contexts if c.plddt),
    }
