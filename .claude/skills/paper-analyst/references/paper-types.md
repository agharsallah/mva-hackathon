# Paper types: what each one owes the reader

Classify in Pass 1 from the abstract, contribution list and section structure. Many papers are mixed (a new method plus a new benchmark); pick the dominant type and note the secondary one. The type sets the standard you judge against - the most common analytic error is grading a survey as if it were an experiment, or a theory paper for lacking error bars.

## Empirical / method paper
*"We propose X and show it beats Y on Z."*  The bulk of ML, NLP, vision, and many bioinformatics papers.
- Owes: a clear problem statement, a described method, fair comparison to the strongest existing baselines under equal conditions, ablations showing which parts matter, variance across runs, and enough detail to reproduce.
- Judge by: would the gain survive a different seed, dataset split, or a properly tuned baseline? Is the improvement practically meaningful or only statistically detectable?
- Typical hidden weaknesses: baselines run with default settings while the new method is tuned; benchmark chosen after seeing results; test set used for model selection.

## Theoretical paper
*"We prove that X holds under assumptions A, B."*
- Owes: precise statements, assumptions listed up front, proofs (or proof sketches with full proofs in the appendix), and a discussion of how restrictive the assumptions are.
- Judge by: do the assumptions match any real setting? Does the theorem say what the abstract implies it says (watch for a strong abstract and a weak theorem)? Are there toy experiments illustrating the result, and do they match the theory's predictions?
- Do not penalise the absence of large-scale experiments. Do flag when a "theoretical guarantee" is quoted by later work as if it applied in practice.

## Systems paper
*"We built X; it is faster/cheaper/more scalable."*
- Owes: architecture and design decisions with rationale, a realistic workload, comparison to production alternatives, measurements of the claimed property (latency, throughput, cost) with variance, and honesty about what was not built.
- Judge by: is the workload representative? Are the competitors configured competently? Does the evaluation isolate the design choice being credited?

## Survey / review
*"We organise the literature on X."*
- Owes: a stated scope and search method (for systematic reviews: databases, queries, inclusion criteria, PRISMA-style flow), a taxonomy that adds structure, coverage of the important work, and open problems.
- Judge by: is the taxonomy useful or merely a list? Is the coverage balanced or centred on the authors' group? Are conflicting findings in the literature acknowledged? For systematic reviews and meta-analyses, apply the bio lens's evidence-synthesis checks (risk of bias assessment, heterogeneity, publication bias).
- Do not expect novel results. Do expect the "what works / doesn't" section of your report to summarise the field's findings rather than the paper's.

## Dataset / benchmark paper
*"We release X, a dataset/benchmark for Y."*
- Owes: collection process, provenance and licensing, annotation protocol and agreement statistics, known biases and coverage gaps, a datasheet or data card, baseline results, and a metric with a justification.
- Judge by: does the benchmark measure the capability it claims to? Could models exploit artefacts? Is the test set contaminated in public pretraining corpora? Are the baselines meaningful?
- The authors' own model winning is not the point; ignore that claim's strength.

## Position / perspective paper
*"We argue the field should X."*
- Owes: a clear thesis, engagement with the strongest counter-arguments, and evidence or examples for each premise.
- Judge by: is the argument valid given the premises, and are the premises supported? Are alternatives given a fair hearing?
- Claims table entries are premises, not results; strength ratings refer to the support for each premise.

## Replication / reproduction study
*"We tried to reproduce X."*
- Owes: fidelity to the original protocol, a clear account of deviations, contact with original authors if results differ, and a distinction between "did not reproduce" and "could not run".
- Judge by: were deviations necessary and acknowledged? Does the study over-claim failure from a single attempt?

## Clinical / experimental biology paper
*"We tested whether X causes/predicts Y in cells/animals/patients."*
- Owes: pre-registration or a stated hypothesis, controls, randomisation and blinding where relevant, sample size justification, appropriate statistics, and effect sizes with confidence intervals.
- The bio lens covers the details; classify here so the report's "Paper type & how to read it" section tells the newcomer why controls matter more than a fancy model.

## Bioinformatics method / resource paper
*"We present a tool/pipeline/database for X."*
- Owes: what the ML/CS method paper owes, plus biological validation (does the prediction match wet-lab truth, not just a held-out split) and a data-leakage story (were related sequences/structures separated between train and test?). For databases: update policy, versioning, download format, licence.

## Quick classification cues

| Cue | Points to |
|---|---|
| "We propose", benchmark tables with bold best numbers | empirical |
| Theorem/Lemma/Proof environments dominate | theoretical |
| Throughput/latency plots, "deployed at" | systems |
| "We survey", taxonomy figure, 100+ references | survey |
| "We introduce a dataset", datasheet, annotation agreement | dataset-benchmark |
| "We argue", few or no experiments | position |
| "We attempt to reproduce" | replication |
| Methods section with reagents, cohorts, p-values | biology |
| Software availability statement, benchmark on CASP/CAFA/etc. | bioinformatics |
