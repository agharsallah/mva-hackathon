# Third disease: Fanconi anemia / FANCA — bounded public-data transfer

**Status: real cached-public computation; partial stages, not end-to-end or live API transfer.**
Executed 2026-10-22. No fixtures, patient records, variants, uploads, GPU, or Modal.
No therapeutic recommendation is supported.

## Reproduce

From repository root, with existing project dependencies and public caches:

```sh
uv run python tools/fanca_transfer.py
uv run ruff check tools/fanca_transfer.py tests/test_fanca_transfer.py
uv run mypy tools/fanca_transfer.py --follow-imports=silent
uv run pytest tests/test_fanca_transfer.py
```

Required cache: the eight files and `manifest.json` under
`build/it4/track2-e2/raw/`, plus `build/primekg/kg.parquet`.
The former cache records source URLs, licenses, original retrieval timestamps,
release identifiers and hashes. This runner performs **zero live requests**.
Missing inputs fail visibly rather than substituting fixtures.
`summary.json` records measured timings, input/output SHA256 hashes and comparisons.
The nested `work/twin/twin.json` preserves full top-genotype details.

## Public case and rationale

`case.json` fixes FANCA/Fanca and the FA-core-complex / DNA interstrand-cross-link
repair mechanism, distinct from MVA's BUB1B spindle checkpoint and Bloom's BLM
recombination/helicase mechanism. No individual FANCA genotype is asserted.

NIH MedlinePlus, [Fanconi anemia](https://medlineplus.gov/genetics/condition/fanconi-anemia/),
retrieved and read 2026-10-22, identifies FANCA/FANCC/FANCG as FA-core-complex
components and describes impaired ICL repair, marrow failure and malignancy risk.
The NIH page was used only to choose and describe the case, not as intervention evidence.
GeneReviews retrieval returned a browser challenge; it was not treated as evidence.

The **34 unique HPO terms** are extracted, not invented, from the cached
`phenotype.hpoa` release 2026-09-02, OMIM:227650, aspect P, excluding NOT.
`hpo_case.tsv` preserves each term's label, source reference and evidence code
(including IEA annotations). These are **disease-level**, not patient or
FANCA-subtype-specific, annotations. The PrimeKG disease-wide Fanconi anemia node
resolves to MONDO:0019391, independently of the grouped complementation-group node.

## Measured computation

First measured pass: **27.78 s** overall, **19.73 s** phenotype stage and **5.81 s**
graph loading plus three walks. Reruns replace `summary.json` with their own timings.

The existing `transfer_it4.do_twin` calls the unchanged phenotype scoring machinery.
Only its build-directory constant is redirected to this case. Its legacy
MVA-specific provenance source labels are corrected explicitly in the new
case-specific runner; numerical outputs are not relabelled or altered.

| Phenotype query/gene | Symmetric best rank / 76,699 | Percentile | Phenodigm rank | Percentile |
|---|---:|---:|---:|---:|
| MVA with-parental / Bub1b, historical | 1,045 | 1.36247% | 768 | 1.00132% |
| Bloom / Blm, historical | 881 | 1.14865% | 828 | 1.07954% |
| Fanconi / Fanca, this run | 37 | 0.04824% | 102 | 0.13299% |

Fanca: 11 annotated genotypes; symmetric/Phenodigm best MGI:3609225.
Empirical IC-matched-null p = **0.019802 / 0.029703** from **100 draws**, seed 0.
Forward metric: rank 2,015 (2.62715%), p = 0.069307.
No calibration panel rerun; historical runs used 1,000 null draws and different
queries. This is portability evidence, **not a controlled accuracy improvement**.
Larger disease queries, model annotation density, and multi-allele/background
genotypes can influence rank.

The unchanged PrimeKG DWPC walk (default metapaths, damping 1) was run identically
for all three diseases on the same cached graph:

| Disease | Paths | Reached drugs | Top-50 raw graph Jaccard vs Fanconi |
|---|---:|---:|---:|
| Fanconi | 8,495 | 2,042 | 1 |
| MVA | 4,265 | 745 | 0.098901 |
| Bloom | 4,521 | 1,037 | 0.041667 |

The three `*_graph_ranking.tsv` files include every reached drug, raw score and
best explanatory path. **They include experimental compounds and are unlabelled
raw graph rankings, not approved-drug generators.** The Fanconi node's gene set
is disease-wide, so low overlap is not proof of FANCA-specific drug efficacy.
These Jaccards must not be compared directly to historical four-generator union
overlap or claimed as completion of Bloom's prior end-to-end protocol.

## Explicit remaining boundary

Completed: sourced case card, real MGI scoring/null/leave-one-term-out/pathway
analysis, and raw PrimeKG walks with an identically computed comparison.

Not executed: approved-drug labelling, intervention-table curation, PRISM sweep,
LINCS reversal, generator convergence/null, K1/K2/K3 safety or clinical/PGx
checks. No infrastructure failure is claimed for stages deliberately omitted
to keep this run bounded. No suitable FANCA-specific therapeutic rescue evidence
was established in this run; phenotype similarity and graph reachability cannot
fill that gap. This does **not** increase the count of end-to-end cases.
