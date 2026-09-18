"""Write ``fixtures/it4/`` — synthetic allele records, per-lane score tables and pairs.

Every value is invented, seeded, and reproducible: ``uv run python tools/make_it4_fixtures.py``
rewrites the folder byte-for-byte. Positions are on chromosome 1 below 1,000,000, far from any
candidate span; no sequence window is written (rule 4 of the coordinate gate). The shapes are
the wave-0 contracts of ``docs/iteration4/plan.md`` §7b: 200 records, a 50-row score table
per MVP lane, 20 biallelic pairs.
"""

from __future__ import annotations

import csv
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mva.zoo.types import allele_id

OUT = Path("fixtures/it4")
SEED = 4
GENES = ["GENEA", "GENEB", "GENEC", "GENED", "GENEE", "GENEF", "GENEG", "GENEH", "GENEI", "GENEJ"]
CONSEQUENCES = [
    ("missense_variant", 0.55),
    ("synonymous_variant", 0.20),
    ("splice_region_variant", 0.10),
    ("stop_gained", 0.05),
    ("frameshift_variant", 0.05),
    ("intron_variant", 0.05),
]
AMINO = "ACDEFGHIKLMNPQRSTVWY"
BASES = "ACGT"
LANES = {
    "alphamissense": ("missense_variant",),
    "esm1b": ("missense_variant",),
    "spliceai": (
        "missense_variant",
        "synonymous_variant",
        "splice_region_variant",
        "intron_variant",
    ),
    "revel": ("missense_variant",),
}


def _consequence(rng: random.Random) -> str:
    names, weights = zip(*CONSEQUENCES, strict=True)
    return rng.choices(names, weights=weights, k=1)[0]


def records(rng: random.Random, n: int = 200) -> list[dict]:
    rows: list[dict] = []
    for i in range(n):
        gene = GENES[i % len(GENES)]
        pos = 100_000 + i * 3_517
        ref = rng.choice(BASES)
        alt = rng.choice([b for b in BASES if b != ref])
        consequence = _consequence(rng)
        aa_pos = rng.randint(2, 900)
        hgvs_p = None
        if consequence == "missense_variant":
            a, b = rng.sample(AMINO, 2)
            hgvs_p = f"p.{a}{aa_pos}{b}"
        elif consequence == "stop_gained":
            hgvs_p = f"p.{rng.choice(AMINO)}{aa_pos}*"
        rows.append(
            {
                "allele_id": allele_id("1", pos, ref, alt),
                "chrom": "1",
                "pos": pos,
                "ref": ref,
                "alt": alt,
                "gene": gene,
                "transcript": f"ENST{i % len(GENES):011d}",
                "consequence": consequence,
                "hgvs_c": f"c.{rng.randint(10, 3000)}{ref}>{alt}",
                "hgvs_p": hgvs_p or "",
                "uniprot": f"P{10000 + i % len(GENES):05d}",
                "is_read_only": "true" if i % 40 == 39 else "false",
                "af_gnomad": round(rng.random() ** 4, 6),
                "clin_sig": rng.choice(["", "", "", "benign", "uncertain_significance"]),
            }
        )
    return rows


def scores(rng: random.Random, recs: list[dict], lane: str, n: int = 50) -> list[dict]:
    eligible = [r for r in recs if r["consequence"] in LANES[lane]]
    chosen = rng.sample(eligible, min(n, len(eligible)))
    return [
        {
            "allele_id": r["allele_id"],
            "model": lane,
            "version": "fixture-1",
            "score": round(rng.random(), 4),
        }
        for r in chosen
    ]


def pairs(rng: random.Random, recs: list[dict], n: int = 20) -> list[dict]:
    by_gene: dict[str, list[dict]] = {}
    for r in recs:
        by_gene.setdefault(r["gene"], []).append(r)
    rows: list[dict] = []
    while len(rows) < n:
        gene = rng.choice(GENES)
        left, right = rng.sample(by_gene[gene], 2)
        rows.append(
            {
                "gene": gene,
                "allele_id_left": left["allele_id"],
                "allele_id_right": right["allele_id"],
                "phase": rng.choice(["trans", "unphased"]),
                "is_confirmed": "false",
            }
        )
    rows[0]["is_confirmed"] = "true"
    return rows


def write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    rng = random.Random(SEED)
    recs = records(rng)
    write(OUT / "records.tsv", recs)
    for lane in LANES:
        write(OUT / "scores" / f"{lane}.tsv", scores(rng, recs, lane))
    write(OUT / "pairs.tsv", pairs(rng, recs))
    print(f"wrote {OUT}: {len(recs)} records, {len(LANES)} lanes, 20 pairs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
