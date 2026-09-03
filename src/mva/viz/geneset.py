"""The curated set of genes the structure explorer may show, and how a symbol resolves.

The panel BED (:mod:`mva.viz.panelbed`) answers one question — *which eight genes was the
proband's callset annotated against* — and it is the only authority on that, because those
intervals are what VEP actually ran over. It cannot answer the other question the structure
explorer needs: *which genes may I draw a fold for*. Those are a superset. A reader
comparing BUBR1's kinase domain against BUB1's wants both on screen, and BUB1 carries no
patient allele at all.

So the set lives in ``ressources/reference/structure_genes.tsv``, generated live from
Ensembl by ``tools/build_gene_set.py`` and committed. Six columns, one row per gene::

    symbol  ensembl_id  group  biotype  coding  note

The one field this module *derives* rather than reads is ``in_panel``, and it derives it
from the BED rather than trusting a seventh column: two files that both claim to say what
is in the panel can disagree, one cannot. ``in_panel`` is the flag that decides whether the
proband's alleles exist for a gene, so it is the last place a stale copy is acceptable.

**Groups** are display grouping, not evidence strength:

* ``panel`` — the annotated eight. The only genes with candidate alleles.
* ``mva-sac`` — documented MVA / spindle-assembly-checkpoint genes outside the panel.
* ``extended`` — requested for comparison; the ``note`` says what is and is not known.

**Symbols are matched case-insensitively**, and one alias is accepted: ``CCDC84`` →
``CENATAC``. That alias is not assumed — ``tools/build_gene_set.py --alias CCDC84=CENATAC``
resolves both symbols against ``/lookup/symbol`` and asserts they are the same Ensembl gene
(confirmed live, ``docs/step-0/methodology/060``). An alias nobody verified is a silent way
to draw the wrong protein, so the list stays short and each entry cites its check.

Nothing here is patient-derived: a gene symbol, a stable id and a biotype are public
reference facts.
"""

import json
from functools import lru_cache
from pathlib import Path

from . import panelbed

#: Relative to the repository root, which is where the API is started from.
DEFAULT_TSV = Path("ressources/reference/structure_genes.tsv")

#: The build manifest written beside the TSV by ``tools/build_gene_set.py``: which
#: Ensembl release resolved these ids, at which commit, and what the TSV hashed to. Read
#: into the ``/panel/structure-genes`` envelope so the reply names the snapshot it is,
#: not just the file it came from.
DEFAULT_PROVENANCE = Path("ressources/reference/structure_genes.provenance.json")

#: What the route reports as its provenance.
SOURCE = f"{DEFAULT_TSV} + {panelbed.DEFAULT_BED}"

#: Alias → current symbol, **each one confirmed against Ensembl** (see the docstring).
ALIASES = {"CCDC84": "CENATAC"}

#: The columns ``tools/build_gene_set.py`` writes, in order.
COLUMNS = ("symbol", "ensembl_id", "group", "biotype", "coding", "note")


def genes(path: Path | None = None) -> list[dict]:
    """Every gene in the set as a ``StructureGene`` dict, in the TSV's own order.

    The TSV's order *is* the display order — the panel first, then the documented MVA
    genes, then the comparison set — so it is preserved rather than sorted here.

    A missing TSV yields an empty list. That is deliberate: the panel routes must keep
    working on a checkout where the reference table has not been built, and an empty set
    reads as "the explorer has nothing curated", which is true.
    """
    return [dict(entry) for entry in _load(str(path or DEFAULT_TSV))]


def lookup(symbol: str, path: Path | None = None) -> dict:
    """One gene by symbol or verified alias, case-insensitively. ``LookupError`` if absent."""
    wanted = canonical_symbol(symbol)
    for entry in _load(str(path or DEFAULT_TSV)):
        if entry["symbol"].upper() == wanted:
            return dict(entry)
    raise LookupError(symbol)


def canonical_symbol(symbol: str) -> str:
    """``symbol`` upper-cased, with a verified alias mapped to the current symbol."""
    upper = symbol.strip().upper()
    return ALIASES.get(upper, upper)


def resolve(gene: str, path: Path | None = None) -> tuple[str, str, bool]:
    """``(symbol, ensembl_id, in_panel)`` for ``gene``. ``LookupError`` if in neither source.

    **The panel BED wins.** Its id is the one the callset was annotated against, so if
    Ensembl has since retired that gene id, an exhibit built on the newer id would place
    the proband's alleles on a gene record they were never called against. The TSV is the
    fallback, and the only source for a gene outside the panel.

    The returned symbol is the set's own spelling, not the caller's: the frontend echoes it
    into titles and cache keys, and ``bub1b`` and ``BUB1B`` must not become two entries.
    """
    wanted = canonical_symbol(gene)
    for symbol, entry in (panelbed.annotations() or {}).items():
        if symbol.upper() == wanted and entry.get("ensembl_id"):
            return symbol, str(entry["ensembl_id"]), True
    found = lookup(gene, path)
    return str(found["symbol"]), str(found["ensembl_id"]), bool(found["in_panel"])


def provenance(path: Path | None = None) -> dict:
    """The manifest facts for the committed TSV, as ``name → value`` for a source line.

    Every value is ``None`` when the manifest is absent — a checkout that has the TSV but
    not its manifest can still serve the set, and the envelope then says ``unknown``
    rather than implying a release nobody recorded.

    The Ensembl release is read off the *inputs* rather than a top-level field, because
    that is where it belongs: the release is a property of the upstream that answered,
    and one manifest can name more than one upstream.
    """
    payload = _manifest(str(path or DEFAULT_PROVENANCE))
    inputs = [entry for entry in payload.get("inputs") or [] if isinstance(entry, dict)]
    outputs = [entry for entry in payload.get("outputs") or [] if isinstance(entry, dict)]
    releases = [str(entry["release"]) for entry in inputs if entry.get("release")]
    return {
        "ensembl_release": releases[0] if releases else None,
        "structure_genes_sha256": (outputs[0].get("sha256") if outputs else None),
        "built_at": payload.get("built_at"),
        "code_version": payload.get("code_version"),
    }


# ── internals ────────────────────────────────────────────────────────────────────────


@lru_cache(maxsize=8)
def _load(path: str) -> tuple[dict, ...]:
    """Parse the TSV once per path. A tuple so the cached value cannot be mutated."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return ()
    lines = [line for line in text.splitlines() if line.strip() and not line.startswith("#")]
    if not lines:
        return ()
    header = lines[0].split("\t")
    in_panel = {symbol.upper() for symbol in (panelbed.annotations() or {})}
    out = []
    for line in lines[1:]:
        row = dict(zip(header, line.split("\t"), strict=False))
        symbol = row.get("symbol", "").strip()
        if not symbol:
            continue
        out.append(
            {
                "symbol": symbol,
                "ensembl_id": row.get("ensembl_id", "").strip(),
                "group": row.get("group", "extended").strip(),
                "in_panel": symbol.upper() in in_panel,
                # An empty cell is `null`, not `""`: the client's type says `string | null`
                # and "unknown biotype" is a different statement from "biotype is blank".
                "biotype": row.get("biotype", "").strip() or None,
                "coding": row.get("coding", "").strip().lower() == "true",
                "note": row.get("note", "").strip(),
            }
        )
    return tuple(out)


@lru_cache(maxsize=4)
def _manifest(path: str) -> dict:
    """Parse the build manifest once per path. ``{}`` when absent or unreadable."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}
