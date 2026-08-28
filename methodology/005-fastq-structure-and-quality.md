# 005 — What are the raw reads, and what depth do they give?

## Question

Read length, lane structure, true coverage and base quality — needed to decide whether
re-calling and SV detection are viable, and to answer the methods form's runtime question
with measured rather than guessed numbers.

## Inputs

8 files, `~/ubuntu/data/WGS_EX2312012_HGWCNDSX7_S16_L00{1..4}_R{1,2}_001.fastq.gz`,
10,195,738,985 – 11,035,873,766 bytes each.

## Commands

Read names and length, per file:

```bash
head -c 200000 "$f" | gzip -cd | head -4
```

Read count, estimated by decompressing a fixed 200 MB compressed slice and scaling by
file size — a full `wc -l` over 80 GB would take roughly half an hour for no extra
precision:

```bash
SLICE=200000000
n=$(head -c $SLICE "$f" | gzip -cd | wc -l)
est_reads=$(( (n/4) * size / SLICE ))
```

Quality, on the first 500,000 read pairs of L001 (report-only, no output files):

```bash
fastp -i ..._L001_R1_001.fastq.gz -I ..._L001_R2_001.fastq.gz \
      --reads_to_process 500000 --json fastp_L001.json --html fastp_L001.html
```

## Observed

Read names: `@A01973:164:HGWCNDSX7:<lane>:1101:...` — instrument A01973, run 164,
flowcell HGWCNDSX7, lanes 1–4, one library (index pair identical across lanes; L003's
first read differs by one base in the index, consistent with a sequencing error in the
index read).

**Read length 149** for both R1 and R2 in all 8 files, sequence and quality strings equal
length.

Estimated reads per file: 131,443,212 – 138,245,967. **Total 160.9 Gbases → 51.9× raw**
against a 3.1 Gb genome. Full table: `ressources/data-profile/fastq_profile.tsv`.

fastp on 500k pairs of L001:

| | |
|---|---|
| Q30, R1 / R2 (before filtering) | 92.92% / 90.03% |
| Q20, R1 / R2 | 97.28% / 95.74% |
| duplication rate | 9.31% |
| insert size peak | 266 bp |
| GC content | 41.41% |
| reads with adapter trimmed | 32,746 of 1,000,000 |
| reads failed low quality | 17,542 of 1,000,000 |

## Conclusions

1. **Read length is 149, not the 151 assumed in the strategy brief.** Minor, but it feeds
   every coverage calculation.
2. **~52× raw against ~44× mapped** (entry 004) is a normal ~15% loss to duplicates and
   unmapped reads. The two independent measurements agreeing is a good consistency check.
3. **Quality is clinical-grade**: Q30 above 90% on both reads, 9.3% duplication, low
   adapter content, GC 41.4% (human, as expected). No trimming is required before
   re-alignment beyond standard adapter handling.
4. **The 266 bp insert size explains the phasing limit** measured in entry 006: physical
   phasing can only reach variants close enough to share a read pair.
5. **4 lanes of one library** means they merge freely, but per-lane read groups should be
   kept if realigning — it costs nothing and makes a single bad lane visible.
