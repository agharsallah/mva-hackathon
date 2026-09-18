"""The five things that can be wrong with one chromosome, written as data.

Kong 2018 (MAD-seq, PMID 29773658) compares five models per chromosome. Each is a claim
about two observable consequences at once — where the heterozygous sites' allele fractions
sit, and how deep the reads are relative to the rest of the genome — and the five differ in
ways that a single statistic cannot separate but a likelihood can.

At cell fraction *f*, writing ``t = f / (2 + f)`` for the band offset a trisomy produces:

======================  ==========================  ==================  ==============
model                   allele-fraction bands       relative depth      extra params
======================  ==========================  ==================  ==============
``normal``              {c}                         1                   —
``monosomy``            {c}                         1 − f/2             f
``mitotic_trisomy``     {c − t, c + t}, equal       1 + f/2             f
``meiotic_trisomy``     {c − t, c, c + t}           1 + f/2             f, w
``cnloh``               {c − f/2, c + f/2}, equal   1                   f
======================  ==========================  ==================  ==============

Two of those rows carry a warning, both pre-registered rather than discovered afterwards:

**Mitotic and meiotic trisomy differ by position, and this pipeline has no position.**
A meiotic non-disjunction keeps a pericentromeric tract with three *distinct* haplotypes
and recombinant tracts further out, so the band structure changes *along* the chromosome.
Collapse position and the two become the same two-band mixture. The third band with weight
``w`` is the best a coordinate-free histogram can do — it captures the tract that stayed
balanced — and it is a weak proxy, not the published discriminator. Anything it says is
reported as weak or not identifiable.

**Copy-neutral loss of heterozygosity and mitotic trisomy share their bands.** Both put
half the sites above the centre and half below, and at small *f* they differ only in depth:
1.0 against 1 + f/2, which is 2.5 % at f = 0.05 — inside ordinary between-chromosome depth
variation from GC content and mappability. Their pairwise ΔBIC is therefore reported on its
own, and the call is refused below the depth precision the sample actually shows.

**Monosomy is carried by depth alone, on purpose.** In a bulk sample the diploid cells
still make a site heterozygous, so a low-fraction monosomy does not remove heterozygous
calls cleanly — what removes them is the caller's threshold, which is not a model anyone
here can write down honestly. The heterozygous-site density is therefore *reported* beside
every fit, from ``results.it2_mosaic_density``, and is not smuggled into the likelihood.

**Every model carries a shared noise component, and without it the comparison is useless.**
On real whole-genome data a few per cent of heterozygous calls have an allele balance that
two clean copies cannot produce at all: collapsed repeats, unflagged copy-number changes,
sites where one allele maps badly. No single beta-binomial matches those tails, and with
200,000 calls per chromosome the mismatch is worth thousands of BIC units — so the richest
model wins everywhere, at implausible parameters, on every chromosome including the ones
that are certainly normal. Measured on this sample before the fix: chromosome 1 preferred a
three-band mixture at f = 0.45 over ``normal`` by ΔBIC 8,058.

So each model is ``(1 − ε)`` of its own bands plus ``ε`` of a deliberately wide
beta-binomial at the centre. All five carry it, all five fit ε, and the comparison is then
about **band structure** rather than about which model happens to have a spare parameter to
spend on the tails. It is the difference between a comparison that answers the question and
one that answers "which of these is most flexible".

**A contig whose noise share is large is not measurable, and is reported as such.** ε under
the ``normal`` model is that contig's honest tail burden. Past :data:`NOISE_CEILING` the
allele balance is not describable by any of these models and a mechanism call would be an
artefact of the repeats — which is what the acrocentric chromosomes here do.

**What counts as a free parameter.** Fitted per chromosome by every model: ρ, ε, plus the
cell fraction and the balanced-tract weight where a model has them. The baseline depth and
its between-chromosome spread are genome-wide and identical across the five, so they cannot
move a ΔBIC and are not counted in *k*. The convention is stated because BIC comparisons are
only meaningful if everyone counts the same way.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

__all__ = [
    "CNLOH",
    "MEIOTIC_TRISOMY",
    "MITOTIC_TRISOMY",
    "MODELS",
    "MONOSOMY",
    "NORMAL",
    "NUISANCE",
    "Band",
    "Model",
    "bands_for",
    "by_name",
    "depth_ratio",
    "offset",
]

#: Fitted per chromosome by every model, including ``normal``: the over-dispersion rho and
#: the noise share epsilon. The baseline depth and its between-chromosome spread are
#: genome-wide and shared across the five, so neither can move a Delta-BIC and neither is
#: counted here.
NUISANCE = 2

#: The over-dispersion of the shared noise component. Deliberately large and deliberately
#: fixed: it is not a measurement of anything, it is a wide shape for "this site's allele
#: balance is not two clean copies". Fitting it would let it drift onto the signal.
NOISE_RHO = 0.30

#: Above this fitted noise share the contig's allele balance is not describable by these
#: models at all, and any mechanism call from it would be an artefact. Ten per cent: an
#: order of magnitude above what the clean autosomes here show (0.9-2.8 %).
NOISE_CEILING = 0.10


@dataclass(frozen=True)
class Band:
    """One allele-fraction band: where it sits, and what share of sites belong to it."""

    centre: float
    weight: float


@dataclass(frozen=True)
class Model:
    """One hypothesis about a chromosome."""

    name: str
    #: plain-English, for the report and the dashboard
    meaning: str
    #: does the model have a cell fraction to fit at all?
    has_fraction: bool
    #: does it have a third, balanced band whose weight is fitted?
    has_tract: bool
    #: free parameters beyond the shared nuisance ones
    extra: int

    @property
    def parameters(self) -> int:
        return NUISANCE + self.extra


NORMAL = Model(
    name="normal",
    meaning="two copies in every cell; the spread is the assay's own",
    has_fraction=False,
    has_tract=False,
    extra=0,
)

MONOSOMY = Model(
    name="monosomy",
    meaning="one copy in a fraction of cells: depth falls and heterozygous sites vanish",
    has_fraction=True,
    has_tract=False,
    extra=1,
)

MITOTIC_TRISOMY = Model(
    name="mitotic_trisomy",
    meaning="a third copy gained after fertilisation: two bands, depth rises",
    has_fraction=True,
    has_tract=False,
    extra=1,
)

MEIOTIC_TRISOMY = Model(
    name="meiotic_trisomy",
    meaning="a third copy inherited: two bands plus a tract that stayed balanced",
    has_fraction=True,
    has_tract=True,
    extra=2,
)

CNLOH = Model(
    name="cnloh",
    meaning="one copy replaced by a duplicate of the other: two bands, depth unchanged",
    has_fraction=True,
    has_tract=False,
    extra=1,
)

#: Declaration order is report order, and the order BIC ties are broken in.
MODELS: tuple[Model, ...] = (NORMAL, MONOSOMY, MITOTIC_TRISOMY, MEIOTIC_TRISOMY, CNLOH)


def by_name(name: str) -> Model:
    for model in MODELS:
        if model.name == name:
            return model
    raise KeyError(f"unknown model {name!r}; known: {', '.join(m.name for m in MODELS)}")


def offset(model: Model, fraction: float) -> float:
    """How far each band sits from the centre, for this model at this cell fraction.

    A trisomy's third copy is one of three, so the minor band sits at ``1/(2+f)`` of the
    reads rather than at ``1/2``; the offset is the difference, ``f / (2 + f)``. Copy-neutral
    loss of heterozygosity replaces a copy instead of adding one, so the denominator stays
    two and the offset is ``f / 2``.
    """
    if model is CNLOH:
        return fraction / 2.0
    return fraction / (2.0 + fraction)


def bands_for(model: Model, fraction: float, centre: float, tract: float = 0.0) -> list[Band]:
    """The bands this model predicts, as (centre, weight) pairs summing to weight 1."""
    if not model.has_fraction or fraction <= 0.0:
        return [Band(centre, 1.0)]
    width = offset(model, fraction)
    if model is MONOSOMY:
        # A lost copy leaves the surviving cells' sites balanced; what changes is how many
        # sites are called heterozygous at all, which the density statistic carries and the
        # allele-fraction likelihood cannot see. One band, deliberately.
        return [Band(centre, 1.0)]
    if model.has_tract:
        share = float(np.clip(tract, 0.0, 1.0))
        return [
            Band(centre - width, (1.0 - share) / 2.0),
            Band(centre, share),
            Band(centre + width, (1.0 - share) / 2.0),
        ]
    return [Band(centre - width, 0.5), Band(centre + width, 0.5)]


def depth_ratio(model: Model, fraction: float) -> float:
    """Expected read depth relative to a normal chromosome's."""
    if not model.has_fraction or fraction <= 0.0:
        return 1.0
    if model is MONOSOMY:
        return 1.0 - fraction / 2.0
    if model is CNLOH:
        return 1.0
    return 1.0 + fraction / 2.0
