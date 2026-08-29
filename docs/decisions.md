# Decisions — the register

**Standing:** the index over [`notes/`](notes/). Each note argues one decision and carries
its own `Standing:` line; this page is the one-screen view. Last checked 2026-08-29.

Rule: a decision is argued in **exactly one** note. Every other document states the result
in one sentence and links the note. Nothing re-argues a decision elsewhere.

## Decisions taken

| Decision | Result | Standing | Note |
|---|---|---|---|
| Patient data in git | Absolute prohibition, any size. Aggregates only. | firm — follows from the DTA, not a preference | [note](notes/no-patient-data-in-the-repository.md) |
| Test data | Synthetic fixtures; only plaintext VCFs may enter git | firm — follows from the above | [note](notes/synthetic-fixtures.md) |
| The delivered bytes | Versioned bucket + hash verification is the source of truth; everything else is derived | firm — 12/12 verified 2026-08-29 | [note](notes/delivery-is-immutable.md) |
| Where shared state lives | Postgres for mutable shared state, Parquet for bulk immutable reads, DuckDB as the engine over both | firm | [note](notes/postgres-for-shared-state.md) |
| Retire the DuckDB file-warehouse (Path A) | **Decided 2026-08-29: deleted.** `remote.py` and the `preflight`/`provision`/`push`/`load`/`ship`/`local`/`query` verbs are gone; `catalog.py` + `stage.py` + the `stage` verb stay because `pg-ingest` reads their Parquet. Rationale: no data-manipulation strategy is settled yet, everything upstream is drafts, and one-off local DuckDB work is a plain Python script — Postgres + MinIO is the platform. | firm | [note](notes/postgres-for-shared-state.md) |
| Chromosome naming | The `chr` prefix is added in one function, `pipeline/variant.py` | firm — enforced by test | [note](notes/chr-prefix-bridge.md) |
| Functional annotation | Enters through a port with a lookup fake; the backend is deliberately unchosen | port settled, backend open | [note](notes/annotation-as-a-port.md) |
| Scorer | A local transcription of the published evaluation code, for rehearsing probes offline | settled for the challenge | [note](notes/local-scorer-replica.md) |
| VCF parsing | Hand-rolled reader for the four FORMAT fields we need; `bcftools` still does the heavy lifting | provisional — revisit if real VCF surface area is needed | [note](notes/hand-rolled-vcf-reader.md) |
| The ranked unit | A pair, not a variant, and pairs must sit in one gene | follows from the answer key; the scoring function inside is provisional | [note](notes/ranking-pairs-not-variants.md) |
| Bio toolchain | micromamba into `~/.local` — no root available | provisional; revisit on Modal | [note](notes/toolchain-choice.md) |

## Open decisions

| Question | Why it is still open |
|---|---|
| Which annotation backend? | Ensembl VEP REST is right for the panel variants today; an offline cache is right for the genome-wide run. Both, staged, is the current lean — see [`roadmap.md`](roadmap.md). |
| Layer-2 schema details | Multi-allelic splitting and INFO-as-columns-vs-MAP are recorded but unresolved — see [`data-layers.md`](data-layers.md). |
| How to close the object-store SSL gap | Tunnel, TLS reverse proxy, or firewall. Not chosen. |

## The original recommendation matrix

Extracted 2026-08-29 from `ideation/draft0-answers.md` §0.1, now in
[`archive/`](../archive/draft0-answers.md). This is the **strategy** sweep taken before
most of the pipeline existed. Rows that later became real decisions are linked to their
note; the rest are recorded direction, not commitments, and several are not started.

| # | Question | Recommended option | Why it beat the alternatives | Since |
|---|---|---|---|---|
| 1 | Data handling | Headers-first checklist, then a **mapping-free k-mer strike** on the FASTQ for published MVA alleles, with alignment launched in parallel on day 1 | detects a known allele in minutes with no alignment; with no BAM shipped, alignment is a 1–2 day dependency | checklist **done** ([`methodology/001`–`006`](../methodology/)); k-mer strike and alignment **not started** |
| 2 | Query / visualize | DuckDB + Parquet for SQL, `slivar` for comp-het logic, igv-reports for evidence | zero infra, deterministic, reproducible; dashboards are a week-3 luxury | partly superseded — DuckDB is the engine, but shared state moved to [Postgres](notes/postgres-for-shared-state.md) |
| 3 | Disease model | Soft Bayesian gene priors **flattened** against the measured phenotype, never hard gene exclusion | rhabdomyosarcoma still favours *BUB1B*, but absent microcephaly promotes the *TP53*/*DICER1* differentials — a hard filter was always the classic trap | direction only; no prior implemented |
| 4 | Literature | Automated **reported-allele catalogue** (PubTator3/LitVar2 + ClinVar) joined against the VCF, LLM triage on top | a published-allele match is a near-instant solve; the join is mechanical | not started |
| 5 | Data structures | Scorer-identical dataclasses + DuckDB + a **probe simulator** with a bitmask hypothesis space, plus one contig-namespace conversion | the simulator turns probe design into computed optimization; the namespace conversion is a live scoring bug if done by hand | dataclasses and the [scorer replica](notes/local-scorer-replica.md) **done**; [contig conversion](notes/chr-prefix-bridge.md) **done**; probe simulator **not started** |
| 6 | Models | Tiered escalation: **free tier (non-PASS + `1/2` sites)** → standard stack → raw-data rescue → foundation models | tier 1.5 is minutes and targets "the caller saw it and suppressed it"; tier 2 is the only source of SV evidence that will ever exist | sequencing kept in [`roadmap.md`](roadmap.md); nothing executed |
| 7 | Statistics | Bayesian ACMG posterior as the `epcr` backbone; greedy info-gain probe policy | defensible arithmetic in the report; the decode tables are already near-optimal | not started |
| 8 | ML | Reciprocal-rank fusion primary + an audited LLM evidence-tournament re-ranker | robust at N=1, transparent, and the agentic layer is the Innovation story | not started |
| 9 | Evaluation | Local scorer reimplementation + GIAB spike-in probands + read-level spiked alleles | the only honest pre-oracle measurement | [scorer replica](notes/local-scorer-replica.md) **done**; spike-ins **not started** |
| 10 | Deterministic vs probabilistic | Deterministic shrink → probabilistic rank → decision-theoretic probe | soundness first, efficiency second; filters logged with removal counts | deterministic layer built ([`pipeline/`](../src/mva/pipeline/)); probabilistic layer not |
| 11 | Database | No new curated DB; a thin analytical layer; optionally publish a public-only N-of-1 toolkit | reproducibility + scalability points without curation liability | **holds** — no curated database was built |
