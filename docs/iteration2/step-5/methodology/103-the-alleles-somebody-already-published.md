# 103 — Of the alleles this child carries, which has anyone already published about?

**Written:** 2026-09-18. **Step:** `step-5` (iteration 2). **Hypotheses:** H036.
Instruments and their refusal semantics:
[102](102-the-sources-and-what-they-could-be-asked.md).

## Hypothesis and prediction

**H036** — *At least one published allele — reported in ClinVar as pathogenic or likely
pathogenic, or carrying at least one publication in LitVar — is present in this child at
heterozygous or homozygous-alternate multiplicity in a gene that step 4 ranks in its top 20.*

**Prediction.** The catalogue join against `results.it2_kmer_genotypes` (origin `clinvar`)
and against the LitVar publication counts of the child's own alleles returns at least one
row whose gene is in the step-4 top 20 and whose k-mer call is `het` or `hom-alt`.

## What would refute it

No published allele of any step-4 top-20 gene is present in the child: every such allele is
`hom-ref` or `no-call`. The leading pair would then be novel on both sides, and the
knowledge route would contribute no allele-level corroboration.

## Inputs

| Source | What was read |
|---|---|
| `results.it2_lr_pairs` | 1,924 distinct `(gene, dbSNP id, consequence class)` alleles across the 815-gene set |
| `results.it2_kmer_genotypes` | `origin LIKE 'clinvar%'`, 88,049 public ClinVar pathogenic alleles typed by k-mer in the raw reads (step 3) |
| `warehouse.it2_insilico_annotations` | ClinVar significance per allele, joined by dbSNP identifier |
| LitVar 2.0 | publications per variant, one request per distinct identifier |
| clinical document | the seven proband terms, only as the source of the target set the gene list came from |

No iteration-1 candidate table. Blind gate: `tools/check_blind.py`.

## Commands

```bash
uv run python tools/fetch_it2_catalogue.py
uv run mva-warehouse pg-load-it2-step5
uv run mva-warehouse pg-derive --only it2_catalogue_overlap
```

## Observed — the two instruments, kept apart

| | count |
|---|---|
| alleles the ranking scored in the gene set | **1,924** |
| of those, **askable** (carry a dbSNP identifier) | **1,914** |
| of those, **never askable** (no identifier — LitVar could not have an opinion) | **10** |
| askable alleles with **at least one publication** | **1,821** (95.1 %) |
| public **ClinVar pathogenic alleles present in this child** at het or hom-alt | **15**, across 14 genes |
| genes in the catalogue overlap table | **540** |

## Observed — H036, and the gene it lands on

The leading gene of step 4's genome-wide ranking carries **both**:

* its **truncating** allele is `rs759242053`, recorded in ClinVar as
  `pathogenic;likely_pathogenic`, and LitVar holds **4 publications** for that exact variant;
* the k-mer route independently types a ClinVar pathogenic allele of the same gene at
  **heterozygous** multiplicity, posterior **1.0**, with **3 of 3 probes agreeing** — no
  aligner and no caller anywhere in that chain.

Its **missense** partner is the opposite case: **no dbSNP identifier at all**, so it is one
of the 10 unqueryable alleles. The leading pair is therefore *one published allele and one
that no literature index has ever seen* — which is exactly the shape a recessive
null + hypomorph model predicts, and the shape a "how famous is this gene" route would have
had nothing to say about.

## Observed — the finding the claim did not ask for

**95.1 % of askable alleles carry a publication.** That is near-saturation: LitVar holds a
citation for almost any variant that has a dbSNP identifier at all, because an identifier is
largely assigned to variants that have been *seen*, and being seen and being written about
are close to the same event at population scale.

The consequence is that *"an allele of this gene has been published about"* is **almost free
information** and orders essentially nothing. It is reported as a count and is deliberately
only a tie-break in the knowledge score ([105](105-does-the-literature-beat-a-hit-count.md)),
never the primary term. A step that had built its ranking on this column would have produced
an ordering of *gene length* — more alleles, more publications — and the matched decoys are
what would have caught it.

## Evidence recorded

| Direction | Strength | Claim | Source |
|---|---|---|---|
| supports | 0.75 | the step-4 leader carries a ClinVar pathogenic allele with 4 publications, and the k-mer route types a ClinVar pathogenic allele in it at het multiplicity, posterior 1.0, 3/3 probes | methodology/103 |
| neutral | 0.50 | 1,821 of 1,914 askable alleles carry ≥ 1 publication, so the column is saturated and orders almost nothing | methodology/103 |
| neutral | 0.40 | the leader's missense partner has no dbSNP identifier and is unqueryable, so the pair is half-published by construction | methodology/103 |

## Limitations, stated beside the result

* **A publication is not evidence about this child.** The 1,821 number says the literature
  has seen these variants in *somebody*; only the 15 ClinVar-carried rows, typed by k-mer in
  this child's own reads, say anything about this patient. The two live in different columns
  and are never summed.
* **"ClinVar pathogenic" is the catalogue's classification, not ours**, and ClinVar
  submissions vary in evidence quality. The claim was filed against presence, not against
  causality.
* **10 unqueryable alleles is a small denominator correction here** — and the rule stands
  regardless of its size, because merging it into a percentage is what would make a gap in a
  public index look like a finding.
* **The catalogue does not know which allele belongs to the leading pair.** It reports per
  gene; the pairing is step 4's.

## Verdict

**H036 — supported, confidence 0.80.** A published, ClinVar-pathogenic allele of the
top-ranked gene is present in this child, confirmed by two instruments that share no code:
the vendor callset's annotation, and a k-mer genotype of the public ClinVar catalogue in the
raw reads. The reasoning for stopping at 0.80 rather than higher is that the claim is about
*presence of a known allele*, which a recessive diagnosis needs but is far from sufficient
for — and 95.1 % saturation means the literature half of the claim was nearly guaranteed.

Next: [104](104-the-papers-the-script-found.md).
