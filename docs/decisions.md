# Decisions — the register

**Standing:** the index over [`notes/`](notes/). Each note argues one decision and carries
its own `Standing:` line; this page is the one-screen view. Last checked 2026-09-04.

Rule: a decision is argued in **exactly one** note. Every other document states the result
in one sentence and links the note. Nothing re-argues a decision elsewhere.

## Decisions taken

| Decision | Result | Standing | Note |
|---|---|---|---|
| Patient data in git | Absolute prohibition, any size. Aggregates only. | firm — follows from the DTA, not a preference | [note](notes/no-patient-data-in-the-repository.md) |
| Test data | Synthetic fixtures; only plaintext VCFs may enter git | firm — follows from the above | [note](notes/synthetic-fixtures.md) |
| The delivered bytes | Versioned bucket + hash verification is the source of truth; everything else is derived | firm — 12/12 verified 2026-08-29 | [note](step-0/notes/delivery-is-immutable.md) |
| Where shared state lives | Postgres for mutable shared state, Parquet for bulk immutable reads, DuckDB as the engine over both | firm | [note](step-0/notes/postgres-for-shared-state.md) |
| Retire the DuckDB file-warehouse (Path A) | **Decided 2026-08-29: deleted.** `remote.py` and the `preflight`/`provision`/`push`/`load`/`ship`/`local`/`query` verbs are gone; `catalog.py` + `stage.py` + the `stage` verb stay because `pg-ingest` reads their Parquet. Rationale: no data-manipulation strategy is settled yet, everything upstream is drafts, and one-off local DuckDB work is a plain Python script — Postgres + MinIO is the platform. | firm | [note](step-0/notes/postgres-for-shared-state.md) |
| Chromosome naming | The `chr` prefix is added in one function, `pipeline/variant.py` | firm — enforced by test | [note](step-0/notes/chr-prefix-bridge.md) |
| Colour in the app | **Decided 2026-09-02:** generated. One script converts Tailwind's own theme once and writes both halves — hex ramps for Plotly/SVG, `--color-*` properties for the classes — because the DOM and a canvas cannot share a mechanism. Components speak in six `Tone`s, never hues. | firm — four gates (`theme:check`, a token test, two eslint rules) | [note](step-0/notes/colour-is-generated.md) |
| The dictionary in the app | **Decided 2026-09-03:** generated, never copied. `docs/dictionary.md` stays the one glossary; `app/tools/gen-dictionary.mjs` turns it into the artifact `/learn` renders, and the generator doubles as the dictionary's link checker. Pages link a word (`dict:` on an Explainer chip) and never restate it. | firm — `dictionary:check` in the gate plus three test files | [note](step-0/notes/dictionary-is-generated-into-the-app.md) |
| 3D in the app | **Built 2026-09-03:** one 3D exhibit only — the candidate protein with both alleles painted on residues — because it is the one view where the third dimension *is* the finding. Raw `three` (React 18 blocks fiber 9), one lazy wrapper in a case-agnostic `src/viz3d/` that imports `lib` only. Every "3D failure locator" rejected on cardinality; two 2D alternatives named instead. | firm — one module, one exhibit | [note](step-0/notes/three-js-behind-one-wrapper.md) |
| The structure toolkit's reuse seams | **Decided 2026-09-03:** a display **group** is a free-form id carrying its own `group_label` and `group_order` in the reference table, and colour is assigned by rank; `in_panel` is the *only* semantic flag an exhibit may branch on. So a new case is one spec TSV, and no type, route or component changes. | firm — asserted over a foreign spec (Python) and invented groups (app), so a layer that re-learns this case's names fails a test | [note](notes/reusable-structure-toolkit.md) |
| Functional annotation | Enters through a port; Ensembl VEP REST is the backend for the panel (entry 031), the genome-wide backend is still open | port settled, panel backend settled, genome-wide open | [note](notes/annotation-as-a-port.md) |
| Scorer | A local transcription of the published evaluation code, for rehearsing probes offline | settled for the challenge | [note](notes/local-scorer-replica.md) |
| VCF parsing | Hand-rolled reader for the four FORMAT fields we need; `bcftools` still does the heavy lifting | provisional — revisit if real VCF surface area is needed | [note](notes/hand-rolled-vcf-reader.md) |
| The ranked unit | A pair, not a variant, and pairs must sit in one gene | follows from the answer key; the scoring function inside is provisional | [note](notes/ranking-pairs-not-variants.md) |
| Bio toolchain | micromamba into `~/.local` — no root available | provisional; revisit on Modal | [note](step-0/notes/toolchain-choice.md) |
| How findings are recorded | **Decided 2026-08-29:** a hypothesis register, not an ADR log. Every research step declares one goal; every claim under it states its prediction and what would refute it *before* the test; every observation is an evidence row naming its source; every verdict is weighed and appended as a revision. Step 0 stays a decision log — machinery is judged by whether it works, not by whether it is true. | firm — the rules are enforced by constructors, not by a template | [`method.md`](method.md), [`017`](step-0/methodology/017-the-research-record.md) |
| Step 0 is closed | **Decided 2026-09-04:** the platform step closed at methodology entry 068. A tool a research step needs is recorded under that step; only a cross-step platform fix still lands in step-0, naming the step that needed it. Entry numbers stay global (next 069). | firm | [`step-0/README.md`](step-0/README.md), [`068`](step-0/methodology/068-step-0-close-out.md) |
| Oracle budget | **Corrected 2026-09-04:** 6 submissions per registered member and one member is registered, so 6, not 18. `BUDGET` in `warehouse/probes.py` is `6 × MVA_TEAM_MEMBERS`. Keep at least one in reserve to the freeze. | firm — follows from the roster | [`hackathon-intel.md` §7](../ideation/hackathon-intel.md) |
| Retrospective claims | **Decided 2026-09-04:** a hypothesis whose test already ran inside step 0 may be filed, prefixed `retrospective:`, citing the entry that ran; it never counts as pre-registered. | firm | [`method.md`](method.md) |
| When to spend a probe | **Gate fixed 2026-09-04, date open:** no upload before the callset is normalized, the hypotheses are filed, the CSV is rehearsed on the scorer replica, and two independent methods agree. Timing is decided when step 6 opens. | firm gate, open date | [`roadmap.md`](roadmap.md) step 6 |
| How confidence is assigned | A log-odds accumulation over evidence strengths that **suggests** a number and prints its arithmetic; committing takes a human, `--commit` and a stated reason | firm as a triage heuristic — explicitly **not** a calibrated posterior, and quoted that way everywhere | [`method.md`](method.md) |
| Phenotype ranking | Reimplemented in Python from HPO's plain-text files rather than running Exomiser: its bundles are Java-only H2 databases at 31.5 GB unpacked, and the published optimisation study puts the **human-only** configuration 16.2 points ahead of the cross-species default — so the components that are hard to reproduce are the ones to omit | settled for this project; revisit if a JVM ever becomes acceptable | [step-3/methodology/067](step-3/methodology/067-phenotype-ranking-without-java.md) |

## Open decisions

| Question | Why it is still open |
|---|---|
| Which annotation backend? | Ensembl VEP REST is right for the panel variants today; an offline cache is right for the genome-wide run. Both, staged, is the current lean — see [`roadmap.md`](roadmap.md). |
| Layer-2 schema details | Multi-allelic splitting and INFO-as-columns-vs-MAP are recorded but unresolved — see [`data-layers.md`](step-0/data-layers.md). |
| How to close the object-store SSL gap | Tunnel, TLS reverse proxy, or firewall. Not chosen. |
| Are the evidence strengths calibrated? | No, and deliberately so for now. Rows drawn from the same underlying data are not independent the way the log-odds sum treats them. A calibrated alternative would need either held-out cases or an explicit dependency structure; neither exists at N=1. Recorded as a limitation rather than solved — see [`method.md`](method.md). |

## The original recommendation matrix

Extracted 2026-08-29 from `ideation/draft0-answers.md` §0.1, now in
[`archive/`](../archive/draft0-answers.md). This is the **strategy** sweep taken before
most of the pipeline existed. Rows that later became real decisions are linked to their
note; the rest are recorded direction, not commitments, and several are not started.

| # | Question | Recommended option | Why it beat the alternatives | Since |
|---|---|---|---|---|
| 1 | Data handling | Headers-first checklist, then a **mapping-free k-mer strike** on the FASTQ for published MVA alleles, with alignment launched in parallel on day 1 | detects a known allele in minutes with no alignment; with no BAM shipped, alignment is a 1–2 day dependency | checklist **done** ([`methodology/001`–`006`](step-0/methodology/)); k-mer strike and alignment **not started** |
| 2 | Query / visualize | DuckDB + Parquet for SQL, `slivar` for comp-het logic, igv-reports for evidence | zero infra, deterministic, reproducible; dashboards are a week-3 luxury | partly superseded — DuckDB is the engine, but shared state moved to [Postgres](step-0/notes/postgres-for-shared-state.md) |
| 3 | Disease model | Soft Bayesian gene priors **flattened** against the measured phenotype, never hard gene exclusion | rhabdomyosarcoma still favours *BUB1B*, but absent microcephaly promotes the *TP53*/*DICER1* differentials — a hard filter was always the classic trap | direction only; no prior implemented |
| 4 | Literature | Automated **reported-allele catalogue** (PubTator3/LitVar2 + ClinVar) joined against the VCF, LLM triage on top | a published-allele match is a near-instant solve; the join is mechanical | not started |
| 5 | Data structures | Scorer-identical dataclasses + DuckDB + a **probe simulator** with a bitmask hypothesis space, plus one contig-namespace conversion | the simulator turns probe design into computed optimization; the namespace conversion is a live scoring bug if done by hand | dataclasses and the [scorer replica](notes/local-scorer-replica.md) **done**; [contig conversion](step-0/notes/chr-prefix-bridge.md) **done**; probe simulator **not started** |
| 6 | Models | Tiered escalation: **free tier (non-PASS + `1/2` sites)** → standard stack → raw-data rescue → foundation models | tier 1.5 is minutes and targets "the caller saw it and suppressed it"; tier 2 is the only source of SV evidence that will ever exist | sequencing kept in [`roadmap.md`](roadmap.md); nothing executed |
| 7 | Statistics | Bayesian ACMG posterior as the `epcr` backbone; greedy info-gain probe policy | defensible arithmetic in the report; the decode tables are already near-optimal | partly — the [evidence weighing](method.md) is a log-odds accumulation with visible arithmetic, but it is a triage heuristic, not an ACMG posterior; the probe policy is not started |
| 8 | ML | Reciprocal-rank fusion primary + an audited LLM evidence-tournament re-ranker | robust at N=1, transparent, and the agentic layer is the Innovation story | not started |
| 9 | Evaluation | Local scorer reimplementation + GIAB spike-in probands + read-level spiked alleles | the only honest pre-oracle measurement | [scorer replica](notes/local-scorer-replica.md) **done**; spike-ins **not started** |
| 10 | Deterministic vs probabilistic | Deterministic shrink → probabilistic rank → decision-theoretic probe | soundness first, efficiency second; filters logged with removal counts | deterministic layer built ([`pipeline/`](../src/mva/pipeline/)); probabilistic layer not |
| 11 | Database | No new curated DB; a thin analytical layer; optionally publish a public-only N-of-1 toolkit | reproducibility + scalability points without curation liability | **holds** — no curated database was built |
