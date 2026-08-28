# Status and roadmap

Where the work stands, what happens next, and how the full 80 GB gets handled.
Measured facts live in [`../ideation/data-findings.md`](../ideation/data-findings.md);
strategy in [`../ideation/hackathon-intel.md`](../ideation/hackathon-intel.md).

---

## 1. Done

### The data is understood

Every file has been opened and profiled. `tools/profile-genomic-data.sh` reproduces the
whole profile in about ten minutes and writes ~600 KB of committable aggregates to
`ressources/data-profile/` while keeping patient-derived slices in `~/ubuntu/work/`.

Five findings changed the plan:

| # | Finding | Consequence |
|---|---|---|
| 1 | Contigs are bare (`15`), scorer demands `chr15` and does not normalize | a copied coordinate is a silent, total miss |
| 2 | Callset is SNV+indel only — no SV caller in its provenance | if an allele is structural, only the FASTQ can reach it |
| 3 | Physical phasing resolves 5 of 1,653 BUB1B pairs (0.3%) | phasing is confirmatory, not the discriminator |
| 4 | No VEP/gnomAD/ClinVar, and `INFO/AF` is within-sample | annotation is the critical path |
| 5 | Proband is male; no mosaic aneuploidy detectable in blood | report the negative, with numbers |

Supporting numbers: 5,012,204 variants (4.09 M SNP / 0.93 M indel / 66,860 multiallelic),
ts/tv 1.94, het:hom 1.61, 271,414 non-PASS, 770,458 records carrying phasing, ~52× raw →
~44× mapped, 2×149 bp, Q30 92.9%, duplication 9.3%, insert peak 266 bp.

### The pipeline skeleton exists and is tested

Seven modules, 69 tests, 0.15 s, no dataset required — see
[`architecture.md`](architecture.md). Built test-first, one seam at a time:
`variant` → `vcf` → `compound_het` → `submission` → `scorer`, with `annotation` as a port
and `ranking` on top. It runs against the real BUB1B locus and produces the phase
classifications above.

### The compliance perimeter is built

No patient data in git, enforced by a narrow plaintext-only fixture guard
([no patient data](notes/no-patient-data-in-the-repository.md),
[synthetic fixtures](notes/synthetic-fixtures.md)). The committed VCF
header is redacted of the lab accession and the provider's internal job paths. A leak scan
over the whole tree comes back clean.

---

## 2. Next steps, in dependency order

### Step 1 — Normalize the callset (hours, local, unblocks everything)

```bash
# The reference must be the no-chr analysis set, matching the VCF's contigs.
bcftools norm -m -both -f GRCh38_no_chr.fa ~/ubuntu/work/proband.vcf.gz \
  -Oz -o ~/ubuntu/work/proband.norm.vcf.gz
bcftools index -t ~/ubuntu/work/proband.norm.vcf.gz
```

66,860 multiallelic sites and 930k indels against an exact-string-matching scorer. Until
this runs, every indel candidate is a coin flip on representation. Needs the reference
FASTA (~3 GB) fetched first.

**Also a code step:** normalization currently happens outside the pipeline. It should
become a tested seam, so that "was this normalized?" is answerable in code rather than by
remembering which shell command was run.

### Step 2 — A real annotator (days, the critical path)

The blocking dependency. BUB1B's 80 variants are almost entirely common intronic dbSNP
entries; only six lack the dbSNP flag. Nothing in the VCF separates them further.

Implement `Annotator.annotate()` against a real backend. Two-stage is cheapest:

- **Now, for the panel:** Ensembl VEP REST over the 861 panel variants. No cache download,
  works today, rate-limited but 861 variants is nothing. Gets a real candidate list this
  week.
- **Later, genome-wide:** offline VEP cache (~25 GB) plus gnomAD frequencies, run on Modal.
  Needed for the unbiased ranking that the methods form rewards.

Required fields: gene symbol, consequence, gnomAD popmax AF. Valuable additions: CADD,
REVEL, AlphaMissense, SpliceAI (the last matters — a deep intronic splice variant is a
strong candidate for a "missing" second allele), and ClinVar significance.

### Step 3 — Phenotype-driven ranking (days, parallel with step 2)

Run Exomiser and LIRICAL on the normalized VCF with the eight HPO terms. This is the
unbiased genome-wide ranking, and it is also the backbone the methods form asks about.
Cross-check against our panel-first result: agreement is evidence, disagreement is a lead.

### Step 4 — Mine the non-PASS calls (hours, high value per hour)

271,414 suppressed calls, dominated by `MQ40` (177,522) and `QD2` (35,402). A real variant
in repetitive or duplicated sequence is exactly what gets flagged. TRIP13 shows the pattern
directly: 6 of its 12 variants are non-PASS.

Minutes of work against a day of re-calling. Do this before touching the FASTQ.

### Step 5 — The FASTQ path (weeks, see section 3)

Only if steps 2–4 do not produce a convincing pair, or if they produce one allele and not
the other. That second case is the designed trap, and it is where the raw reads earn their
80 GB.

### Step 6 — Spend the first probe

Not before steps 2–4. A probe is worth spending once the candidate list is real; before
that it is a coin flip that burns 1/18 of the team's total budget. Rehearse it in
`scorer.py` first, and keep a ledger of who spent what and what came back.

---

## 3. Handling the whole 80 GB

### What the raw reads are for

Exactly one thing: finding an allele the delivered VCF does not contain. That is a
structural variant, a deep intronic variant in a region the caller skipped, or a low-VAF
mosaic call below the caller's threshold. Nothing else justifies the compute.

This matters because it means the FASTQ work is **conditional and targeted**, not a
prerequisite. Do not start a genome-wide re-call on day one.

### Local capacity, honestly

| | Available | Verdict |
|---|---|---|
| Cores | 12 | workable |
| RAM | 15 GB | **the binding constraint** |
| Disk | 766 GB free | fine — a 44× BAM is ~100 GB, CRAM ~40 GB |

15 GB of RAM rules out `bwa-mem2`, whose GRCh38 index wants ~40 GB. Classic `bwa mem`
(~6 GB index) or `minimap2` fit. But throughput is the real problem: 1.08 billion read
pairs across 12 cores is roughly **a day and a half of continuous alignment**, with no
checkpointing and a machine that cannot do anything else meanwhile.

**So the full alignment belongs on Modal, and the targeted work belongs local.**

### Strategy A — targeted read recovery (local, hours, do this first)

Full alignment is not required to inspect one gene. Build a k-mer set from the panel gene
sequences plus flanks, stream the eight FASTQ files once, and keep read pairs sharing
k-mers with the target. That reduces 161 Gb to well under a gigabyte, which then aligns to
the *full* GRCh38 in minutes — aligning to the full reference matters, so that reads which
truly belong elsewhere map elsewhere rather than being forced into the panel.

```
8 × fastq.gz ──stream──► k-mer filter (panel ± 50 kb) ──► ~0.5 GB of read pairs
                                                              │
                                                    bwa mem → full GRCh38
                                                              ▼
                                        sorted BAM over the candidate loci
                                                              │
                              ┌───────────────────────────────┼─────────────────┐
                              ▼                               ▼                 ▼
                    mosdepth per-exon              Manta / Delly          IGV inspection
                    (single-exon deletions)        (SV breakpoints)       (eyeball it)
```

One full streaming pass over 80 GB of gzip is roughly 40–60 minutes on this machine, and it
is I/O bound, so it can run overnight alongside other work. This is the highest-value use
of the raw data per unit of compute, and it directly addresses the trap in finding #2.

### Strategy B — full re-call (Modal, when strategy A is not enough)

Justified when the gene is still unknown after steps 2–4, or when a genome-wide SV callset
is wanted for the write-up.

| Stage | Tool | Shape | Rough cost |
|---|---|---|---|
| Align | bwa-mem2, 32–64 vCPU | 161 Gb → ~100 GB BAM | 3–6 h |
| Mark duplicates + sort | samtools / sambamba | | 1–2 h |
| Small variants | DeepVariant (GPU) | independent second opinion vs Sentieon | 1–3 h |
| Structural variants | Manta + Delly, consensus | **the point of the exercise** | 2–4 h |
| Coverage | mosdepth | exon-level, finds single-exon deletions | minutes |

Practical notes that decide whether this works:

- **Keep lanes separate through alignment**, with per-lane read groups (`@RG` with `ID`
  per lane, shared `SM`). It costs nothing, it lets duplicate marking work correctly, and
  it makes a single bad lane visible instead of silently degrading the callset.
- **Checkpoint per lane.** Four independent alignment jobs that merge afterwards means a
  failure costs one lane, not the run.
- **Store CRAM, not BAM**, referenced against the same no-chr GRCh38. Roughly 2.5× smaller,
  and the reference is fixed for the project anyway.
- **Track wall-clock and cost per stage as you go.** Methods form Q17 asks for runtime and
  cost, and measured numbers beat estimates on the Scalability criterion.
- **Use the same no-chr reference throughout**, or the new callset will disagree with the
  delivered one on every contig name.

### Strategy C — the smoke loop (already in place)

`~/ubuntu/work/smoke/smoke_200k_R{1,2}.fastq.gz` holds 200k verified-paired read pairs.
Develop and debug the whole align → call → annotate → rank → emit chain against it, where a
full run takes seconds, and only then point the finished pipeline at 161 Gb. It also turns
the runtime answer on the methods form into something measured rather than guessed.

Caveat recorded in the script: those reads come from the head of L001, so they are all from
tile 1101. Fine for exercising a pipeline, not a representative quality sample — use the
`fastp` figures for quality.

### Data lifecycle and the deletion obligation

Everything derived lands under `~/ubuntu/work/`, which is one directory to delete. That is
deliberate: on close, `rm -rf ~/ubuntu/data ~/ubuntu/work` plus any Modal volumes covers
the whole obligation, and the confirmation email to the organisers can be sent honestly.

Anything written outside that directory — a stray BAM in a home folder, a notebook
checkpoint, a Modal volume nobody remembers — is a compliance liability. Keep the tree
boring.

---

## 4. Sequencing of the two tracks

Track 1's automated pipeline (steps 1–4) is also the Track 2 foundation: mechanism
characterisation is only rigorous once the variant is confirmed. Track 2 gets one
submission with no resubmission, so it goes late and grounded, not early and hedged.

The qualitative review after the leaderboard freeze is where a tie between teams at 100
points is broken. That makes steps 1–3 worth doing properly even in the branch where a
probe gets lucky early — the reproducible pipeline *is* the tiebreaker, not decoration.
