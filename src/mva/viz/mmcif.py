"""A hand-rolled reader for the two mmCIF blocks a backbone trace needs.

**mmCIF** (macromolecular Crystallographic Information File) is the modern replacement for
the fixed-column PDB format: a text file of *categories*, each a table. The syntax half —
tokenising a line, reading one ``loop_`` table, and what value forms are supported — lives
in :mod:`mva.viz.mmcif_tokens`. This module is the structural half: it gives those rows of
strings meaning.

It reads exactly two of those tables and ignores the rest:

* ``_atom_site`` — one row per atom. Keeping only ``label_atom_id == "CA"`` reduces a
  ~1 MB file to one point per residue, which is the whole payload the 3D exhibit draws.
* ``_struct_conf`` / ``_struct_sheet_range`` — secondary-structure segments (helices and
  strands), when the file carries them.

**What one trace is, precisely.** Every choice below is made explicitly and reported on
:class:`Trace`, because each one silently changes which residues get drawn:

* **one model.** ``pdbx_PDB_model_num`` selects the *first model number the file names*
  (model 1 in every AlphaFold and almost every PDB entry). An NMR ensemble holds 20
  superposed copies of the same chain; without this filter they arrive as duplicate
  residue numbers and are dropped only as a side effect of de-duplication.
* **one chain.** The first ``label_asym_id`` that actually *has* alpha carbons in that
  model — not the first atom row's chain, which for an entry whose file starts with a
  ligand or a nucleic-acid chain would yield an empty trace. ``label_asym_id`` is the
  file's own chain key and is not always the author chain id a reader calls "chain A".
* **one numbering axis.** ``label_seq_id`` (the sequence index the residues are keyed by,
  the same axis ``GeneCandidate.protein_pos`` is measured on) when the chain has it, and
  ``auth_seq_id`` (the depositor's own numbering, which can start anywhere) only when the
  chain has *no* label numbering at all. A chain carrying both patchily is refused, not
  mixed: half a trace on each axis is a wrong picture, not a partial one. Which axis was
  used is on ``Trace.seq_axis``.
* **no insertion codes.** A residue with a non-blank ``pdbx_PDB_ins_code`` (``52A`` next
  to ``52``) cannot be placed on an integer axis, so it is dropped and *counted* on
  ``Trace.dropped_insertion_codes`` rather than silently collapsing onto its neighbour.
* **one alternate location.** No altloc, or the first — see :data:`_MAIN_ALT`.

**Why hand-rolled, no dependency.** Same argument as
[the VCF reader](../../../docs/notes/hand-rolled-vcf-reader.md): a full mmCIF library
(gemmi, biotite, Biopython) brings a compiled wheel and a whole structural-biology object
model to read two tables out of a file we already fetch. The subset here is a tokeniser
and a loop reader — with tests against a committed real file — and it fails loudly rather
than guessing.

Two facts about AlphaFold files were **verified live**, not assumed (see
``docs/step-0/methodology/056``, and ``058`` for this hardening pass):

* ``B_iso_or_equiv`` carries **pLDDT** (the model's own per-residue confidence, 0–100),
  not a crystallographic B-factor. An experimental entry's column means the other thing,
  so the caller says which file it handed over.
* AlphaFold CIFs carry ``_struct_conf`` (DSSP-derived) but **no** ``_struct_sheet_range``.
  Strands appear inside ``_struct_conf`` with ``conf_type_id == "STRN"``. Both sources are
  read so an experimental PDB entry, which uses ``_struct_sheet_range``, also works.
"""

from dataclasses import dataclass, field
from typing import Any

from .mmcif_tokens import MmcifError, as_float, as_int, loop_rows, value

__all__ = [
    "AMINO_ACIDS",
    "MmcifError",
    "Trace",
    "ca_trace",
    "ca_trace_detail",
    "covered",
    "loop_rows",
    "secondary",
]

#: Three-letter residue name → one-letter amino-acid code. The 20 standard residues plus
#: the two ambiguity codes the PDB uses. Anything else — a ligand, a modified residue, a
#: nucleotide — becomes ``"X"``: unknown is a state to render, not a row to drop.
AMINO_ACIDS: dict[str, str] = {
    "ALA": "A",
    "ARG": "R",
    "ASN": "N",
    "ASP": "D",
    "CYS": "C",
    "GLN": "Q",
    "GLU": "E",
    "GLY": "G",
    "HIS": "H",
    "ILE": "I",
    "LEU": "L",
    "LYS": "K",
    "MET": "M",
    "PHE": "F",
    "PRO": "P",
    "SER": "S",
    "THR": "T",
    "TRP": "W",
    "TYR": "Y",
    "VAL": "V",
    "ASX": "B",
    "GLX": "Z",
    "SEC": "U",
    "PYL": "O",
}

#: Alternate-location labels a backbone trace accepts: no alternates, or the first one.
#: Taking both would put two coordinates on one residue number.
_MAIN_ALT = frozenset({".", "?", "", "A", "1"})


@dataclass(frozen=True)
class Trace:
    """One chain's alpha carbons, plus every choice the parse had to make to get them.

    The choices are here and not in the HTTP payload on purpose: the frozen TS contract
    (``app/src/api/types/protein.ts``) has no field for them, and inventing one would make
    the client and the contract disagree. They exist so the parse can be *asserted* in
    tests and *quoted* in a methodology entry, and so a mixed-axis file fails loudly
    instead of arriving as a plausible-looking trace.
    """

    residues: list[dict[str, Any]] = field(default_factory=list)
    #: The ``label_asym_id`` that was traced.
    chain: str | None = None
    #: Which ``_atom_site`` column the residue numbers came from: ``label`` or ``auth``.
    seq_axis: str = "label"
    #: The ``pdbx_PDB_model_num`` kept, or ``None`` when the file has no model column.
    model: str | None = None
    #: Residues refused because they carry an insertion code (``52A``).
    dropped_insertion_codes: int = 0


def ca_trace(text: str, *, confidence: bool) -> list[dict[str, Any]]:
    """One entry per modelled residue: ``n``, ``aa``, ``ca``, ``plddt``.

    The list half of :func:`ca_trace_detail`, which is what the HTTP payload carries.
    """
    return ca_trace_detail(text, confidence=confidence).residues


def ca_trace_detail(text: str, *, confidence: bool) -> Trace:
    """The full parse: the residues, and the chain / model / axis they came from.

    Ascending residue number, one row per residue, alpha carbons only. ``confidence``
    says whether ``B_iso_or_equiv`` is a pLDDT — true for an AlphaFold model, false for an
    experimental structure, where the column is a B-factor and reporting it as confidence
    would be a category error. Rounding (2 decimals on ångström, 1 on pLDDT) is applied
    here because the payload ships over HTTP a thousand residues at a time; a hundredth of
    an ångström is far below the model's own resolution.
    """
    atoms = loop_rows(text, "atom_site")
    if not atoms:
        raise MmcifError("no _atom_site loop — not a coordinate file")
    model = _first_model(atoms)
    in_model = [atom for atom in atoms if model is None or _model_of(atom) == model]
    chain = _first_ca_chain(in_model)
    if chain is None:
        raise MmcifError("no alpha-carbon atoms in the coordinate file")
    carbons = [
        atom
        for atom in in_model
        if atom.get("label_atom_id") == "CA"
        and value(atom.get("label_asym_id")) == chain
        and value(atom.get("label_alt_id", "."), keep_null=True) in _MAIN_ALT
    ]
    placeable = [atom for atom in carbons if not _insertion_code(atom)]
    axis = _sequence_axis(placeable, chain)
    residues = _residues(placeable, axis=axis, confidence=confidence)
    if not residues:
        raise MmcifError(f"chain {chain}: no placeable alpha carbon survived the filters")
    return Trace(
        residues=residues,
        chain=chain,
        seq_axis=axis,
        model=model,
        dropped_insertion_codes=len(carbons) - len(placeable),
    )


def secondary(text: str) -> list[dict[str, Any]]:
    """Helix and strand segments, from whichever table the file uses.

    ``_struct_conf`` holds helices (``conf_type_id`` starting ``HELX``) and, in AlphaFold's
    DSSP output, strands (``STRN``); ``_struct_sheet_range`` holds strands in an
    experimental entry. ``TURN`` and ``BEND`` rows are dropped: they are neither, and
    painting them would imply an annotation the file does not make.
    """
    out: list[dict[str, Any]] = []
    for row in loop_rows(text, "struct_conf"):
        kind = _conformation(value(row.get("conf_type_id")) or "")
        segment = _segment(kind, row) if kind else None
        if segment:
            out.append(segment)
    for row in loop_rows(text, "struct_sheet_range"):
        segment = _segment("strand", row)
        if segment:
            out.append(segment)
    out.sort(key=lambda s: (s["start"], s["end"], s["kind"]))
    return out


def covered(numbers: list[int]) -> list[list[int]]:
    """``numbers`` collapsed into inclusive runs: ``[1,2,3,7,8] -> [[1,3],[7,8]]``.

    The complement of these ranges is *unmeasured*, which is a different claim from
    "modelled and fine" — the exhibit paints it as absent for that reason.
    """
    runs: list[list[int]] = []
    for number in sorted(set(numbers)):
        if runs and number == runs[-1][1] + 1:
            runs[-1][1] = number
        else:
            runs.append([number, number])
    return runs


# ── internals ────────────────────────────────────────────────────────────────────────


def _residues(atoms: list[dict[str, str]], *, axis: str, confidence: bool) -> list[dict[str, Any]]:
    """The rows, keyed by the ``axis`` sequence number, first coordinate per residue wins."""
    seen: set[int] = set()
    out: list[dict[str, Any]] = []
    for atom in atoms:
        number = as_int(value(atom.get(f"{axis}_seq_id")))
        position = _coordinates(atom)
        if number is None or number in seen or position is None:
            continue
        seen.add(number)
        plddt = as_float(atom.get("B_iso_or_equiv")) if confidence else None
        out.append(
            {
                "n": number,
                "aa": AMINO_ACIDS.get((value(atom.get("label_comp_id")) or "").upper(), "X"),
                "ca": position,
                "plddt": None if plddt is None else round(plddt, 1),
            }
        )
    out.sort(key=lambda residue: residue["n"])
    return out


def _first_model(atoms: list[dict[str, str]]) -> str | None:
    """The first ``pdbx_PDB_model_num`` the table names, or ``None`` if it has no column."""
    for atom in atoms:
        model = _model_of(atom)
        if model is not None:
            return model
    return None


def _model_of(atom: dict[str, str]) -> str | None:
    return value(atom.get("pdbx_PDB_model_num"))


def _first_ca_chain(atoms: list[dict[str, str]]) -> str | None:
    """The first ``label_asym_id`` that has an alpha carbon, so one trace is one molecule.

    AlphaFold monomer models have a single chain ``A``; an experimental entry can hold a
    complex whose file opens with a ligand, a water or a nucleic-acid chain, and taking
    the first atom row's chain would trace something with no backbone at all.
    Concatenating chains instead would draw a tube between two molecules that never touch.
    Partner chains are phase 2 (``partners`` in the contract).
    """
    for atom in atoms:
        chain = value(atom.get("label_asym_id"))
        if chain and atom.get("label_atom_id") == "CA":
            return chain
    return None


def _insertion_code(atom: dict[str, str]) -> str | None:
    """The residue's insertion code, if it has a real one. ``.``/``?``/blank read as none."""
    code = value(atom.get("pdbx_PDB_ins_code"))
    return code.strip() or None if code else None


def _sequence_axis(atoms: list[dict[str, str]], chain: str) -> str:
    """``"label"`` or ``"auth"`` — one axis for the whole chain, or a refusal.

    ``label_seq_id`` is the axis of record. Falling back per *row* (the ``a or b`` idiom
    this replaces) puts some residues on the sequence index and others on the depositor's
    numbering, which are unrelated integers; the trace then looks fine and is wrong.
    """
    labelled = sum(1 for atom in atoms if as_int(value(atom.get("label_seq_id"))) is not None)
    if labelled == len(atoms):
        return "label"
    if labelled == 0:
        return "auth"
    raise MmcifError(
        f"chain {chain}: label_seq_id on {labelled} of {len(atoms)} alpha carbons — "
        "the label and auth numbering axes would be mixed"
    )


def _coordinates(atom: dict[str, str]) -> list[float] | None:
    values = [as_float(atom.get(f"Cartn_{axis}")) for axis in ("x", "y", "z")]
    if any(number is None for number in values):
        return None
    return [round(number, 2) for number in values if number is not None]


def _conformation(conf_type: str) -> str | None:
    upper = conf_type.upper()
    if upper.startswith("HELX"):
        return "helix"
    if upper.startswith(("STRN", "SHEET")):
        return "strand"
    return None


def _segment(kind: str, row: dict[str, str]) -> dict[str, Any] | None:
    """One inclusive residue range out of a segment row, on a single numbering axis.

    ``beg_label_seq_id`` is on the same axis as ``_atom_site.label_seq_id``. ``auth_seq_id``
    is the depositor's own numbering and can start anywhere; it is the fallback only, and
    only when *both* ends lack label numbering — one end on each axis is not a range.
    """
    for prefix in ("label", "auth"):
        start = as_int(value(row.get(f"beg_{prefix}_seq_id")))
        end = as_int(value(row.get(f"end_{prefix}_seq_id")))
        if start is not None and end is not None:
            return {"kind": kind, "start": min(start, end), "end": max(start, end)}
    return None
