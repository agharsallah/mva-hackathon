"""Transfer cards: the same pipeline, a **different case** — not a different gene.

The decoy control (:mod:`mva.drugs.decoy`) holds the child fixed and swaps the gene, which
measures *specificity*: how much of the drug list any gene would have produced. It cannot
measure *portability*, because everything case-shaped — the disease query, the clinical
terms, the tumour context, the standard-of-care exclusions — is still the proband's.

A **transfer card** swaps all of it. A different disease with its own OMIM/MONDO/Orphanet
identifiers, its own public phenotype annotation read out of ``phenotype.hpoa`` rather than
typed, its own tumour context and its own standard-of-care list. Nothing of the template's
``case`` survives. What *is* copied, deliberately and by deep copy, is the machinery that is
a property of the method and not of the child:

* ``anti_directions`` — "do not further weaken a checkpoint that is already weak" and "a
  spindle poison needs the checkpoint the patient does not have" are statements about
  mitotic-checkpoint disease, not about one child;
* ``evidence_ladder`` — the five rungs and the rule that reads them;
* ``constraints`` — market-approved only, public sources only, DrugBank not queried.

The card says so in its own ``transfer`` block, so a reader never has to infer it.

**What a transfer run can show.** That the pipeline is case-agnostic in fact and not only
in claim: a new card, no code change, no hand-written query, and the same tables come out.
The per-case counts are printed side by side so a reader can see the pipeline behaved
comparably on both.

**What it cannot show.** That the second case's drug list is any good. A transfer card
carries no alleles and no curated ``evidence.tsv``, so only the **automated** rungs (1, 4
and 5 — approval, a registered trial in the tumour context, a paediatric pointer) can
appear at all. Rungs 2 and 3 are curated by a person and are structurally absent. Every
comparison row prints ``curated_rows`` for exactly that reason. The rows themselves are
:mod:`mva.drugs.compare`'s job — this module owns the *card*, that one owns every
side-by-side count a control produces.

Coordinate-free by construction, like every card: genes, consequences and identifiers only.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .mechanism import MechanismCard

__all__ = ["HpoAnnotation", "TransferSpec", "hpo_annotation", "load_spec", "transfer_card"]

#: The direction ids a card must declare, in order. Fixed so the per-direction columns of
#: the comparison mean the same thing on both cards.
DIRECTION_IDS = ("D1", "D2", "D3", "D4")

#: The ``qualifier`` value that means *this disease does **not** present this feature*.
#: Such a row is an annotation about an absence and must never become a search term.
NEGATED = "NOT"

#: The line ``phenotype.hpoa`` states its release on.
VERSION_PREFIX = "#version:"


# ── the phenotype annotation, read rather than typed ─────────────────────────────────


@dataclass(frozen=True)
class HpoAnnotation:
    """One disease's public phenotype annotation, with the file version behind it."""

    disease_id: str
    disease_name: str
    terms: tuple[str, ...]
    excluded: tuple[str, ...]
    version: str
    source: str
    rows: int

    @property
    def provenance(self) -> str:
        """One sentence naming the file, its release and what was skipped."""
        skipped = f", {len(self.excluded)} NOT-qualified row(s) skipped" if self.excluded else ""
        return (
            f"{self.source} (HPO annotation release {self.version}), rows for "
            f"{self.disease_id}: {self.rows} read, {len(self.terms)} distinct term(s)"
            f"{skipped}"
        )


def hpo_annotation(path: Path | str, disease_id: str) -> HpoAnnotation:
    """Every HPO term ``phenotype.hpoa`` annotates ``disease_id`` with, and the release.

    ``phenotype.hpoa`` is a ``#``-commented TSV: a header block of ``#key: value`` lines,
    then one row per (disease, term) annotation. A row whose ``qualifier`` column is
    ``NOT`` states that the disease *does not* show that feature; it is collected into
    ``excluded`` and never into ``terms``, because a search built from it would ask the
    opposite question. Terms keep file order, deduplicated, so a re-read asks the APIs in
    the same sequence.

    Raises ``LookupError`` when the disease has no rows — a card built on an annotation
    that is not there would be a card built on nothing.
    """
    where = Path(path)
    version = ""
    header: list[str] = []
    terms: dict[str, None] = {}
    excluded: dict[str, None] = {}
    name = ""
    rows = 0
    for line in where.read_text(encoding="utf-8").splitlines():
        if line.startswith(VERSION_PREFIX):
            version = line[len(VERSION_PREFIX) :].strip()
            continue
        if line.startswith("#") or not line.strip():
            continue
        fields = line.split("\t")
        if not header:
            header = fields
            continue
        row = dict(zip(header, fields, strict=False))
        if row.get("database_id") != disease_id:
            continue
        rows += 1
        name = name or str(row.get("disease_name") or "")
        term = str(row.get("hpo_id") or "")
        if not term:
            continue
        if str(row.get("qualifier") or "").strip().upper() == NEGATED:
            excluded.setdefault(term, None)
        else:
            terms.setdefault(term, None)
    if not rows:
        raise LookupError(f"{where}: no annotation rows for {disease_id}")
    return HpoAnnotation(
        disease_id=disease_id,
        disease_name=name,
        terms=tuple(terms),
        excluded=tuple(excluded),
        version=version,
        source=where.as_posix(),
        rows=rows,
    )


# ── the spec: a committed JSON file describing the second case ───────────────────────


@dataclass(frozen=True)
class TransferSpec:
    """What a second case is made of. Every field is public knowledge, cited in the file."""

    gene: dict[str, Any]
    case: dict[str, Any]
    mechanism: dict[str, Any]
    directions: list[dict[str, Any]]
    picked_by: str
    hpo_source: dict[str, Any] = field(default_factory=dict)

    @property
    def symbol(self) -> str:
        return str(self.gene.get("symbol", ""))

    @property
    def disease_id(self) -> str:
        """The annotation key: ``OMIM:<n>`` built from the case's OMIM phenotype number."""
        return f"OMIM:{self.case.get('omim_phenotype')}"

    def with_phenotype(self, annotation: HpoAnnotation) -> TransferSpec:
        """The same spec with the public phenotype annotation **read in**, never typed.

        The clinical terms of a transfer case are not a judgement anyone makes here: they
        are whatever ``phenotype.hpoa`` annotates the disease with on the release named in
        its own ``#version`` line. Both the terms and that line travel into the card, so a
        reader can re-derive the list from the same file.
        """
        case = dict(self.case)
        case["hpo_terms"] = list(annotation.terms)
        case["hpo_terms_excluded"] = list(annotation.excluded)
        case["clinical_terms_source"] = annotation.provenance
        return TransferSpec(
            gene=self.gene,
            case=case,
            mechanism=self.mechanism,
            directions=self.directions,
            picked_by=self.picked_by,
            hpo_source={
                "path": annotation.source,
                "version": annotation.version,
                "disease_id": annotation.disease_id,
                "disease_name": annotation.disease_name,
                "rows_read": annotation.rows,
                "terms": len(annotation.terms),
                "excluded": len(annotation.excluded),
                "rule": "rows whose qualifier column is NOT are skipped, never searched",
            },
        )


def load_spec(path: Path | str) -> TransferSpec:
    """Read one committed ``transfer_spec.json``. Malformed input raises, never guesses."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"{path}: a transfer spec must be a JSON object")
    return TransferSpec(
        gene=dict(payload["gene"]),
        case=dict(payload["case"]),
        mechanism=dict(payload["mechanism"]),
        directions=[dict(entry) for entry in payload["repurposing_directions"]],
        picked_by=str(payload["picked_by"]),
        hpo_source=dict(payload.get("hpo_source") or {}),
    )


def _checked_directions(spec: TransferSpec) -> list[dict[str, Any]]:
    """The spec's four directions, with exactly one of them the tumour-context direction.

    ``context: true`` is the *only* way a direction earns the automated rungs 4 and 5
    (:func:`mva.drugs.ladder._context_directions`), because those rungs rest on a
    registered trial in the tumour. Put it on a mechanism direction and a trial about the
    tumour silently becomes evidence about the mechanism; leave it off every direction and
    the card can never reach above rung 1. Both are wrong quietly, so both raise here.
    """
    ids = tuple(str(entry.get("id", "")) for entry in spec.directions)
    if ids != DIRECTION_IDS:
        raise ValueError(f"a transfer card needs directions {DIRECTION_IDS}, got {ids}")
    flagged = [entry["id"] for entry in spec.directions if entry.get("context") is True]
    if flagged != [DIRECTION_IDS[-1]]:
        raise ValueError(
            f"exactly one direction carries context=true and it is the tumour direction "
            f"{DIRECTION_IDS[-1]}; got {flagged or 'none'}"
        )
    return [
        {
            "id": str(entry["id"]),
            "name": str(entry["name"]),
            "rationale": str(entry["rationale"]),
            "seed_targets": [str(symbol) for symbol in entry["seed_targets"]],
            "context": entry.get("context") is True,
        }
        for entry in spec.directions
    ]


def transfer_card(
    template: MechanismCard, spec: TransferSpec, *, today: str | None = None
) -> dict[str, Any]:
    """A full card for ``spec``'s case, carrying nothing of the template's case.

    ``case``, ``gene``, ``mechanism`` and ``repurposing_directions`` come from the spec
    alone — there is no ``proband_id`` and no inherited clinical term. ``anti_directions``,
    ``evidence_ladder`` and ``constraints`` are deep-copied from the template because they
    are case-agnostic (see the module docstring), and the ``transfer`` block records that
    they were copied and why. ``alleles`` is empty: no variant in any person is asserted.
    """
    date = today or datetime.now(tz=UTC).date().isoformat()
    raw = template.raw
    directions = _checked_directions(spec)
    return {
        "_standing": (
            "TRANSFER CARD — a pipeline demonstration on a second case, not a finding for "
            f"the proband. No allele in any person is asserted. Built {date} from "
            f"{spec.picked_by}, with the template card's case-agnostic blocks (anti-"
            f"directions, evidence ladder, constraints) copied from the "
            f"{template.gene_symbol} card version {template.version}. Only the automated "
            "rungs apply: this card has no curated evidence.tsv."
        ),
        "version": 1,
        "transfer": {
            "template_gene": template.gene_symbol,
            "template_card_version": template.version,
            "picked_by": spec.picked_by,
            "comparable": (
                "automated rungs only (1, 4 and 5: approval, a registered trial in the "
                "tumour context, a paediatric pointer). Rungs 2 and 3 are curated by a "
                "person and are structurally absent from a transfer card."
            ),
            "copied_from_template": {
                "blocks": ["anti_directions", "evidence_ladder", "constraints"],
                "why": (
                    "case-agnostic machinery: the checkpoint anti-directions are statements "
                    "about mitotic-checkpoint disease, the rungs and their rule are the "
                    "method, and the constraints are the challenge's own eligibility rules. "
                    "Everything case-shaped is built from the spec."
                ),
            },
            "inherited_from_template_case": "nothing",
            "hpo_source": dict(spec.hpo_source),
        },
        "case": copy.deepcopy(spec.case),
        "gene": copy.deepcopy(spec.gene),
        "alleles": [],
        "mechanism": copy.deepcopy(spec.mechanism),
        "repurposing_directions": directions,
        "anti_directions": copy.deepcopy(raw.get("anti_directions", [])),
        "evidence_ladder": copy.deepcopy(raw.get("evidence_ladder", {})),
        "constraints": copy.deepcopy(raw.get("constraints", {})),
        "history": [
            {
                "version": 1,
                "date": date,
                "change": f"transfer card for {spec.symbol} / {spec.case.get('disease')}",
            }
        ],
    }
