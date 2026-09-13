# Step 3 — alignment-free genotype and copy number

**Standing:** **complete, 2026-09-13.** Six claims filed before the run, six settled:
**four refuted (H024, H026, H027, H029), two supported (H025, H028).** The step's own headline claim is one of the refutations,
and it is the most useful thing the step produced. Hands over to
[step 4](../step-4/README.md). Iteration 2, `step-3`.

**Goal** (from `src/mva/science/steps.py`):

> Read without an aligner or a caller, are the discovered alleles at heterozygous
> multiplicity, is every target-gene exon at two copies, and which public ClinVar P/LP
> alleles are present at all?

Design: [`plan.md`](../plan.md) §3 step 3, as revised by
[§11.4](../plan.md#114-step-3-revised). Tools: [`execution.md`](../execution.md) §3.

## What this step is for

Everything step 2 concluded passed through an aligner and a caller. Both are models with
assumptions — where a read belongs, what a haplotype looks like. This step reads the same
bytes with neither: it writes the 31 letters around each allele twice, once as the reference
has them and once as the allele has them, and counts how often each spelling appears. One
copy puts a spelling into about half the reads covering that place, two into nearly all,
none into a handful from sequencing error.

Where the two instruments agree, an allele has survived a genuinely disjoint method. Where
they disagree, the disagreement is the finding — and it turned out there was a great deal of
it.

The step also produced the one thing it could not have arranged: **a positive control.**
Nothing in the copy-number measurement was told which chromosome anything was on, or that
the proband is male. It read the X at half the autosomal dosage anyway — 0.95 against 2.00.
An instrument that finds the one copy-number change that is certainly there, without being
pointed at it, has earned the absences it reports everywhere else.

## Results

| | |
|---|---|
| alleles typed | **164,044** — 75,733 from step 2's callers, 88,754 ClinVar P/LP alleles of the 792 genes, 20,000 calibration markers |
| probe pairs, after uniqueness | **381,510** of 439,851 designed |
| pairs dropped because the **alternate** k-mer already exists in GRCh38 | **37,306** — the filter step 2 did not have |
| read windows counted | **1,876,842,047**, in 765 s on the laptop |
| read-pair double counting, measured | **1.0309** — 3.1 % of observations, not assumed away |
| fitted per-copy coverage | **17.96×** (35.93× diploid) against **35.2×** predicted from read length alone |
| variance-to-mean ratio | **2.91** — Poisson would have been three times too confident |
| calls | 20,231 het · 13,098 hom-alt · 57,648 hom-ref · **73,067 no-call** |
| **vendor-reported alleles confirmed** (target genes) | **645 / 671 = 96.1 %** |
| **vendor-unreported alleles confirmed** (target genes) | **140 / 397 = 35.3 %** |
| copy-number regions | **1,430** — 664 at exon scale, 766 genes pooled from 12,588 thin exons |
| **median copy number** | **2.00** on autosomes, **0.95** on chromosome X — a male proband's single X, found with nothing told to the measurement |
| null band, from the decoys | **[1.028, 2.823]** over 703 regions |

## Claims — all six resolved

| Id | Verdict | Conf. | Claim |
|---|---|---|---|
| H024 | **refuted** | 0.15 | *every* step-2 het call in a reachable target gene is confirmed — 453 of 518 are |
| H025 | **supported** | 0.60 | a ClinVar P/LP allele is present at het multiplicity — one genuinely is, four are an artefact |
| H026 | **refuted** | 0.30 | no target exon falls below the null band — one does, `BRD4` exon 7 at 0.85 |
| H027 | **refuted** | 0.08 | ≥ 80 % of the 1,199 vendor-unreported alleles confirmed — **27–43 %** are |
| H028 | **supported** | 0.85 | both lead alleles at one-copy multiplicity — both, posterior 1.0, unanimous |
| H029 | **refuted** | 0.20 | unreachable genes yield no confident genotype — they yield 215 |

### H027 is the result the step exists for

Step 2 found 1,199 alleles the delivered callset never reported, and six of ten target genes
reached a biallelic candidate **only** through them ([090](../step-2/methodology/090-the-alleles-the-vendor-never-reported.md)).
This step predicted in writing that ≥ 80 % would be corroborated by an independent
instrument.

| Tier | Vendor **reported** | Vendor **never reported** |
|---|---|---|
| core | 0.910 | **0.327** |
| mechanism-term | 0.954 | **0.432** |
| net | 0.972 | **0.347** |
| decoy | 0.948 | **0.319** |

The left column is what makes the right one mean something: the same instrument, in the same
run, over the same genes, confirms 91–97 % of what the vendor's pipeline *did* report. So
the instrument works, and **roughly two thirds of the 1,199 are not corroborated**. Every
step-2 biallelic count that rested on them is an upper bound, and the read route now carries
a measured per-allele error rate instead of a caveat — which is exactly what the
pre-registered refutation clause said would happen.

### What can be said about the lead pair

Phasing it is impossible ([088](../step-2/methodology/088-the-alleles-the-reads-carry.md):
10,911 bp apart against ~266 bp fragments). The strongest remaining statement is dosage, and
it holds: both alleles at **11/12** and **18/16** reference-to-alternate counts, called
heterozygous at posterior 1.0 with all three probes agreeing, by an instrument with no
aligner and no caller in it. A caller artefact does not produce two balanced single-copy
dosages. **It is not trans evidence** and the step does not offer it as any.

## Gates, and what each one did

| # | Stage | Gate | Outcome |
|---|---|---|---|
| 0 | MAPQ of off-target reads | computed before any model is fitted | **pass** — and the feared pile-up is absent ([093](methodology/093-where-the-aligner-was-unsure.md)) |
| 1 | probe design | ≥ 3 pairs per allele; alt count 0, ref count 1 | **pass**, 95,372 alleles fully probed, 15,525 with none, all listed |
| 2 | counting kernel | exact agreement with `mva.reads.scan.counts` on ≤ 20 probes | **pass** — 38 against 38, no disagreement |
| 3 | negative-binomial fit | λ consistent with measured depth | **pass** — 35.93× against 35.2× predicted from read length |
| 4 | genotype calls | posterior and probe agreement on every call; no-call is a state | **pass** |
| 5 | copy number | k-mer count and both denominators printed per region | **pass** — 1,430 regions, median 2.00 autosomal ([097](methodology/097-copy-number-without-an-aligner.md)) |
| 6 | decoy symmetry | identical rules, both rates stated | **pass** — targets and decoys within a few points in both columns |

## What went wrong, and was caught

Three defects, all found inside the run and all recorded rather than quietly fixed:

| What | How it surfaced | Consequence |
|---|---|---|
| a fractional count made every genotype class impossible at once, so `argmax` read `NaN` as **homozygous reference** | a `RuntimeWarning` nobody had to act on | 22,475 alleles; **changed no number**, because all were already below the probe floor — verified, not assumed |
| a CSV sniffer read a quoted empty field as two literal quote marks, so `caller_genotype <> ''` matched every row | the headline figure looked wrong and was not believed | core confirmation read 0.008 instead of 0.910; never reached a verdict |
| genes in the bait's ±50 kb padding were counted as *targets* | the same figure | target rate read 34 % instead of 96 % |

The first was latent rather than harmful. The other two would have put wrong numbers in the
report, and both were caught by looking at a figure and disbelieving it.

## Limitations, stated beside the results

* **The fitted error rate is too tight.** At 0.000247 the model expects 0.0089 alternate
  counts at a homozygous-reference site, so an observed 2 already forces a heterozygous call.
  Four of H025's five "present" ClinVar alleles sit at alternate fractions of 0.06–0.09 — a
  tenth of a real heterozygote — and none was called by any caller. Recorded, not repaired:
  changing the rule after seeing the data is choosing the answer.
* **Indel probes use FastGT's idea, not its numbers.** It validated substitutions only.
* **Class priors are uniform**, which is right for typing nominated alleles and wrong for a
  genome scan. Stated as a choice.
* **The two λ estimates differ by 5.6 %** (reference and alternate sides of the same
  markers). That is reference bias; it is small, reported, and did not retire the fit.
* **Unfiltered biallelic counts still favour the decoys** (core 0.237, decoy 0.258). The
  discrimination lives in the filter, never in the gene list — the same lesson as step 2.

## The tools this step needed

| Thing | What it is |
|---|---|
| `src/mva/calling/mapq.py` | per-region mapping quality, and the reachability rule read off it |
| `src/mva/kmer/probes.py` | reference/alternate pair design, alternate-side uniqueness, indel anchors |
| `src/mva/kmer/count.py` | per-k-mer multiplicity over a read batch; `hits_per_read` and the fragment collapse |
| `src/mva/kmer/genotype.py` | the negative-binomial empirical-Bayes fit, posteriors, dropout, error threshold |
| `src/mva/kmer/copynumber.py` | local-flank copy number, the resolution rule, the null band |
| `src/mva/warehouse/it2_step3_tables.py` + `mva-warehouse pg-load-it2-step3` | six tables, two lineage rows each |
| `src/mva/warehouse/analysis_it2_kmer.py` | the three derivations that answer a claim |
| `src/mva/viz/steps_it2_step3.py` + `app/src/pages/Step3.tsx` | `GET /api/steps/step-3` and the deep page |
| `tools/measure_it2_mapq.py` · `build_it2_probes.py` · `run_it2_step3_counts.py` · `check_it2_kernel.py` · `fit_it2_genotypes.py` · `measure_it2_copynumber.py` | the six stages |
| `tools/export_it2_step3_{tables,analysis}.py` · `render_it2_step3_figures.py` · `it2_step3_charts.py` | the tables, the one source of numbers, the exhibits |

Also closed here: **audit row D7** — `it2_exon_depth_by_exon` now carries the per-exon depth
grid entry 092 measured, so the dashboard can read it and step 3's copy-number denominators
share it.

## Methodology

| Entry | Question |
|---|---|
| [093](methodology/093-where-the-aligner-was-unsure.md) | Where do the off-target reads pile up, and which genes may step 3 report on at all? |
| [095](methodology/095-the-probes-and-the-counting-kernel.md) | Can an allele be spelled both ways, and does a new counting kernel count what it claims? |
| [096](methodology/096-the-alleles-at-their-multiplicity.md) | At what multiplicity do the reads carry these alleles? |
| [097](methodology/097-copy-number-without-an-aligner.md) | Is every target-gene exon at two copies? |

[094](../../step-0/methodology/094-the-register-mirror-crossed-an-iteration.md) is a
cross-step platform fix this step surfaced, filed under step 0 as `CLAUDE.md` requires.

## What this hands to step 4

* The read route's **measured** error: ~1 in 3 vendor-unreported alleles corroborated,
  ~19 in 20 vendor-reported ones. Step 6 weights it with these numbers, not a band.
* The lead pair at **one copy each** — dosage, explicitly not phase.
* `results.it2_kmer_pairs`: step 2's biallelic genes recounted on confirmed calls only.
* A reachability flag per gene, so no absence is quoted without the reason it is possible.
