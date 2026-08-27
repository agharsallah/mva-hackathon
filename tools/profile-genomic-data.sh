#!/usr/bin/env bash
#
# Profile the gated dataset without copying patient data into the repo.
#
#   usage: tools/profile-genomic-data.sh /path/to/data [workdir]
#
# Two output destinations, and the split is deliberate:
#
#   ressources/data-profile/   COMMITTABLE — headers, contig lists, aggregate counts.
#                              File shape and summary statistics only. No variant
#                              records, no read sequences.
#
#   <workdir>/                 LOCAL ONLY, NEVER COMMITTED — panel VCF extract and a
#                              small FASTQ subsample for pipeline smoke tests. Real
#                              patient sequence, covered by the DTA, delete within
#                              30 days of hackathon close.
#
set -euo pipefail

DATA_DIR="${1:?usage: profile-genomic-data.sh /path/to/data [workdir]}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="${2:-$(cd "$DATA_DIR/.." && pwd)/work}"
PROFILE="$REPO/ressources/data-profile"

mkdir -p "$PROFILE" "$WORK/panel" "$WORK/smoke" "$WORK/stats"

VCF_SRC="$(find "$DATA_DIR" -maxdepth 1 -name "*.vcf.gz" | sort | sed -n 1p)"
VCF="$WORK/proband.vcf.gz"
SAMPLE_ALIAS="PROBAND01"

log() { printf '\n=== %s\n' "$*"; }

# sha256sum on Linux, shasum on macOS.
sha256() { command -v sha256sum >/dev/null && sha256sum || shasum -a 256; }

# ---------------------------------------------------------------------------
# 0. Preflight
# ---------------------------------------------------------------------------
log "preflight"
missing=()
for t in bcftools tabix; do command -v "$t" >/dev/null || missing+=("$t"); done
if [ ${#missing[@]} -gt 0 ]; then
  echo "missing tools: ${missing[*]}" >&2
  echo "install with: micromamba create -p ~/.local/micromamba/envs/bio \\" >&2
  echo "                -c conda-forge -c bioconda bcftools samtools htslib seqkit fastp" >&2
  exit 1
fi
[ -n "$VCF_SRC" ] || { echo "no *.vcf.gz found in $DATA_DIR" >&2; exit 1; }

# The shipped .tbi predates its VCF and carries no count metadata, so bcftools
# refuses to report per-contig counts from it. Rebuild ours in the work dir and
# leave the delivered files untouched.
ln -sf "$VCF_SRC" "$VCF"
[ -f "$VCF.tbi" ] || { log "re-indexing (shipped .tbi is stale)"; bcftools index -f -t "$VCF"; }

log "manifest"
{
  printf '%s\t%s\t%s\n' file bytes sha256_first_1MB
  for f in "$DATA_DIR"/*; do
    [ -f "$f" ] || continue
    # Hashing the first MB only detects a corrupt or truncated download without
    # reading 80 GB.
    printf '%s\t%s\t%s\n' "$(basename "$f")" "$(wc -c < "$f")" \
      "$(head -c 1048576 "$f" | sha256 | cut -d' ' -f1)"
  done
} > "$PROFILE/manifest.tsv"

# ---------------------------------------------------------------------------
# 1. VCF — header, shape, aggregate counts
# ---------------------------------------------------------------------------
log "VCF header (sample ID and internal paths redacted)"
# The header leaks the lab accession and the sequencing provider's DNAnexus job
# paths in the GATK/Sentieon command lines. Neither belongs in a public repo.
bcftools view -h "$VCF" \
  | awk -v alias="$SAMPLE_ALIAS" 'BEGIN{OFS="\t"}
      /^#CHROM/ { for (i = 10; i <= NF; i++) $i = alias; print; next } { print }' \
  | sed -E -e "s/WGS_EX[0-9]+/$SAMPLE_ALIAS/g" \
           -e 's#/home/dnanexus/inputs/input[0-9]+/#<input>/#g' \
           -e 's#/home/dnanexus/#<workdir>/#g' \
  > "$PROFILE/vcf_header.txt"

log "field inventory"
grep -E '^##(INFO|FORMAT|FILTER)' "$PROFILE/vcf_header.txt" \
  | sed -E 's/^##([A-Z]+)=<ID=([^,]+).*Description="([^"]*)".*/\1\t\2\t\3/' \
  > "$PROFILE/vcf_fields.tsv"

log "per-contig record counts"
bcftools index -s "$VCF" > "$PROFILE/vcf_contig_counts.tsv"

log "bcftools stats (few minutes)"
bcftools stats "$VCF" > "$WORK/stats/vcf_stats.txt"
# Keep the aggregates; drop the per-QUAL-bin block, which is thousands of lines.
awk '/^(SN|TSTV|SiS|AF|IDD|ST|DP)\t/ && ++n <= 200' "$WORK/stats/vcf_stats.txt" \
  > "$PROFILE/vcf_stats_summary.txt"

log "FILTER / genotype / phasing tallies (one full pass, few minutes)"
bcftools query -f '%FILTER\t[%GT]\t[%PID]\n' "$VCF" | awk -F'\t' '
  { filt[$1]++; gt[$2]++; if ($3 != ".") phased++; total++ }
  END {
    print "## FILTER counts";   for (k in filt) printf "%s\t%d\n", k, filt[k]
    print "\n## genotype counts"; for (k in gt) printf "%s\t%d\n", k, gt[k]
    printf "\n## records_in_phase_group\t%d\n", phased + 0
    printf "## total_records\t%d\n", total
  }' > "$PROFILE/vcf_filter_gt_counts.tsv"

log "per-chromosome allele balance (mosaic aneuploidy fingerprint)"
# A chromosome in mosaic trisomy/monosomy shifts het VAF off 0.5 and shifts depth.
# Depth is bounded to 15-80x so that repeat pile-ups and dropouts do not swamp the signal.
bcftools query -i 'GT="het" && FILTER="PASS" && TYPE="snp"' -f '%CHROM\t[%AD]\n' "$VCF" \
  | awk -F'\t' '
      { split($2, a, ","); d = a[1] + a[2]; if (d < 15 || d > 80) next
        vaf = a[2] / d; c = $1; n[c]++; s[c] += vaf; dp[c] += d
        if (vaf >= 0.40 && vaf <= 0.60) mid[c]++ }
      END { printf "%s\t%s\t%s\t%s\t%s\n", "chrom","n_het","mean_vaf","mean_dp","pct_in_0.40_0.60"
        for (i = 1; i <= 24; i++) { c = i; if (i == 23) c = "X"; if (i == 24) c = "Y"
          if (n[c] > 0) printf "%s\t%d\t%.4f\t%.1f\t%.1f\n", c, n[c], s[c]/n[c], dp[c]/n[c], 100*mid[c]/n[c] } }' \
  > "$PROFILE/vcf_chrom_allele_balance.tsv"

# ---------------------------------------------------------------------------
# 2. FASTQ — lane structure, depth, quality. No sequence emitted.
# ---------------------------------------------------------------------------
log "FASTQ profile (estimated from a 200 MB compressed slice per file)"
SLICE=200000000
{
  printf '%s\t%s\t%s\t%s\t%s\n' file bytes read_len est_reads est_gbases
  for f in "$DATA_DIR"/*.fastq.gz; do
    [ -f "$f" ] || continue
    size=$(wc -c < "$f")
    # A truncated gzip stream makes the decoder exit nonzero after emitting what it
    # could; that is the intent here, so the failure is swallowed.
    rl=$(head -c 400000 "$f" | gzip -cd 2>/dev/null | sed -n '2p' | tr -d '\n' | wc -c || true)
    n=$(head -c "$SLICE" "$f" | gzip -cd 2>/dev/null | wc -l || true)
    est=$(( (n / 4) * size / SLICE ))
    printf '%s\t%s\t%s\t%s\t%s\n' "$(basename "$f")" "$size" "$rl" "$est" \
      "$(awk -v r="$est" -v l="$rl" 'BEGIN { printf "%.2f", r * l / 1e9 }')"
  done
} > "$PROFILE/fastq_profile.tsv"
awk -F'\t' 'NR > 1 { g += $5 } END { printf "est_total_gbases\t%.1f\nest_raw_coverage_x\t%.1f\n", g, g / 3.1 }' \
  "$PROFILE/fastq_profile.tsv" >> "$PROFILE/fastq_profile.tsv"

log "FASTQ read-name headers (index barcode redacted)"
{
  echo "# First read name per file. Index barcode redacted (library identity, not biology)."
  printf '%s\t%s\n' file read_name
  for f in "$DATA_DIR"/*.fastq.gz; do
    [ -f "$f" ] || continue
    hdr=$(head -c 4000 "$f" | gzip -cd 2>/dev/null | sed -n '1p' || true)
    printf '%s\t%s\n' "$(basename "$f")" \
      "$(printf '%s' "$hdr" | sed -E 's/ ([12]:[YN]:[0-9]+:).*/ \1<redacted-index>/')"
  done
} > "$PROFILE/fastq_read_headers.tsv"

if command -v fastp >/dev/null; then
  log "FASTQ quality QC (500k read pairs of L001)"
  R1="$(find "$DATA_DIR" -maxdepth 1 -name "*L001_R1_001.fastq.gz" | sort | sed -n 1p)"
  R2="${R1/_R1_/_R2_}"
  # Report-only: no -o/-I output, so nothing is written but the JSON/HTML.
  fastp -i "$R1" -I "$R2" --reads_to_process 500000 \
        --json "$WORK/stats/fastp_L001.json" --html "$WORK/stats/fastp_L001.html" 2>/dev/null
  python3 - "$WORK/stats/fastp_L001.json" > "$PROFILE/fastq_qc_L001.tsv" <<'PY'
import json, sys
d = json.load(open(sys.argv[1])); s = d["summary"]
print("metric\tvalue")
for phase in ("before_filtering", "after_filtering"):
    b = s[phase]
    print(f"{phase}.total_reads\t{b['total_reads']}")
    print(f"{phase}.q30_rate\t{b['q30_rate']:.4f}")
    print(f"{phase}.gc_content\t{b['gc_content']:.4f}")
print(f"duplication_rate\t{d['duplication']['rate']:.4f}")
print(f"insert_size_peak\t{d['insert_size']['peak']}")
print(f"adapter_trimmed_reads\t{d['adapter_cutting']['adapter_trimmed_reads']}")
print("# sampled from lane L001, first 500000 read pairs")
PY
fi

# ---------------------------------------------------------------------------
# 3. Panel — counts are committable, records are not
# ---------------------------------------------------------------------------
BED="$PROFILE/mva_panel_grch38.bed"
log "MVA panel BED (public gene coordinates)"
[ -s "$BED" ] || python3 "$REPO/tools/mva_panel_bed.py" "$BED" 20000 \
  || echo "panel BED fetch failed — rerun with network access" >&2

if [ -s "$BED" ]; then
  # The panel BED is chr-prefixed; this VCF's contigs are not. Strip on the way in.
  grep -v '^#' "$BED" | awk 'BEGIN{OFS="\t"}{ sub(/^chr/, "", $1); print $1, $2, $3, $4 }' \
    | sort -k1,1 -k2,2n > "$WORK/panel/panel_nochr.bed"

  log "panel variant counts (a count is not a record — committable)"
  {
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' gene chrom start end n_all n_pass
    while IFS=$'\t' read -r c s e sym; do
      printf '%s\tchr%s\t%s\t%s\t%s\t%s\n' "$sym" "$c" "$((s + 1))" "$e" \
        "$(bcftools view -H -r "${c}:$((s + 1))-${e}" "$VCF" 2>/dev/null | wc -l)" \
        "$(bcftools view -H -f PASS -r "${c}:$((s + 1))-${e}" "$VCF" 2>/dev/null | wc -l)"
    done < "$WORK/panel/panel_nochr.bed"
  } > "$PROFILE/panel_variant_counts.tsv"

  log "panel VCF extract -> $WORK (LOCAL ONLY, DO NOT COMMIT)"
  bcftools view -R "$WORK/panel/panel_nochr.bed" -Oz -o "$WORK/panel/panel_mva.vcf.gz" "$VCF"
  bcftools index -f -t "$WORK/panel/panel_mva.vcf.gz"
fi

log "FASTQ smoke subsample -> $WORK (LOCAL ONLY, DO NOT COMMIT)"
# 200k read pairs exercise a full align/call pipeline in seconds. Note these come from
# the head of the file, so they are all from tile 1101 — fine for a smoke test, not a
# representative quality sample. Use the fastp figures above for quality.
for r in R1 R2; do
  f="$(find "$DATA_DIR" -maxdepth 1 -name "*L001_${r}_001.fastq.gz" | sort | sed -n 1p)"
  head -c 120000000 "$f" | gzip -cd 2>/dev/null | head -800000 | gzip \
    > "$WORK/smoke/smoke_200k_${r}.fastq.gz" || true
done

log "done"
echo
echo "COMMITTABLE  -> $PROFILE"; ls -lh "$PROFILE"
echo
echo "LOCAL ONLY   -> $WORK  (patient sequence; never commit, delete within 30 days of close)"
