# 084 — Which genes do the child's symptoms alone nominate?

**Written:** 2026-09-10. **Run:** 2026-09-10/11. **Step:** `step-1` (iteration 2).
**Hypotheses tested:** H012 (**refuted**), H013 (**supported**), H014 (**refuted**),
H015 (**refuted**) — all four filed before the run.
**Verified:** against HPO release `hp/releases/2026-06-23`.

> **Register ids, stated once.** The plan ([`plan.md`](../../plan.md) §3 step 1) labels
> these claims H012, H013, H030 and H035. The register allocates ids in filing order, so
> the plan's H030 and H035 are **H014** and **H015** here. The register is authoritative;
> this table is the mapping.
>
> | Plan label | Register id | Claim |
> |---|---|---|
> | H012 | H012 | recall@300 ≥ 0.90 |
> | H013 | H013 | the target set holds a recessive chromosome-instability gene |
> | H030 | H014 | the two rankers agree on ≥ 50 % of the top 300 |
> | H035 | H015 | fewer than 20 % of protein-coding genes are uncurated |

## Inputs

| Source | What was read | Version / receipt |
|---|---|---|
| clinical | the proband's HPO terms, both sets: `proband-only` (7 terms) and `with-parental` (8) | `ressources/hackathon-rules/Challenge_Clinical_Phenotype_1.md`, owned by `src/mva/phenotype/terms.py` |
| public | `hp.obo` — the ontology graph | `hp/releases/2026-06-23`, sha256 `a5092cbd…` |
| public | `genes_to_phenotype.txt` — the curation corpus that is ranked | same release, sha256 `26cb7ee0…` |
| public | `ressources/reference/coding_regions.tsv` — gene shape for decoy matching, and the protein-coding denominator | Ensembl 116, built by `tools/build_coding_regions.py` |
| public | Phen2Gene and Monarch semsim REST, queried 2026-09-10 | `mva.phenotype.remote` |

**No genomic data of this child was read.** Step 1 chooses the target set with the DNA
never opened; the only genomic file touched is the public reference gene model. No
iteration-1 table was read — `mva-science check --blind iteration2` is the gate.

**Why the pinned release and not the newest.** HPO has since published 2026-09-01. The
committed reference tables and every iteration-1 result were built on 2026-06-23, and the
scratch files still match that release byte for byte (sha256 above). Ranking on a newer
release would make this run incomparable with the tables it sits beside for no gain step 1
needs. Upgrading is a separate, recorded decision.

## Hypothesis and prediction — written before the run

- **H012** recall@300 of the phenotype-only ranker on held-out recessive diseases is ≥ 0.90.
- **H013** the target set contains at least one gene whose curated disease is a recessive
  chromosome-instability syndrome.
- **H014** the two independent rankers agree on ≥ 50 % of their top 300.
- **H015** fewer than 20 % of protein-coding genes have no HPO curation.

## What would refute them

H012: recall@300 < 0.90 — N is then raised until it is met, *before* step 2's bait is
built, and the raise recorded. H013: no such gene. H014: overlap < 50 %. H015: ≥ 20 %
uncurated, in which case the `uncurated` tier is the larger blind spot it then is.

## Commands

```
uv run python tools/build_it2_targets.py            # target set + decoys + provenance
uv run mva-phenotype benchmark --sample 200 --seed 20260910
uv run mva-phenotype agreement --limit 300
uv run mva-warehouse pg-load-it2                    # -> results.it2_targets, it2_decoys
```

## Observed

### The target set

| Tier | Rows | Meaning |
|---|---|---|
| `core` | 62 | top 50 by symptom score, plus mechanism-term genes that also scored inside it |
| `net` | 272 | ranks 51–300 |
| `mechanism-term` | 70 | annotated at or under HP:0002916 / HP:0003220, admitted regardless of rank |
| **total** | **404** | 353 earned their place by score; 51 entered by the mechanism rule alone |

Both term sets were ranked and **unioned on best rank**: 5,259 genes scored for
`proband-only`, 5,261 for `with-parental`, out of 5,267 considered. 396 shape-matched
decoys were drawn from seed `20260910`, excluding the 2,502 genes annotated with any of
the case's terms. Loaded to `results.it2_targets` / `results.it2_decoys`, each with
lineage rows naming **both** the public release and the clinical document.

### H012 — held-out recall, 200 recessive diseases

| N | recall | 95 % bootstrap interval |
|---|---|---|
| 1 | 0.000 | [0.000, 0.000] |
| 10 | 0.030 | [0.010, 0.055] |
| 50 | 0.125 | [0.080, 0.175] |
| **300** | **0.360** | **[0.295, 0.420]** |
| 1000 | 0.565 | [0.495, 0.630] |

Median rank 326. **49 of 200 genes were unrankable**: the withheld disease is the only one
curating them, so removing it removes the gene from the corpus entirely.

### H013 — chromosome-instability genes present

33 target genes carry a curated **autosomal-recessive** disease annotated at or under the
two mechanism roots (BLM, BRCA2, BRIP1, CENATAC, … — listed by query, not by hand).

### H014 — two-ranker overlap

Phen2Gene returned 18,882 genes and shares **97 of the top 300 (32.3 %)**. Monarch semsim
returns only 50 rows; 13 of those 50 are shared (26.0 %), reported over the window it
actually filled rather than over 300, because dividing truncation by a window a service
never filled prints it as disagreement.

### H015 — the uncurated blind spot

**14,523 of 19,723 protein-coding genes (73.6 %) have no HPO curation at all.**

## Verdict

| Claim | Verdict | Confidence |
|---|---|---|
| H012 recall@300 ≥ 0.90 | **refuted** | 0.04 |
| H013 a recessive chromosome-instability gene is present | **supported** | 0.83 |
| H014 two rankers agree on ≥ 50 % | **refuted** | 0.10 |
| H015 < 20 % uncurated | **refuted** | 0.02 |

Confidence is the register's transparent triage heuristic, not a calibrated posterior.

**H013 is weakened on purpose.** The mechanism-term rule guarantees such genes a seat, so
the claim is close to true by construction. It is reported as a sanity check on the rule,
not as a discovery.

**H012's refutation changes the plan, and the plan's own remedy does not apply.** The
pre-registered fix was "raise N until recall reaches 0.90, before step 2's bait is built".
It cannot be met: recall@1000 is 0.565, and a quarter of held-out genes are unrankable at
*any* N because curation describes them through one disease only. No cutoff of a
phenotype-only ranker reaches 0.90 on this corpus. Raising N to 1000 would triple the bait
for +0.21 recall and still miss two genes in five. **Decision, recorded here:** N stays at
300, the target set is described as an *enrichment*, never as coverage, and the safety net
is step 4's genome-wide ranking, which reads every gene in the VCF and applies no target
set at all. Step 2 must not be read as exhaustive over the genes that matter.

**What the number is, and is not.** Ground truth and scoring database share curators, so
this is an internal consistency check, not an external validation, and it carries no
genomic background — every gene here is a candidate, where a real case has an exome of
them. The comparable external figure is step 4's spike-in recall. It is also *stricter*
than Exomiser's published top-1 figures in one respect and weaker in another: the held-out
rule removes the disease's own curation of its gene, which those benchmarks do not do, and
there is no variant evidence to break ties.

**Assumptions and limitations.** (1) The benchmark ran on 200 of 3,240 eligible diseases,
sampled from the seed; the intervals are bootstrap intervals over those 200. (2) The
degradation parameters (1–2 terms blurred to a parent, 1–2 noise terms) follow Zemojtel
2014 but were not tuned to this corpus. (3) `coding_regions.tsv` is the protein-coding
denominator; a different gene model would move the 73.6 % by a few points, not by a
factor. (4) Phen2Gene was queried live and its knowledge-base version is whatever the
service served on 2026-09-10 — recorded as the retrieval date, which is weaker than a
pinned local install.

**Incidental observation, disclosed.** The H013 query returned its 33 genes
alphabetically, and the iteration-1 candidate gene is among them. It was not used to
select, filter or order anything, and no step-1 output depends on it. The comparison that
step 6 exists to make has not been performed.

## What this hands to step 2

`results.it2_targets` (404 rows, tiered) and `results.it2_decoys` (396 rows) are the bait
input and its null. Padding is core ±50 kb, net ±2 kb, as the plan fixes. Step 2 inherits
the four assumptions above, and this one in particular: **the target set is an enrichment
with measured recall ≈ 0.36, not coverage** — a gene absent from it is not thereby
excluded, and the report must never say otherwise.
