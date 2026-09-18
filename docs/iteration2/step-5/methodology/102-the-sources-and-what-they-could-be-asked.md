# 102 — Which public sources answer this step, what they were asked, and what could not be asked at all

**Written:** 2026-09-18. **Step:** `step-5` (iteration 2).
**Hypotheses:** none tested here. This is an *instrument* entry under the carve-out in
[`../../../method.md`](../../../method.md): it installs and measures the four public
sources the step reads, and the machinery it builds serves **H036–H040**, all five filed
**before** the first request in this entry was sent. The claims are settled in
[103](103-the-alleles-somebody-already-published.md),
[104](104-the-papers-the-script-found.md),
[105](105-does-the-literature-beat-a-hit-count.md) and
[106](106-where-the-missense-sits-in-the-protein.md).
Precedent for an instrument entry with no verdict of its own:
[093](../../step-3/methodology/093-where-the-aligner-was-unsure.md),
[095](../../step-3/methodology/095-the-probes-and-the-counting-kernel.md),
[098](../../step-4/methodology/098-the-lanes-and-what-they-were-calibrated-against.md).

**Supersedes nothing.** It records two cuts against
[`plan.md` §3 step 5](../../plan.md) and one measured defect that would have produced a
wrong headline.

## Question

Which public knowledge sources can be asked about this case at all, what exactly is each
one asked, and — the question that decides whether any later number means anything — what
is each one *unable* to be asked?

## Inputs

| Source | What was read | Version / receipt |
|---|---|---|
| `results.it2_lr_pairs` (step 4) | every allele the genome-wide ranking scored, as `(gene, dbSNP id, consequence class)` | 51,920 hypotheses over 11,465 genes, loaded 2026-09-18 |
| `results.it2_targets`, `results.it2_decoys` (step 1) | the 404 symptom-nominated genes and the 396 length- and exon-matched controls | seeded draw, step 1 |
| `results.it2_kmer_genotypes` (step 3) | public ClinVar pathogenic alleles typed in the raw reads, `origin LIKE 'clinvar%'` | 88,049 typed, 15 present at het or hom-alt |
| `warehouse.it2_insilico_annotations` (step 4) | ClinVar significance and AlphaMissense class per allele, joined by dbSNP id | 38,087 alleles, 9,506 with a ClinVar significance |
| clinical document | the **seven proband HPO term labels**, from `mva.phenotype.terms.PROBAND_ONLY` — never retyped | `ressources/hackathon-rules/Challenge_Clinical_Phenotype_1.md` |
| LitVar 2.0 | publications per dbSNP variant | `https://www.ncbi.nlm.nih.gov/research/litvar2-api`, read 2026-09-18 |
| PubTator 3.0 | papers per (gene, clinical feature) search | `https://www.ncbi.nlm.nih.gov/research/pubtator3-api`, read 2026-09-18 |
| UniProt / InterPro / AlphaFold DB | reviewed human accession, domain ranges, per-residue pLDDT | REST, read 2026-09-18 |
| PubMed E-utilities | the citation-volume baseline, through the existing `mva.drugs.sources.pubmed` client | `esearch` with `retmax=0` |

**No iteration-1 candidate table is an input**, and no iteration-1 decode table. Every
input above is either an iteration-2 `results.it2_*` table, a platform annotation table, the
clinical document, or a public API. `tools/check_blind.py` reads the table above and runs
inside `tools/check-python.sh`; it is what turns that sentence into a check.

## Commands

```bash
uv run mva-science hypothesis-add --step step-5 …      # H036-H040, before anything below
uv run python tools/fetch_it2_catalogue.py             # LitVar, per allele
uv run python tools/build_it2_anchors.py --interval 0.7  # PubTator, per (gene, term)
uv run python tools/score_it2_protein.py               # UniProt -> InterPro -> AlphaFold
uv run python tools/run_it2_knowledge_baselines.py     # PubMed counts + the two nulls
```

## Observed — the gene set, and why it is three sets unioned

**815 genes**: the 404 targets, the 396 matched decoys and the top 20 of step 4's ranking,
deduplicated. **1,924 distinct alleles** across them — one row per
`(gene, dbSNP id, consequence class)` the ranking scored.

The decoys are in the gene set from the first request rather than added afterwards. They
are matched to the targets on **coding length and exon count**, which matters more in this
step than anywhere else in the iteration: a longer gene carries more alleles *and* attracts
more papers, so an unmatched control set would measure gene size and call it knowledge.

## Observed — a defect that would have produced a wrong headline

The first full LitVar pass reported **0 published alleles out of 1,914 askable**. That is a
publishable-looking sentence and it was entirely false.

LitVar's identifier for a variant is `litvar@rs1801376##`. The trailing `##` is part of the
identifier — but `#` in a URL begins a *fragment*, so an HTTP client sends everything
before it and drops the rest. LitVar then answered the truncated identifier with
`HTTP 400 {"detail":"Variant not found"}`, which the adapter correctly reads as "nobody has
published about this variant". Every allele. Measured directly:

| identifier in the path | `rs1801376` | `rs80359507` | `rs759242053` |
|---|---|---|---|
| unencoded | 0 publications | 0 | 0 |
| percent-encoded (`litvar%40rs1801376%23%23`) | **66** | **42** | **4** |

Fixed in `mva.knowledge.sources.litvar_path`, pinned by a test that asserts no `#` survives
into the path. The stale cache was deleted and the pass re-run.

**The shape of the failure is worth more than the fix.** It did not raise, did not log, and
did not look wrong: it produced a complete table of zeros with a plausible story attached
("this child's alleles are private, so nobody has written about them"). The only thing that
caught it was checking the adapter against a variant whose answer was already known.

## Observed — what each source refuses, and in which words

| Source | Refusal | Read as |
|---|---|---|
| LitVar 2.0 | `HTTP 400 {"detail":"Variant not found"}` — **not** 404, and not an empty list | no publication mentions this variant. Any *other* 400 still raises |
| PubTator 3.0 | `HTTP 429` at one request per 0.34 s while another stage read LitVar on the same host | the courtesy interval is a parameter, not a constant; the pass runs at 0.7 s |
| UniProt | no reviewed human entry for a gene symbol | `("", 0)` and the gene is recorded as unresolvable, never fuzzy-matched to a neighbour |
| AlphaFold DB | no model for an accession | an empty pLDDT map, which the verdict reads as "no structural opinion" |
| Ensembl VEP | no canonical protein consequence for an allele | residue 0 and a stated reason on the row |

## Observed — the two cuts, both recorded rather than made silently

**ESM1b is cut.** [`plan.md` §3 step 5](../../plan.md) named
`facebook/esm1b_t33_650M_UR50S` for a zero-shot second opinion on missense alleles. It needs
`torch` — which is not a dependency of this repository — and a ~2.5 GB checkpoint, to score
**45 residues**. AlphaMissense is already computed for every allele in
`warehouse.it2_insilico_annotations` and is the calibrated missense score the step-4 lane
actually used. The second opinion in this step is therefore **structural context** —
InterPro domain membership and AlphaFold pLDDT, over two REST APIs and no new dependency —
and plan claim H025 is restated as **H040** accordingly.

**The LLM evidence tournament is cut.** It is cut (1) in the plan's own cut order
([`plan.md` §4](../../plan.md), reaffirmed in §11.9). What the plan asked the tournament to
be measured *against* is kept and becomes the step's actual test: the PubMed-hit-count
baseline and the step-4-posterior comparison (**H039**). No Anthropic dependency enters the
repository. Cohen's κ is retired with the bracket it was to measure.

## The instrument, and what makes it reusable

`src/mva/knowledge/` — five modules, no gene, no disease and no coordinate in any of them:

| Module | What it answers |
|---|---|
| `sources.py` | the three adapters, each taking a `mva.drugs.cache.Fetcher` as its first argument, exactly like every adapter under `mva.drugs.sources` |
| `catalogue.py` | published-allele counts per **sample** allele, with `NOT_ASKED` kept distinct from zero |
| `anchors.py` | (gene × term) searches folded into per-paper matched-term counts |
| `protein.py` | accession → domain ranges → per-residue confidence, returning fractions of protein length and never a residue |
| `baselines.py` | Spearman ρ, top-k overlap, and the decoy AUC delegated to `mva.pipeline.nulls` |

Caching, the courtesy interval, the retry ladder and the provenance digest are **not** in
this package: they belong to the `Fetcher` the whole repository already shares, which is why
`mva.knowledge` takes one import layer between `mva.warehouse` and `mva.drugs`.

## Limitations, stated beside the result

* **LitVar is keyed on dbSNP.** An allele with no identifier cannot be asked about, and the
  catalogue counts it as `unqueryable` rather than as unpublished. 10 of 1,924 fall here —
  a small number, and the point stands regardless of its size: the two absences are
  different findings and are never merged into one coverage percentage.
* **PubTator's matched-term count is a co-occurrence, not a reading.** A paper returned by
  the query `GENE AND Short stature` mentions both; it does not necessarily *report* that
  feature in a patient with a variant in that gene. The decoy column is what keeps the
  number honest, not the number itself.
* **InterPro's `domain` type is a pre-registered choice.** Families and superfamilies span
  most of a protein, so counting them would make the domain test pass for almost any
  residue. They are fetched and stored anyway, and reported in their own column, because
  the two readings can disagree.
* **Nothing here is a measurement about the child.** The one column in this step that is
  comes from step 3: a k-mer genotype of the public ClinVar pathogenic catalogue in the raw
  reads.

## Conclusion

Four sources installed, each with its refusal semantics measured rather than assumed; one
silent-zero defect found and fixed before it reached a claim; two plan items cut with their
reasons and their replacements recorded. The gene set, the allele set and the term set are
fixed, and the four claims can now be tested.

Next: [103](103-the-alleles-somebody-already-published.md).
