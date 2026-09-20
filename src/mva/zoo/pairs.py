"""Building the callset's biallelic **pairs** — the unit iteration 4 ranks.

The answer to this case is not one allele but a **compound-heterozygous pair** (two different
broken copies of the same gene, one inherited from each parent). So before any model score is
touched, the callset has to be turned into a list of candidate pairs.

Two builders, one shape:

* :func:`pairs_from_fixture` reads ``fixtures/it4/pairs.tsv`` — synthetic, for tests.
* :func:`pairs_from_alleles` reads real ``results.coding_alleles`` rows and delegates the
  pairing and the phase call to the pipeline that already owns them
  (:mod:`mva.pipeline.compound_het`). No second implementation of phase exists in this
  package, and none should.

Both emit :class:`Pair`, which carries a gene symbol and two ``allele_id`` hashes and never a
coordinate — that is what makes a pair safe to write into a doc, a table or a figure.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "DEFAULT_PAIR_RULE",
    "MAX_CALLS_PER_GENE",
    "PAIR_RULES",
    "READ_ONLY_PHASE",
    "Pair",
    "PairBuild",
    "pairs_from_alleles",
    "pairs_from_fixture",
    "read_only_pairs",
]

#: The phase label of a pair one of whose alleles was never in the VCF. It is **not**
#: ``unknown``: ``unknown`` means the reads were consulted and could not say, while this
#: means no genotype exists to consult. Keeping the two apart is what stops a hypothesis
#: being read as a phased call.
READ_ONLY_PHASE = "no-genotype"

#: Which pair of a confirmed gene gets the flag, when the gene carries more than one.
#:
#: ``lof+missense``
#:     prefer the pair that carries one truncating allele (a premature stop or equivalent)
#:     plus one missense allele — the shape a recessive loss-of-function case usually takes.
#:     If that does not single one pair out, every pair of the gene is flagged and the note
#:     says so.
#: ``all``
#:     flag every pair of the gene and make no claim about shape.
#:
#: There is no gene constant in this module. The gene is a **configuration value**
#: (``[case] confirmed_gene``); this package never knows which illness it is ranking.
PAIR_RULES: tuple[str, ...] = ("lof+missense", "all")
DEFAULT_PAIR_RULE = "lof+missense"

#: Consequence classes that make a confirmed-pair candidate the *expected* shape: one
#: truncating allele (a premature stop) plus one missense allele (a changed amino acid).
_TRUNCATING = ("stop_gained", "frameshift", "splice_donor", "splice_acceptor", "start_lost")
_MISSENSE = ("missense",)

#: Genes with more heterozygous calls than this are skipped when building pairs: the pair
#: count grows as n², and a gene with hundreds of het calls is a mapping artefact, not a
#: compound-het candidate. Skipped genes are reported, never silently dropped.
MAX_CALLS_PER_GENE = 60


@dataclass(frozen=True)
class Pair:
    """Two heterozygous alleles of one gene, proposed as a biallelic hit.

    ``phase`` is the physical-phasing verdict (``trans`` = one allele per parental copy,
    ``cis`` = both on the same copy, ``unknown`` = the reads could not say). Only the gene
    symbol and the two ``allele_id`` hashes are carried, so a ``Pair`` is safe to write
    anywhere.
    """

    gene: str
    left_id: str
    right_id: str
    phase: str = "unknown"
    is_confirmed: bool = False

    @property
    def key(self) -> tuple[str, str, str]:
        """The identity used to join one pair across lanes (order-independent)."""
        low, high = sorted((self.left_id, self.right_id))
        return (self.gene, low, high)


@dataclass(frozen=True)
class PairBuild:
    """The pairs of a real callset plus the bookkeeping the report has to state."""

    pairs: list[Pair]
    confirmed_note: str
    genes: int = 0
    het_calls: int = 0
    skipped_genes: tuple[str, ...] = ()


# ---------------------------------------------------------------------------------------
# Building pairs
# ---------------------------------------------------------------------------------------


def pairs_from_fixture(
    path: str | Path,
    *,
    confirmed_gene: str = "",
    rule: str = DEFAULT_PAIR_RULE,
) -> list[Pair]:
    """Read a ``pairs.tsv`` fixture — the synthetic stand-in for a real callset's pairs.

    Columns: ``gene, allele_id_left, allele_id_right, phase, is_confirmed``.

    ``confirmed_gene`` makes the *case config* decide which pair is flagged, exactly as it
    does for a real callset: the file's ``is_confirmed`` column is then ignored. Left empty,
    the column is trusted, which is what a fixture written for one specific scenario wants.
    """
    with Path(path).open(encoding="utf-8", newline="") as handle:
        rows = [
            Pair(
                gene=row["gene"],
                left_id=row["allele_id_left"],
                right_id=row["allele_id_right"],
                phase=row.get("phase", "unknown") or "unknown",
                is_confirmed=str(row.get("is_confirmed", "")).lower() == "true",
            )
            for row in csv.DictReader(handle, delimiter="\t")
        ]
    if not confirmed_gene:
        return rows
    return _flag_confirmed(rows, confirmed_gene, {}, rule)[0]


def pairs_from_alleles(
    rows: Iterable[Mapping[str, Any]],
    *,
    confirmed_gene: str = "",
    consequences: Mapping[str, str] | None = None,
    max_calls_per_gene: int = MAX_CALLS_PER_GENE,
    rule: str = DEFAULT_PAIR_RULE,
) -> PairBuild:
    """Build the callset's biallelic pairs from ``results.coding_alleles`` rows.

    Each row is one ALT allele of one VCF record: ``chrom, pos, ref, alt, gene, gt`` and the
    physical-phasing columns ``pgt``/``pid``. The rows are turned into
    :class:`mva.pipeline.vcf.Call` objects, grouped by gene, and handed to the existing
    :func:`mva.pipeline.compound_het.candidate_pairs`, which keeps the heterozygous calls and
    classifies each pair's phase. Cis pairs (both changes on the same parental copy) are
    dropped here, exactly as the pipeline defines them.

    ``confirmed_gene`` is the case's answer gene, by symbol, from ``[case] confirmed_gene``;
    empty (the default) means no pair is flagged and the note says so. ``consequences`` maps
    ``allele_id`` to the VEP consequence string; it is used only to pick which of several
    ``confirmed_gene`` pairs carries the flag, under ``rule`` (:data:`PAIR_RULES`).
    """
    from ..pipeline.compound_het import candidate_pairs
    from ..pipeline.variant import Variant
    from ..pipeline.vcf import Call
    from .types import allele_id

    by_gene: dict[str, list[tuple[Call, str, str]]] = {}
    for row in rows:
        gene = str(row.get("gene") or "")
        if not gene:
            continue
        chrom, pos = str(row["chrom"]), int(row["pos"])
        ref, alt = str(row["ref"]), str(row["alt"])
        call = Call(
            variant=Variant(chrom, pos, ref.upper(), alt.upper()),
            genotype=str(row.get("gt") or ""),
            filters=tuple(str(row.get("filter") or "PASS").split(";")),
            depth=_as_int(row.get("dp")),
            ref_depth=None,
            alt_depth=None,
            phase_set=_as_text(row.get("pid")),
            phase_gt=_as_text(row.get("pgt")),
        )
        by_gene.setdefault(gene, []).append((call, allele_id(chrom, pos, ref, alt), gene))

    pairs: list[Pair] = []
    skipped: list[str] = []
    het_calls = 0
    for gene, entries in sorted(by_gene.items()):
        if len(entries) > max_calls_per_gene:
            skipped.append(gene)
            continue
        ids = {id(call): key for call, key, _ in entries}
        calls = [call for call, _, _ in entries]
        het_calls += sum(1 for call in calls if call.is_het)
        for candidate in candidate_pairs(calls):
            if not candidate.is_compound_het_candidate:
                continue
            pairs.append(
                Pair(
                    gene=gene,
                    left_id=ids[id(candidate.left)],
                    right_id=ids[id(candidate.right)],
                    phase=candidate.phase.value,
                )
            )

    flagged, note = _flag_confirmed(pairs, confirmed_gene, consequences or {}, rule)
    return PairBuild(
        pairs=flagged,
        confirmed_note=note,
        genes=len(by_gene),
        het_calls=het_calls,
        skipped_genes=tuple(skipped),
    )


def _flag_confirmed(
    pairs: Sequence[Pair], gene: str, consequences: Mapping[str, str], rule: str
) -> tuple[list[Pair], str]:
    """Mark the confirmed pair(s) of ``gene``; say in words which rule did the marking."""
    if rule not in PAIR_RULES:
        raise ValueError(f"unknown confirmed_pair_rule {rule!r}; expected one of {PAIR_RULES}")
    if not gene:
        return list(pairs), "no confirmed pair declared: the case names no confirmed gene"
    in_gene = [p for p in pairs if p.gene.upper() == gene.upper()]
    if not in_gene:
        return list(pairs), (
            f"no pair built for {gene}: the confirmed pair is absent from the callset"
        )
    chosen = in_gene
    note = f"{gene} has one pair; flagged confirmed"
    if len(in_gene) > 1:
        chosen, note = _choose(gene, in_gene, consequences, rule)
    marked = {p.key for p in chosen}
    out = [
        Pair(p.gene, p.left_id, p.right_id, p.phase, is_confirmed=p.key in marked) for p in pairs
    ]
    return out, note


def _choose(
    gene: str, in_gene: Sequence[Pair], consequences: Mapping[str, str], rule: str
) -> tuple[list[Pair], str]:
    """Which of several pairs of one gene carries the flag, and the sentence that says why."""
    if rule == "all":
        return list(in_gene), (
            f"{gene} has {len(in_gene)} pairs and the rule is `all`; every one is flagged"
        )
    shaped = [p for p in in_gene if _is_stop_plus_missense(p, consequences)]
    if len(shaped) == 1:
        return shaped, (
            f"{gene} has {len(in_gene)} pairs; rule `lof+missense` flagged the one carrying a "
            f"truncating allele plus a missense allele"
        )
    return list(in_gene), (
        f"{gene} has {len(in_gene)} pairs and rule `lof+missense` did not single one out "
        f"({len(shaped)} matched); all {len(in_gene)} are flagged confirmed"
    )


def _is_stop_plus_missense(pair: Pair, consequences: Mapping[str, str]) -> bool:
    left = (consequences.get(pair.left_id) or "").lower()
    right = (consequences.get(pair.right_id) or "").lower()
    for a, b in ((left, right), (right, left)):
        if any(t in a for t in _TRUNCATING) and any(m in b for m in _MISSENSE):
            return True
    return False


def _as_int(value: Any) -> int | None:
    return None if value is None or value == "" else int(value)


def _as_text(value: Any) -> str | None:
    return None if value is None or value == "" else str(value)


# ---------------------------------------------------------------------------------------
# The alleles the VCF never had (plan §7 opt-A row A7)
# ---------------------------------------------------------------------------------------


def read_only_pairs(
    read_only: Iterable[Mapping[str, Any] | Any],
    vcf_pairs_source: Iterable[Mapping[str, Any]],
    *,
    max_partners_per_gene: int = MAX_CALLS_PER_GENE,
) -> list[Pair]:
    """Pair each **read-only** allele with every VCF allele of the same gene.

    *What a read-only allele is.* Iteration 2 found 1,199 alleles that the aligned reads
    support but that no VCF record contains — the caller never emitted a row for them
    (`ideation/data-findings.md`). They carry no genotype, so
    :func:`mva.pipeline.compound_het.candidate_pairs` cannot touch them: it decides
    heterozygosity and phase from ``GT``, and there is none.

    *Why pair them anyway.* A compound heterozygote needs two broken copies of one gene. If
    one of them is an allele the caller dropped, the VCF alone can never propose that pair —
    the case would look like a single heterozygous carrier. This function proposes exactly
    those pairs, and labels every one :data:`READ_ONLY_PHASE` so that no reader and no table
    can mistake a hypothesis for a phased call.

    *What it deliberately does not do.* It does not merge these into the ranked pair set. The
    ranking's denominator is the VCF pairs, the confirmed pair's percentile is measured
    against them, and quietly adding tens of thousands of unphased hypotheses would move
    every percentile in the report without adding a single genotype. They are reported as
    their own table.

    ``max_partners_per_gene`` applies the same n² guard :func:`pairs_from_alleles` uses: a
    gene with hundreds of calls is a mapping artefact.
    """
    from .types import allele_id

    partners: dict[str, list[str]] = {}
    for row in vcf_pairs_source:
        gene = str(row.get("gene") or "")
        if not gene:
            continue
        key = allele_id(str(row["chrom"]), int(row["pos"]), str(row["ref"]), str(row["alt"]))
        partners.setdefault(gene, []).append(key)

    out: list[Pair] = []
    for record in read_only:
        gene = str(_text(record, "gene") or "")
        left = str(_text(record, "allele_id") or "")
        if not gene or not left:
            continue
        same_gene = [key for key in dict.fromkeys(partners.get(gene, ())) if key != left]
        if not same_gene or len(same_gene) > max_partners_per_gene:
            continue
        out.extend(
            Pair(gene=gene, left_id=left, right_id=right, phase=READ_ONLY_PHASE)
            for right in same_gene
        )
    return out


def _text(record: Mapping[str, Any] | Any, name: str) -> Any:
    if isinstance(record, Mapping):
        return record.get(name)
    return getattr(record, name, None)
