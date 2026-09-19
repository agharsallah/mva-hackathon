# Step 5 — the knowledge engine, and the baselines that judge it

**Standing:** **complete, 2026-09-18.** Five claims filed before the first request, five
settled: **three supported (H036, H038, H039), two refuted (H037, H040).** Hands over to
[step 6](../step-6/README.md) and [step 7](../step-7/README.md). Iteration 2, `step-5`.

**Goal** (from `src/mva/science/steps.py`):

> Does public knowledge — published alleles, case reports, protein-language models —
> nominate or corroborate a pair for this phenotype?

Design: [`plan.md` §3 step 5](../plan.md). Two of its items are **cut**, both with their
reasons and their replacements recorded in
[102](methodology/102-the-sources-and-what-they-could-be-asked.md): **ESM1b** and the
**LLM evidence tournament**.

## What this step is for

A literature route is the easiest route in this pipeline to fool yourself with. The gene at
the top of any biomedical search is the gene most has been written about, and in a candidate
set derived from a patient's symptoms that is very often the gene somebody already solved. A
route can therefore produce a correct-looking top row and have learned nothing about this
child, and nothing in its own output distinguishes the two cases.

So the step is built around its own null from the first line: the **396 matched decoy genes**
go through the identical queries, and the knowledge ranking is measured against a **PubMed
hit-count baseline**. Both conditions had to hold before the route was allowed to contribute
a rank to step 6 — the design note is
[`notes/why-the-baseline-is-the-test.md`](notes/why-the-baseline-is-the-test.md).

## Results

| | |
|---|---|
| genes queried | **815** — 404 targets, 396 matched decoys, step 4's top 20, deduplicated |
| alleles asked of LitVar 2.0 | **1,924**, of which **1,914 askable** and **10** with no dbSNP identifier |
| askable alleles with ≥ 1 publication | **1,821** — 95.1 %, a **saturated** column that orders nothing |
| ClinVar pathogenic alleles **this child carries** | **15**, typed by k-mer in the raw reads (step 3) — including one in the step-4 leading gene, het, posterior 1.0 |
| PubTator searches | **5,705** (815 genes × 7 proband terms), 4,105 anchor rows over 758 genes |
| genes whose best paper covers ≥ 5 of 7 features | **54** — 38 targets, **16 decoys** |
| of those, genes in step 4's top 20 | **0** |
| **target vs matched decoy** | **AUC 0.634 [0.593, 0.672]** — separates |
| **vs the citation baseline** | **ρ = 0.024**, top-5 overlap **0 of 5** — reorders |
| leading missense: domain / structure / AlphaMissense | **outside** every InterPro domain · pLDDT **91.06** · **agrees** |

## Claims — all five resolved

| Id | Verdict | Conf. | Claim |
|---|---|---|---|
| H036 | **supported** | 0.80 | a published allele of a top-20 gene is present in this child — the leader's truncating allele is ClinVar pathogenic with 4 papers, and the k-mer route types it at het |
| H037 | **refuted** | 0.15 | a ≥ 5-feature paper names a top-20 gene — none does; the threshold selects surveys |
| H038 | **supported** | 0.78 | the knowledge score separates targets from matched decoys — AUC 0.634, interval excludes 0.5 |
| H039 | **supported** | 0.85 | the ranking reorders the citation baseline — ρ = 0.024, top-5 overlap 0 |
| H040 | **refuted** | 0.20 | the leading missense is in a domain, confidently modelled, and AlphaMissense agrees — it is the last two, not the first |

### The refutation that is the step's best finding

**H037 — no five-feature paper names a leading gene, and the reason is the threshold.**

Look at what a five-or-more-feature paper turned out to be. **PMID 37217505**, a broad
clinical-genomics survey, supplies the six-feature anchor for **68 of the 815 genes at
once** — decoys included. Two more high-scoring rows are **conference proceedings**. The
matched-feature count as pre-registered measures *breadth of coverage*, and the papers that
cover the most ground are surveys, guidelines and meeting abstracts.

Meanwhile the script — without being told the gene — surfaced this for the step-4 leader:

> **PMID 35804254** · *Pathogenic correlation between mosaic variegated aneuploidy 1 (MVA1)
> and a novel BUB1B variant: a reappraisal of a severe syndrome* · Neurol Sci 2022 ·
> matched **Rhabdomyosarcoma; Premature birth; Small for gestational age** — **3 of 7**.

The child's disease, the child's gene, a novel variant, a severe presentation. The
pre-registered threshold ranks it **below a survey naming 68 genes**. The instrument works;
the threshold was wrong, and it was not moved after the run
([104](methodology/104-the-papers-the-script-found.md)).

### The two the route passed, and what they do and do not license

**H038.** AUC **0.634 [0.593, 0.672]**. The separation is traceable: the published-allele
column is **250 targets against 254 decoys** — flat — so all of it comes from the
matched-feature count and none from the saturated literature column. It is a *modest*
separation and is quoted as one: step 4's likelihood ratio reached **0.706** on the same two
gene sets.

**H039.** **ρ = 0.024**, top-5 overlap **0 of 5**, with only two genes tied at the boundary
that decides entry, so the zero is not an artefact of alphabetical tie-breaking.

| | top 5 |
|---|---|
| by knowledge score | `DDX11`, `TTLL5`, `F13B`, `VIPAS39`, `ADAT3` |
| by PubMed hit count | `REST`, `AR`, `NODAL`, `BAX`, `FAS` |

### The result neither claim asked for, and the one step 6 must act on

**The knowledge ordering does not point at the causal gene, and its own leaders are decoys.**

| step-4 rank | gene | knowledge rank (of 815) | best paper |
|---|---|---|---|
| 1 | `BUB1B` | **293** | 3 features |
| 2 | `ADAMTS1` | 470 | 2 |
| 3 | `HLA-DRB1` | 445 | 2 |
| 6 | `RAI1` | 201 | 3 |

And the knowledge route's own **top two genes are decoys**; **10 of its top 25** are. So it
is a ranking route by its own pre-registered tests — it separates from its controls and it
is not citation volume — **and** its ranking is wrong at the top and uninformative about the
confirmed lead. Both are true at once, and step 6 carries both: AUC 0.634 is a weight, not a
licence to outvote a route that measured 0.706 and put the causal gene first.

## What went wrong, and was caught

| What | How it surfaced | Consequence |
|---|---|---|
| the first full LitVar pass reported **0 published alleles of 1,914** | checking the adapter against a variant whose answer was already known | LitVar's id ends `##`; `#` starts a url fragment, so the client sent a truncated id and LitVar answered *Variant not found* every time. Percent-encoded, `rs1801376` goes 0 → **66** papers. It did not raise, did not log, and came with a plausible story attached |
| the catalogue counted ClinVar k-mer rows in the *askable* denominator | reading the coverage figure | those rows carry no dbSNP id by construction, so every carried pathogenic allele inflated "never askable". Split by `origin`; the carried count now rides in the bar label, not in a bar |
| the domain chart repeated each gene's map once per allele, and every tick rendered plotly-blue | rendering the exhibit and looking at it | one row per gene; an `-open` symbol takes its stroke from `marker.color`, not `marker.line.color` |
| the citation scatter drew only the 25 rows the API page serves | reading it — a flat band that proved nothing | ρ is a statement about all 815 genes, so the figure reads a full-table block and the page keeps its 25 |
| the top-5 overlap was being quoted without the tie width behind it | re-reading the module | `tied_at` reports how many genes share the boundary score; the page says the overlap is partly alphabetical when the tie is wider than the slots it fills |

## Limitations, stated beside the results

* **A publication is not evidence about this child.** 95.1 % of askable alleles carry a
  paper, so that column is saturated and separates almost nothing. The one column on this
  page that *is* about the patient comes from a different instrument: step 3's k-mer
  genotypes of the public ClinVar catalogue in the raw reads.
* **Co-occurrence is not a case report.** `GENE AND Short stature` returns papers mentioning
  both; nothing in the query says the paper reports that feature in a patient carrying a
  variant in that gene. That is exactly how H037 failed.
* **The matched-feature count is over the first page of each search**, not every page. The
  per-term totals are complete across all pages, so the two numbers are not symmetric. The
  cut applies identically to the decoys.
* **A term label is a string.** A paper writing "growth retardation" rather than "short
  stature" is invisible here.
* **Length-matched decoys are load-bearing.** A longer gene carries more alleles and
  attracts more papers; an unmatched control set would have measured gene size.
* **InterPro's `domain` type is a pre-registered choice.** Families and superfamilies span
  most of a protein and would make the domain test pass for almost any residue. They are
  stored and reported in their own column, and for the leading allele the two readings
  disagree.
* **ESM1b was cut**, so H040 tests a second *kind* of evidence rather than a second model.
  Recorded as a limitation, not as a substitution of equal weight.
* **A knowledge score orders genes. It is not a probability that a gene is causal**, and
  every place that quotes one says so.

## The tools this step needed

| Thing | What it is |
|---|---|
| `src/mva/knowledge/sources.py` | LitVar 2.0 and PubTator 3.0 over the shared `Fetcher`, with each API's refusal semantics pinned by a test |
| `src/mva/knowledge/catalogue.py` | allele-first publication counts, with `NOT_ASKED` kept distinct from zero |
| `src/mva/knowledge/anchors.py` | (gene × term) searches folded into per-paper matched-feature counts |
| `src/mva/knowledge/protein.py` | UniProt → InterPro → AlphaFold, returning fractions of protein length and never a residue |
| `src/mva/knowledge/baselines.py` | Spearman ρ, top-k overlap, the tie width behind it, and the decoy AUC delegated to `mva.pipeline.nulls` |
| `src/mva/warehouse/it2_step5_tables.py` + `analysis_it2_knowledge.py` | six tables with three lineage rows each, and six derivations — one per claim |
| `src/mva/viz/steps_it2_step5.py` + `app/src/pages/Step5.tsx` | `GET /api/steps/step-5` and the deep page |
| `tools/it2_step5_common.py` | the gene set, the allele list and one TSV writer, shared by all four stages |
| `tools/fetch_it2_catalogue.py` · `build_it2_anchors.py` · `score_it2_protein.py` · `run_it2_knowledge_baselines.py` | the four stages |
| `tools/export_it2_step5_analysis.py` · `it2_step5_charts.py` · `render_it2_step5_figures.py` | the one source of numbers and the six exhibits |

`mva.knowledge` is **case-agnostic**: no gene, no disease, no coordinate anywhere in it. Give
it a gene list and a term list and it answers for another case — which is the second
deliverable this project is built for. Fetching, caching, the courtesy interval and the
provenance digest are not in it: they belong to the `Fetcher` the repository already shares,
which is why the package takes one import layer above `mva.drugs`.

## Methodology

| Entry | Question |
|---|---|
| [102](methodology/102-the-sources-and-what-they-could-be-asked.md) | Which public sources answer this, what were they asked, and what could not be asked at all? |
| [103](methodology/103-the-alleles-somebody-already-published.md) | Of the alleles this child carries, which has anyone already published about? |
| [104](methodology/104-the-papers-the-script-found.md) | Which published papers discuss a candidate gene alongside this child's own features? |
| [105](methodology/105-does-the-literature-beat-a-hit-count.md) | Does the route order anything a publication count does not, and can it tell a candidate from a control? |
| [106](methodology/106-where-the-missense-sits-in-the-protein.md) | Where does the leading missense allele sit in its protein, and does the structure agree? |

Design note: [`notes/why-the-baseline-is-the-test.md`](notes/why-the-baseline-is-the-test.md).

## Exhibits

`/steps/step-5` on the dashboard, and `figures/track1/iteration2/step-5/` (each as `.png`, plus an
`index.html` with captions and legends), rendered by `tools/render_it2_step5_figures.py` from
`build/it2/step-5/analysis.json`: `sources`, `catalogue`, `anchors`, `citations`, `separation`, `domains`.

## What this hands to steps 6 and 7

* **A ranking route with a measured weight** — AUC 0.634 [0.593, 0.672] — that passed both
  pre-registered conditions and whose ranking is nonetheless wrong at the top.
* **A published-allele corroboration for the leading gene**, from two instruments that share
  no code: the callset's ClinVar annotation and a k-mer genotype of the public ClinVar
  catalogue in the raw reads.
* **A citable mechanism paper for the leading gene**, found by script rather than by hand:
  PMID 35804254 — which is Track 2's mechanism evidence, not Track 1's.
* **A negative result worth stating in the report**: the matched-feature threshold that any
  literature route would reach for selects survey papers, and a specificity term is what a
  future iteration needs.
