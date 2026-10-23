"""ProteinGym assay registry for the abundance calibration."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["CANDIDATE_ASSAYS", "AssaySpec"]


@dataclass(frozen=True)
class AssaySpec:
    dms_id: str
    uniprot: str
    gene: str
    assay_kind: str
    intracellular_abundance: bool


CANDIDATE_ASSAYS: tuple[AssaySpec, ...] = (
    AssaySpec("CP2C9_HUMAN_Amorosi_2021_abundance", "P11712", "CYP2C9", "VAMP-seq", True),
    AssaySpec("ERBB2_HUMAN_Elazar_2016", "P04626", "ERBB2", "membrane insertion", False),
    AssaySpec("HXK4_HUMAN_Gersing_2023_abundance", "P35557", "GCK", "DHFR-PCA abundance", True),
    AssaySpec("KCNJ2_MOUSE_Coyote-Maestas_2022_surface", "P35561", "Kcnj2", "surface FACS", False),
    AssaySpec("LYAM1_HUMAN_Elazar_2016", "P14151", "SELL", "membrane insertion", False),
    AssaySpec("NUD15_HUMAN_Suiter_2020", "Q9NV35", "NUDT15", "VAMP-seq", True),
    AssaySpec("OPSD_HUMAN_Wan_2019", "P08100", "RHO", "surface expression", False),
    AssaySpec("PRKN_HUMAN_Clausen_2023", "O60260", "PRKN", "GFP stability/abundance", True),
    AssaySpec("PTEN_HUMAN_Matreyek_2021", "P60484", "PTEN", "VAMP-seq", True),
    AssaySpec("Q53Z42_HUMAN_McShan_2019_expression", "Q53Z42", "HLA-A", "surface FACS", False),
    AssaySpec("SPIKE_SARS2_Starr_2020_expression", "P0DTC2", "S", "yeast surface display", False),
    AssaySpec("TPMT_HUMAN_Matreyek_2018", "P51580", "TPMT", "VAMP-seq", True),
    AssaySpec("VKOR1_HUMAN_Chiasson_2020_abundance", "Q9BQB6", "VKORC1", "VAMP-seq", True),
)
