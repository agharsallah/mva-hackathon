"""Readers for the four public files a mouse-to-human phenotype comparison needs.

The comparison asks "which mouse *genotype* looks most like this patient?". Answering it
needs four things, each a plain tab-separated MGI or uPheno report:

* **Genotype -> MP terms** (``MGI_PhenoGenoMP.rpt``). MGI (Mouse Genome Informatics)
  curates, per mouse genotype, the **MP** terms (Mammalian Phenotype ontology - HPO's mouse
  counterpart) that papers observed. A genotype is the allele pair(s) a mouse carries, e.g.
  ``Bub1b<tm1Jvd>/Bub1b<tm1Jvd>`` (two copies of one engineered allele).
* **Allele -> class** (``MGI_PhenotypicAllele.rpt``). MGI labels each allele with attributes
  such as ``Hypomorph`` (reduced function) or ``Null/knockout`` (no function). That label is
  what lets a result say "the best-matching mouse is a hypomorph", in MGI's words, not ours.
* **HP <-> MP bridges** (SSSOM files). SSSOM is a TSV format for term-to-term mappings
  between ontologies, one row per mapping with a predicate (exact / broad / narrow / related)
  and a justification. Three sources, read into one :class:`BridgeRow` shape.
* **Disease -> HP terms** (``phenotype.hpoa``), for positive controls.

Parsing only: nothing here scores. Every reader is gene- and disease-agnostic.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Genotype:
    """One MGI genotype and every MP term curated to it (all rows merged)."""

    genotype_id: str
    composition: str
    allele_symbols: tuple[str, ...]
    background: str
    marker_ids: tuple[str, ...]
    mp_terms: frozenset[str]
    pmids: frozenset[str]


@dataclass(frozen=True)
class Allele:
    """One MGI allele with MGI's own type and attribute labels."""

    allele_id: str
    symbol: str
    allele_type: str
    attributes: tuple[str, ...]
    pmids: tuple[str, ...]
    marker_id: str
    marker_symbol: str
    synonyms: tuple[str, ...]


@dataclass(frozen=True)
class BridgeRow:
    """One HP -> MP mapping, from whichever source asserted it."""

    hp: str
    mp: str
    predicate: str
    source: str
    #: 1 = curated or logical; 2 = fuzzy fallback, used only when a term has no tier-1 row.
    tier: int


def _rows(path: str | Path) -> Iterator[list[str]]:
    """Non-comment, non-empty lines split on tabs."""
    with Path(path).open(encoding="utf-8") as handle:
        for raw in handle:
            if not raw.strip() or raw.startswith("#"):
                continue
            yield raw.rstrip("\n").split("\t")


def parse_pheno_geno_mp(path: str | Path) -> dict[str, Genotype]:
    """``MGI_PhenoGenoMP.rpt`` -> genotype id -> :class:`Genotype`.

    Columns (no header): allelic composition, allele symbols (``|``), genetic background,
    MP id, PubMed id, marker ids (``|``), genotype id. One row per (genotype, MP, paper).
    """
    terms: dict[str, set[str]] = {}
    pmids: dict[str, set[str]] = {}
    first: dict[str, list[str]] = {}
    for cols in _rows(path):
        if len(cols) < 7 or not cols[3].startswith("MP:"):
            continue
        gid = cols[6].strip()
        first.setdefault(gid, cols)
        terms.setdefault(gid, set()).add(cols[3].strip())
        if cols[4].strip():
            pmids.setdefault(gid, set()).add(cols[4].strip())
    out: dict[str, Genotype] = {}
    for gid, cols in first.items():
        out[gid] = Genotype(
            genotype_id=gid,
            composition=cols[0],
            allele_symbols=tuple(s for s in cols[1].split("|") if s),
            background=cols[2],
            marker_ids=tuple(m for m in cols[5].split("|") if m),
            mp_terms=frozenset(terms[gid]),
            pmids=frozenset(pmids.get(gid, set())),
        )
    return out


def parse_phenotypic_alleles(path: str | Path) -> dict[str, Allele]:
    """``MGI_PhenotypicAllele.rpt`` -> allele **symbol** -> :class:`Allele`.

    Keyed by symbol because a genotype row names its alleles by symbol. Columns used:
    0 allele id, 1 symbol, 3 type, 4 attributes (``|``), 5 PubMed, 6 marker id,
    7 marker symbol, 12 synonyms (``|``).
    """
    out: dict[str, Allele] = {}
    for cols in _rows(path):
        if len(cols) < 8:
            continue
        cols = cols + [""] * (13 - len(cols))  # noqa: PLW2901 - pad short rows in place
        out[cols[1]] = Allele(
            allele_id=cols[0],
            symbol=cols[1],
            allele_type=cols[3],
            attributes=tuple(a for a in cols[4].split("|") if a),
            pmids=tuple(p for p in cols[5].split(",") if p),
            marker_id=cols[6],
            marker_symbol=cols[7],
            synonyms=tuple(s for s in cols[12].split("|") if s),
        )
    return out


def marker_symbols(alleles: dict[str, Allele]) -> dict[str, str]:
    """Marker (gene) id -> symbol, as the allele report spells it."""
    return {a.marker_id: a.marker_symbol for a in alleles.values() if a.marker_id}


def parse_mgi_sssom(path: str | Path) -> list[BridgeRow]:
    """The Mouse-Human Mapping Initiative's MGI-curated HP <-> MP SSSOM (tier 1).

    Its header names ``object_id`` (HP) before ``subject_id`` (MP); columns are located by
    name so a reordered release still parses.
    """
    rows = _rows(path)
    header = next(rows, [])
    col = {name: i for i, name in enumerate(header)}
    out: list[BridgeRow] = []
    for cols in rows:
        hp, mp = cols[col["object_id"]], cols[col["subject_id"]]
        if hp.startswith("HP:") and mp.startswith("MP:"):
            out.append(BridgeRow(hp, mp, cols[col["predicate_id"]], "mgi-curated", 1))
    return out


def parse_upheno_logical(path: str | Path) -> list[BridgeRow]:
    """uPheno species-independent SSSOM (tier 1): HP and MP sharing one ``UPHENO:`` class.

    The file maps each species-independent class to species terms; an HP and an MP term
    mapped to the same class are logically equivalent up to species.
    """
    by_class: dict[str, list[str]] = {}
    for cols in _rows(path):
        if len(cols) >= 3 and cols[0].startswith("UPHENO:"):
            by_class.setdefault(cols[0], []).append(cols[2])
    out: list[BridgeRow] = []
    for upheno, members in by_class.items():
        hps = [m for m in members if m.startswith("HP:")]
        mps = [m for m in members if m.startswith("MP:")]
        out.extend(
            BridgeRow(hp, mp, f"shared {upheno}", "upheno-logical", 1) for hp in hps for mp in mps
        )
    return out


def parse_upheno_bestmatches(path: str | Path, min_score: float = 0.0) -> list[BridgeRow]:
    """uPheno ``hp-to-mp-bestmatches.tsv`` (tier 2): the single fuzzy best MP per HP term.

    Columns: HP id, HP label, MP id, MP label, equivalence score (ancestor Jaccard),
    subclass score. ``min_score`` filters on the equivalence score.
    """
    out: list[BridgeRow] = []
    for cols in _rows(path):
        if len(cols) < 5 or not cols[0].startswith("HP:") or not cols[2].startswith("MP:"):
            continue
        if float(cols[4]) >= min_score:
            out.append(BridgeRow(cols[0], cols[2], f"jaccard {cols[4]}", "upheno-bestmatch", 2))
    return out


def parse_disease_terms(path: str | Path, disease_id: str) -> tuple[str, ...]:
    """The HP terms ``phenotype.hpoa`` annotates to one disease, ``NOT`` rows excluded.

    Only aspect ``P`` (phenotypic abnormality) rows: onset, inheritance and frequency
    modifiers are not features a mouse could be annotated with.
    """
    rows = _rows(path)
    header = next(rows, [])
    col = {name: i for i, name in enumerate(header)}
    seen: dict[str, None] = {}
    for cols in rows:
        if cols[col["database_id"]] != disease_id or cols[col["qualifier"]] == "NOT":
            continue
        if cols[col["aspect"]] == "P":
            seen.setdefault(cols[col["hpo_id"]], None)
    return tuple(seen)


def disease_name(path: str | Path, disease_id: str) -> str | None:
    """The label ``phenotype.hpoa`` gives a disease id, or ``None``."""
    for cols in _rows(path):
        if cols and cols[0] == disease_id:
            return cols[1]
    return None
