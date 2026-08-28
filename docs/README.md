# Documentation

Start here, in this order.

| Document | Answers |
|---|---|
| [`../CONTEXT.md`](../CONTEXT.md) | What do the words mean? Domain vocabulary — proband, cis/trans, epcr, probe, non-PASS. |
| [`architecture.md`](architecture.md) | How do the pieces fit? Data flow, seams, sharp edges, extension points. |
| [`roadmap.md`](roadmap.md) | What is done, what is next, and how the 80 GB gets handled. |
| [`../ideation/data-findings.md`](../ideation/data-findings.md) | What is actually in the data? Measured, not assumed. |
| [`../ideation/hackathon-intel.md`](../ideation/hackathon-intel.md) | What is the strategy? Scoring mechanics, probe protocol, timeline. |
| [`../ressources/data-profile/`](../ressources/data-profile/) | The raw evidence behind the findings. |
| [`../methodology/`](../methodology/) | How was each result reached? One entry per analysis actually run — inputs, commands, observed output, conclusion. |

## Design notes

Why the code currently looks the way it does. These are working notes, not commitments —
we are still exploring, so each one carries its standing: what is settled, what is
provisional, and what would prompt a rethink.

| Note | Standing |
|---|---|
| [No patient data in the repository](notes/no-patient-data-in-the-repository.md) | firm — follows from the DTA |
| [Synthetic fixtures](notes/synthetic-fixtures.md) | firm — follows from the above |
| [Annotation enters through a port](notes/annotation-as-a-port.md) | port settled, backend open |
| [A local replica of the scorer](notes/local-scorer-replica.md) | settled for the challenge |
| [A hand-rolled VCF reader](notes/hand-rolled-vcf-reader.md) | provisional |
| [Ranking pairs, not variants](notes/ranking-pairs-not-variants.md) | follows from the answer key |
| [Toolchain choice](notes/toolchain-choice.md) | provisional |
