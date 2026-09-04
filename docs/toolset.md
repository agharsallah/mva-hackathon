# Toolset — what answers what

**Standing:** current as of 2026-09-04, written from executed `--help` output, the route
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

## Submission and the scorer — spending an oracle probe

Budget is **6 submissions**; `probe-budget` is the authority on what is left.

| Question | CLI | API route / app page | Module |
|---|---|---|---|
| Build a candidate submission CSV | — | `/api/probe/build` · `/probes` | `pipeline/submission.py`, `viz/probebuild.py` |
| Grade it offline before spending a probe | — | — | `pipeline/scorer.py` |
| How many probes are left? | `mva-warehouse probe-budget` | `/api/probe/ledger` · `/probes` | `warehouse/probes.py` |
| Record a spent submission and its reply | `mva-warehouse probe-log`, `probe-list` | `/api/probe/ledger` | `warehouse/probes.py`, `cli_ledger.py` |
| Bind an oracle reply to the claims it tested | `mva-science probe-link` | `/science` | `science/evidence.py` |

> The offline replica and its ambiguous zone: [`notes/local-scorer-replica.md`](notes/local-scorer-replica.md).

## The research record — what do we believe, and why?

| Question | CLI | API route / app page | Module |
|---|---|---|---|
| The step map and each step's goal | `mva-science steps` | — | `science/steps.py` |
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
| **Layer 2 unbuilt** — no typed `variants` / `genotypes` / `variant_info` tables | every query re-parses layer 1 text | [`step-0/data-layers.md`](step-0/data-layers.md) |
| **No normalization seam** — `bcftools norm` runs by hand, outside the pipeline | "was this normalized?" is answered by memory, and indel spellings can miss the scorer | [`step-1/`](step-1/) |
| **No genome-wide annotator** — VEP REST is wired for the 8-gene panel only | rarity and consequence exist for the panel, not the ~5M callset | [`step-2/`](step-2/) |
| **No alignment, no SV calling** — no BAM path, no structural-variant or deep-intronic caller | a second allele the caller could not emit is unreachable | [`step-5/`](step-5/) |
| **Track 2 has zero code** — no drug, target or trial source wired | drug repurposing is desk research until a module exists | [`step-8/`](step-8/) |

## How to add a tool

1. Record it in the methodology of the **step that needed it** — tooling is not its own step.
2. An app page is **one entry in `app/src/app/modules/index.ts`** plus a fixture; nothing else registers a route.
3. An API route returns the envelope `{data, cached_at, source}` and lives in a `viz/routes_*.py` router.
4. Python stays **≤ 400 lines per module** and obeys the layering in [`../src/mva/README.md`](../src/mva/README.md) — `io`, `pipeline`, `render` import no sibling.
