# Documentation index

**Standing:** the single index. Every live document in the repository is listed here; if a
doc is not on this page it does not exist yet. Last checked 2026-08-29.

Each topic has exactly one owner. Before writing a new doc, extend the owner below.

## Start here

| Document | Answers |
|---|---|
| [`current-state.md`](current-state.md) | What exists right now? Provisioned infrastructure, what runs, repo layout, known gaps. Owns repo and infra numbers. |
| [`dictionary.md`](dictionary.md) | I have no genetics background — what *is* any of this? Every domain term from scratch, with diagrams. |
| [`../CONTEXT.md`](../CONTEXT.md) | Which word do we use for it? Naming discipline for code and write-ups, plus what to avoid. |

## The system

| Document | Answers |
|---|---|
| [`architecture.md`](architecture.md) | How do the pieces fit? Data flow, seams, sharp edges, extension points. |
| [`exploration.md`](exploration.md) | How do I actually *look* at the data? The exploration toolkit — exhibits, graded checks, one interactive page. |
| [`infrastructure.md`](infrastructure.md) | How do I operate Postgres and the object store? Setup, verbs, tunnels, credentials. |
| [`data-layers.md`](data-layers.md) | What shape does the data take on the way in? Layer 0 bytes → layer 1 anchor → layer 2 typed tables. |
| [`reads-storage.md`](reads-storage.md) | Where do the raw reads go, and what can you ask of them? A design study — not built. |

## Direction and reasoning

| Document | Answers |
|---|---|
| [`roadmap.md`](roadmap.md) | What is next, in dependency order, and how the full 80 GB gets handled. |
| [`decisions.md`](decisions.md) | What was decided and does it still hold? The register over `notes/`. |
| [`notes/`](notes/) | Why the code looks like this. One decision per file, each with a `Standing:` line. |

## Evidence

| Document | Answers |
|---|---|
| [`../ideation/data-findings.md`](../ideation/data-findings.md) | What is actually in the data? Measured, not assumed. **Owns every dataset number.** |
| [`../ideation/hackathon-intel.md`](../ideation/hackathon-intel.md) | What is the strategy? Scoring mechanics, oracle protocol, master plan. |
| [`../ressources/hackathon-rules/`](../ressources/hackathon-rules/) | The challenge documents: phenotype, submission contract, methods form, rules. |
| [`../ressources/data-profile/`](../ressources/data-profile/) | The raw evidence behind the findings. |
| [`../methodology/`](../methodology/) | How was each result reached? One append-only entry per analysis run. |
| [`../figures/`](../figures/) | The generated report artifacts. |
| [`../archive/`](../archive/) | Superseded documents, kept for provenance. Never current. |

## Design notes

Working notes, not commitments. Each carries its standing: what is settled, what is
provisional, what would prompt a rethink. Full register with results:
[`decisions.md`](decisions.md).

| Note | Standing |
|---|---|
| [No patient data in the repository](notes/no-patient-data-in-the-repository.md) | firm — follows from the DTA |
| [Synthetic fixtures](notes/synthetic-fixtures.md) | firm — follows from the above |
| [Delivery is immutable](notes/delivery-is-immutable.md) | firm — verified 12/12 hashes |
| [Postgres for shared state](notes/postgres-for-shared-state.md) | settled; Path A retirement open |
| [The chr-prefix bridge](notes/chr-prefix-bridge.md) | firm — one function, enforced by test |
| [Annotation enters through a port](notes/annotation-as-a-port.md) | port settled, backend open |
| [A local replica of the scorer](notes/local-scorer-replica.md) | settled for the challenge |
| [A hand-rolled VCF reader](notes/hand-rolled-vcf-reader.md) | provisional |
| [Ranking pairs, not variants](notes/ranking-pairs-not-variants.md) | follows from the answer key |
| [Toolchain choice](notes/toolchain-choice.md) | provisional |
