# Lens: experimental biology, clinical and life sciences

Use for wet-lab, animal, clinical, epidemiological, ecological and genomics *experiments*. The core question: **do the design, controls and sample size support the causal or predictive reading the authors give the result?**

The tradition here is critical appraisal (CASP, Cochrane Risk of Bias, JBI). Those checklists are written for medicine; the questions below generalise them to any experimental biology paper. Answer them in the report's "Validity, bias & reproducibility" section, and feed findings into "Limitations - not stated".

## 1. Question and design
- Is there a focused question with a defined population/system, intervention or exposure, comparator, and outcome (PICO/PECO)? Vague questions permit post-hoc storytelling.
- Is the design capable of answering it? Observational designs cannot establish causation; in-vitro results do not establish in-vivo effects; animal models do not establish human effects. Note each inferential leap the authors make.
- Was the study pre-registered or the hypothesis stated before data collection? If exploratory, is it labelled as such?

## 2. Controls
- Negative controls (no treatment, vehicle, scrambled sequence, isotype antibody), positive controls (a known effect), and technical controls (loading controls, housekeeping genes, spike-ins).
- Are controls processed alongside samples (same batch, same day, same operator)? Batch confounding is the most common silent failure in omics data.
- For knockouts/knockdowns: is the effect rescued? Off-target checks?

## 3. Sample size, replication and units
- Biological vs technical replicates: three wells from the same culture are one biological replicate. Check the *n* definition in figure legends.
- Sample size justification or power calculation. Small n with large effect claims is fragile; small n with a null result proves nothing.
- Independence: repeated measures on the same animals or patients treated as independent inflate significance.
- Is the number of animals/patients that started the same as the number analysed? Where did the rest go?

## 4. Randomisation, blinding and allocation
- Were subjects randomised to groups? How?
- Were experimenters and assessors blinded, especially for subjective readouts (histology scoring, behaviour)?
- Allocation concealment in trials.

## 5. Measurement
- Are the assays validated for this use (antibody specificity, primer efficiency, instrument calibration)?
- Are the outcomes the pre-specified primary outcomes, or were secondary outcomes promoted after the fact?
- Surrogate endpoints versus clinically or biologically meaningful ones.

## 6. Statistics
- Test matches the data type and design (paired vs unpaired, parametric assumptions checked, corrections for multiple comparisons in omics - FDR, Bonferroni).
- Effect sizes and confidence intervals reported, not only p-values. "Significant" with a trivial effect size is not a finding.
- p-hacking signals: many p-values just under 0.05; outcomes switched between methods and results; subgroup analyses without correction.
- For omics: were the differential expression thresholds pre-specified? How many tests were run?

## 7. Reporting completeness
- Reagent identifiers (RRIDs, catalogue numbers, cell line authentication, mycoplasma testing).
- Species, strain, sex, age; sex as a biological variable considered?
- Raw data deposited (GEO, SRA, PRIDE, PDB, Zenodo) with accession numbers that resolve.
- Reporting guideline followed (ARRIVE for animals, CONSORT for trials, STROBE for observational, MIAME/MINSEQE for arrays/sequencing)?

## 8. Interpretation
- Do conclusions stay within the design's reach? "Associated with" becoming "causes" in the discussion or abstract is common.
- Are alternative explanations considered (confounding, reverse causation, selection bias, regression to the mean)?
- Are negative or inconsistent results shown and discussed, or only the supportive ones?
- Generalisability: from this strain, cell line, cohort, or population to the ones the abstract implies.

## 9. Images and blots
- Western blots: full-length blots in supplement, loading controls from the same blot, no unexplained splices. Quantification from at least three biological replicates.
- Micrographs: representative image plus quantification; scale bars; same magnification across conditions.
- Duplicated or mirrored image panels across figures or papers are a serious integrity flag - describe what you observed rather than accusing.

## 10. Conflicts and provenance
- Funding source and author conflicts, especially when the intervention is a product.
- Journal quality; predatory venue signals (no peer review timeline, unusually fast acceptance).
- Retraction or expression-of-concern check via the metadata step or a search of the title with "retraction".

## 11. Evidence synthesis (systematic reviews and meta-analyses)
- Search reproducible (databases, dates, query strings, PRISMA flow diagram).
- Inclusion criteria fixed in advance; two independent screeners.
- Risk-of-bias assessment of included studies (RoB 2, ROBINS-I, Newcastle-Ottawa).
- Heterogeneity reported (I²) and explored; publication bias assessed (funnel plot, Egger's test).
- Certainty grading (GRADE) for each outcome.

## Reproducibility score cues for this lens
- 5: full protocol, all raw data deposited, reagents identified, code for analysis released, independent replication published
- 4: full protocol, data deposited, reagents identified; no independent replication
- 3: protocol reasonably complete but data or key reagent details missing
- 2: methods summarised, data "available on request"
- 1: key steps missing (concentrations, timings, n per group unclear)

## Vocabulary a newcomer will need
Add these to the glossary when they appear: biological vs technical replicate, negative/positive control, vehicle, knockdown vs knockout, rescue experiment, batch effect, FDR, effect size, confidence interval, power, blinding, PICO, surrogate endpoint, pre-registration, RRID, accession number.
