# Roadmap — what is next

**Standing:** direction, re-checked 2026-08-29. What already exists is
[`current-state.md`](current-state.md)'s job, not this page's. Measured facts live in
[`../ideation/data-findings.md`](../ideation/data-findings.md); strategy in
[`../ideation/hackathon-intel.md`](../ideation/hackathon-intel.md); decisions in
[`decisions.md`](decisions.md).

---

## 1. Next steps, in dependency order

### Step 1 — Normalize the callset (hours, local, unblocks everything)

```bash
# The reference must be the no-chr analysis set, matching the VCF's contigs.
bcftools norm -m -both -f GRCh38_no_chr.fa ~/ubuntu/work/proband.vcf.gz \
  -Oz -o ~/ubuntu/work/proband.norm.vcf.gz
bcftools index -t ~/ubuntu/work/proband.norm.vcf.gz
```

Multiallelic sites and indels ([counts](../ideation/data-findings.md)) against an
exact-string-matching scorer. Until this runs, every indel candidate is a coin flip on
representation. Needs the reference
FASTA (~3 GB) fetched first.

**Also a code step:** normalization currently happens outside the pipeline. It should
become a tested seam, so that "was this normalized?" is answerable in code rather than by
remembering which shell command was run.

### Step 2 — A real annotator (days, the critical path)

The blocking dependency. The panel's variants are almost entirely common intronic dbSNP
entries and nothing in the VCF separates them further
([measured](../ideation/data-findings.md) §6).

Implement `Annotator.annotate()` against a real backend. Two-stage is cheapest:

- **Now, for the panel:** Ensembl VEP REST over the panel variants. No cache download,
  works today, and rate limiting is irrelevant at that volume. Gets a real candidate list
  this week.
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

The suppressed calls are dominated by `MQ40` and `QD2`
([counts](../ideation/data-findings.md) §3). A real variant in repetitive or duplicated
sequence is exactly what gets flagged, and TRIP13 shows the pattern directly.

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

## 2. Phase 2 — the platform work, in order

The pipeline steps above need a platform underneath them. This is that work, sequenced so
each item unblocks the next. Nothing here is started.

| # | Item | Why now | Owner doc |
|---|---|---|---|
| 1 | **Build layer 2** — `variants`, `genotypes`, `variant_info` from `variants_raw` | the annotation join has nowhere to land until the callset is typed and one-row-per-ALT | [`data-layers.md`](data-layers.md) |
| 2 | **Port the annotator** — implement `Annotator.annotate()` against Ensembl VEP REST | the critical path; the port and its tests already exist | [note](notes/annotation-as-a-port.md) |
| 3 | **Mine the non-PASS calls** | minutes of work against a day of re-calling; needs only layer 2 | §1 step 4 |
| 4 | **The FASTQ path** — k-mer strike first, full re-call only if it fails | the only route to a structural allele; conditional, not a prerequisite | §3 |
| 5 | **Close the lineage gap** — real object keys, real hashes, and one edge per derivation | "which bytes produced this result" must be a query, not an argument, before the report | [note](notes/delivery-is-immutable.md) |
| 6 | **Build the probe ledger** — a Postgres table of who spent which submission, its content, and the decoded reply | the budget is 18 submissions and it is tracked nowhere; this is exactly the mutable shared state Postgres was chosen for | [note](notes/postgres-for-shared-state.md) |

One infrastructure gap sits alongside these and is not blocked by them: the DuckDB
file-warehouse verbs are superseded but still in the CLI. See
[`current-state.md` §5](current-state.md#5-known-gaps).

## 2b. Still open — questions with no answer yet

Carried over from `ideation/draft0-answers.md` §12.2 (now in [`archive/`](../archive/)),
re-checked 2026-08-29. None of these has been resolved.

| Unknown | How to resolve | Blocks what |
|---|---|---|
| Consequence and population frequency of the panel variants | VEP + gnomAD v4 + dbNSFP join — **the blocking dependency** | everything downstream of ranking; there is no ranking signal in the file today |
| Coverage of BUB1B / TRIP13 / CEP57 exons and splice sites | `mosdepth` on the candidate loci — needs a BAM, so gated on the FASTQ path | whether "absent" means absent, especially for telomere-proximal *TRIP13* |
| Whether an SV is one of the two alleles | align, then Manta / Delly / smoove 2-of-3 consensus + GATK-gCNV | the single largest blind spot: an SV allele *cannot* be in the delivered VCF |
| Whether either candidate allele is already in ClinVar | ClinVar join — public data, runnable today | circularity disclosure; near-instant confirmation if yes |
| Whether the aneuploid fraction is simply below the allele-balance floor | binned-depth + BAF karyogram from aligned reads — a lower floor than the VCF-only pass | strength of the diagnostic corroboration paragraph |
| Whether `HP:0200067` (a parental feature) should enter the proband's term set | run Exomiser / LIRICAL with and without, report the delta | phenotype LR calibration |
| Whether nephrocalcinosis is part of the MVA picture or independent | literature check against reported MVA cases | whether it is a differential lead or a footnote |

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
| Disk | 766 GB free | fine — a BAM at this depth is ~100 GB, CRAM ~40 GB |

15 GB of RAM rules out `bwa-mem2`, whose GRCh38 index wants ~40 GB. Classic `bwa mem`
(~6 GB index) or `minimap2` fit. But throughput is the real problem: the full read set
across 12 cores is roughly **a day and a half of continuous alignment**, with no
checkpointing and a machine that cannot do anything else meanwhile.

**So the full alignment belongs on Modal, and the targeted work belongs local.**

### Strategy A — targeted read recovery (local, hours, do this first)

Full alignment is not required to inspect one gene. Build a k-mer set from the panel gene
sequences plus flanks, stream the eight FASTQ files once, and keep read pairs sharing
k-mers with the target. That reduces the whole read set to well under a gigabyte, which then aligns to
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
| Align | bwa-mem2, 32–64 vCPU | the full read set → ~100 GB BAM | 3–6 h |
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
full run takes seconds, and only then point the finished pipeline at the full delivery. It also turns
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

Track 1's automated pipeline (§1 steps 1–4) is also the Track 2 foundation: mechanism
characterisation is only rigorous once the variant is confirmed. Track 2 gets one
submission with no resubmission, so it goes late and grounded, not early and hedged.

The qualitative review after the leaderboard freeze is where a tie between teams at 100
points is broken. That makes §1 steps 1–3 worth doing properly even in the branch where a
probe gets lucky early — the reproducible pipeline *is* the tiebreaker, not decoration.

### Track 2 — drug repurposing

**No work has been executed on Track 2.** Nothing has been searched, ranked, or written.
What follows is only what
[`hackathon-intel.md` §5](../ideation/hackathon-intel.md) already records, kept here so the
placeholder is visible rather than forgotten.

- Scored 35% rigor / 25% impact / 25% innovation / 15% scalability. One shot, no
  resubmission, so it goes late.
- Mechanism angle to characterise: SAC weakening → chromosome missegregation → aneuploidy
  and tumorigenesis. The report must be structured along methods-form Q14 (LoF vs GoF,
  pathway, downstream consequence).
- Directions named in the brief, none investigated: agents that reinforce the spindle
  assembly checkpoint, aneuploidy-selective stressors exploiting proteotoxic and metabolic
  stress, proteostasis strategies if the variant is a hypomorph, and cancer-prevention
  framing for the child's actual malignancy.
- Expected sources, per the methods form: DrugBank, ChEMBL, ClinicalTrials.gov, OMIM,
  PubMed. Market-approved drugs only.
- Deliverables: report, public repo, 3-minute pitch video, one designated submitter.
