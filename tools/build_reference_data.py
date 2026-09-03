#!/usr/bin/env python3
"""Build the committable population-reference tables in `ressources/reference/`.

Two public sources, no patient data anywhere in this script:

  gnomad   gnomAD v4.1 gene constraint metrics  -> gnomad_constraint.tsv
  clinvar  ClinVar GRCh38 VCF over a gene panel -> clinvar_panel.tsv

Both subcommands download to a scratch directory (default `build/reference-scratch/`,
gitignored) and write only the small derived TSV into the repository. The scratch
inputs are 95 MB and 193 MB and are deliberately never committed.

The third table, `qc_norms.tsv`, is a hand-curated literature table and is not
generated here — it has no machine-readable upstream. It still gets a manifest, whose
inputs are the citations its own rows carry.

Every subcommand writes a `*.provenance.json` beside the table it touches, and
`manifests` writes all three for the committed tables without regenerating anything —
which is the case that matters when an upstream has moved on since the commit: the
manifest must describe the bytes in the repository, not the bytes on the server today.

Usage:
  uv run tools/build_reference_data.py gnomad    [--scratch DIR] [--out FILE]
  uv run tools/build_reference_data.py clinvar   [--scratch DIR] [--out FILE] [--bed FILE]
  uv run tools/build_reference_data.py qc-norms  [--out FILE]
  uv run tools/build_reference_data.py manifests [--scratch DIR] [--bed FILE]

`clinvar` needs `bcftools` (>=1.10) and `tabix` on PATH.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

from mva.viz import referencemanifest

REPO = Path(__file__).resolve().parent.parent
DEFAULT_SCRATCH = REPO / "build" / "reference-scratch"
DEFAULT_BED = REPO / "ressources" / "data-profile" / "mva_panel_grch38.bed"
REFERENCE = REPO / "ressources" / "reference"

# The two upstream URLs have one owner, `mva.viz.referencemanifest`, because the manifest
# and the fetch must name the same object: a manifest recording a URL the build did not
# use would be worse than none.
GNOMAD_URL = referencemanifest.GNOMAD_URL
CLINVAR_URL = referencemanifest.CLINVAR_URL

GNOMAD_SCRATCH = "gnomad.v4.1.constraint_metrics.tsv"
CLINVAR_SCRATCH = "clinvar_GRCh38.vcf.gz"

GNOMAD_OUT = REFERENCE / "gnomad_constraint.tsv"
CLINVAR_OUT = REFERENCE / "clinvar_panel.tsv"
QC_NORMS_OUT = REFERENCE / "qc_norms.tsv"


# ── shared ───────────────────────────────────────────────────────────────────


def fetch(url: str, dest: Path) -> Path:
    """Download `url` to `dest` unless a non-empty file is already there."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        print(f"cached  {dest}  ({dest.stat().st_size:,} bytes)", file=sys.stderr)
        return dest
    print(f"fetch   {url}", file=sys.stderr)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url) as r, tmp.open("wb") as fh:
        shutil.copyfileobj(r, fh, length=1 << 20)
    tmp.replace(dest)
    print(f"wrote   {dest}  ({dest.stat().st_size:,} bytes)", file=sys.stderr)
    return dest


def manifest(built: dict, out: Path) -> Path:
    """Write `built` beside `out` as `<name>.provenance.json` and say so.

    Written on every run, never by hand: a manifest a human edits is a claim, and a claim
    about provenance is exactly the thing that must not be one.
    """
    path = referencemanifest.write(built, out.with_suffix(".provenance.json"))
    sha = built["outputs"][0]["sha256"]
    print(f"manifest {path}  (describes {out.name} sha256 {sha[:8]}…)")
    return path


def read_panel(bed: Path) -> list[dict]:
    """Parse the panel BED. Returns rows with the `chr` prefix kept and stripped."""
    rows = []
    for line in bed.read_text().splitlines():
        if not line or line.startswith(("#", "track", "browser")):
            continue
        f = line.split("\t")
        rows.append(
            {
                "chrom": f[0],
                "vcf_chrom": f[0][3:] if f[0].startswith("chr") else f[0],
                "start": int(f[1]),
                "end": int(f[2]),
                "symbol": f[3] if len(f) > 3 else "",
            }
        )
    return rows


# ── gnomAD constraint ────────────────────────────────────────────────────────

# Source column -> output column. The upstream file carries 55 columns and two
# transcript namespaces (Ensembl ENST rows and RefSeq NM/XM rows); only the
# Ensembl rows populate chromosome / transcript_type, so they are the ones kept.
GNOMAD_COLUMNS: list[tuple[str, str]] = [
    ("gene", "gene"),
    ("gene_id", "ensembl_gene_id"),
    ("transcript", "transcript"),
    ("chromosome", "chrom"),
    ("mane_select", "mane_select"),
    ("canonical", "canonical"),
    ("transcript_type", "transcript_type"),
    ("cds_length", "cds_length"),
    ("num_coding_exons", "num_coding_exons"),
    ("lof.obs", "lof_obs"),
    ("lof.exp", "lof_exp"),
    ("lof.oe", "oe_lof"),
    ("lof.oe_ci.lower", "oe_lof_lower"),
    ("lof.oe_ci.upper", "loeuf"),
    ("lof.oe_ci.upper_bin_decile", "loeuf_decile"),
    ("lof.pLI", "pli"),
    ("lof.z_score", "lof_z"),
    ("mis.obs", "mis_obs"),
    ("mis.exp", "mis_exp"),
    ("mis.oe", "oe_mis"),
    ("mis.z_score", "mis_z"),
    ("syn.obs", "syn_obs"),
    ("syn.exp", "syn_exp"),
    ("syn.oe", "oe_syn"),
    ("syn.z_score", "syn_z"),
    ("constraint_flags", "constraint_flags"),
]


def _flags(value: str) -> str:
    """`["outlier_mis","outlier_syn"]` -> `outlier_mis,outlier_syn`; `[]` -> empty.

    The upstream cell embeds double quotes, which a TSV writer would have to quote,
    producing a field no `COPY ... FORMAT text` reader handles. Flatten it instead.
    """
    inner = value.strip().lstrip("[").rstrip("]").replace('"', "").replace("'", "")
    return ",".join(part.strip() for part in inner.split(",") if part.strip())


def _num(value: str) -> str:
    """Render gnomAD's scientific notation as a plain decimal; pass NA through."""
    if value in ("", "NA", "NaN"):
        return "NA"
    try:
        f = float(value)
    except ValueError:
        return value
    if f == int(f) and abs(f) < 1e15:
        return str(int(f))
    return f"{f:.6g}"


def build_gnomad(scratch: Path, out: Path, panel: list[dict]) -> None:
    src = fetch(GNOMAD_URL, scratch / "gnomad.v4.1.constraint_metrics.tsv")
    keep_syms = {r["symbol"] for r in panel}
    seen_syms: set[str] = set()
    kept = 0
    out.parent.mkdir(parents=True, exist_ok=True)
    with src.open(newline="") as fh, out.open("w", newline="") as wfh:
        reader = csv.DictReader(fh, delimiter="\t")
        missing = [c for c, _ in GNOMAD_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            sys.exit(f"gnomAD schema changed, columns absent: {missing}")
        writer = csv.writer(wfh, delimiter="\t", lineterminator="\n")
        writer.writerow([o for _, o in GNOMAD_COLUMNS])
        for row in reader:
            # One canonical Ensembl protein-coding transcript per gene.
            if not row["transcript"].startswith("ENST"):
                continue
            if row["canonical"] != "true" or row["transcript_type"] != "protein_coding":
                continue
            writer.writerow(
                [
                    _flags(row[c]) if c == "constraint_flags" else _num(row[c])
                    for c, _ in GNOMAD_COLUMNS
                ]
            )
            kept += 1
            if row["gene"] in keep_syms:
                seen_syms.add(row["gene"])
    print(f"gnomad  {kept:,} rows -> {out}  ({out.stat().st_size:,} bytes)")
    absent = sorted(keep_syms - seen_syms)
    print(
        f"gnomad  panel genes present: {len(seen_syms)}/{len(keep_syms)}"
        + (f"  MISSING {absent}" if absent else "")
    )


# ── ClinVar panel subset ─────────────────────────────────────────────────────

CLINVAR_HEADER = [
    "chrom",
    "pos",
    "ref",
    "alt",
    "rsid",
    "gene",
    "clnsig",
    "clnrevstat",
    "condition",
    "variation_id",
]

CLINVAR_QUERY = (
    "%CHROM\\t%POS\\t%REF\\t%ALT\\t%ID\\t%INFO/RS\\t%INFO/GENEINFO"
    "\\t%INFO/CLNSIG\\t%INFO/CLNREVSTAT\\t%INFO/CLNDN\\n"
)


def _require(tool: str) -> str:
    path = shutil.which(tool)
    if not path:
        sys.exit(f"{tool} not found on PATH (brew install bcftools)")
    return path


def clinvar_release_date(vcf: Path) -> str:
    """Read the ##fileDate line from the VCF header — the authoritative release date."""
    with gzip.open(vcf, "rt") as fh:
        for line in fh:
            if not line.startswith("##"):
                break
            if line.startswith("##fileDate="):
                return line.strip().split("=", 1)[1]
    return "unknown"


def _clean(value: str) -> str:
    return "" if value in (".", "") else value


def _gene_symbol(geneinfo: str, fallback: str) -> str:
    """GENEINFO is `SYMBOL:GeneID|SYMBOL:GeneID`. Prefer the panel gene when listed."""
    if geneinfo in (".", ""):
        return fallback
    symbols = [part.split(":", 1)[0] for part in geneinfo.split("|") if part]
    if fallback in symbols:
        return fallback
    return symbols[0] if symbols else fallback


def build_clinvar(scratch: Path, out: Path, panel: list[dict]) -> None:
    bcftools = _require("bcftools")
    _require("tabix")
    vcf = fetch(CLINVAR_URL, scratch / "clinvar_GRCh38.vcf.gz")
    fetch(CLINVAR_URL + ".tbi", scratch / "clinvar_GRCh38.vcf.gz.tbi")

    print(f"clinvar release (##fileDate): {clinvar_release_date(vcf)}")

    # The panel BED is chr-prefixed; the ClinVar GRCh38 VCF contigs are bare.
    # Write a stripped BED so bcftools -R matches instead of silently returning
    # zero rows, which is indistinguishable from "no variants here".
    regions = scratch / "panel_bare_contigs.bed"
    regions.write_text(
        "".join(f"{r['vcf_chrom']}\t{r['start']}\t{r['end']}\t{r['symbol']}\n" for r in panel)
    )

    # Region -> gene fallback, for records whose GENEINFO omits the panel symbol.
    by_region = {(r["vcf_chrom"], r["start"], r["end"]): r["symbol"] for r in panel}

    out.parent.mkdir(parents=True, exist_ok=True)
    rows = 0
    with out.open("w", newline="") as wfh:
        writer = csv.writer(wfh, delimiter="\t", lineterminator="\n")
        writer.writerow(CLINVAR_HEADER)
        for (chrom, start, end), symbol in by_region.items():
            proc = subprocess.run(
                [
                    bcftools,
                    "query",
                    "-r",
                    f"{chrom}:{start + 1}-{end}",
                    "-f",
                    CLINVAR_QUERY,
                    str(vcf),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            for line in proc.stdout.splitlines():
                f = line.split("\t")
                rsid = _clean(f[5])
                writer.writerow(
                    [
                        f[0],
                        f[1],
                        f[2],
                        f[3],
                        f"rs{rsid}" if rsid else "",
                        _gene_symbol(f[6], symbol),
                        _clean(f[7]),
                        _clean(f[8]),
                        _clean(f[9]),
                        f[4],
                    ]
                )
                rows += 1
    print(f"clinvar {rows:,} rows -> {out}  ({out.stat().st_size:,} bytes)")


# ── entry point ──────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("gnomad", "clinvar", "qc-norms", "manifests"):
        s = sub.add_parser(name)
        s.add_argument("--scratch", type=Path, default=DEFAULT_SCRATCH)
        s.add_argument("--bed", type=Path, default=DEFAULT_BED)
        s.add_argument("--out", type=Path, default=None)
    args = p.parse_args(argv)

    panel = read_panel(args.bed)
    if not panel:
        sys.exit(f"no panel rows parsed from {args.bed}")
    print(f"panel   {len(panel)} genes from {args.bed}", file=sys.stderr)

    vcf = args.scratch / CLINVAR_SCRATCH
    if args.cmd == "gnomad":
        out = args.out or GNOMAD_OUT
        build_gnomad(args.scratch, out, panel)
        manifest(referencemanifest.gnomad(out, args.scratch / GNOMAD_SCRATCH, args.bed), out)
    elif args.cmd == "clinvar":
        out = args.out or CLINVAR_OUT
        build_clinvar(args.scratch, out, panel)
        manifest(referencemanifest.clinvar(out, vcf, vcf.with_suffix(".gz.tbi"), args.bed), out)
    elif args.cmd == "qc-norms":
        out = args.out or QC_NORMS_OUT
        manifest(referencemanifest.qc_norms(out), out)
    else:
        # Manifests for the committed tables, regenerating nothing. The honest move when
        # an upstream has published a newer release than the one the repository holds.
        manifest(
            referencemanifest.gnomad(GNOMAD_OUT, args.scratch / GNOMAD_SCRATCH, args.bed),
            GNOMAD_OUT,
        )
        manifest(
            referencemanifest.clinvar(CLINVAR_OUT, vcf, vcf.with_suffix(".gz.tbi"), args.bed),
            CLINVAR_OUT,
        )
        manifest(referencemanifest.qc_norms(QC_NORMS_OUT), QC_NORMS_OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
