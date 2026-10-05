# SEPIQ 2026 — antibody–antigen interface prediction

**Standing:** 2026-10-05 — the naming discipline for code and write-ups: one chosen word
per idea, plus what to avoid. Distinct from [`docs/dictionary.md`](docs/dictionary.md),
which *teaches* the concepts; this file *fixes the vocabulary*.

Predicting which residues form the interface between a VHH nanobody and HER2 (Track A),
and the atomic structure of that complex (Track B). The challenge statement is
[`docs/challenge.md`](docs/challenge.md).

The vocabulary below is what the code, the docs and the write-ups all use. Where the field
offers several words for one idea, one is picked and the rest are listed to avoid. **This
list grows as the work does** — an idea that gets a second name in a second module is a
naming failure to fix here, not a synonym to tolerate.

## Language

### The two molecules

**Binder**:
The VHH side of a pair, in code. Used wherever the chain's *role* is what matters — a
chain name, a record field, a function parameter.
_Avoid_: antibody, nanobody, ligand, query (as a field name)

**VHH**:
The same molecule, in prose and in documentation, where the reader needs the real word.
A single-domain antibody: one chain, ~120 residues, the whole binder.
_Avoid_: sdAb, single-domain Ab, camelid antibody

**Target**:
The HER2 side of a pair, in code. The counterpart to **binder**, for the same reason.
_Avoid_: antigen (as a field name), receptor, protein, subject

**Antigen**:
The same molecule, in prose. The thing being bound.
_Avoid_: substrate, host protein

**Chain**:
One sequence within a record, addressed by name (`binder`, `target`). Named, never
positional: an interface model that silently swapped its two inputs would still run.
_Avoid_: strand, sequence slot, input 1 / input 2

### The thing being predicted

**Epitope**:
The residues on the **target** that the binder touches.
_Avoid_: binding site (ambiguous — it does not say which side), antigenic determinant

**Paratope**:
The residues on the **binder** that do the touching.
_Avoid_: binding site, CDR (a paratope is mostly but not only inside the CDRs)

**Interface**:
Both sides together. Use it only when both are meant; otherwise say epitope or paratope.
_Avoid_: contact region, binding interface (redundant)

**Contact map**:
The boolean `len(binder) × len(target)` matrix. "Interface residues" is that matrix
collapsed onto one axis — say which.
_Avoid_: contact matrix, adjacency map, interaction map

### The data

**Record**:
One unit of work: named chains plus open metadata, keyed by a content-addressed `item_id`.
The thing a model scores. In code: `SequenceRecord`.
_Avoid_: sample, example, instance, datapoint, row

**Item id**:
The stable content key — 16 hex characters of SHA-256 over the chain contents. Two runs
that build the same record agree on its id without coordinating.
_Avoid_: hash, uid, key, record id

**Cluster**:
The organisers' sequence-family grouping, from the `Cluster` column. **The unit every
train/test split is taken over** — never the row.
_Avoid_: family, group, bucket

**Screen**:
The selection experiment the dataset came out of, as a whole.
_Avoid_: panning, assay, experiment (unqualified)

**Competition column**:
A count column measured with HER2 pre-blocked by a known antibody (trastuzumab,
pertuzumab, RabMAb). The route from sequence-level labels to coarse epitope labels.
_Avoid_: blocking column, inhibition column

**Sentinel**:
The `-500` that appears in score columns. Not a number — a marker. It is converted or
excluded explicitly, never arithmetic'd.
_Avoid_: missing value, NA, placeholder, floor

### The modelling

**Lane**:
One frozen third-party model behind the shared adapter contract. The unit of comparison.
_Avoid_: model run, predictor, pipeline, arm

**Model card**:
A lane's declaration — name, exact version, licence, what it reads, what may ship. A TOML
table in the registry, never a value hard-coded in Python.
_Avoid_: config, model spec, entry

**Tier**:
Where a lane runs: 1 = precomputed table, 2 = local CPU, 3 = remote GPU.
_Avoid_: level, class, stage

**Catalogue-adjacent**:
A lane trained on the same public data an evaluation is drawn from. Reported, never
silently dropped and never silently pooled.
_Avoid_: contaminated, leaky, pretrained-on-test

**Coverage**:
The fraction of a record set one lane can score. A lane at 40% is a lane with a stated
domain, not a broken lane.
_Avoid_: hit rate, applicability, recall (which means something else here)

### Results

**Split**:
A train/validation/test partition, **always taken over clusters**. Any quoted metric names
its split; a metric without one is not a result.
_Avoid_: fold, partition, holdout (unqualified)

**Leakage**:
Near-identical sequences appearing on both sides of a split. The single easiest way to get
a wrong answer on this dataset.
_Avoid_: contamination, overlap

**Manifest**:
The committed JSON beside a derived table recording how it was made — sources, parameters,
tool, version. A derived table without one is not a result.
_Avoid_: metadata, provenance file, lineage record

## Naming rules

- **One word per idea.** If a second name for the same thing appears in a second module,
  fix it here and in the code — do not let both live.
- **Role names in code, real names in prose.** `binder`/`target` as field names;
  VHH/antigen in the writing. The reader must learn the real word, and the code must not
  depend on which molecule happens to be which.
- **Never abbreviate in a public name.** `paratope`, not `para`. The cost of typing is
  paid once; the cost of decoding is paid by every reader.
- **A sentinel is never silently coerced.** `-500` is the standing example.
