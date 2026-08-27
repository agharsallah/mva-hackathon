#!/usr/bin/env bash
# Split the site dump into addressable sections and convert the methods xlsx to markdown.
# Everything this touches is already in git — safe by construction.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$REPO/ressources/hackathon-rules"
OUT="$SRC/extracted"
mkdir -p "$OUT"

# 1. raw_hackathon.txt -> one file per "=>SECTION" marker
awk -v out="$OUT" '
  /^=>/ { name = tolower(substr($0,3)); gsub(/[^a-z0-9]+/,"-",name);
          f = out "/" name ".txt"; print "" > f; next }
  f     { print >> f }
' "$SRC/raw_hackathon.txt"

# 2. methods_description_form.xlsx -> markdown (stdlib only, no openpyxl)
python3 "$REPO/tools/xlsx_to_md.py" \
  "$SRC/methods_description_form.xlsx" \
  "$OUT/methods_description_form.md"

echo "--- extracted ---"
ls -lh "$OUT"
