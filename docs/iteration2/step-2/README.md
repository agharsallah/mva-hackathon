# Step 2 — discover the alleles from the reads

**Standing:** **complete, 2026-09-12** — after a completion audit found it was not.
The step was declared closed with four pre-registered items unrun and the iteration's own
blind gate red; [`notes/completion-audit.md`](notes/completion-audit.md) is the tracker that
recorded the gap and closed it, and entries [089](methodology/089-the-instruments-and-the-gate-that-was-skipped.md)
and [090](methodology/090-the-alleles-the-vendor-never-reported.md) are what running the
missing stages produced. One of them **flipped a verdict**. Hands over to
[step 3](../step-3/README.md). Iteration 2, `step-2`.

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

## Results

| | |
|---|---|
| reads swept | 1,071,835,104 → **14,657,560 matched (1.36752 %**, against a bait covering 1.361 % of the genome) |
| fragments recovered | 7,886,613, **every one complete** |
| aligned | 15,829,813 records, **98.87 % mapped** |
| depth | **median 44.08×** over 3,020 baited intervals; 29 below 10× |
| alleles called | **131,530** rows, two callers of disjoint model class |
| alleles the callset never reported | **1,199** in or beside a coding exon, all annotated ([090](methodology/090-the-alleles-the-vendor-never-reported.md)) |
| structural variants | 18,186 raw; **164 credible two-method-class consensus calls** |
| phase blocks | 6,823 |

## Claims — all resolved

| Id | Verdict | Conf. | Claim |
|---|---|---|---|
| H016 | **supported** | 0.88 | at least one target gene carries a biallelic candidate — ten do, three core tier |
| H019 | **supported** | 0.70 | phasing closes the chain, or names the gap — it named the gap |
| H020 | **refuted** | 0.07 | decoys yield fewer candidates per gene — **they yield exactly as many** |
| H021 | **supported** | 0.65 | the bait recovers ≥ 90 % of reads carrying a known allele (0.9052) |
| H022 | **supported** | 0.88 | ≥ 99 % concordance with the delivered callset (0.9957 / 0.9927) |
| H023 | **refuted** | 0.25 | a two-class deletion does overlap an exon of a rare-allele gene — in two genes, one a decoy |
| ~~H017~~ | **superseded** by H022 | | named DeepVariant, which has no arm64 build ([089](methodology/089-the-instruments-and-the-gate-that-was-skipped.md)) |
| ~~H018~~ | **superseded** by H023 | | named Manta/LUMPY/GRIDSS, none of which have one ([089](methodology/089-the-instruments-and-the-gate-that-was-skipped.md)) |

**H020 changed verdict after the step was first declared closed**, and the reason is the
point of the audit. The scoring query judged an allele by joining an annotation table built
from the delivered callset, so an allele only the read-derived callers saw could not be
scored at all — a route built to find what the vendor missed could only rediscover what the
vendor found. Annotating those 1,199 alleles (plan stage 11, skipped) made targets and
decoys **exactly equal** at 10/396. The earlier twofold difference was the artefact. The
consequence was pre-registered and stands: the read route enters the step-6 fusion at
reduced weight.

The two supersessions change the **instrument**, never the claim: H022 still asks for
≥ 99 % concordance against a caller sharing no code with the vendor's, and H023 still
requires two *method classes*, which is what Kosugi 2019 Fig. 6–7 actually supports.
Both are recorded as new register revisions with their reasoning and now with the
platform survey as an evidence row, never as edits.

**Gates:** recovery within 0.5–2× of prediction (1.18×) **pass**; every fragment paired
**pass**; `unseen` bait k-mers = 0 **pass**; scaling, projected kernel-only pass 45.9 min
against 60 min **pass, run late** ([089](methodology/089-the-instruments-and-the-gate-that-was-skipped.md));
off-target < 5 % **fail at 8.79 %**, and
[086](methodology/086-can-the-off-target-gate-be-reached.md) shows no available parameter
reaches it.

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

| `src/mva/calling/` | the adapters: minimap2, mosdepth, freebayes, bcftools, delly, dysgu, whatshap |
| `src/mva/kmer/scaling.py`, `tools/scale_it2_bait.py` | the stage-4 scaling gate |
| `warehouse/it2_step2_tables.py`, `analysis_it2.py`, `analysis_it2_sv.py` | the six tables and the pair SQL |
| `warehouse/annotate_reads.py` + `mva-warehouse annotate-it2-reads` | VEP for the alleles the callset never reported |
| `mva.pipeline.stats.fisher_exact_greater` | the exact test behind every target-vs-decoy p |
| `tools/export_it2_step2_analysis.py` | the figures' one source of numbers |
| `tools/render_it2_step2_figures.py`, `render_it2_step2_results.py` | the eight exhibits |
| `tools/check_blind.py` | the blind gate, as a gate CI runs |
| the DNA-literal rule in `tools/check_coordinates.py` | patient *sequence*, not just position |
| `src/mva/viz/steps_it2.py` + `app/src/pages/Step2.tsx` | `GET /api/steps/step-2` and the deep page, aggregates only |

Nothing is outstanding. The audit note tracks what each of these closed.

## Methodology

| Entry | Question |
|---|---|
| [085](methodology/085-the-bait-and-where-it-runs.md) | Can 42 Mb of reference be turned into a k-mer bait, and where must the pass run? |
| [086](methodology/086-can-the-off-target-gate-be-reached.md) | Could any parameter have passed the off-target gate, and at what cost? |
| [087](methodology/087-the-pass-and-what-it-recovered.md) | What did one pass over 1.07 billion reads actually recover? |
| [088](methodology/088-the-alleles-the-reads-carry.md) | What do the recovered reads say — concordance, pairs, phase, structural variants? |
| [089](methodology/089-the-instruments-and-the-gate-that-was-skipped.md) | Which instruments were available, and does the kernel scale as the plan assumed? |
| [090](methodology/090-the-alleles-the-vendor-never-reported.md) | What happens to H016 and H020 once the alleles only our callers saw are scored? |

## Notes

| Note | What it owns |
|---|---|
| [`notes/completion-audit.md`](notes/completion-audit.md) | what ran, what did not, and what the step's findings change for later steps |
