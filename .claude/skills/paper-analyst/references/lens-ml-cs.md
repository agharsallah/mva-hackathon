# Lens: machine learning, AI and computer science

Use for algorithm, model, systems, benchmark, HCI and theory papers. The core question: **are the baselines and benchmarks fair, and would the gain survive a different seed, split, or a competently tuned competitor?**

Work through the sections below during Pass 2 and 3. Each question is followed by why it matters and what a red flag looks like. Answer in the report's "Validity, bias & reproducibility" section and feed specific findings into "Limitations - not stated".

## 1. Problem and framing
- Is the task the paper solves the task the abstract describes? Watch for a broad abstract ("general reasoning") and a narrow evaluation (one synthetic benchmark).
- Is the metric the community metric for that task, and if not, why? A new metric introduced alongside a new method deserves suspicion.
- Are there obvious simpler alternatives the paper does not mention (a linear model, a lookup table, a retrieval baseline, "just fine-tune the big model")?

## 2. Baselines
- Are the strongest recent baselines included, or older/weaker ones? Check the related-work section against the results table: a method praised in related work but missing from the table is a red flag.
- Were baselines tuned with the same budget as the proposed method? Look for "we use the default hyperparameters from the original paper" applied only to baselines.
- Are baseline numbers copied from other papers (different preprocessing, splits, or hardware) or rerun? Copied numbers are marked with citations in the table; rerun numbers usually are not.
- Is the proposed method's advantage larger than the variance between baseline runs?

## 3. Data and splits
- Train/validation/test discipline: was the test set touched during development? Papers that report "best of N on test" or tune on the test set are common.
- Contamination: for LLM-era papers, could the test data be in the pretraining corpus? Does the paper check?
- Distribution shift: are results shown on any data the method was not developed against?
- Dataset size and class balance; whether the datasets are standard versions (e.g. which ImageNet split, which GLUE tasks were dropped).

## 4. Statistical reporting
- Number of seeds/runs. Single-run results on small benchmarks are noise. Look for mean and standard deviation or confidence intervals.
- Significance tests where differences are small; effect sizes where differences are large.
- Bolded "best" numbers that differ from the runner-up by less than one standard deviation.
- Cherry-picked subsets: results reported on a subset of standard tasks without explaining the selection.

## 5. Ablations and analysis
- Does an ablation exist for each claimed component? A component with no ablation has no demonstrated contribution.
- Does performance degrade gracefully or collapse when a component is removed? Collapse often indicates the "component" is really the whole method.
- Is there analysis of *why* it works (probing, visualisation, failure cases), or only that it works?

## 6. Compute and scale
- Compute budget for the method versus baselines (parameters, FLOPs, GPU-hours, wall-clock). A 10x bigger model beating a smaller one is not a methodological advance.
- Does the gain persist at scale, or only at the scale tested? Do the authors extrapolate from small models?
- Energy/cost reporting if the paper claims efficiency.

## 7. Reproducibility (Pineau checklist, condensed)
For every model/algorithm: clear description, complexity analysis, code link. For theory: statement of assumptions, complete proofs. For datasets: statistics, splits, preprocessing, link or reason for withholding. For experiments: hyperparameter ranges and selection method, number of runs, central tendency and variation, runtime, hardware. Mark each as present/absent; the missing ones drive the Reproducibility score.

## 8. Systems-specific
- Workload realism: benchmark traces vs. production traces; microbenchmarks vs. end-to-end.
- Competitor configuration competence; version numbers.
- Isolation: does the experiment credit the right design decision, or a confounded bundle of changes?
- Failure modes, tail latency, resource limits - not just the mean.

## 9. Theory-specific
- Assumptions versus reality (i.i.d., convexity, infinite width, realizability).
- Does the theorem's rate/bound have practical content (constants, dependence on dimension)?
- Are the toy experiments consistent with the theorem's predictions, including where the theorem predicts failure?

## 10. Human-subject and HCI-specific
- Participant count and recruitment (students? crowd workers? experts?).
- Within- vs between-subject design; counterbalancing; learning effects.
- Ethics approval and consent.
- Qualitative claims supported by quotes or coded analysis, not vibes.

## 11. Broader concerns
- Dual-use, fairness, and privacy statements: present, and consistent with the method?
- Conflicts of interest: industry authors evaluating their own product; benchmarks owned by the authors.

## Reproducibility score cues for this lens
- 5: code + weights + configs + data; someone else has reproduced (check citing papers, Papers-with-Code-style leaderboards, GitHub issues)
- 4: everything released, no independent reproduction
- 3: code without weights/configs, or "code upon request"
- 2: detailed appendix, no code
- 1: hyperparameters or data unspecified
