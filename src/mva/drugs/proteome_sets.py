"""Declared gene sets for proliferation correction: published lists, never tuned on the data.

A **proliferation score** is one number per perturbation (a drug, a knockout) that says how
much it moved the cell-cycle machinery. Here it is the median (proteome) or mean (LINCS)
change over a published gene set. A gene whose protein or mRNA simply follows the cell cycle
- ``BUB1B`` is one - rises and falls with that score; the part of its change the score does
not explain is the **proliferation-corrected** response.

The sets are the Tirosh et al. 2016 (Science 352:189, PMID 27124452) S-phase (43) and
G2/M (54) genes, in the updated symbols Seurat ships as ``cc.genes.updated.2019``
(``MLF1IP``→``CENPU``, ``FAM64A``→``PIMREG``, ``HN1``→``JPT1``). They are the most widely
reused cell-cycle phase lists in single-cell work, they were defined on tumour cells without
any drug, and they are short enough to state in full here.

:data:`SAC_MODULE` is the spindle-assembly-checkpoint and kinetochore group removed from the
score in the sensitivity variant, so a compound that raises that whole module is not
"corrected away" by a score that contains part of it.

Nothing here names a patient or a position; these are gene symbols from two papers.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable

__all__ = [
    "ALIASES",
    "SAC_MODULE",
    "TIROSH_G2M",
    "TIROSH_S",
    "members",
]

#: Tirosh 2016 S-phase genes (Seurat ``cc.genes.updated.2019$s.genes``).
TIROSH_S: tuple[str, ...] = (
    "MCM5", "PCNA", "TYMS", "FEN1", "MCM2", "MCM4", "RRM1", "UNG", "GINS2", "MCM6",
    "CDCA7", "DTL", "PRIM1", "UHRF1", "CENPU", "HELLS", "RFC2", "RPA2", "NASP", "RAD51AP1",
    "GMNN", "WDR76", "SLBP", "CCNE2", "UBR7", "POLD3", "MSH2", "ATAD2", "RAD51", "RRM2",
    "CDC45", "CDC6", "EXO1", "TIPIN", "DSCC1", "BLM", "CASP8AP2", "USP1", "CLSPN", "POLA1",
    "CHAF1B", "BRIP1", "E2F8",
)  # fmt: skip

#: Tirosh 2016 G2/M genes (Seurat ``cc.genes.updated.2019$g2m.genes``).
TIROSH_G2M: tuple[str, ...] = (
    "HMGB2", "CDK1", "NUSAP1", "UBE2C", "BIRC5", "TPX2", "TOP2A", "NDC80", "CKS2", "NUF2",
    "CKS1B", "MKI67", "TMPO", "CENPF", "TACC3", "PIMREG", "SMC4", "CCNB2", "CKAP2L", "CKAP2",
    "AURKB", "BUB1", "KIF11", "ANP32E", "TUBB4B", "GTSE1", "KIF20B", "HJURP", "CDCA3", "JPT1",
    "CDC20", "TTK", "CDC25C", "KIF2C", "RANGAP1", "NCAPD2", "DLGAP5", "CDCA2", "CDCA8", "ECT2",
    "KIF23", "HMMR", "AURKA", "PSRC1", "ANLN", "LBR", "CKAP5", "CENPE", "CTCF", "NEK2",
    "G2E3", "GAS2L3", "CBX5", "CENPA",
)  # fmt: skip

#: Current symbol → older spellings a dataset may still use (LINCS 2021, CCLE 2020).
ALIASES: dict[str, tuple[str, ...]] = {
    "CENPU": ("MLF1IP",),
    "PIMREG": ("FAM64A",),
    "JPT1": ("HN1",),
}

#: Spindle-assembly checkpoint + outer-kinetochore genes (the sensitivity exclusion).
SAC_MODULE: frozenset[str] = frozenset(
    {
        "BUB1", "BUB1B", "BUB3", "MAD1L1", "MAD2L1", "TTK", "CDC20", "AURKB", "CENPE",
        "CENPF", "NDC80", "NUF2", "KIF2C", "CDCA8", "CENPA", "HJURP", "ZWINT", "KNL1",
    }
)  # fmt: skip


def members(
    genes: Iterable[str], available: Collection[str], exclude: Collection[str] = ()
) -> tuple[str, ...]:
    """The set's genes a dataset holds, under the dataset's own spelling, minus ``exclude``.

    A gene is looked up by its current symbol first, then by each alias; the dataset's
    spelling is returned so the caller can index its own matrix. Order follows ``genes``.
    """
    dropped = set(exclude)
    out: list[str] = []
    for gene in genes:
        if gene in dropped:
            continue
        for form in (gene, *ALIASES.get(gene, ())):
            if form in available and form not in dropped:
                out.append(form)
                break
    return tuple(out)
