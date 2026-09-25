"""The R1 case card for the **transfer** case: Bloom syndrome (`BLM`).

Written to answer one question — *how much has to be written to move route R1 to a second
disease?* — so it is deliberately the only new file R1's transfer needed. Same contract as
:mod:`mva.drugs.readthrough_case` (the BUB1B card): thresholds, allele factors, scenarios,
and a prose block for the manifests. The generic modules are untouched.

**The allele is from the literature, not from a patient.** Bloom syndrome is caused mostly by
premature-termination alleles — German 2007 (PMID 17407155) found 54 of 64 registry mutations
terminate translation early — and the allele modelled here, `BLM` c.1642C>T (p.Gln548*), is one
of the pathogenic stops **measured** in Toledano 2024 (PMID 39174735). That is why this case is
the transfer case: the model's prediction can be checked against a real measurement, which the
BUB1B case could not do (``HOLDOUT_CONTEXTS``).

**What Bloom syndrome does not have, and BUB1B does:** a graded dosage series. There is no
published `BLM` hypomorph ladder — carriers are healthy and biallelic loss gives the syndrome.
So ``THRESHOLDS`` has two rungs, and that is a property of the *disease literature*, not of the
code. The dosage table for this case is therefore coarser than the BUB1B one, and says so.

Nothing here is a recommendation, and no number is a measurement in any living person.
"""

from __future__ import annotations

import csv
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from mva.drugs.readthrough_dosage import Allele, DrugEffect, Scenario, Threshold

__all__ = [
    "ALLELE",
    "BENCHMARK_PANEL",
    "DOSAGE_PARAMETERS",
    "DOSSIER",
    "HOLDOUT_CONTEXTS",
    "NOTES",
    "PUBLISHED_ALLELES",
    "THRESHOLDS",
    "best_readthrough",
    "scenarios",
]

#: The published allele this case models, in the shape the callset reader returns. Taken from
#: the literature: ClinVar-pathogenic `BLM` nonsense allele measured in Toledano 2024
#: (PMID 39174735) and of the class German 2007 (PMID 17407155) reports for the BS Registry.
#: No patient of this project carries it.
ALLELE: dict[str, Any] = {
    "transcript": "ENST00000355112",
    "hgvs_c": "ENST00000355112.8:c.1642C>T",
    "hgvs_p": "p.Gln548Ter",
    "consequence": "stop_gained",
    "clin_sig": "pathogenic (Bloom syndrome; published allele, not a patient of this project)",
    "af_gnomad": None,
    "source": "PMID:39174735 (measured PTC panel); allele class PMID:17407155",
}

#: The *measured* context of that same allele in the published dataset. The holdout stage
#: removes it from the fit entirely and then predicts it, so the comparison is external.
HOLDOUT_CONTEXTS: tuple[str, ...] = ("BLM_Q548X",)

#: The benchmark panel is a property of the measurement dataset, not of the gene, so the
#: BUB1B card's panel is reused unchanged. ``BLM_Q548X`` is deliberately **not** in it: the
#: external check holds it out separately, and a context cannot be both the control and the test.
BENCHMARK_PANEL = frozenset(
    {
        "CFTR_G542X",
        "CFTR_W1282X",
        "CFTR_R1162X",
        "CFTR_R553X",
        "CFTR_G550X",
        "CFTR_Y1092X(tag)",
        "CFTR_Y1092X(taa)",
        "TP53_R213X",
        "DMD_R1051X",
        "DMD_R3381X",
        "USH2A_R626X",
        "PTEN_R130X",
        "BUB1B_R114X",
        "CEP57_R339X",
    }
)

#: Percent of the wild-type **diploid** BLM level, and what that level produces. Two rungs:
#: the disease has no published graded hypomorph series (see the module docstring).
THRESHOLDS: tuple[Threshold, ...] = (
    Threshold("wild type", 100.0, "healthy", "reference"),
    Threshold(
        "heterozygous carrier (one syndrome-causing allele)",
        50.0,
        "healthy; sister-chromatid-exchange frequency indistinguishable from controls",
        "PMID:4140506 (Chaganti 1974: normal SCE in BS heterozygotes); PMID:17407155",
    ),
    Threshold(
        "biallelic premature-termination alleles",
        0.0,
        "Bloom syndrome: growth deficiency, sun sensitivity, ~90 SCE per metaphase "
        "(controls ~7), immunodeficiency, early and multiple cancers",
        "PMID:4140506; PMID:7585968; PMID:17407155",
    ),
)

#: The share of a nonsense allele's message that escapes nonsense-mediated decay. No `BLM`
#: allele-specific measurement is used here; 0.10 is carried over from the BUB1B card as a
#: generous upper reading of "undetectable", and is a **stated assumption, not a measurement**.
NMD_ESCAPE = 0.10

#: What a complete NMD blockade would lift that to (a hypothetical ceiling, never a dose).
NMD_INHIBITED = 1.0

#: How well a readthrough product works: the near-cognate amino acid at codon 548 sits inside
#: the helicase's N-terminal region, and nothing is measured for it. 0.5 is a stated guess.
PRODUCT_ACTIVITY = 0.5

PUBLISHED_ALLELES = "ressources/track2/it5/transfer/r1/blm_allele_note.md"

#: No hand-written candidate dossier for this case: the dossier is BUB1B content, not code.
DOSSIER = False

DOSAGE_PARAMETERS: dict[str, Any] = {
    "nmd_escape": NMD_ESCAPE,
    "nmd_escape_under_inhibition": NMD_INHIBITED,
    "readthrough_product_activity": PRODUCT_ACTIVITY,
    "genotype_modelled": "homozygous p.Gln548Ter (both alleles premature stops)",
    "model": "per allele, 0.5 x mrna x protein_per_mrna x full_length x specific_activity",
    "threshold_resolution": (
        "two rungs only: BLM has no published graded hypomorph series, so a scenario between "
        "0 % and 50 % has no published genotype to be read against"
    ),
}


def _stop_allele(readthrough: float = 0.0, *, escape: float = NMD_ESCAPE) -> Allele:
    return Allele(
        label="stop",
        mrna=escape,
        protein_per_mrna=1.0,
        full_length=readthrough,
        specific_activity=PRODUCT_ACTIVITY if readthrough else 1.0,
        basis="NMD-competent premature stop; no full-length protein without a readthrough agent",
    )


def _healthy() -> Allele:
    return Allele(
        label="healthy",
        mrna=1.0,
        protein_per_mrna=1.0,
        full_length=1.0,
        specific_activity=1.0,
        basis="a wild-type copy",
    )


def best_readthrough(path: Path, *, controlled_only: bool = True) -> dict[str, float]:
    """The predicted readthrough per drug, as a fraction, from this route's own table.

    Identical contract to the BUB1B card: only drugs whose held-out control passed, and the
    dataset's no-drug column is never a treatment.
    """
    out: dict[str, float] = {}
    if not path.is_file():
        return out
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            if not row["predicted_readthrough"] or row["drug_name"] == "Untreated":
                continue
            if controlled_only and row["control_passed"] != "true":
                continue
            out[row["drug_name"]] = float(row["predicted_readthrough"]) / 100.0
    return out


def scenarios(facts: dict[str, Any], predicted: dict[str, float]) -> list[Scenario]:
    """Wild type, carrier, the modelled homozygote, and what a readthrough agent could add."""
    out = [
        Scenario("wild type", (_healthy(), _healthy()), note="reference: two healthy copies"),
        Scenario(
            "heterozygous carrier (a parent)",
            (_healthy(), _stop_allele()),
            note="healthy, with normal SCE (PMID 4140506) — the yardstick a treatment aims at",
        ),
        Scenario(
            "Bloom syndrome, homozygous p.Gln548Ter (untreated)",
            (_stop_allele(), _stop_allele()),
            note="both messages are destroyed by NMD; neither copy makes full-length helicase",
        ),
    ]
    for drug, fraction in sorted(predicted.items(), key=lambda item: -item[1]):
        out.append(
            Scenario(
                f"homozygote + {drug} (readthrough only)",
                (_stop_allele(), _stop_allele()),
                drug=DrugEffect(
                    drug,
                    applies_to="stop",
                    readthrough=fraction,
                    product_activity=PRODUCT_ACTIVITY,
                    source="this route's model, controlled on the declared benchmark panel",
                ),
                note=(
                    f"both alleles respond; each message is still at most "
                    f"{100 * NMD_ESCAPE:.0f}% present"
                ),
            )
        )
    out.append(
        Scenario(
            "homozygote + best agent + complete NMD blockade (upper bound, not a dose)",
            (_stop_allele(), _stop_allele()),
            drug=DrugEffect(
                "best predicted agent + NMD inhibition",
                applies_to="stop",
                nmd_escape_to=NMD_INHIBITED,
                readthrough=max(predicted.values(), default=0.0),
                product_activity=PRODUCT_ACTIVITY,
                source="readthrough from this route's model; the NMD term is a hypothetical",
            ),
            note="every assumption at its most generous, to see the ceiling of this route",
        )
    )
    out.append(
        Scenario(
            "homozygote + a perfect readthrough agent (arithmetic ceiling)",
            (_stop_allele(), _stop_allele()),
            drug=DrugEffect(
                "hypothetical: full transcript, best measured readthrough, wild-type product",
                applies_to="stop",
                nmd_escape_to=NMD_INHIBITED,
                readthrough=max(predicted.values(), default=0.0),
                product_activity=1.0,
                source="arithmetic ceiling, not any real agent",
            ),
            note="not achievable; it bounds what these two alleles could ever be worth",
        )
    )
    _ = facts
    return out


#: The prose the manifests carry for this case (same attribute names as
#: :mod:`mva.drugs.readthrough_notes`, which holds the BUB1B wording).
NOTES = SimpleNamespace(
    SOURCES={
        "literature": (
            "PMID:39174735 (measured readthrough, 5,837 pathogenic PTCs); PMID:4140506, "
            "PMID:7585968, PMID:17407155 (Bloom syndrome genotype-phenotype)"
        ),
        "clinical": (
            "none: this is a transfer case used to measure the route's portability. No "
            "patient of this project has Bloom syndrome and no HPO term is read here"
        ),
        "genomic": (
            "a published allele of the BLM gene, read from the literature; no callset, no "
            "genomic position, no patient sequence"
        ),
        "public": "Ensembl REST (transcript model, CDS) and UniProt P54132 (domains)",
    },
    READTHROUGH_ASSUMPTIONS=(
        "readthrough rate depends far more on the stop codon and its +4/-1 context than on the "
        "gene it sits in, so a group mean learned on other genes' stops transfers to this one"
    ),
    READTHROUGH_LIMITATIONS=(
        "one reporter assay in one cell line (HEK293T), 144 nt of native context and no "
        "chromatin; a percent-of-no-PTC reporter number is not a percent of endogenous protein"
    ),
    READTHROUGH_COLUMN_NOTES={
        "predicted_readthrough": "group mean for this stop codon and context, in the assay's unit",
        "backoff_level": "which key answered: stop+4-1, stop+4, stop or drug",
        "control_passed": "the drug's own held-out control on the declared benchmark panel",
    },
    DOSAGE_ASSUMPTIONS=(
        "BLM function is proportional to the amount of working helicase and the two alleles "
        "add; the healthy carrier state (50 %) is the target a treatment would aim at"
    ),
    DOSAGE_LIMITATIONS=(
        "no BLM protein level has been measured for the modelled genotype, and the disease has "
        "no published graded hypomorph series, so every intermediate total lands between two "
        "rungs with nothing published in between; the NMD-escape and product-activity factors "
        "are stated assumptions carried over from the BUB1B card, not BLM measurements"
    ),
    DOSAGE_VALIDATION=(
        "the untreated homozygote must land at the syndrome rung and the carrier at the healthy "
        "rung, which is the only calibration the published genotypes support"
    ),
    DOSAGE_COLUMN_NOTES={
        "total_pct_of_wild_type": "percent of the wild-type diploid amount of working BLM",
        "gain_pct_points": (
            "percentage points this scenario's drug adds over the same scenario untreated"
        ),
        "nearest_published_genotype": (
            "the published genotype whose level is closest, as a yardstick only"
        ),
    },
)
