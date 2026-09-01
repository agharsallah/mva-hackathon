# Methodology log — step 0

**Relocated 2026-08-29** from the repository root `methodology/` to
[`docs/step-0/methodology/`](.). Entries 001–016 all belong to step 0 (first contact with
the delivery, then the platform), so the log moved whole rather than being split. The
entries themselves are unchanged apart from relative link paths, which the move forced.
Later steps get their own `docs/step-<n>/methodology/`, and the numbering continues across
them — 017 is the next entry, wherever it lands.

One entry per analysis actually executed, recording the question, the exact inputs and
commands, the observed output, and the conclusion drawn — enough for someone else to
reproduce it and reach the same conclusion or disagree with it.

**Nothing here is estimated or assumed.** Every number is copied from a run whose output
was seen. Where a value is an estimate from sampling rather than a full count, the entry
says so and gives the sampling parameters.

**No patient variant coordinates appear here.** Entries record counts, distributions and
classifications; the positions themselves stay in the warehouse database, queried through
the reads/viz API, per
[no patient data in the repository](../../notes/no-patient-data-in-the-repository.md).

## Environment

All runs below, unless stated otherwise:

| | |
|---|---|
| Machine | 12 cores, 15 GB RAM, Linux 6.6.87.2-microsoft-standard-WSL2 |
| Dates | 001–007: 2026-08-28. 008–015: 2026-08-29. Each entry states its own. |
| Data | `~/ubuntu/data/`, 10 files, 80 GiB, unmodified |
| bcftools / samtools / htslib | 1.24 (micromamba, conda-forge + bioconda) |
| fastp | 1.3.6 |
| Python | 3.13 (the project venv, `uv`) |

This index may be corrected. **The numbered entries may not** — they are append-only, and a
superseded finding is corrected by a new entry that says so, never by editing the old one.

Reproduce the environment with `tools/setup-env.sh`, then `source tools/activate.sh`.

## Entries

| # | Question |
|---|---|
| [001](001-vcf-provenance-and-structure.md) | What produced this VCF, and what is in its header? |
| [002](002-callset-quality-and-composition.md) | Is the callset trustworthy, and what is its composition? |
| [003](003-panel-gene-variant-counts.md) | How many variants sit in the MVA candidate genes? |
| [004](004-sex-and-aneuploidy-from-allele-balance.md) | What is the proband's sex, and is mosaic aneuploidy visible? |
| [005](005-fastq-structure-and-quality.md) | What are the raw reads, and what depth do they give? |
| [006](006-phasing-power-on-bub1b.md) | How much of the compound-het search space can phasing resolve? |
| [007](007-exploration-toolkit.md) | Can the whole data profile be read, graded and rendered from code? |
| [008](008-duckdb-warehouse.md) | Can the derived tables be queried in SQL on a shared box, and what does "install DuckDB on a server" mean? |
| [009](009-hosted-database-choice.md) | Which hosted database should sit under DuckDB, and what goes in it? |
| [010](010-postgres-ingest-and-derivations.md) | Can the profile be ingested into hosted Postgres and have results written back? |
| [011](011-duckdb-fidelity-and-ingestion-gates.md) | Is DuckDB lossless, and what of the 85 GB should actually be ingested? |
| [012](012-read-storage-options.md) | How should the raw reads be normalised and stored, and in what database? |
| [013](013-remote-object-store.md) | How can server-side files be queried from a laptop without SSH? |
| [014](014-source-of-truth-and-lineage.md) | Is the delivery preserved unchanged, verified, and traceable? |
| [015](015-step-1-consolidation.md) | Is the repository coherent enough to build phase 2 on? |
| [016](016-lineage-backfill-and-probe-ledger.md) | Which bytes produced each table, and who spent which oracle submission? |
| [017](017-the-research-record.md) | Can the investigation itself be made machine-readable? **The last platform entry** — from 018 every entry is a test bound to a hypothesis under a research goal ([`../../method.md`](../../method.md)). |
| [018](018-fastq-conversion-engine-choice.md) | Which library should parse 1.08 billion reads into Parquet? *(step-0 machinery, so no hypothesis — see the entry's opening note.)* |
| [019](019-where-the-read-bytes-come-from.md) | Where do the FASTQ bytes come from, and can they be read straight out of the object store? *(step-0 machinery, no hypothesis.)* |
| [020](020-presigned-urls-defeat-compression-inference.md) | Does a reader still recognise gzip when the URL ends in a signature? **Amends 019.** |
| [021](021-the-row-group-is-a-memory-budget.md) | Why did the winning engine run out of memory on real data? **Corrects the memory verdict of 018.** |
| [022](022-engine-bakeoff-on-the-delivery.md) | Which engine converts the delivered reads, measured on the delivery? **Authorises the full conversion.** |
| [023](023-the-exact-read-census.md) | Is the read store correct, and how many reads does the delivery actually hold? **Supersedes the read count of 005.** |
| [024](024-the-kmer-strike-works.md) | Does a mapping-free k-mer search over 1.07 billion reads work, and how fast? |
| [025](025-many-probes-one-pass.md) | Why did 20 probes take 10× one probe, and what makes batching actually free? |
| [026](026-multi-literal-matching-needs-aho-corasick.md) | Why did the regex fix fail on the server, and what is the delivery's k-mer noise floor? |
| [027](027-aho-corasick-confirmed.md) | Does the Aho-Corasick fix hold on the server? **Closes 026: 335 s for 20 probes.** |
| [028](028-viz-api.md) | Can one HTTP service serve the warehouse, the object store and the job API to a browser, with no endpoint able to trigger a whole-genome scan? *(step-0 machinery, no hypothesis.)* |
| [029](029-viz-app.md) | Can a React app turn those endpoints into seven pages that each answer one question and explain their own domain terms? *(step-0 machinery, no hypothesis.)* |
| [030](030-population-reference-data.md) | What does "normal" look like? Three public, non-patient reference tables, small enough to commit and join-ready. *(step-0 machinery, no hypothesis.)* |
| [031](031-vep-rest-panel-annotation.md) | Can a REST-backed annotator fill the open annotation port and land every panel allele in the warehouse with lineage? *(step-0 machinery, no hypothesis.)* |
| [032](032-reference-comparison-tables.md) | Can the reference tables be staged through the existing path and joined into three comparison tables the browser reads in under a second? *(step-0 machinery, no hypothesis.)* |
| [033](033-compare-page.md) | Can the browser hold the case against the healthy population — rarity, constraint, and QC norms — on one page? *(step-0 machinery, no hypothesis.)* |
| [034](034-data-catalog-endpoints.md) | Can two endpoints describe every object and table — what it is, what it contains, when it arrived, where it lives — without scanning the data? *(step-0 machinery, no hypothesis.)* |
| [035](035-catalog-page.md) | Can the catalogue render as one page: the delivery's cards, a filterable table inventory, and the read store's card? *(step-0 machinery, no hypothesis.)* |
| [036](036-table-semantics-registry.md) | Can every table and column state what it means and why it exists — and can a test refuse to let that description go stale when a new table lands? *(step-0 machinery, no hypothesis.)* |
| [037](037-baf-karyogram.md) | At 1 Mb resolution, does any segment's allele balance leave 0.5 or any arm step in depth — or is the aneuploid fraction below what a VCF can resolve? *(step-0 machinery, no hypothesis.)* |
| [038](038-pair-matrix.md) | Can the compound-heterozygous pair space be materialised and drawn so that the 99.7 % phasing leaves unresolved reads as the finding rather than as a rendering failure — and does it reproduce entry 006? *(step-0 machinery, no hypothesis.)* |
| [039](039-candidate-funnel.md) | How does the callset narrow from 5,012,204 records to a candidate pair set, what does each filter cost, and can the genome→panel scope change be shown rather than hidden? *(step-0 machinery, no hypothesis.)* |
| [040](040-locus-gene-track.md) | Can Ensembl REST supply a gene's exon structure and protein domains server-side — and can our own alleles be placed in amino-acid space at all, given that `panel_annotations` never stored a protein position? *(step-0 machinery, no hypothesis.)* |
| [041](041-science-page.md) | Can a read-only surface render the research register honestly while its two tables do not exist yet — without creating them, and without confusing "absent" with "empty"? *(step-0 machinery, no hypothesis.)* |
| [042](042-universal-search.md) | Can one box resolve a gene symbol, a region or an rsID against the live callset — and what actually limits how wide a window the unindexed raw layer can serve? **Measures the span cost (flat: the cap is a payload guard, not a latency one) and the rsID bake-off (both mechanisms are ~1 s, so the answer is to chain them).** *(step-0 machinery, no hypothesis.)* |
| [044](044-url-state.md) | Can every exhibit selection move into the URL so one link is one complete figure reference — without noisy URLs, without history spam, and without two exhibits overwriting each other? *(step-0 machinery, no hypothesis.)* |
| [045](045-orphan-tables.md) | Which warehouse tables and `bcftools stats` sections had no surface — and for each one, is it worth serving? **Measures the section census: the delivered stats file has no `QUAL` section, and `SiS` duplicates the `AF` singleton bin.** *(step-0 machinery, no hypothesis.)* |
| [046](046-probe-builder.md) | Can dashboard candidates become a validated Track 1 submission CSV in the browser — with no coordinate typed, no second copy of the format rules, and the header proven against the organisers' own template? *(step-0 machinery, no hypothesis.)* |
| [047](047-observed-expected-extension.md) | Which further WGS QC metrics can this warehouse measure against a PMID/DOI-citable range, and can the verdict be shown on the Overview tiles rather than only on Compare? **Adds 7 cited norms (20 → 27 rows) and 4 verdicts (12 → 16 comparable): SNV/indel 4.393 below, het count 3,113,937 above, PASS-only dbSNP 91.07% below the modern 99.2%, PASS-SNV 93.89% above the 2011 89.89% floor. Three metrics stay measurable-but-unnormed, each with the source saying why.** *(step-0 machinery, no hypothesis.)* |
| [048](048-gene-background.md) | Is each panel gene's variant density and PASS share normal for its chromosome and for the genome, or an outlier? **Measures the per-gene z table against the 2,961-window background: TRIP13 is a −4.02 σ PASS-share outlier (callability, not pathogenicity), and every gene reads low on density for a reason that is about gene bodies, not about the panel.** *(step-0 machinery, no hypothesis.)* |
| [049](049-suppressed-calls.md) | Inside the candidate panel, what did the caller suppress, under which FILTER reason, and is any of it a plausible hidden second allele? **Measures the per-gene, per-reason census: 20 suppressed records over 8 genes, TRIP13 6 of 12 (reproducing the recorded figure), and none of the 20 is both rare and protein-altering — VEP had in fact annotated every one of them.** *(step-0 machinery, no hypothesis.)* |
| [050](050-pair-comparator.md) | Can any two heterozygous alleles of one panel gene be compared field by field, given a phase verdict looked up in the server's own resolved-pair list, and handed to the submission builder without a coordinate being retyped? *(step-0 machinery, no hypothesis.)* |
| [051](051-clinvar-presence.md) | Run the ClinVar join backwards: of every pathogenic / likely-pathogenic site ClinVar holds in the panel, which are present in this callset? **Measures 2,129 P/LP sites → exactly 1 present (BUB1B `stop_gained`, het, PASS), reached independently of the VEP route in 031; the other 2,128 absent, 0 uncomparable. Exact-string matching makes presence a lower bound: 1,306 of the 2,129 are indel-shaped.** *(step-0 machinery, no hypothesis.)* |
