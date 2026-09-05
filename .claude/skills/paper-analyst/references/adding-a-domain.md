# Adding a domain lens

The skill ships with lenses for ML/CS, experimental biology, and bioinformatics. When a paper comes from another field, use the closest existing lens, say in the report that no dedicated lens exists yet, and - if the user is likely to read more papers from that field - offer to add one. A lens file is short: 60-120 lines of questions, each with why it matters and what a red flag looks like.

## What every lens needs

1. **Core question** - one sentence stating what "good evidence" means in this field. Examples:
   - Economics: "Is the identification strategy credible, and is the effect economically meaningful, not just significant?"
   - Psychology / social science: "Was the study pre-registered and powered, and does the measure capture the construct?"
   - Chemistry / materials: "Are characterisation data sufficient to establish the claimed structure and purity, and were yields and conditions reported fully?"
   - Physics / engineering: "Are uncertainties propagated, and are systematic errors bounded, not just statistical ones?"
   - Mathematics: "Are the proofs complete and the statements as strong as the abstract implies?"
2. **Sections** following the same shape as the existing lenses: framing, comparison/baselines or controls, data/sample, statistics or proofs, reporting standards, interpretation, field-specific traps, reproducibility score cues, vocabulary for the glossary.
3. **Field reporting guidelines** to check against (e.g. CONSORT, PRISMA, ARRIVE, APA JARS, EQUATOR network entries, journal-specific checklists).
4. **Community benchmarks or standards** if they exist, so author-defined evaluations can be spotted.
5. **Reproducibility score cues** mapped to the 1-5 scale used in the report template.

## How to build one quickly

- Ask the user for two or three papers they consider well done and one they distrust; the differences usually reveal the field's standards.
- Search for "<field> critical appraisal checklist", "<field> reporting guidelines", "<field> replication crisis" and "<field> reviewer guidelines" - reviewer guidelines from the field's main conference or journal are the richest source.
- Write the questions in the same voice as the existing lenses: question, why it matters, red flag.
- Save as `references/lens-<field>.md`, add a row to the "Choosing the lens" table in SKILL.md and to the reference file table, and add the field's cue words to `paper-types.md` if a new paper type appears (e.g. "field study", "case report").

## Keeping lenses honest

A lens is a list of questions, not a verdict machine. Papers can be excellent while failing a checklist item for good reasons, and the report should say when a "missing" element is genuinely inapplicable rather than penalise it. When a lens item and the paper's field conventions conflict, explain the convention to the newcomer instead of marking the paper down.
