# Documentation index

**Standing:** the single index. Every live document in the repository is listed here; if a
doc is not on this page it does not exist yet. Last checked 2026-08-29.

Each topic has exactly one owner. Before writing a new doc, extend the owner below.

Work is grouped by **step**, matching [`roadmap.md`](roadmap.md). Everything already built
— the delivery, the object store, the warehouse, the exploration toolkit — is
[step 0](step-0/README.md). The pages below it are cross-step: they describe the whole
project, not one phase of it.

## Start here

| Document | Answers |
|---|---|
| [`current-state.md`](current-state.md) | What exists right now? Provisioned infrastructure, what runs, repo layout, known gaps. Owns repo and infra numbers. |
| [`dictionary.md`](dictionary.md) | I have no genetics background — what *is* any of this? Every domain term from scratch, with diagrams. |
| [`../CONTEXT.md`](../CONTEXT.md) | Which word do we use for it? Naming discipline for code and write-ups, plus what to avoid. |

## Step 0 — the platform (built)

Full index and what "step 0" covers: [`step-0/README.md`](step-0/README.md).

| Document | Answers |
|---|---|
| [`step-0/architecture.md`](step-0/architecture.md) | How do the pieces fit? Data flow, seams, sharp edges, extension points. |
| [`step-0/infrastructure.md`](step-0/infrastructure.md) | How do I operate Postgres and the object store? Setup, verbs, tunnels, credentials. |
| [`step-0/data-layers.md`](step-0/data-layers.md) | What shape does the data take on the way in? Layer 0 bytes → layer 1 anchor → layer 2 typed tables. |
| [`step-0/exploration.md`](step-0/exploration.md) | How do I actually *look* at the data? The exploration toolkit — exhibits, graded checks, one interactive page. |
| [`step-0/reads-storage.md`](step-0/reads-storage.md) | Where do the raw reads go, and what can you ask of them? A design study — not built. |
| [`step-0/methodology/`](step-0/methodology/) | How was each step-0 result reached? One append-only entry per executed run, 001–016. |
| [`step-0/notes/`](step-0/notes/) | Why the platform looks like this. Four decisions, one file each. |

## Direction and reasoning

| Document | Answers |
|---|---|
| [`roadmap.md`](roadmap.md) | What is next, in dependency order, and how the full 80 GB gets handled. |
| [`../ideation/solution-paths.md`](../ideation/solution-paths.md) | Six routes to the causal pair, conventional → inventive, and when to spend a probe. Owns the portfolio. |
| [`decisions.md`](decisions.md) | What was decided and does it still hold? The register over every `notes/` file, step-0 included. |
| [`notes/`](notes/) | Why the *pipeline* looks like this — the decisions not yet tied to a built step. |

## Evidence

| Document | Answers |
|---|---|
| [`../ideation/data-findings.md`](../ideation/data-findings.md) | What is actually in the data? Measured, not assumed. **Owns every dataset number.** |
| [`../ideation/hackathon-intel.md`](../ideation/hackathon-intel.md) | What is the strategy? Scoring mechanics, oracle protocol, master plan. |
| [`../ressources/hackathon-rules/`](../ressources/hackathon-rules/) | The challenge documents: phenotype, submission contract, methods form, rules. |
| [`../ressources/data-profile/`](../ressources/data-profile/) | The raw evidence behind the findings. |
| [`../figures/`](../figures/) | The generated report artifacts. |
| [`../archive/`](../archive/) | Superseded documents, kept for provenance. Never current. |

## Design notes

Working notes, not commitments. Each carries its standing: what is settled, what is
provisional, what would prompt a rethink. Full register with results:
[`decisions.md`](decisions.md).

| Note | Where | Standing |
|---|---|---|
| [No patient data in the repository](notes/no-patient-data-in-the-repository.md) | cross-step | firm — follows from the DTA |
| [Synthetic fixtures](notes/synthetic-fixtures.md) | cross-step | firm — follows from the above |
| [Delivery is immutable](step-0/notes/delivery-is-immutable.md) | step 0 | firm — verified 12/12 hashes |
| [Postgres for shared state](step-0/notes/postgres-for-shared-state.md) | step 0 | firm; Path A deleted 2026-08-29 |
| [The chr-prefix bridge](step-0/notes/chr-prefix-bridge.md) | step 0 | firm — one function, enforced by test |
| [Toolchain choice](step-0/notes/toolchain-choice.md) | step 0 | provisional |
| [A hand-rolled VCF reader](notes/hand-rolled-vcf-reader.md) | pipeline | provisional |
| [A local replica of the scorer](notes/local-scorer-replica.md) | pipeline | settled for the challenge |
| [Annotation enters through a port](notes/annotation-as-a-port.md) | pipeline | port settled, backend open |
| [Ranking pairs, not variants](notes/ranking-pairs-not-variants.md) | pipeline | follows from the answer key |
