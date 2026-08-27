#!/usr/bin/env python3
"""Build a GRCh38 BED for the MVA candidate gene panel from the Ensembl REST API.

Coordinates are fetched rather than hardcoded so they are reproducible and cannot
drift silently. Only gene symbols leave the machine — no patient data is involved.

Usage: mva_panel_bed.py OUT.bed [PAD_BP]
"""

import json
import sys
import time
import urllib.error
import urllib.request

# MVA1/2/3 plus the atypical/candidate genes reported in case series.
PANEL = [
    ("BUB1B", "MVA1, spindle assembly checkpoint, cancer predisposition"),
    ("CEP57", "MVA2, rhizomelic shortening, usually no malignancy"),
    ("TRIP13", "MVA3, Wilms tumour predisposition"),
    ("CENPE", "atypical MVA, case reports"),
    ("CEP192", "candidate, centrosome"),
    ("SMC5", "candidate, chromosome maintenance"),
    # Rhabdomyosarcoma predisposition differential — rules out the obvious mimics.
    ("TP53", "Li-Fraumeni differential for rhabdomyosarcoma"),
    ("DICER1", "DICER1 tumour predisposition differential"),
]

ENSEMBL = "https://rest.ensembl.org/lookup/symbol/homo_sapiens/{}?content-type=application/json"


def lookup(symbol: str, attempts: int = 4) -> dict:
    """Ensembl rate-limits with 503s; back off and retry rather than dropping a gene."""
    req = urllib.request.Request(ENSEMBL.format(symbol), headers={"User-Agent": "mva-hackathon"})
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp)
        except (urllib.error.URLError, TimeoutError):
            if attempt == attempts - 1:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def main(out_path: str, pad: int) -> None:
    rows, failed = [], []
    for symbol, note in PANEL:
        try:
            g = lookup(symbol)
        except (urllib.error.URLError, TimeoutError) as exc:
            failed.append(f"{symbol}: {exc}")
            continue
        if g.get("assembly_name") != "GRCh38":
            failed.append(f"{symbol}: assembly is {g.get('assembly_name')}, expected GRCh38")
            continue
        start = max(0, int(g["start"]) - 1 - pad)  # BED is 0-based half-open
        end = int(g["end"]) + pad
        rows.append((f"chr{g['seq_region_name']}", start, end, symbol, g["id"], note))

    rows.sort(key=lambda r: (r[0], r[1]))
    with open(out_path, "w") as fh:
        fh.write(f"# MVA candidate panel, GRCh38, {pad} bp padding, source: Ensembl REST\n")
        fh.write("# chrom\tstart\tend\tsymbol\tensembl_id\tnote\n")
        for chrom, start, end, symbol, gid, note in rows:
            fh.write(f"{chrom}\t{start}\t{end}\t{symbol}\t{gid}\t{note}\n")

    print(f"wrote {out_path}: {len(rows)} genes")
    for f in failed:
        print(f"  FAILED {f}", file=sys.stderr)
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 20000)
