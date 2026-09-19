# Toolset — what answers what

**Standing:** current as of 2026-09-19 for the research-record table (entry 126: the steps
routes, the figure and entry routes, the iteration switcher). The rest is current as of
2026-09-05 (layer-2 coding scan, `annotate-coding`, probe designer added) and has **not** been
re-checked since — `mva-zoo` and the iteration-4 tooling are known to be missing from it.
Written from executed `--help` output, the route
tables in `src/mva/viz/`, the module manifest in `app/src/app/modules/index.ts`, and
`pyproject.toml` `[project.scripts]`. Every name below was verified to exist.

## How to read it

Find your **question** in the left column of the table for its domain. The row gives three
ways to answer it: a **CLI** verb for a terminal or an agent, an **API route / app page**
for the browser surface, and the **module** that owns the logic when you have to read or
extend the code. API routes are all prefixed `/api` and return one envelope,
`{data, cached_at, source}`. Measured numbers are never restated here — the owner is
[`../ideation/data-findings.md`](../ideation/data-findings.md).

Seven CLIs exist: `mva-warehouse`, `mva-science`, `mva-explore`, `mva-reads`,
`mva-phenotype`, plus two servers, `mva-reads-api` and `mva-viz-api`. Run everything with
`uv run`.

---

## Source and lineage — where did this byte come from?

| Question | CLI | API route / app page | Module |
|---|---|---|---|
| What did the publisher deliver? | `mva-warehouse source-scan` | `/api/provenance/sources` · `/catalog` | `warehouse/source.py` |
| Is the delivery in the object store, hash-verified? | `mva-warehouse source-upload`, `source-status`, `source-check` | `/api/catalog/objects` | `warehouse/objects.py` |
| Fetch straight from publisher to bucket (server-side) | `mva-warehouse source-fetch` | — | `warehouse/cli_source/` |
| What produced this table, from what? | `mva-warehouse lineage-list` | `/api/provenance/lineage` · `/provenance` | `warehouse/lineage.py`, `lineage_edges.py` |
| Which public reference inputs are pinned? | — | `/api/provenance/reference` | `warehouse/reference.py`, `viz/refprovenance.py` |
| Which derivation runs have been logged? | `mva-warehouse pg-list` | `/api/provenance/derivations` | `warehouse/derivation.py` |

## The callset — what is in the VCF?

Layer 1 is the lossless all-text raw table; derivations are named SQL over it.

| Question | CLI | API route / app page | Module |
|---|---|---|---|
| What does the VCF header declare? | `mva-warehouse vcf-shape` | — | `warehouse/vcfstage.py` |
| Does the reader lose anything? | `mva-warehouse vcf-verify` | — | `warehouse/integrity.py` |
| Load the callset as layer 1 | `mva-warehouse vcf-stage`, `vcf-ingest` | — | `warehouse/vcfstage.py` |
| Run every named derivation | `mva-warehouse pg-derive` | — | `warehouse/analysis*.py` |
| Ad-hoc SQL | `mva-warehouse pg-query`, `s3-query` | — | `warehouse/postgres.py` |
| Filter / quality / depth / Ts-Tv / indel shape | — | `/api/callset/filters`, `funnel`, `depth-distribution`, `tstv`, `indel-lengths`, `substitutions`, `zygosity-split`, `observed-expected` · `/callset` | `analysis.py`, `analysis_stats.py`, `analysis_funnel.py`, `analysis_reference_qc.py` |
| Is any chromosome in the wrong copy number? | — | `/api/genome/baf-bins`, `allele-balance`, `contig-density`, `density-bins` · `/genome` | `analysis_karyogram.py`, `analysis.py` |
| Records in one region | — | `/api/callset/region` · `/search` | `viz/search.py`, `search_resolve.py` |

## Reads — the raw FASTQ, made queryable

| Question | CLI | API route / app page | Module |
|---|---|---|---|
| Convert FASTQ to the sharded Parquet store | `mva-reads convert` | — | `reads/convert.py`, `engines.py` |
| Does the store match the delivery? | `mva-reads verify` | — | `reads/verify.py` |
| Per-lane yield, filter rate, quality profile | `mva-reads qc`, `status` | `/api/reads/runs`, `yield`, `flowcell`, `cycle-quality`, `quality-levels`, `partitions` · `/reads` | `reads/schema.py`, `viz/readstore.py` |
| **k-mer strike** (does this sequence appear in the reads, either strand?) | `mva-reads scan`, `count` | `/api/probe/scan`, `/api/probe/count` (async: `/api/jobs/...`) | `reads/scan.py`, `triage.py`, `routes_reads.py` |
| Arbitrary SQL over the reads | `mva-reads sql` | — | `reads/access.py`, `store.py` |

## Annotation and reference — is this variant rare and damaging?

| Question | CLI | API route / app page | Module |
|---|---|---|---|
| Annotate panel alleles through Ensembl VEP REST | `mva-warehouse annotate-panel` | `/api/panel/annotations` · `/panel` | `pipeline/annotate_vep.py`, `vep_response.py`, `warehouse/annotate.py` |
| Annotate every coding allele genome-wide (layer 2, resumable) | `mva-warehouse annotate-coding` | — | `warehouse/annotate_coding.py`, `analysis_coding.py`, `reference_coding.py`; `tools/build_coding_regions.py` |
| gnomAD frequency and constraint | — | `/api/panel/constraint` · `/compare` | `analysis_reference.py` |
| Is this site in ClinVar as pathogenic? | — | `/api/panel/clinvar-presence` · `/compare` | `analysis_clinvar.py` |
| Gene structure / protein structure for one gene | — | `/api/panel/gene-structure`, `/api/panel/protein-structure`, `/api/panel/structure-genes`, `/api/prediction/{accession}` | `viz/genestructure.py`, `proteinstructure.py`, `mmcif.py` |
| Rebuild the committed reference tables | `tools/build_reference_data.py`, `tools/build_gene_set.py` | — | `warehouse/reference.py` |

> The annotation seam is a port, not a vendor binding — see
> [`notes/annotation-as-a-port.md`](notes/annotation-as-a-port.md).

## Candidates and pairs — which two variants?

| Question | CLI | API route / app page | Module |
|---|---|---|---|
| Which het pairs exist inside a panel gene? | `mva-warehouse pg-derive` (`panel_het_pairs`) | `/api/panel/het-pairs` · `/panel` | `analysis_pairs.py` |
| Which calls did the filters suppress? | `mva-warehouse pg-derive` (`panel_suppressed`, `panel_filter_census`) | `/api/panel/suppressed` | `analysis_suppressed.py` |
| Candidate funnel, gene background | `mva-warehouse pg-derive` (`candidate_funnel`, `panel_gene_background`, `panel_candidates`) | `/api/callset/funnel`, `/api/panel/background` | `analysis_funnel.py`, `analysis_background.py`, `analysis_reference.py` |
| Are two variants in *cis* or *trans*? | — | `/api/panel/locus` · `/panel` | `viz/phase.py` |
| Enumerate and rank compound-het pairs | — | — | `pipeline/compound_het.py`, `pipeline/ranking.py` |

> Ranking scores pairs, not single variants — [`notes/ranking-pairs-not-variants.md`](notes/ranking-pairs-not-variants.md).

## Phenotype — which gene do the symptoms name?

| Question | CLI | API route / app page | Module |
|---|---|---|---|
| Rank every curated gene against the child's HPO terms | `mva-phenotype rank` | `/api/phenotype/genes`, `/api/phenotype/terms` · `/phenotype` | `phenotype/prioritise.py`, `similarity.py` |
| Why did one gene place there? | `mva-phenotype gene` | `/api/phenotype/gene` | `phenotype/associations.py`, `ontology.py` |
| What changes if a term is dropped? | `mva-phenotype delta` | `/api/phenotype/delta` | `phenotype/prior.py` |
| Do two hosted rankers agree? | `mva-phenotype agreement` | — | `phenotype/remote.py` |

## Knowledge — what has already been published, and is that worth anything?

| Question | CLI | API route / app page | Module |
|---|---|---|---|
| Has anyone published about the alleles **this sample** carries? (LitVar 2.0, one dbSNP identifier at a time; an allele with no identifier is `NOT_ASKED`, never zero) | `uv run python tools/fetch_it2_catalogue.py` | `/api/steps/step-5` → `catalogue` · `/track1/iteration2/step-5` | `knowledge/catalogue.py`, `knowledge/sources.py` |
| Does any single paper discuss a candidate gene alongside several of the patient's features? (PubTator 3.0, one search per gene × term, so the matched-term count is per paper) | `uv run python tools/build_it2_anchors.py` | `/api/steps/step-5` → `anchors` | `knowledge/anchors.py` |
| Does a missense allele land in an annotated domain, where the structure model is confident? (UniProt → InterPro → AlphaFold DB; positions as fractions of protein length, never residues) | `uv run python tools/score_it2_protein.py` | `/api/steps/step-5` → `protein`, `domains` | `knowledge/protein.py` |
| **Does any of that order anything a raw publication count does not?** (matched-decoy AUC and a Spearman/top-k comparison against PubMed hit counts; both conditions must hold before the route may rank) | `uv run python tools/run_it2_knowledge_baselines.py` | `/api/steps/step-5` → `citations`, `groups` | `knowledge/baselines.py`, `pipeline/nulls.py` |

Fetching, caching, the courtesy interval and the provenance digest are **not** in
`mva.knowledge`: every function takes the `mva.drugs.cache.Fetcher` the repository already
shares, which is why the package sits one import layer above `mva.drugs`.

## Submission and the scorer — spending an oracle probe

Budget is **6 submissions**; `probe-budget` is the authority on what is left.

| Question | CLI | API route / app page | Module |
|---|---|---|---|
| Build a candidate submission CSV | — | `/api/probe/build` · `/probes` | `pipeline/submission.py`, `viz/probebuild.py` |
| Grade it offline before spending a probe | — | — | `pipeline/scorer.py` |
| Read a submission as a measurement: decode table + expected information gain over a hypothesis space | `tools/design_submission.py` | — | `pipeline/probe_design.py` |
| Cross-check the replica against the organisers' published `evaluation.py`, key by key | inside `tools/design_submission.py` (`--reference-scorer`) | — | `pipeline/scorer_reference.py` |
| Is a patient coordinate anywhere in the tree? (quality gate) | `tools/check_coordinates.py` | — | `tools/coordinate_allowlist.txt` |
| Turn the committed, coordinate-free `spec.selectors.json` into the gitignored spec (exactly one warehouse row per allele) | `tools/resolve_submission_spec.py` | — | `warehouse/submission_spec.py` |
| Derive every non-coordinate field of a submission row — facts for the notes from the selector's table, allele score, epcr ladder anchored on the register, in-callset priors — and write the coordinate-free `derivation.json` + `derivation.md` | `tools/resolve_submission_spec.py` (a `derivation` block in the selectors) | `/api/submissions` (`selectors.derivation`) · `/submissions` | `warehouse/submission_facts.py`, `warehouse/submission_rows.py` |
| Is an iteration folder complete, fresh, consistent and — if frozen — untouched? (quality gate) | `tools/check_iteration.py` | — | — |
| Freeze iteration n, open iteration n+1 (docs + submission folders), bump `ITERATION` | `tools/new_iteration.py` | — | `science/steps.py` |
| Every submission iteration in the app: state, deliverables, decode table, coordinate-free selectors, contributions, lineage per submission (raw VCF + clinical terms + tables + edges), audit trail (probe ledger, register) | `tools/resolve_submission_spec.py --record-lineage` (writes the edges) | `/api/submissions`, `/api/submissions/{track}/{n}/report`, `/api/submissions/{track}/{n}/figure/{slug}` · `/submissions` | `viz/submissions*.py`, `warehouse/submission_lineage.py` |
| How many probes are left? | `mva-warehouse probe-budget` | `/api/probe/ledger` · `/probes` | `warehouse/probes.py` |
| Record a spent submission and its reply | `mva-warehouse probe-log`, `probe-list` | `/api/probe/ledger` | `warehouse/probes.py`, `cli_ledger.py` |
| Bind an oracle reply to the claims it tested | `mva-science probe-link` | `/science` | `science/evidence.py` |

> The offline replica and its ambiguous zone: [`notes/local-scorer-replica.md`](notes/local-scorer-replica.md).

## Track 2 — which approved drugs act on the mechanism?

Case-agnostic: everything reads the mechanism card, nothing hard-codes a gene.

| Question | CLI | API route / app page | Module |
|---|---|---|---|
| What did Track 1 hand over? (gene, protein, allele classes, mechanism, directions, seed targets) | `mva-drugs card` | `/api/track2` → `card` | `drugs/mechanism.py` · `ressources/track2/mechanism.json` |
| Which genes make up the target set? (seeds + Reactome pathway members matching `checkpoint|kinetochore|mitotic`) | `mva-drugs targets` | `/api/track2` → `targets`, `pathways` | `drugs/pathway.py`, `drugs/sources/reactome.py` |
| Which molecules touch those targets, and which are market-approved? (Open Targets, ChEMBL, DGIdb; openFDA label check) | `mva-drugs drugs` | `/api/track2` → `candidates` (`approved` bool) | `drugs/candidates.py`, `drugs/sources/{opentargets,chembl,dgidb,openfda}.py` |
| Which trials exist for the disease and for each approved drug in the tumour context? | `mva-drugs trials` | `/api/track2` → `trials` | `drugs/sources/clinicaltrials.py` |
| What does PubMed say about the gene, the pathway and each direction? | `mva-drugs literature` | `/api/track2` → `literature` | `drugs/sources/pubmed.py` |
| Everything above into `ressources/track2/*.tsv` with a provenance manifest each, from cache when possible | `mva-drugs snapshot [--refresh]` | `/api/track2` → `catalog`, `summary` | `drugs/snapshot.py`, `drugs/provenance.py`, cache under `build/track2-cache/` |
| Where did each Track 2 table come from? (card version, API hosts by roll-up digest, the Track 1 iteration, the target set) | `uv run python tools/record_track2_lineage.py` | `/api/track2` → `lineage`, `register`, `linked_iterations`, `strategy` | `warehouse/track2_lineage.py`, `viz/track2*.py` |

## The research record — what do we believe, and why?

| Question | CLI | API route / app page | Module |
|---|---|---|---|
| The step map and each step's goal | `mva-science steps` | `/api/steps` · `/track1` | `science/steps.py`, `science/step_maps/` |
| **Any** iteration's steps, its claims, its blind-gate rows, and the submission folders it fed | — | `/api/steps?iteration=<name>` · `/track1/<iteration>` and `/track2/<iteration>` | `viz/steps.py` |
| One figure a step drew, as it was rendered | `tools/render_it2_step*.py`, `tools/render_track1_figures.py`, `tools/render_track2_figures.py` | `/api/steps/<iteration>/<slug>/figure/<name>` | `viz/steps_artifacts.py` |
| One methodology entry, verbatim, without leaving the page | — | `/api/steps/<iteration>/<slug>/entry/<name>` · `/track1/<iteration>/<slug>` | `viz/steps_artifacts.py` |
| The deep analysis under a step page (iteration 2 only; other iterations render the record alone) | — | `/api/steps/step-<n>` · `/track1/iteration2/step-<n>` | `viz/steps_it2*.py` |
| The navigation tree itself — Decide ▸ Track ▸ Iteration ▸ Step | `uv run python tools/gen_steps_nav.py` (`--check` in `pnpm check`) | the `decide` section of every page | `tools/gen_steps_nav.py` → `app/src/app/modules/steps.generated.ts` |
| File a claim (needs a prediction and a refutation) | `mva-science hypothesis-add` | — | `science/hypothesis.py` |
| Change a belief (append a revision) | `mva-science hypothesis-revise` | — | `science/record.py` |
| Record one sourced observation | `mva-science evidence-add`, `evidence-list` | `/api/science/evidence` · `/science` | `science/evidence.py` |
| Every claim, latest revision | `mva-science board`, `show` | `/api/science/hypotheses` · `/science` | `science/views/` |
| Weigh the evidence, see the arithmetic | `mva-science verdict` | `/science` | `science/record.py` |
| The publish gate (no coordinates, no unevidenced verdicts) | `mva-science check` | — | `science/cli/` |
| Write the committed mirror into `hypotheses/` | `mva-science export` | — | `science/export.py` |

## Reporting and figures

| Question | CLI | API route / app page | Module |
|---|---|---|---|
| Full interactive data-profile report | `mva-explore report`, `checks`, `locus`, `export` | — | `explore/report.py`, `checks.py`, `explore/views/` |
| Render the research record as HTML | `mva-science report` | — | `science/report.py`, `science/dossier.py` |
| Shared report shell, palette, figure unit | — | `/style-guide` | `render/theme.py`, `figure.py`, `report.py` |
| Serve the JSON API / read service | `mva-viz-api`, `mva-reads-api` | `/api/health`, `/api/health/dependencies` · `/status` | `viz/serve.py`, `viz/health.py`, `reads/api/` |
| Host the API for the deployed dashboard | `tools/setup-viz-api-service.sh` | — | `viz/auth.py`, `docs/step-0/infrastructure.md` §3 |
| Host the dashboard behind a password | `vercel --prod` (root dir `app`) | the whole app | `app/middleware.ts`, `app/api/`, `app/server/`, `app/README.md` § Hosting |
| The browser app | `pnpm --dir app dev` | every page in `app/src/app/modules/index.ts` | `app/src/pages/` |

## Quality gates

| Question | Command |
|---|---|
| Is the Python shippable? | `tools/check-python.sh` (`--fix` to autofix) — format, lint, module size, import layering, mypy, pytest |
| Is one module too long? | `uv run python tools/check_module_size.py` |
| Does the package layering hold? | `uv run lint-imports` |
| Is the app shippable? | `pnpm --dir app run check` — typecheck, lint, format, theme, dictionary, tests |
| Is the commit message well-formed? | `tools/check-commit-msg.sh` |

---

## Gaps — what has no tool yet

| Gap | Consequence | Owner |
|---|---|---|
| **Layer 2 built for the coding fraction only** — `results.coding_alleles` / `coding_candidates` / `gene_biallelic` ([069](iteration1/step-2/methodology/069-layer-2-coding-scan.md)); no genome-wide typed `variants` / `genotypes` / `variant_info` | non-coding queries still re-parse layer 1 text | [`step-0/data-layers.md`](step-0/data-layers.md) |
| **No normalization seam** — `bcftools norm` runs by hand, outside the pipeline | "was this normalized?" is answered by memory, and indel spellings can miss the scorer | [`iteration1/step-1/`](iteration1/step-1/) |
| **Annotator covers coding alleles, not the whole callset** — `mva-warehouse annotate-coding` annotates every coding allele genome-wide through VEP REST, checkpointed ([069](iteration1/step-2/methodology/069-layer-2-coding-scan.md)); deep-intronic and UTR alleles are still unannotated | a non-coding second allele is invisible to the rarity/consequence filter | [`iteration1/step-2/`](iteration1/step-2/) |
| **No alignment, no SV calling** — no BAM path, no structural-variant or deep-intronic caller | a second allele the caller could not emit is unreachable | [`iteration1/step-5/`](iteration1/step-5/) |
| **Track 2 has its data layer, not its ranking** — `mva-drugs snapshot` gathers targets, approved candidates, trials and literature from seven public APIs into `ressources/track2/` with manifests; no scoring or evidence-table renderer yet | candidates exist as rows, not as argued hypotheses | [`iteration1/step-8/`](iteration1/step-8/) |

## How to add a tool

1. Record it in the methodology of the **step that needed it** — tooling is not its own step.
2. An app page is **one entry in `app/src/app/modules/index.ts`** plus a fixture; nothing else registers a route.
3. An API route returns the envelope `{data, cached_at, source}` and lives in a `viz/routes_*.py` router.
4. Python stays **≤ 400 lines per module** and obeys the layering in [`../src/mva/README.md`](../src/mva/README.md) — `io`, `pipeline`, `render` import no sibling.
