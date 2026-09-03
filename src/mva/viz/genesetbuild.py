"""Resolving a curated list of gene symbols against Ensembl into gene-set rows.

The reusable half of ``tools/build_gene_set.py``: the spec format, the Ensembl calls, the
alias check, the panel assertion and the TSV rendering. The tool keeps only its command
line. Split out so the build is importable — ``tests/test_viz_genesetbuild.py`` drives the
whole thing over a foreign two-gene spec with a mocked transport, which a ``tools/`` script
could not be asked to do.

**Nothing here is case-specific.** The input is *which symbols, in which display group,
with which label, in which order, with which one-line note*; the output is one row per gene
carrying the facts only Ensembl can answer — the stable gene id, the biotype, and whether
the canonical transcript translates. A downstream explorer needs exactly those three to
decide whether it may draw a protein at all. Group ids are free-form strings: this module
never reads meaning into one, and the only group it treats specially is the one the caller
*names* as the panel group (``check_panel``).

Three live-verified facts drove the code rather than being assumed — ``/lookup/symbol``
does **not** resolve a retired symbol and ``/xrefs/symbol`` does; the xref reply is a
*list*, so an alias is confirmed by *membership* of the primary's gene id, never by "one
match"; and ``canonical_transcript`` is versioned while a transcript object's ``id`` is
not, so the match is on the part before the dot. The replies that proved each are in
``docs/step-0/methodology/060``.

``coding`` is *"the canonical transcript carries a Translation"*, not *"the biotype string
says protein_coding"*. Those disagree: a gene can be annotated ``protein_coding`` while the
transcript the rest of the pipeline indexes into has no translation, and a protein exhibit
built on the biotype alone would then 502 instead of saying "no protein".

Reads one public keyless API. Touches no warehouse table and no patient record.
"""

import time
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path

import httpx

#: The public Ensembl REST server. Same host the panel annotation and the viz routes use.
ENSEMBL_BASE = "https://rest.ensembl.org"

#: The output's column order. Mirrors ``StructureGene`` in ``app/src/api/types/protein.ts``
#: minus ``in_panel``, which the server derives from the panel BED rather than storing twice.
COLUMNS = (
    "symbol",
    "ensembl_id",
    "group",
    "group_label",
    "group_order",
    "biotype",
    "coding",
    "note",
)

#: The spec columns this module understands. ``symbol`` and ``group`` are required; the
#: other three have defaults, so a two-column spec is a valid spec.
SPEC_REQUIRED = ("symbol", "group")
SPEC_OPTIONAL = ("group_label", "group_order", "note")


class EnsemblLookupError(RuntimeError):
    """Ensembl could not be reached, or refused a symbol. Never faked around."""


@dataclass(frozen=True)
class Wanted:
    """One requested gene, before Ensembl has been asked anything.

    ``group`` is an opaque id — the value the API and the URL carry. ``group_label`` is
    the sentence a reader sees, ``group_order`` where the group sits in the display. All
    three travel with the row rather than living in a table the frontend hardcodes, which
    is what makes a new case a new spec TSV instead of a code change.
    """

    symbol: str
    group: str
    note: str = ""
    group_label: str = ""
    group_order: int | None = None


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
            self.wanted.group_label,
            str(self.wanted.group_order if self.wanted.group_order is not None else 0),
            self.biotype,
            "true" if self.coding else "false",
            self.wanted.note,
        ]


# ── input ────────────────────────────────────────────────────────────────────────────


def read_spec(path: Path) -> list[Wanted]:
    """A spec TSV, keyed by column *name* so a spec may carry two columns or five.

    ``symbol`` and ``group`` are required; ``group_label``, ``group_order`` and ``note``
    are optional and filled in by :func:`fill_groups`. By name rather than position, so
    adding a sixth column never renumbers the other five.
    """
    lines = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    if not lines:
        raise ValueError(f"{path}: no rows")
    header = [cell.strip() for cell in lines[0].split("\t")]
    missing = [name for name in SPEC_REQUIRED if name not in header]
    if missing:
        raise ValueError(f"{path}: header is missing {missing}; got {header!r}")
    out = []
    for line in lines[1:]:
        row = dict(zip(header, (cell.strip() for cell in line.split("\t")), strict=False))
        if not row.get("symbol") or not row.get("group"):
            raise ValueError(f"{path}: row needs a symbol and a group: {line!r}")
        out.append(
            Wanted(
                symbol=row["symbol"],
                group=row["group"],
                note=row.get("note", ""),
                group_label=row.get("group_label", ""),
                group_order=_order(path, row.get("group_order")),
            )
        )
    return fill_groups(out)


def _order(path: Path, cell: str | None) -> int | None:
    if not cell:
        return None
    try:
        return int(cell)
    except ValueError as bad:
        raise ValueError(f"{path}: group_order must be an integer, got {cell!r}") from bad


def read_flags(groups: Sequence[str], notes: Sequence[str], labels: Sequence[str]) -> list[Wanted]:
    """``--group name=A,B``, ``--note A=text``, ``--group-label name=text``, for a set
    small enough to type. Group order is declaration order, the only ordering given."""
    note_of = dict(pair.split("=", 1) for pair in notes)
    label_of = dict(pair.split("=", 1) for pair in labels)
    out: list[Wanted] = []
    for order, spec in enumerate(groups):
        name, _, symbols = spec.partition("=")
        name = name.strip()
        out.extend(
            Wanted(symbol, name, note_of.get(symbol, ""), label_of.get(name, ""), order)
            for symbol in (s.strip() for s in symbols.split(",") if s.strip())
        )
    return fill_groups(out)


def fill_groups(wanted: Sequence[Wanted]) -> list[Wanted]:
    """Give every row its group's label and order, and refuse a group that disagrees.

    Defaults are the honest ones: a group with no label is labelled by its own id, and a
    group with no stated order sorts where it first appears, which is the order the spec
    file already reads in. A group id carrying two different labels — or two different
    orders — is a spec bug and raises, because the frontend groups by id and would
    otherwise render one of the two arbitrarily.
    """
    labels = _one_per_group(wanted, "label", lambda row: row.group_label or None)
    stated = _one_per_group(wanted, "order", lambda row: row.group_order)
    orders = {group: index for index, group in enumerate(dict.fromkeys(r.group for r in wanted))}
    orders.update(stated)
    return [
        replace(row, group_label=labels.get(row.group) or row.group, group_order=orders[row.group])
        for row in wanted
    ]


def _one_per_group(wanted, what: str, read) -> dict:
    """``group -> value``, raising when two rows of one group state different values."""
    out: dict = {}
    for row in wanted:
        value = read(row)
        if value is None:
            continue
        seen = out.setdefault(row.group, value)
        if seen != value:
            raise ValueError(f"group {row.group!r}: two {what}s, {seen!r} and {value!r}")
    return out


# ── resolution ───────────────────────────────────────────────────────────────────────


#: Attempts per symbol, and the pause between them. The *routes* never retry
#: (``mva.viz.genestructure._call`` says why); a batch build is the opposite case — one
#: transient 503 halfway through throws away every good reply before it — so a bounded
#: retry belongs here and nowhere else. Observed live: ``/lookup/symbol/…/BRD9`` answered
#: 503 once and 200 on the next attempt.
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
    """Gene ids ``/xrefs/symbol/…/<symbol>`` matches — the cross-references, which is
    where a retired symbol still lives. Empty when nothing does."""
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
    matches, and a gene on both the primary assembly and a patch scaffold legitimately
    appears twice, so "exactly one match" would refuse a correct alias.
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


def reuse(wanted: Sequence[Wanted], existing: Sequence[dict]) -> list[Resolved]:
    """Re-apply curation to rows already resolved, calling nothing.

    Group ids, labels, ranks and notes are *curation*: renaming a group changes no fact
    Ensembl owns. Re-resolving 23 symbols to rewrite a label would spend the upstream, and
    would silently swap in whatever the current release says about genes the recorded build
    measured — a second change nobody asked for. So this path keeps the Ensembl-derived
    columns of ``existing`` verbatim (the reader is :func:`mva.viz.geneset.genes`) and takes
    everything else from the spec.

    A wanted symbol the existing table does not carry raises: it has no measured id, and
    inventing one is the failure mode the whole build exists to avoid. Add it with a live
    run instead. The manifest a ``reuse`` build writes says the release was carried over
    rather than fetched — see :func:`mva.viz.genesetmanifest.manifest`.
    """
    known = {str(row["symbol"]).upper(): row for row in existing}
    out = []
    for row in wanted:
        found = known.get(row.symbol.upper())
        if found is None:
            raise LookupError(
                f"{row.symbol}: not in the existing table, so it has no resolved gene id. "
                "Run without --reuse to resolve it against Ensembl."
            )
        out.append(
            Resolved(
                wanted=row,
                ensembl_id=str(found.get("ensembl_id") or ""),
                display_name=str(found["symbol"]),
                biotype=str(found.get("biotype") or ""),
                transcript=None,
                # `coding` is the only derived flag, and `Resolved` derives it from
                # `protein is not None`. A sentinel rather than a real translation id,
                # because this path measured nothing: the flag is carried, not re-checked.
                protein="carried-over" if found.get("coding") else None,
            )
        )
    return out


# ── output ───────────────────────────────────────────────────────────────────────────


def render(found: Sequence[Resolved]) -> str:
    """The TSV: a header row of column names, then one row per gene, in input order."""
    lines = ["\t".join(COLUMNS)]
    lines += ["\t".join(entry.row()) for entry in found]
    return "\n".join(lines) + "\n"


def manifest_rows(found: Sequence[Resolved]) -> list[dict]:
    """The plain-data view :func:`mva.viz.genesetmanifest.manifest` takes."""
    return [
        {
            "symbol": entry.wanted.symbol,
            "group": entry.wanted.group,
            "group_label": entry.wanted.group_label,
            "note": entry.wanted.note,
        }
        for entry in found
    ]
