"""The genotype half of the likelihood ratio: what one allele's annotation is worth.

Four evidence lanes, **one calibrated tool per consequence class, chosen before any score was
seen** (Pejaver 2022's own recommendation, and the reason this module's constants are frozen
here rather than tuned later):

===============  =====================================================================
consequence      lane
===============  =====================================================================
protein-truncating  LOFTEE-style rules over the transcript (Karczewski 2020) — where the
                    stop falls decides whether the transcript is destroyed or escapes
                    nonsense-mediated decay
missense            AlphaMissense's own three-class call (Cheng 2023)
splice window       SpliceAI's delta score (Jaganathan 2019)
synonymous/other    the consequence class alone
===============  =====================================================================

**Everything above lives in one correlation group.** A missense predictor tuned on ClinVar
and ClinVar itself are not independent evidence, and neither is a canonical splice-site
consequence and a SpliceAI score for the same base. Exactly one of them contributes — the
strongest — and the rest are kept in the record, damped and named. Population frequency and
the caller's own FILTER are separate lanes, because neither was trained on the others.

CADD is absent: Ensembl's REST VEP does not serve the plugin and no local file exists. The
plan had already demoted it to a tie-break outside the calibrated lanes, so its absence
removes no lane. LOFTEE is reimplemented from its published rules, not run — this module
produces *LOFTEE-style* reasoning, and never claims the tool's benchmark.

Nothing here is case-specific: the same lanes score any allele of any gene.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .acmg import Strength, cap
from .likelihood import Lane

#: One correlation group for every lane that answers "does this allele break the protein".
ALLELE_EFFECT = "allele-effect"

#: VEP consequence terms that truncate the protein product.
TRUNCATING = frozenset(
    {
        "transcript_ablation",
        "splice_acceptor_variant",
        "splice_donor_variant",
        "stop_gained",
        "frameshift_variant",
        "start_lost",
    }
)

#: VEP terms that change the protein without truncating it.
MISSENSE = frozenset({"missense_variant", "protein_altering_variant"})

#: VEP terms inside or beside a splice site — the window SpliceAI is asked about.
SPLICE_WINDOW = frozenset(
    {
        "splice_acceptor_variant",
        "splice_donor_variant",
        "splice_region_variant",
        "splice_donor_5th_base_variant",
        "splice_donor_region_variant",
        "splice_polypyrimidine_tract_variant",
    }
)

#: Terms that leave the protein sequence intact.
SILENT = frozenset({"synonymous_variant", "stop_retained_variant", "start_retained_variant"})

#: ClinVar assertions read as pathogenic, and as benign. Conflicting assertions are read as
#: neither: a disagreement among submitters is not evidence in either direction.
CLINVAR_PATHOGENIC = ("pathogenic", "likely_pathogenic")
CLINVAR_BENIGN = ("benign", "likely_benign")
CLINVAR_CONFLICTING = ("conflicting",)

#: SpliceAI's own published cutoffs on the delta score — 0.2 high recall, 0.5 recommended,
#: 0.8 high precision (Jaganathan 2019; the thresholds as the tool's own documentation
#: states them). The mapping from a cutoff to an ACMG rung is **not** in the paper and is a
#: choice this step pre-registered; see :data:`SPLICE_CEILING`.
SPLICEAI_HIGH_PRECISION = 0.8
SPLICEAI_RECOMMENDED = 0.5
SPLICEAI_HIGH_RECALL = 0.2

#: No published ACMG calibration for AlphaMissense or SpliceAI could be read from its own
#: paper during this step, so both lanes are capped: they carry a direction and at most a
#: moderate strength, never strong. Pre-registered in methodology entry 098, before any
#: score was seen, and tested by the sensitivity analysis that re-ranks with the cap moved.
MISSENSE_CEILING = Strength.MODERATE
SPLICE_CEILING = Strength.MODERATE

#: Allele frequency above which an allele is too common to cause a disease with fewer than
#: 50 known patients worldwide. Mirrors :data:`mva.pipeline.ranking.RARE_AF`; kept as its own
#: name because this module reads a *ladder* of frequencies, not a single cut.
COMMON_AF = 5e-3
RARE_AF = 1e-3
ULTRA_RARE_AF = 1e-4

#: Multiplier for a call the caller itself did not pass. A down-weight, never a cut — the
#: whole point of a likelihood ratio is that a suppressed call can still win. The number is a
#: pre-registered choice, not a measurement, and the sensitivity analysis moves it.
NON_PASS_LR = 1.0 / 3.0

#: The published NMD rule is "the last exon, or the last 50 bp of the penultimate exon".
#: Ensembl's REST VEP reports which exon of how many a variant falls in but not how long
#: that exon is, so the last exon is read directly and the penultimate one is **one rung
#: lower** rather than either accepted or discarded — the rule could not be resolved, and
#: saying so in the strength is more honest than picking a side.
PENULTIMATE_IS_UNRESOLVED = True


@dataclass(frozen=True)
class AlleleEvidence:
    """Everything one allele's annotations say, in the shape the lanes read.

    Built by the caller from ``warehouse.coding_annotations`` joined to
    ``warehouse.it2_insilico_annotations``; every field is optional because a real annotation
    table has holes, and a hole is a lane that stays silent rather than a row that is dropped.
    """

    consequence: str = ""
    impact: str = ""
    gnomad_af: float | None = None
    gnomad_af_grpmax: float | None = None
    clin_sig: str = ""
    am_pathogenicity: float | None = None
    am_class: str = ""
    spliceai_ds_max: float | None = None
    exon_index: int | None = None
    exon_total: int | None = None
    filters: str = ""

    @property
    def terms(self) -> frozenset[str]:
        """The VEP consequence terms, split on the ``&`` VEP joins them with."""
        return frozenset(t for t in self.consequence.replace(",", "&").split("&") if t)

    @property
    def is_truncating(self) -> bool:
        return bool(self.terms & TRUNCATING)

    @property
    def is_missense(self) -> bool:
        return bool(self.terms & MISSENSE)

    @property
    def in_splice_window(self) -> bool:
        return bool(self.terms & SPLICE_WINDOW)

    @property
    def is_silent(self) -> bool:
        return bool(self.terms & SILENT) and not self.in_splice_window

    @property
    def passed(self) -> bool:
        """Whether the caller passed this call. An empty or ``.`` FILTER means it did."""
        value = self.filters.strip()
        return value in {"", ".", "PASS"}

    @property
    def frequency(self) -> float | None:
        """The frequency to judge rarity by — the highest genetic-ancestry group where known.

        gnomAD's *grpmax* is the right number for a recessive disease: an allele rare overall
        but common in one population is common in that population's carriers.
        """
        values = [v for v in (self.gnomad_af, self.gnomad_af_grpmax) if v is not None]
        return max(values) if values else None


@dataclass(frozen=True)
class AlleleLanes:
    """The lanes one allele produced, and the class that decided which tool spoke for it."""

    lane_class: str
    lanes: tuple[Lane, ...] = field(default_factory=tuple)

    @property
    def scored_by(self) -> str:
        """The name of the lane that a correlation group would let through, or ``""``."""
        effect = [lane for lane in self.lanes if lane.group == ALLELE_EFFECT]
        if not effect:
            return ""
        best = max(effect, key=lambda lane: abs(lane.log10_lr))
        return best.name if not best.is_silent else ""


def lanes_for(evidence: AlleleEvidence, *, source: str) -> AlleleLanes:
    """Every lane one allele earns, ready to hand to :func:`mva.pipeline.likelihood.combine`.

    ``source`` is the receipt carried onto every lane — the table and the run the annotation
    came from. No lane is ever omitted for being unfavourable, and an allele whose
    annotations are entirely missing still returns the frequency and FILTER lanes.
    """
    lanes = [
        _consequence_lane(evidence, source),
        _missense_lane(evidence, source),
        _splice_lane(evidence, source),
        _clinvar_lane(evidence, source),
        _frequency_lane(evidence, source),
        _filter_lane(evidence, source),
    ]
    return AlleleLanes(lane_class=lane_class(evidence), lanes=tuple(lanes))


def lane_class(evidence: AlleleEvidence) -> str:
    """Which consequence class owns this allele — one tool per class, decided up front."""
    if evidence.is_truncating:
        return "truncating"
    if evidence.is_missense:
        return "missense"
    if evidence.in_splice_window:
        return "splice"
    if evidence.is_silent:
        return "silent"
    return "other"


def degrade(likelihood_ratio: float, *, observed: int, required: int = 2) -> float:
    """LIRICAL's degrading recessive genotype ratio, as a function rather than a cliff.

    A recessive disease needs ``required`` damaged copies. Seeing fewer is evidence against,
    but it is not proof: the missing allele may be a call the pipeline never made. Rather
    than zeroing the gene, the ratio is taken to the power of the fraction observed, so one
    of two damaging alleles keeps the square root of the evidence (Robinson 2020).
    """
    if required <= 0:
        raise ValueError("a recessive hypothesis requires at least one allele")
    fraction = min(max(observed / required, 0.0), 1.0)
    return likelihood_ratio**fraction


def _consequence_lane(evidence: AlleleEvidence, source: str) -> Lane:
    if evidence.is_truncating:
        strength, why = _truncating_strength(evidence)
        return Lane.from_strength("consequence", strength, source, group=ALLELE_EFFECT, note=why)
    if evidence.is_silent:
        return Lane.from_strength(
            "consequence",
            Strength.SUPPORTING_BENIGN,
            source,
            group=ALLELE_EFFECT,
            note="protein sequence unchanged and outside the splice window",
        )
    return Lane.from_strength(
        "consequence",
        Strength.NONE,
        source,
        group=ALLELE_EFFECT,
        note=f"class {lane_class(evidence)} is scored by its own tool",
    )


def _truncating_strength(evidence: AlleleEvidence) -> tuple[Strength, str]:
    """LOFTEE-style reasoning: where the truncation falls decides what it is worth.

    A premature stop codon usually destroys the message rather than shortening the protein,
    because the cell detects it and degrades the transcript (nonsense-mediated decay, NMD).
    NMD does not reach the last exon, so a stop there often leaves a shortened protein that
    still does something. That is why *where* the truncation falls matters as much as *that*
    it happened.
    """
    index, total = evidence.exon_index, evidence.exon_total
    if total == 1:
        return Strength.MODERATE, "single-exon transcript: no NMD, truncation may be tolerated"
    if index is None or total is None:
        return Strength.STRONG, "no exon numbering: the NMD rule could not be applied"
    if index >= total:
        return Strength.MODERATE, f"last exon ({index}/{total}): escapes NMD"
    if index == total - 1:
        return (
            Strength.STRONG,
            (
                f"penultimate exon ({index}/{total}): the last-50-bp rule needs exon "
                "lengths VEP REST does not report, so the rung is lowered, not guessed"
            ),
        )
    return Strength.VERY_STRONG, f"exon {index}/{total}: in the NMD-competent body"


def _missense_lane(evidence: AlleleEvidence, source: str) -> Lane:
    if not evidence.is_missense or not evidence.am_class:
        return Lane.from_strength(
            "alphamissense", Strength.NONE, source, group=ALLELE_EFFECT, note="no score"
        )
    call = evidence.am_class.strip().lower()
    if call == "likely_pathogenic":
        strength = cap(Strength.MODERATE, MISSENSE_CEILING)
    elif call == "likely_benign":
        strength = cap(Strength.SUPPORTING_BENIGN, Strength.SUPPORTING_BENIGN)
    else:
        strength = Strength.NONE
    score = evidence.am_pathogenicity
    note = f"AlphaMissense {call}" + (f" ({score:.3f})" if score is not None else "")
    return Lane.from_strength("alphamissense", strength, source, group=ALLELE_EFFECT, note=note)


def _splice_lane(evidence: AlleleEvidence, source: str) -> Lane:
    score = evidence.spliceai_ds_max
    if score is None:
        return Lane.from_strength(
            "spliceai", Strength.NONE, source, group=ALLELE_EFFECT, note="no score"
        )
    if score >= SPLICEAI_HIGH_PRECISION:
        strength = cap(Strength.MODERATE, SPLICE_CEILING)
    elif score >= SPLICEAI_RECOMMENDED:
        strength = cap(Strength.SUPPORTING, SPLICE_CEILING)
    elif score >= SPLICEAI_HIGH_RECALL:
        strength = Strength.NONE
    else:
        strength = Strength.SUPPORTING_BENIGN
    return Lane.from_strength(
        "spliceai",
        strength,
        source,
        group=ALLELE_EFFECT,
        note=f"SpliceAI delta {score:.3f}",
    )


def _clinvar_lane(evidence: AlleleEvidence, source: str) -> Lane:
    value = evidence.clin_sig.strip().lower()
    if not value:
        return Lane.from_strength(
            "clinvar", Strength.NONE, source, group=ALLELE_EFFECT, note="no submission"
        )
    if any(token in value for token in CLINVAR_CONFLICTING):
        return Lane.from_strength(
            "clinvar",
            Strength.NONE,
            source,
            group=ALLELE_EFFECT,
            note="submitters disagree: not evidence either way",
        )
    if any(token in value for token in CLINVAR_PATHOGENIC):
        strength = Strength.STRONG
    elif any(token in value for token in CLINVAR_BENIGN):
        strength = Strength.STRONG_BENIGN
    else:
        strength = Strength.NONE
    return Lane.from_strength(
        "clinvar", strength, source, group=ALLELE_EFFECT, note=f"ClinVar {value}"
    )


def _frequency_lane(evidence: AlleleEvidence, source: str) -> Lane:
    af = evidence.frequency
    if af is None:
        return Lane.from_strength(
            "frequency",
            Strength.SUPPORTING,
            source,
            note="absent from gnomAD (PM2_supporting)",
        )
    if af >= COMMON_AF:
        strength = Strength.STRONG_BENIGN
    elif af >= RARE_AF:
        strength = Strength.MODERATE_BENIGN
    elif af >= ULTRA_RARE_AF:
        strength = Strength.NONE
    else:
        strength = Strength.SUPPORTING
    return Lane.from_strength("frequency", strength, source, note=f"gnomAD grpmax {af:.3g}")


def _filter_lane(evidence: AlleleEvidence, source: str) -> Lane:
    if evidence.passed:
        return Lane("filter", 1.0, source, note="caller passed the call")
    return Lane(
        "filter",
        NON_PASS_LR,
        source,
        note=f"caller filtered the call ({evidence.filters}) — down-weighted, not dropped",
    )
