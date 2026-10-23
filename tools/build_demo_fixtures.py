"""Write the shareable demo dataset to ``app/src/fixtures/demo/`` from ``fixtures/data/``.

The demo build (``pnpm build:demo``) never calls an API and reads only this directory plus
the public reference files listed in ``app/src/fixtures/loader.ts``. Every file here is
SYNTHETIC: counts are rescaled to a ~35x GIAB HG002-like genome and jittered by a seeded
PRNG, the sample is renamed HG002, and the phenotype is the public OMIM 257300 (MVA1)
disease annotation instead of the real proband's terms. Re-run after a fixture changes:

    uv run python tools/build_demo_fixtures.py
"""

import json
import random
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "app/src/fixtures/data"
OUT = ROOT / "app/src/fixtures/demo"

# The pages the demo keeps (Overview, Learn, Data, Case) read exactly these payloads.
FILES = [
    "overview",
    *(
        f"callset-{n}"
        for n in (
            "depth-distribution",
            "filters",
            "funnel",
            "genotypes",
            "indel-lengths",
            "observed-expected",
            "substitutions",
            "tstv",
            "zygosity-split",
        )
    ),
    "genome-allele-balance",
    "genome-contig-density",
    "genome-density-per-mb",
    "reads-lane-reads",
    "reads-partitions",
    "reads-runs",
    "reads-yield",
    *(
        f"panel-{n}"
        for n in (
            "annotations-extra",
            "background",
            "clinvar",
            "clinvar-sites",
            "constraint",
            "genes",
            "het-pairs",
            "suppressed-census",
            "structure-genes",
            "suppressed-records",
        )
    ),
    "phenotype-delta",
    "phenotype-gene-detail",
    "phenotype-genes-proband-only",
    "phenotype-genes-with-parental",
    "phenotype-terms",
    "search-lookups",
]

# Integers that are identities, coordinates or reference facts — never rescaled.
FIXED_KEYS = {
    "pos",
    "length",
    "bin",
    "lane",
    "read_num",
    "read_length",
    "stage_no",
    "entrez_id",
    "rank",
    "variation_id",
    "review_stars",
    "impact_rank",
    "shards",
    "n_files",
    "chrom",
    "allele_ix",
    "samples",
    "canonical_contigs",
    "span_bp",
    "contig_n_bins",
    "curated_terms",
    "information_content",
    "best_ic",
    "af_bin",
    "expected_low",
    "expected_high",
    "gnomad_af",
    "gnomad_af_grpmax",
    "af",
}
# Public reference data (gnomAD constraint, ClinVar counts): copied, only renamed.
PASSTHROUGH = {"panel-constraint", "panel-clinvar", "panel-structure-genes"}
READ_KEYS = {
    "reads",
    "total_reads",
    "est_coverage_x",
    "mean_depth_x",
    "mean_dp",
    "est_reads",
    "source_bytes",
    "parquet_bytes",
    "est_gbases",
    "gigabytes",
    "gib",
}
COUNT_SCALE = 0.96  # HG002 v4.2.1-like call count vs the source genome
READ_SCALE = 0.68  # ~35x instead of ~52x

# Real proband terms -> public MVA1 (OMIM 257300) HPO annotation terms.
TERMS = {
    "HP:0000121": ("HP:0002667", "Nephroblastoma", "Nephrocalcinosis"),
    "HP:0001508": ("HP:0000252", "Microcephaly", "Failure to thrive"),
    "HP:0003202": ("HP:0001305", "Dandy-Walker malformation", "Skeletal muscle atrophy"),
    "HP:0001622": ("HP:0000518", "Cataract", "Premature birth"),
    "HP:0001518": ("HP:0001511", "Intrauterine growth retardation", "Small for gestational age"),
    "HP:0200067": ("HP:0003826", "Stillbirth", "Recurrent spontaneous abortion"),
}
NOTE = "public OMIM 257300 (MVA1) annotation — demo case, not a real patient"

rng = random.Random(257300)


def jitter(value: float, scale: float, spread: float) -> float:
    return value * scale * (1 + rng.uniform(-spread, spread))


def transform(node, key: str | None = None):
    if isinstance(node, dict):
        out = {k: transform(v, k) for k, v in node.items()}
        if "note" in out and "hpo_id" in out:
            out["note"] = NOTE
        return out
    if isinstance(node, list):
        return [transform(v, key) for v in node]
    if isinstance(node, bool) or node is None:
        return node
    if isinstance(node, str):
        return rename(node)
    if key in FIXED_KEYS:
        return node
    scale = READ_SCALE if key in READ_KEYS else 1.0
    if isinstance(node, int):
        if abs(node) < 20:
            return node
        return round(jitter(node, scale * COUNT_SCALE, 0.02))
    return round(jitter(node, scale, 0.01), 6)


def rename(text: str) -> str:
    text = re.sub("proband01", "hg002", text)
    text = re.sub("PROBAND01", "HG002", text)
    for old_id, (new_id, new_label, old_label) in TERMS.items():
        text = text.replace(old_id, new_id).replace(old_label, new_label)
    return text


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for stale in OUT.glob("*.json"):
        stale.unlink()
    for name in FILES:
        data = json.loads((SRC / f"{name}.json").read_text())
        data = json.loads(rename(json.dumps(data))) if name in PASSTHROUGH else transform(data)
        if name == "phenotype-terms":
            for s in data["sets"]:
                s["rationale"] = f"{s['name']}: demo term set from the public MVA1 annotation."
        (OUT / f"{name}.json").write_text(json.dumps(data, separators=(",", ":")) + "\n")
    print(f"wrote {len(FILES)} files to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
