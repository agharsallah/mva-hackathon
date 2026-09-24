# 150 — The child's phenotype twin among 76,699 MGI mouse genotypes

**Step:** iteration 4, [step 9](../README.md), experiment E2. **Date:** 2026-09-24. **Claims:**
H085 (`P4-20`), H086 (`P4-21`). **Sources:** both — the clinical dataset (the 8 HPO terms) is
the query; the genome enters only through the gene under test (BUB1B, from the Track 1 pair).
No genomic position, allele or read is used.

## Question

Which mouse genotype is the child's phenotypic twin — and are the interventions published in
that model the right ones to import into Track 2?

## Hypothesis and prediction

Filed in the register before this entry (`mva-science hypothesis-add`, 2026-09-24):

| id | claim | prediction |
|---|---|---|
| H085 `P4-20` | the child's terms match Bub1b mice better than almost every other mouse model | best Bub1b genotype in the top 5 % of all MGI genotypes |
| H086 `P4-21` | a hypomorph (or compound hypomorph) Bub1b genotype matches best | top Bub1b genotype carries a hypomorphic allele, not a null / knockout / het-null |

Analysis plan, fixed **before the first scoring run** (written in this section first):

| choice | fixed value | why |
|---|---|---|
| unit | one MGI genotype (`MGI_PhenoGenoMP.rpt`, every genotype with ≥ 1 MP term) | the genotype, not the gene, is what carries the allele class H086 is about |
| space | MP (Mammalian Phenotype ontology); each HP term projected onto MP | mouse annotations stay native; only 8 query terms are translated |
| bridge, tier 1 | MGI curated HP↔MP SSSOM (any predicate) ∪ uPheno logical equivalents (HP and MP sharing one `UPHENO:` class) | curated or logically derived |
| bridge, tier 2 | uPheno `hp-to-mp-bestmatches` (Jaccard of ancestors), only when tier 1 is empty | lexical/structural fallback, flagged per term |
| information content | IC(m) = −ln(share of genotypes whose MP closure contains m) | the mouse corpus sets rarity, as Phenodigm does |
| score (primary) | symmetric best-match-average Resnik: mean of child→genotype and genotype→child BMA | same rollup as `mva.phenotype.similarity` (entry 067) |
| score (secondary) | Phenodigm-style: ½(max/max_opt + BMA_sym/avg_opt) | a second rollup; a claim holds only if both agree |
| rank | pessimistic: rank = number of genotypes scoring ≥ the genotype; percentile = rank / N | ties never help Bub1b |
| term set | primary: all 8 (as H085 is worded); also proband-only 7 | the parental term is a parent's phenotype (below) |
| null | 1,000 random 8-term HP sets; each child term replaced by a random tier-1/2-mappable HP term with projected IC within ±0.25 nats; empirical p = (1 + #null sets whose best Bub1b percentile ≤ observed) / 1,001 | is it the child's terms, or any terms this specific? |
| positive control | Bloom syndrome (OMIM:210900) → *Blm*: 20 draws of 8 of its HPO annotations (seeded); prediction: median best-*Blm* percentile ≤ 5 % | closest analogue: chromosome instability + growth restriction + cancer, with mouse mutants in MGI |
| calibration panel | MVA1 (OMIM:257300 → *Bub1b*), Duchenne (*Dmd*), Marfan (*Fbn1*), achondroplasia (*Fgfr3*), Rett (*Mecp2*), Bardet–Biedl 1 (*Bbs1*), Nijmegen breakage (*Nbn*), same protocol; prediction: ≥ 5 of 7 in the top 5 % | the method's hit rate on known disease→mouse pairs |
| within-pathway | best genotype of *Trip13, Cep57, Bub1, Bub3, Mad2l1, Ttk, Cdc20* | are the other MVA / SAC mice as close? |
| leave-one-term-out | drop each term, re-rank the best Bub1b genotype | which terms carry the match |
| allele class (H086) | from MGI allele attributes: a genotype is *hypomorph* if any Bub1b allele is `Hypomorph`; *null* if its Bub1b alleles are only `Null/knockout` (homo- or heterozygous with `+`); *knock-in* otherwise (patient-mutation or point-mutation alleles) | MGI's own labels, not ours |

**The parental term.** HP:0200067 (recurrent spontaneous abortion) describes the child's
mother, a heterozygous carrier. In a mouse genotype, MP "miscarriage" is the phenotype *of that
genotype's females*. So on the 8-term set a model scores for its own females miscarrying,
which is not what the parents' history says. We score both; the 7-term set is the
biologically cleaner reading, the 8-term set is the one H085 names.

## What would refute it

- H085: the best Bub1b genotype ranks outside the top 25 %.
- H086: a null / knockout / heterozygous-null Bub1b genotype scores highest.
- The method (not a hypothesis): if the Bloom control's median percentile is > 25 %, a Bub1b
  result says nothing about the method and is reported as uninterpretable.

## Inputs

Raw files in `build/it4/track2-e2/raw/` (not committed; `manifest.json` there, copied into
[`ressources/phenotype/phenotype_twin.provenance.json`](../../../../ressources/phenotype/phenotype_twin.provenance.json)).
All fetched 2026-09-24.

| file | release / Last-Modified | bytes | sha256 (first 16) | licence |
|---|---|---|---|---|
| `MGI_PhenoGenoMP.rpt` (genotype → MP) | 2026-09-21 | 54,098,874 | `3649756742d27455` | MGI: free use, cite MGI |
| `MGI_PhenotypicAllele.rpt` (allele type + attributes) | 2026-09-21 | 32,307,545 | `4939874cf83d5ad0` | MGI: free use, cite MGI |
| `mp.obo` | `releases/2026-08-25` | 7,679,452 | `30840ff64fd27b14` | CC BY 4.0 |
| `hp.obo` | `hp/releases/2026-09-01` | 10,863,613 | `93dace952fcb3ec4` | HPO licence |
| `phenotype.hpoa` (controls) | 2026-09-02 | 35,816,037 | `e89aa39c8f97bf5a` | HPO licence |
| `mp_hp_mgi_all.sssom.tsv` (tier 1) | GitHub master | 328,986 | `6b23131d80d596a8` | CC BY 4.0 |
| `upheno-species-independent.sssom.tsv` (tier 1) | GitHub master | 2,554,239 | `9caed6f21238b5fa` | CC BY 4.0 |
| `hp-to-mp-bestmatches.tsv` (tier 2) | GitHub master | 1,262,175 | `f9ec5b8b7a777463` | CC BY 4.0 |

Code: `src/mva/phenotype/cross_species{,_io,_controls,_run}.py`, `tools/phenotype_twin.py`,
`tools/render_step9_e2.py`; tests `tests/test_cross_species.py` (10, synthetic ontology).
Parameters: null n = 1,000, seed 0, IC window ±0.25 nats; controls k = 8, 20 draws, seed 0.

Corpus: **76,699** genotypes (0 unresolved MP ids), **14,860** live MP terms, **13,680** HP terms
with a bridge row (13,083 with projected IC > 0 = the null pool), **22** Bub1b genotypes.

## Commands

```sh
uv run python tools/phenotype_twin.py fetch              # 8 files, manifest.json
uv run python tools/phenotype_twin.py run --gene Bub1b   # 53 s on the laptop, no Modal
uv run python tools/render_step9_e2.py                   # three figures
uv run pytest -q tests/test_cross_species.py             # 10 passed
```

The run was repeated three times (after two refactors); `phenotype_twin.json` was identical
each time (runtime field aside).

## Observed output

**How the child's terms enter MP** (tier 1 = 4 of 8 terms; the 3 tier-2 child terms are exact
label matches):

| HP term | MP projection | source (tier) | projected IC (nats) |
|---|---|---|---|
| rhabdomyosarcoma | increased rhabdomyosarcoma incidence | uPheno best match (2) | 7.44 |
| nephrocalcinosis | nephrocalcinosis | uPheno best match (2) | 7.58 |
| short stature | decreased body height / length / size | MGI curated + uPheno logical (1) | 7.24 |
| failure to thrive | postnatal growth retardation | MGI curated + uPheno logical (1) | 3.75 |
| skeletal muscle atrophy | skeletal muscle atrophy | uPheno best match (2) | 6.47 |
| premature birth | short gestation period; early parturition | MGI curated + uPheno logical (1) | 10.15 |
| small for gestational age | decreased fetal size / embryo weight / fetal weight / birth weight / birth body size | MGI curated (1) | 7.51 |
| parental miscarriage | increased miscarriage rate | uPheno best match (2) | 8.61 |

**H085 — best Bub1b genotype among 76,699** (pessimistic rank; p = IC-matched null, n = 1,000):

| term set | rollup | best Bub1b genotype | rank | percentile | null median percentile | empirical p |
|---|---|---|---|---|---|---|
| 8 terms | symmetric (primary) | K243R/+ (`Bub1b<tm1.1Hsl>/+`) | 1,045 | 1.36 % | 14.06 % | 0.026 |
| 8 terms | Phenodigm-style | H/H (`Bub1b<tm1Jvd>/<tm1Jvd>`, MGI:3046582) | 768 | 1.00 % | 10.52 % | 0.060 |
| 8 terms | forward (not pre-registered) | H/H | 39 | 0.05 % | 1.88 % | 0.005 |
| 7 terms | symmetric | K243R/+ | 818 | 1.07 % | 14.54 % | 0.018 |
| 7 terms | Phenodigm-style | H/L1002P (`<tm1Jvd>/<tm3.1Jvd>`) | 667 | 0.87 % | 11.15 % | 0.040 |
| 7 terms | forward | H/H | 65 | 0.08 % | 2.00 % | 0.015 |

Gene level (each gene's best genotype, 24,195 genes): Bub1b ranks 833 (symmetric), 638
(Phenodigm), 40 (forward) on 8 terms; 661 / 550 / 69 on 7.

Why the null matters: with 22 genotypes to choose from, Bub1b's *best* genotype lands at a median
10–14 % even for random terms of the same specificity. The raw 1 % is ~10× better than that, not
~100×.

**H086 — which Bub1b genotype** (8 terms; ranks symmetric / Phenodigm):

| genotype | MGI class | MP terms | rank sym | rank Phenodigm |
|---|---|---|---|---|
| K243R/+ (acetylation-deficient knock-in) | knock-in | 14 | **1,045** | 886 |
| H/H (MGI:3046582) | hypomorph | 18 | 1,773 | **768** |
| H/L1002P (compound, Sieben 2020) | hypomorph | 18 | 9,447 | 788 |
| Gt(neo-btk)1Dai/+ (best null) | null | 3 | 10,420 | 6,431 |
| X753/+ (GTTA truncating knock-in) | knock-in | 18 | 11,848 | 1,598 |

No null-class genotype is the best under any rollup or term set.

**What each winner matches** (Resnik per child term, nats; `explain()`):

- H/H: muscle atrophy ↔ *muscular atrophy* 5.68; failure to thrive ↔ *postnatal growth
  retardation* 3.75 (exact); premature birth and parental miscarriage ↔ *female infertility*
  via *abnormal female reproductive system physiology* 3.82; rhabdomyosarcoma ↔ *muscular
  atrophy* via *abnormal muscle morphology* 3.16 (**not** a tumour term — H/H carries none);
  short stature ↔ *cachexia* via *decreased body size* 2.47; SGA 1.44 (generic); nephrocalcinosis 0.
- K243R/+: rhabdomyosarcoma ↔ *increased sarcoma incidence* 5.30; three growth terms 1.44 via
  *enlarged spleen* (the root of the growth/size branch); five terms 0. Its symmetric lead comes
  from the reverse direction: its 14 tumour terms all meet rhabdomyosarcoma near *neoplasm*.
- Nephrocalcinosis scores 0 for **every** Bub1b genotype: MGI holds no kidney term for Bub1b.

**Leave-one-term-out** (8 terms). Symmetric: only dropping rhabdomyosarcoma worsens Bub1b
(1,045 → 1,505, and the winner flips to H/H); every other drop leaves or improves the rank
(767–1,044). Phenodigm: only dropping failure to thrive worsens it (768 → 882); dropping muscle
atrophy flips the winner to K243R/+ (667); others 500–708. The two rollups disagree because of one
axis each: the tumour axis (K243R/+) vs the growth/muscle axis (H/H).

**Within-pathway** (8 terms; best genotype percentile symmetric / Phenodigm): Bub1b 1.36 / 1.00;
Bub1 1.09 / 0.94 (`Bub1<tm1Ssta>` homozygous + CAG-creER, a conditional deletion); Ttk 7.20 / 1.85;
Trip13 8.79 / 14.33; Cdc20 10.88 / 8.12; Bub3 13.63 / 1.90 (Bub3/Rae1 double het); Mad2l1
13.64 / 6.21; Cep57 16.37 / 15.40.

**Positive control and calibration** (median percentile of the causal gene's best genotype over
20 draws of 8 disease terms; symmetric / Phenodigm):

| disease → gene | terms (mappable) | median sym | median Phenodigm | ≤ 5 %? |
|---|---|---|---|---|
| **Bloom → Blm** (the pre-declared control) | 42 (41) | 2.73 % | 1.40 % | yes |
| MVA1 → Bub1b | 57 (56) | 10.38 % | 6.34 % | **no** |
| Duchenne → Dmd | 30 (30) | 0.06 % | 0.05 % | yes |
| Marfan → Fbn1 | 70 (67) | 0.04 % | 0.03 % | yes |
| Achondroplasia → Fgfr3 | 44 (42) | 0.04 % | 0.02 % | yes |
| Rett → Mecp2 | 33 (31) | 0.58 % | 0.42 % | yes |
| Bardet–Biedl 1 → Bbs1 | 62 (61) | 2.25 % | 0.86 % | yes |
| Nijmegen breakage → Nbn | 75 (73) | 0.33 % | 0.94 % | yes |

Figures: [`figures/it4/step9-e2-rank.svg`](../../../../figures/it4/step9-e2-rank.svg),
[`step9-e2-terms.svg`](../../../../figures/it4/step9-e2-terms.svg),
[`step9-e2-controls.svg`](../../../../figures/it4/step9-e2-controls.svg).

**Interventions.** [`ressources/track2/model_interventions.tsv`](../../../../ressources/track2/model_interventions.tsv)
(12 rows, PMIDs verified by esummary 2026-09-24): D5 senolytic/mTOR 4 rows (p16 deletion
18516091, INK-ATTAC 22048312, Pak2 depletion 31209047, mTORC1 observation 31738183 — plus the
analogue dasatinib/sirolimus), D3 3 rows (SIRT2-Tg + NMN 24825348, BubR1 overexpression
23242215, SIRT2-Tg null effect on wild-type 38009412), caution 3 rows (p19Arf 18516091, p53/p21
23602569, K243R acetylation 23878276 with 25285631), new Wnt 1 row (sFRP3 30609266), carriers 1
row (GTTA/+ 23300461).

## Verdict

- **Method: valid.** Bloom → Blm median 2.73 % / 1.40 % (prediction ≤ 5 % met); calibration 6 of
  7 in the top 5 % on both rollups (prediction ≥ 5 met). The one miss is MVA1's own HPO
  annotation → Bub1b (10.4 % / 6.3 %).
- **H085: supported.** Best Bub1b genotype at 1.36 % (symmetric) and 1.00 % (Phenodigm) on 8
  terms, 1.07 % / 0.87 % on 7 — all inside the 5 % prediction, far from the 25 % refutation.
  Against the IC-matched null the result is significant on 5 of 6 (term set × rollup) cells
  (p 0.005–0.040); 8-term Phenodigm p = 0.060. Strength: moderate — about 10× better than
  chance, not 100×.
- **H086: not supported as pre-registered; not refuted.** The rule was "both rollups agree".
  They do not: symmetric names the K243R/+ acetylation-deficient knock-in (neither hypomorph nor
  null), Phenodigm names H/H (8 terms) or H/L1002P (7 terms). Forward (not pre-registered) names
  H/H. No null genotype wins anywhere (best null: rank 10,420 / 6,431). The disagreement is
  explained, not noise: the hypomorph matches the child's growth, muscle and perinatal terms;
  the knock-in matches only the tumour.

## Limitations

- **Projection, not a unified ontology.** HP terms are mapped into MP, then Resnik runs in MP.
  OWLSim over uPheno would also let near-miss terms meet in a shared cross-species ancestor.
- **Three child terms bridge by the tier-2 fuzzy file** (exact label matches here); the
  parental term's bridge is tier 2 too.
- **Annotation depth biases the rollups.** Symmetric rewards sparsely annotated genotypes
  (top genotypes overall have 1–3 MP terms); forward rewards heavily annotated ones. Hence two
  pre-registered rollups and a null.
- **Perinatal terms match through the mouse mothers.** Premature birth and parental miscarriage
  meet H/H via *female infertility* — a phenotype of the mutant's own females, not of its pups.
- **MGI absence ≠ phenotype absence.** No Bub1b mouse has a kidney term; that is an unphenotyped
  organ as much as a negative.
- The null keeps each term's IC but not its branch; random sets can mix branches the child's
  set does not.
- Interventions: abstract-level only; no effect sizes; full texts not read.

## Conclusion

The child's phenotype sits in the top ~1 % of 76,699 mouse genotypes for Bub1b, about 10×
better than IC-matched chance, with a method that finds Bloom, Duchenne, Marfan and four other
disease genes. The closest *model* depends on which half of the child you weigh: growth, muscle
and perinatal → the BubR1 hypomorph (H/H, H/L1002P) where the senolytic and SIRT2 rescues were
done; the tumour → the acetylation-deficient K243R/+ knock-in, where no intervention exists.
Import the H/H interventions (D5 senolytic, D3 NAD+/SIRT2) with the caveat that no approved drug
has been tested in any BubR1 model.
