"""The public inputs of a variant atlas: one UniProt accession in, structure and features out.

A **variant atlas** is a table with one row per possible single-residue substitution of a
protein (every position × every other amino acid: 19 × length rows), each row carrying
predicted effects and the structural context of its residue. This module fetches and parses
the protein-generic inputs; :mod:`mva.drugs.variant_atlas` joins them.

Sources, all public and keyed by the UniProt accession alone:

* **AlphaFold DB** (``alphafold.ebi.ac.uk/api/prediction/<acc>``, CC BY 4.0) — the predicted
  structure. Its B-factor column holds **pLDDT** (0–100, the model's per-residue confidence);
  below ~50 a residue is usually disordered, not folded.
* **UniProtKB** (``rest.uniprot.org``, CC BY 4.0) — the canonical sequence and the curated
  features (domains, regions, motifs).
* **InterPro** (``ebi.ac.uk/interpro/api``, CC0) — member-database domain calls (Pfam, CDD,
  SMART, PROSITE profiles).

**RSA** (relative solvent accessibility: the fraction of a residue's surface that water can
touch, 0 = buried core, 1 = fully exposed) is computed here with the Shrake–Rupley algorithm
(dots on each atom's probe-inflated sphere; a dot inside any neighbour is buried) and divided
by the theoretical maximum of Tien et al. 2013 (PLoS One 8:e80635). numpy + scipy only.

No patient data enters this module: every input is named by a public accession.
"""

from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

__all__ = [
    "MAX_ASA",
    "Feature",
    "Residue",
    "alphafold_pdb",
    "features_from",
    "interpro_entries",
    "ken_boxes",
    "parse_pdb",
    "parse_region",
    "read_esm1b_matrix",
    "residues_from_pdb",
    "shrake_rupley",
    "uniprot_entry",
]

AF_API = "https://alphafold.ebi.ac.uk/api/prediction/{acc}"
UNIPROT = "https://rest.uniprot.org/uniprotkb/{acc}.json"
INTERPRO = "https://www.ebi.ac.uk/interpro/api/entry/all/protein/uniprot/{acc}/?page_size=200"

THREE_TO_ONE = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C", "GLN": "Q", "GLU": "E",
    "GLY": "G", "HIS": "H", "ILE": "I", "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F",
    "PRO": "P", "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
}  # fmt: skip

#: Theoretical maximum accessible surface area per residue, Å² (Tien et al. 2013).
MAX_ASA = {
    "A": 129.0, "R": 274.0, "N": 195.0, "D": 193.0, "C": 167.0, "Q": 225.0, "E": 223.0,
    "G": 104.0, "H": 224.0, "I": 197.0, "L": 201.0, "K": 236.0, "M": 224.0, "F": 240.0,
    "P": 159.0, "S": 155.0, "T": 172.0, "W": 285.0, "Y": 263.0, "V": 174.0,
}  # fmt: skip

#: Van der Waals radii, Å (Bondi 1964) — the values Biopython's Shrake–Rupley uses.
RADII = {"C": 1.70, "N": 1.55, "O": 1.52, "S": 1.80, "H": 1.20, "SE": 1.90}

#: UniProt feature types that name a stretch of the protein worth reading a variant against.
UNIPROT_TYPES = ("Domain", "Region", "Motif", "Repeat", "Zinc finger", "Coiled coil")
#: InterPro member databases whose domain calls are kept.
INTERPRO_DBS = ("pfam", "cdd", "smart", "profile")


@dataclass(frozen=True)
class Residue:
    position: int  # 1-based, as the structure numbers it
    aa: str
    plddt: float
    rsa: float


@dataclass(frozen=True)
class Feature:
    name: str
    start: int
    end: int
    source: str

    def covers(self, position: int) -> bool:
        return self.start <= position <= self.end


def _download(url: str, path: Path) -> Path:
    """``url`` → ``path`` once; later calls read the cached file."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(url, headers={"User-Agent": "mva-variant-atlas"})
        with urllib.request.urlopen(request, timeout=120) as reply:
            path.write_bytes(reply.read())
    return path


def _json(url: str, path: Path) -> Any:
    return json.loads(_download(url, path).read_text())


def alphafold_pdb(accession: str, cache: Path) -> Path:
    """The AlphaFold DB model (PDB format) for one UniProt accession, cached under ``cache``."""
    meta = _json(AF_API.format(acc=accession), cache / "alphafold_api.json")
    entry = meta[0]
    return _download(str(entry["pdbUrl"]), cache / Path(str(entry["pdbUrl"])).name)


def uniprot_entry(accession: str, cache: Path) -> dict[str, Any]:
    data: dict[str, Any] = _json(UNIPROT.format(acc=accession), cache / "uniprot.json")
    return data


def interpro_entries(accession: str, cache: Path) -> dict[str, Any]:
    data: dict[str, Any] = _json(INTERPRO.format(acc=accession), cache / "interpro.json")
    return data


def parse_pdb(text: str, chain: str = "A") -> tuple[list[tuple[int, str, float]], np.ndarray,
                                                   np.ndarray, list[int]]:  # fmt: skip
    """``(residues, coords, radii, atom_residue_index)`` from one chain's ATOM records.

    ``residues`` is ``(position, one-letter aa, pLDDT)`` in file order; pLDDT is read from
    the CA atom's B-factor column (AlphaFold writes the same value on every atom).
    """
    residues: list[tuple[int, str, float]] = []
    coords: list[tuple[float, float, float]] = []
    radii: list[float] = []
    owner: list[int] = []
    seen: dict[int, int] = {}
    for line in text.splitlines():
        if not line.startswith("ATOM") or line[21] != chain:
            continue
        name, res, pos = line[12:16].strip(), line[17:20], int(line[22:26])
        if res not in THREE_TO_ONE:
            continue
        element = (line[76:78].strip() or name[0]).upper()
        if element == "H":
            continue
        if pos not in seen:
            seen[pos] = len(residues)
            residues.append((pos, THREE_TO_ONE[res], float("nan")))
        if name == "CA":
            p, aa, _ = residues[seen[pos]]
            residues[seen[pos]] = (p, aa, float(line[60:66]))
        coords.append((float(line[30:38]), float(line[38:46]), float(line[46:54])))
        radii.append(RADII.get(element, 1.80))
        owner.append(seen[pos])
    return residues, np.array(coords), np.array(radii), owner


def _sphere(n: int) -> np.ndarray:
    """``n`` near-uniform unit vectors (golden-spiral), the Shrake–Rupley test dots."""
    k = np.arange(n) + 0.5
    phi = np.arccos(1 - 2 * k / n)
    theta = np.pi * (1 + 5**0.5) * k
    return np.stack([np.cos(theta) * np.sin(phi), np.sin(theta) * np.sin(phi), np.cos(phi)], 1)


def shrake_rupley(
    coords: np.ndarray, radii: np.ndarray, probe: float = 1.4, n_points: int = 100
) -> np.ndarray:
    """Solvent-accessible surface area per atom, Å²."""
    from scipy.spatial import cKDTree

    dots = _sphere(n_points)
    inflated = radii + probe
    tree = cKDTree(coords)
    reach = float(inflated.max())
    area = np.zeros(len(coords))
    for i, centre in enumerate(coords):
        near = [j for j in tree.query_ball_point(centre, inflated[i] + reach) if j != i]
        points = centre + inflated[i] * dots
        if near:
            gap = ((points[:, None, :] - coords[near][None, :, :]) ** 2).sum(-1)
            exposed = ~(gap < inflated[near][None, :] ** 2).any(1)
        else:
            exposed = np.ones(n_points, dtype=bool)
        area[i] = 4 * np.pi * inflated[i] ** 2 * exposed.mean()
    return area


def residues_from_pdb(text: str, chain: str = "A") -> list[Residue]:
    """Per residue: position, amino acid, pLDDT and RSA (capped at 1.0)."""
    residues, coords, radii, owner = parse_pdb(text, chain)
    atom_area = shrake_rupley(coords, radii)
    per_residue = np.zeros(len(residues))
    np.add.at(per_residue, np.array(owner), atom_area)
    return [
        Residue(pos, aa, plddt, min(1.0, float(per_residue[i]) / MAX_ASA[aa]))
        for i, (pos, aa, plddt) in enumerate(residues)
    ]


def ken_boxes(sequence: str) -> list[Feature]:
    """Every literal K-E-N tripeptide (a KEN box: an APC/C degron / CDC20-binding motif)."""
    return [
        Feature("KEN box (sequence scan)", m.start() + 1, m.start() + 3, "sequence scan: KEN")
        for m in re.finditer("(?=KEN)", sequence)
    ]


def features_from(uniprot: dict[str, Any], interpro: dict[str, Any] | None) -> list[Feature]:
    """Curated UniProt features plus InterPro member-database domain calls."""
    out: list[Feature] = []
    for item in uniprot.get("features", []):
        if item.get("type") not in UNIPROT_TYPES:
            continue
        loc = item["location"]
        start, end = loc["start"].get("value"), loc["end"].get("value")
        if start is None or end is None:
            continue
        name = item.get("description") or item["type"]
        out.append(Feature(str(name), int(start), int(end), f"UniProt {item['type']}"))
    for entry in (interpro or {}).get("results", []):
        meta = entry["metadata"]
        if meta.get("source_database") not in INTERPRO_DBS:
            continue
        for protein in entry.get("proteins", []):
            for location in protein.get("entry_protein_locations", []):
                out.extend(
                    Feature(
                        str(meta.get("name") or meta["accession"]),
                        int(fragment["start"]),
                        int(fragment["end"]),
                        f"InterPro {meta['source_database']} {meta['accession']}",
                    )
                    for fragment in location.get("fragments", [])
                )
    return out


def parse_region(spec: str) -> Feature:
    """``"name:start-end:source"`` → a Feature (the CLI's ``--region``)."""
    name, span, source = spec.split(":", 2)
    start, end = span.split("-")
    return Feature(name, int(start), int(end), source)


def read_esm1b_matrix(path: Path) -> dict[tuple[int, str], float]:
    """Brandes et al. 2023 (PMID 37563329) ESM1b LLR matrix → ``{(position, alt): llr}``.

    The file is one CSV per isoform: header ``,M 1,A 2,...``; one row per amino acid.
    LLR ≤ 0; more negative = the model finds the substitution less plausible.
    """
    lines = path.read_text().splitlines()
    positions = [int(cell.split()[1]) for cell in lines[0].split(",")[1:]]
    out: dict[tuple[int, str], float] = {}
    for line in lines[1:]:
        cells = line.split(",")
        for pos, value in zip(positions, cells[1:], strict=True):
            out[(pos, cells[0])] = float(value)
    return out
