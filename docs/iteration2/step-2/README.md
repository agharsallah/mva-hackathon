# Step 2 — discover the alleles from the reads

**Standing:** opened 2026-09-11 by step 1's handover; the instrument is built and the bait
is cut (entry [085](methodology/085-the-bait-and-where-it-runs.md)); **the pass has not
run**. Iteration 2, `step-2`.

**Goal** (from `src/mva/science/steps.py`):

> Which alleles do the raw reads carry in the target set, discovered without the vendor
> caller — small variants, structural variants, per-exon coverage, and read-backed phase?

The design — bait, align, call, annotate, enumerate, phase — is [`plan.md`](../plan.md)
§3 step 2. What `execution.md` §3 said about *tools* is corrected below: it routed this
step to a Linux server or a cloud VM, and everything but one stage now runs here.

## What step 1 hands over

| Input | Where | Note |
|---|---|---|
| target set, 404 rows, tiered | `results.it2_targets` | bait input |
| matched decoy set, 396 rows | `results.it2_decoys` | the read route's null (H020) |
| padding, fixed in advance | core and mechanism-term ±50 kb, net and decoy ±2 kb | plan §3 step 2 |
| the assumption step 2 inherits | **the target set is an enrichment with measured recall ≈ 0.36, not coverage** | [084](../step-1/methodology/084-the-blind-target-set.md) |

That last row is load-bearing. A gene absent from the target set is **not** excluded by
step 2; it is simply not baited. The genome-wide safety net is step 4.

## Claims

| Id | Status | Claim |
|---|---|---|
| H016 | proposed | at least one target gene carries a biallelic candidate in the read-derived calls |
| H019 | proposed | for the top candidate pair, read-backed phasing closes the chain or names the gap that prevents it |
| H020 | proposed | the decoy set yields fewer biallelic candidates per gene than the target set |
| **H021** | proposed | the reference k-mer bait at its chosen stride recovers ≥ 90 % of the reads carrying a known alternate allele inside the baited region |
| **H022** | proposed | the read-derived calls agree with the delivered callset at ≥ 99 % of sites where both call |
| **H023** | proposed | no SV supported by two callers of different method classes, outside the bait-edge zone, removes or duplicates a coding exon of a gene that also carries a rare heterozygous protein-altering allele |
| ~~H017~~ | **superseded** by H022 | named DeepVariant, which has no arm64 build |
| ~~H018~~ | **superseded** by H023 | named Manta/LUMPY/GRIDSS, none of which have one |

The two supersessions change the **instrument**, never the claim: H022 still asks for
≥ 99 % concordance against a caller sharing no code with the vendor's, and H023 still
requires two *method classes*, which is what Kosugi 2019 Fig. 6–7 actually supports.
Both are recorded as new register revisions with their reasoning, never as edits.

## Where it runs — corrected from `execution.md` §2

Everything runs on the laptop **except the single pass over 1.07 billion reads**.

| Stage | Where | Why |
|---|---|---|
| bait, uniqueness filter, witness probes | laptop | pure NumPy over the reference; no Linux-only k-mer counter needed |
| **the read pass** | the job service, `POST /bait` | 55.8 s per shard from here (measured, and parallelism does not help) = 4.2 h per pass, against minutes beside the data |
| align, coverage, call, SV, phase, pairs, tables, figures | laptop | arm64 builds exist for every tool actually used |

The tool substitutions that make that true, and what each costs:

| `execution.md` said | Actually used | Consequence |
|---|---|---|
| KMC 3 / Jellyfish | `mva.kmer` uniqueness pass | none — it computes the same off-target count from a smaller problem |
| DeepVariant | freebayes + `bcftools call -m` | weaker on indels; SNV and indel concordance are reported separately (H022) |
| Manta + Delly + LUMPY + GRIDSS | delly + dysgu | two method classes kept; fewer callers, so the consensus is thinner and says so |
| WhatsHap + HapCUT2 | WhatsHap + our own fragment counter | the second opinion is auditable rather than a second black box |
| bwa-mem2 | `minimap2 -ax sr -I 4G` | index in minutes inside 16 GiB |

## Order, and the gate each stage must pass

| # | Stage | Gate |
|---|---|---|
| 1 | reference prepared | contig count matches the callset's; headers bare |
| 2 | bait cut | bases, k-mers and expected recovery printed **before** the pass |
| 3 | uniqueness filter | off-target k-mers < 5 %; `unseen` = 0 |
| 4 | scaling test | projected pass < 1 h server-side |
| 5 | **the pass** | recovered reads within 0.5–2× of expected |
| 6 | bait recall | H021 ≥ 0.90 |
| 7 | recover paired FASTQ | R1/R2 counts equal; names round-trip byte-exactly |
| 8–9 | align, coverage | on-target ≥ 80 %; no target exon < 10× without a note |
| 10–11 | call, annotate | both callers emit; every allele annotated or listed as failed |
| 12 | SV consensus | two method classes; bait-edge calls flagged; DUP/INV carry their precision prior |
| 13–15 | pairs, phase, concordance | H016, H020; H019; H022 |

A stage whose gate fails does not feed the next one — the failure is the finding.

## The tools this step needed, and where they are filed

Built here because a research step's tools are filed under that step (CLAUDE.md):

| Thing | What it is |
|---|---|
| `src/mva/kmer/` | 2-bit k-mer packing, canonical form, bait cutting, the uniqueness pass, membership |
| `src/mva/reads/bait.py`, `recover.py`, `baitjob.py`, `cli_bait.py` | the sweep, the orphaned-mate pass, FASTQ recovery, the `mva-reads bait` verb |
| `POST /bait` on `mva-reads-api` | the same sweep as a job, beside the data |
| `tools/build_reference_genome.py` | the coordinate system, bare-contig, with its provenance |
| `tools/build_it2_bait.py` | the bait and its gate numbers |
| `tools/build_it2_witness.py` | H021's probe set, drawn by script from the callset |

Still to build: `src/mva/calling/` (the adapters), `warehouse/it2_step2_tables.py` and
`analysis_it2.py` (the tables and the pair SQL), `tools/render_it2_step2_figures.py`, the
`/steps/step-2` page, and the DNA-literal rule in `tools/check_coordinates.py`.

## Methodology

| Entry | Question |
|---|---|
| [085](methodology/085-the-bait-and-where-it-runs.md) | Can 42 Mb of reference be turned into a k-mer bait, and where must the pass run? |
