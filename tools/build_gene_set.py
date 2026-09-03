"""Resolve a curated list of gene symbols against Ensembl into a committed TSV.

    uv run python tools/build_gene_set.py --spec ressources/reference/structure_genes.spec.tsv
    uv run python tools/build_gene_set.py --group panel=BUB1B,TP53 --note BUB1B="MVA1"
    uv run python tools/build_gene_set.py --spec … --alias CCDC84=CENATAC --dry-run

Case-agnostic on purpose: nothing about MVA is hardcoded. The input is *which symbols, in
which display group, with which one-line note*; the output is one row per gene carrying the
facts only Ensembl can answer — the stable gene id, the biotype, and whether the canonical
transcript translates. A downstream explorer needs exactly those three to decide whether it
may draw a protein at all.

Three live-verified facts drove the code rather than being assumed (the replies are in
``docs/step-0/methodology/060``):

* ``/lookup/symbol/homo_sapiens/<symbol>?expand=1`` does **not** resolve a retired symbol.
  ``CCDC84``, HGNC's own previous symbol for ``CENATAC``, gets ``400 {"error":"No valid
  lookup found for symbol CCDC84"}``. That was the assumption the first version of this
  tool made, and it was wrong.
* ``/xrefs/symbol/homo_sapiens/<symbol>`` does. It answers with a *list* of matching
  objects, so an alias is confirmed by the primary symbol's gene id appearing in it — not
  by the list having one entry. ``CCDC84`` returns two gene ids, and the second is CENATAC
  again on a patch scaffold, which is why "exactly one match" would be the wrong test.
* ``canonical_transcript`` is versioned (``ENST00000287598.11``) while each transcript
  object's ``id`` is not, so the match is on the part before the dot — the same rule
  :func:`mva.viz.genestructure.pick_transcript` already applies.

``coding`` is *"the canonical transcript carries a Translation"*, not *"the biotype string
says protein_coding"*. Those disagree: a gene can be annotated ``protein_coding`` while the
transcript the rest of the pipeline indexes into has no translation, and a protein exhibit
built on the biotype alone would then 502 instead of saying "no protein".

**Run order: this tool first, then ``tools/build_protein_fixture.py``**, which records this
TSV's sha256 as an input and goes stale otherwise — rerun it with ``--manifest-only`` after
every run here (``--force`` if the gene set changed). See ``docs/step-0/methodology/063``.

Reads one public keyless API. Touches no warehouse table and no patient record, so it runs
on a bare checkout and its output is publishable.
"""

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from mva.viz import ensembl, genesetmanifest, panelbed

#: The public Ensembl REST server. Same host the panel annotation and the viz routes use.
ENSEMBL_BASE = "https://rest.ensembl.org"

DEFAULT_OUT = Path("ressources/reference/structure_genes.tsv")
DEFAULT_SPEC = Path("ressources/reference/structure_genes.spec.tsv")
DEFAULT_PROVENANCE = Path("ressources/reference/structure_genes.provenance.json")

#: The output's column order. Mirrors ``StructureGene`` in ``app/src/api/types/protein.ts``
#: minus ``in_panel``, which the server derives from the panel BED rather than storing twice.
COLUMNS = ("symbol", "ensembl_id", "group", "biotype", "coding", "note")


class EnsemblLookupError(RuntimeError):
    """Ensembl could not be reached, or refused a symbol. Never faked around."""


@dataclass(frozen=True)
class Wanted:
    """One requested gene, before Ensembl has been asked anything."""

    symbol: str
    group: str
    note: str


@dataclass(frozen=True)
class Resolved:
    """One gene as Ensembl reports it, plus the facts kept for the audit trail."""

    wanted: Wanted
    ensembl_id: str
    display_name: str
    biotype: str
    transcript: str | None
    protein: str | None

    @property
    def coding(self) -> bool:
        """Whether the canonical transcript translates — see the module docstring."""
        return self.protein is not None

    def row(self) -> list[str]:
        return [
            self.wanted.symbol,
            self.ensembl_id,
            self.wanted.group,
            self.biotype,
            "true" if self.coding else "false",
            self.wanted.note,
        ]


# ── input ────────────────────────────────────────────────────────────────────────────


def read_spec(path: Path) -> list[Wanted]:
    """A three-column TSV (``symbol group note``) with a header row, in display order."""
    lines = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    if not lines:
        raise SystemExit(f"{path}: no rows")
    header = lines[0].split("\t")
    if header[:3] != ["symbol", "group", "note"]:
        raise SystemExit(f"{path}: expected header 'symbol\tgroup\tnote', got {header!r}")
    out = []
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) < 2:
            raise SystemExit(f"{path}: row needs at least symbol and group: {line!r}")
        note = parts[2].strip() if len(parts) > 2 else ""
        out.append(Wanted(parts[0].strip(), parts[1].strip(), note))
    return out


def read_flags(groups: list[str], notes: list[str]) -> list[Wanted]:
    """``--group name=A,B`` plus ``--note A=text``, for a set small enough to type."""
    note_of = dict(pair.split("=", 1) for pair in notes)
    out: list[Wanted] = []
    for spec in groups:
        name, _, symbols = spec.partition("=")
        out.extend(
            Wanted(symbol, name.strip(), note_of.get(symbol, ""))
            for symbol in (s.strip() for s in symbols.split(",") if s.strip())
        )
    return out


# ── resolution ───────────────────────────────────────────────────────────────────────


#: Attempts per symbol, and the pause between them.
#:
#: The *routes* deliberately never retry (``mva.viz.genestructure._call`` says why: a
#: request-scoped fetch behind a cache recovers more cheaply by the reader pressing
#: refresh). A batch build is the opposite case — one transient 503 halfway through 23
#: symbols throws away 22 good replies — so a bounded retry belongs here and nowhere else.
#: Observed live: ``/lookup/symbol/…/BRD9`` answered 503 once and 200 on the next attempt.
ATTEMPTS, PAUSE = 4, 2.0


def lookup(client: httpx.Client, base_url: str, symbol: str) -> dict:
    """``/lookup/symbol/homo_sapiens/<symbol>?expand=1``, or a stated failure."""
    url = f"{base_url.rstrip('/')}/lookup/symbol/homo_sapiens/{symbol}?expand=1"
    for attempt in range(1, ATTEMPTS + 1):
        try:
            response = client.get(url, headers={"Accept": "application/json"})
        except httpx.HTTPError as error:
            reason = f"GET {url}: {type(error).__name__}: {error}"
        else:
            if response.status_code == 200:
                body = response.json()
                if not isinstance(body, dict) or not body.get("id"):
                    raise EnsemblLookupError(f"GET {url}: reply carried no gene id")
                return body
            # A 4xx is the server saying this symbol is wrong; retrying cannot fix that.
            if response.status_code < 500:
                raise EnsemblLookupError(
                    f"GET {url} -> {response.status_code}: {response.text[:200]}"
                )
            reason = f"GET {url} -> {response.status_code}: {response.text[:120]}"
        if attempt == ATTEMPTS:
            raise EnsemblLookupError(f"{reason} (after {ATTEMPTS} attempts)")
        print(f"    retry {attempt}/{ATTEMPTS - 1} after {reason}")
        time.sleep(PAUSE)
    raise AssertionError("unreachable")


def canonical(reply: dict) -> dict | None:
    """The canonical transcript object, matched on the unversioned id.

    Falls back to ``is_canonical``, then to any transcript that translates — the order
    :func:`mva.viz.genestructure.pick_transcript` uses, kept identical on purpose so the
    ``coding`` flag written here cannot disagree with what the live route will find.
    """
    transcripts = [t for t in reply.get("Transcript") or [] if isinstance(t, dict)]
    if not transcripts:
        return None
    wanted = str(reply.get("canonical_transcript") or "").split(".")[0]
    for entry in transcripts:
        if wanted and entry.get("id") == wanted:
            return entry
    for entry in transcripts:
        if entry.get("is_canonical"):
            return entry
    coding = [entry for entry in transcripts if entry.get("Translation")]
    return (coding or transcripts)[0]


def resolve(client: httpx.Client, base_url: str, wanted: Wanted) -> Resolved:
    """One gene, resolved and reported. Prints the reply facts for the methodology entry."""
    reply = lookup(client, base_url, wanted.symbol)
    transcript = canonical(reply) or {}
    translation = transcript.get("Translation") or {}
    found = Resolved(
        wanted=wanted,
        ensembl_id=str(reply["id"]),
        display_name=str(reply.get("display_name") or wanted.symbol),
        biotype=str(reply.get("biotype") or ""),
        transcript=transcript.get("id"),
        protein=translation.get("id"),
    )
    print(
        f"  {wanted.symbol:<12} {found.ensembl_id}  {found.biotype:<16} "
        f"canonical={found.transcript} protein={found.protein or '—'} "
        f"display_name={found.display_name} "
        f"chr{reply.get('seq_region_name')}:{reply.get('start')}-{reply.get('end')} "
        f"strand={reply.get('strand')} group={wanted.group}"
    )
    if found.display_name.upper() != wanted.symbol.upper():
        print(
            f"    note: Ensembl reports the current symbol as {found.display_name!r}; "
            f"{wanted.symbol!r} resolved as an alias or previous symbol."
        )
    return found


def xref_symbol(client: httpx.Client, base_url: str, symbol: str) -> list[str]:
    """Gene ids ``/xrefs/symbol/homo_sapiens/<symbol>`` matches. Empty when nothing does.

    Unlike ``/lookup/symbol`` this endpoint searches the cross-references, which is where a
    retired symbol still lives — see the module docstring for the reply that proved it.
    """
    url = f"{base_url.rstrip('/')}/xrefs/symbol/homo_sapiens/{symbol}"
    try:
        response = client.get(url, headers={"Accept": "application/json"})
    except httpx.HTTPError as error:
        raise EnsemblLookupError(f"GET {url}: {type(error).__name__}: {error}") from error
    if response.status_code != 200:
        return []
    body = response.json()
    return [
        str(row["id"])
        for row in (body if isinstance(body, list) else [])
        if isinstance(row, dict) and row.get("type") == "gene" and row.get("id")
    ]


def check_alias(client: httpx.Client, base_url: str, alias: str, primary: str) -> bool:
    """Confirm ``alias`` and ``primary`` name the same Ensembl gene. Never assumed.

    The test is *membership*, not equality: the xref reply lists every object the symbol
    matches, and a gene present on both the primary assembly and an alternate patch
    scaffold legitimately appears twice. Requiring a single match would refuse a correct
    alias; requiring the primary's id to be among the matches would not.
    """
    matches = xref_symbol(client, base_url, alias)
    target = lookup(client, base_url, primary)["id"]
    same = target in matches
    verdict = "CONFIRMED" if same else "REFUSED"
    print(
        f"  alias {alias} → {primary}: {verdict} — "
        f"/xrefs/symbol/{alias} matches {matches or 'nothing'}; "
        f"/lookup/symbol/{primary} is {target}"
    )
    return same


def borrow_bed_notes(wanted: list[Wanted], bed: Path) -> list[Wanted]:
    """Fill an empty note from the panel BED, so one fact has one owner.

    The BED's sixth column already says why each panel gene is on the candidate list, and
    CLAUDE.md's rule is that a measured or curated fact has exactly one owner. So a spec row
    with a blank note for a gene the BED knows borrows the BED's line rather than restating
    it — which also means editing the BED updates the explorer on the next rebuild.
    """
    notes = {
        symbol: (entry.get("note") or "") for symbol, entry in panelbed.annotations(bed).items()
    }
    return [
        entry
        if entry.note or not notes.get(entry.symbol)
        else Wanted(entry.symbol, entry.group, notes[entry.symbol])
        for entry in wanted
    ]


def check_panel(found: list[Resolved], bed: Path, group: str) -> list[str]:
    """Every ``group`` gene's resolved id must equal the panel BED's. Returns the failures.

    The BED is the panel's source of truth: the callset was annotated against those exact
    intervals, so a gene whose live id has moved on cannot be shown carrying the proband's
    alleles. Reported as an assertion rather than silently preferring one side.
    """
    annotations = panelbed.annotations(bed)
    problems = []
    for entry in found:
        if entry.wanted.group != group:
            continue
        expected = (annotations.get(entry.wanted.symbol) or {}).get("ensembl_id")
        if expected is None:
            problems.append(f"{entry.wanted.symbol}: group {group!r} but not in {bed}")
        elif expected != entry.ensembl_id:
            problems.append(
                f"{entry.wanted.symbol}: BED says {expected}, Ensembl says {entry.ensembl_id}"
            )
    return problems


# ── output ───────────────────────────────────────────────────────────────────────────


def render(found: list[Resolved]) -> str:
    """The TSV: a header row of column names, then one row per gene, in input order."""
    lines = ["\t".join(COLUMNS)]
    lines += ["\t".join(entry.row()) for entry in found]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, help=f"TSV of symbol/group/note (e.g. {DEFAULT_SPEC})")
    parser.add_argument("--group", action="append", default=[], help="name=SYM,SYM")
    parser.add_argument("--note", action="append", default=[], help="SYM=one-line note")
    parser.add_argument("--alias", action="append", default=[], help="ALIAS=PRIMARY to verify")
    parser.add_argument("--bed", type=Path, default=panelbed.DEFAULT_BED, help="panel BED")
    parser.add_argument(
        "--panel-group", default="panel", help="group whose ids must match the BED (default: panel)"
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="where to write the TSV")
    parser.add_argument(
        "--provenance",
        type=Path,
        default=DEFAULT_PROVENANCE,
        help=f"where to write the build manifest (default: {DEFAULT_PROVENANCE})",
    )
    parser.add_argument("--base-url", default=ENSEMBL_BASE, help="Ensembl REST base")
    parser.add_argument("--dry-run", action="store_true", help="resolve and print, write nothing")
    args = parser.parse_args()

    wanted = read_spec(args.spec) if args.spec else read_flags(args.group, args.note)
    if not wanted:
        raise SystemExit("nothing to resolve: pass --spec or --group")

    wanted = borrow_bed_notes(wanted, args.bed)
    print(f"resolving {len(wanted)} symbols against {args.base_url}")
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        # Asked first and printed, because it is the fact that dates every other line
        # below: the same symbol resolves to different biotypes across releases.
        release = ensembl.release(args.base_url, client=client)
        print(f"ensembl release {release or 'unknown'} (GET {args.base_url}/info/data)")
        found = [resolve(client, args.base_url, entry) for entry in wanted]
        aliases = [pair.split("=", 1) for pair in args.alias]
        refused = [
            f"{a} is not the same gene as {p}"
            for a, p in aliases
            if not check_alias(client, args.base_url, a, p)
        ]

    problems = check_panel(found, args.bed, args.panel_group) + refused
    if problems:
        for line in problems:
            print(f"FAIL {line}", file=sys.stderr)
        raise SystemExit(1)

    coding = [entry.wanted.symbol for entry in found if entry.coding]
    print(f"\n{len(coding)} of {len(found)} genes have a translating canonical transcript")
    print(f"non-coding: {[e.wanted.symbol for e in found if not e.coding] or 'none'}")
    if args.dry_run:
        print("--dry-run: nothing written")
        return
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(found), encoding="utf-8")
    print(f"{args.out} — {args.out.stat().st_size:,} bytes, {len(found)} rows")

    # The manifest is written from the file that was *just* written, so its digest can
    # never describe a different TSV than the one on disk beside it.
    built = genesetmanifest.manifest(
        [
            {"symbol": e.wanted.symbol, "group": e.wanted.group, "note": e.wanted.note}
            for e in found
        ],
        args.out,
        args.spec,
        args.bed,
        args.base_url,
        release,
    )
    args.provenance.write_text(json.dumps(built, indent=2) + "\n", encoding="utf-8")
    print(
        f"{args.provenance} — sha256 {built['outputs'][0]['sha256']}, "
        f"{len(built['literature'])} genes with a cited OMIM/PMID"
    )


if __name__ == "__main__":
    main()
