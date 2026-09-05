# Assessing code and data

Run this when `scan_paper.py` or the metadata step finds a repository or dataset link. The goal is not to grade the repository for its own sake; it is to tell the reader (a) how much of the paper's result they could actually rerun, and (b) what it would take to reuse the method on their own problem.

Start with `inspect_repo.py`, then work through the sections below. Reproducibility numbers from conferences are sobering - roughly a third of "code available" claims at submission time do not survive reviewer checking - so verify rather than trust the paper's availability statement.

## 1. Availability and provenance
- Is the link live? Does the README name the paper? Is this the **official** implementation (authors' accounts, linked from the paper) or a **reimplementation**? Reimplementations are useful for learning but are not evidence that the paper's numbers hold.
- Licence: none (all rights reserved - you cannot legally reuse), permissive (MIT, BSD, Apache-2.0), copyleft (GPL - your derivative must be open), non-commercial (CC-BY-NC, research-only), or model-specific licences (weights under different terms from code). Flag any mismatch between the paper's claims of openness and the actual licence.
- Activity: last push date, open issues, whether archived. A repo untouched for three years with 40 open issues will not install cleanly.
- Issues mentioning "reproduce", "results", "mismatch", "different numbers": read the titles `inspect_repo.py` returns; they are the most honest reproducibility signal available.

## 2. ML Code Completeness Checklist
Five items, each yes / partial / no with the file that proves it:

| Item | Evidence to look for |
|---|---|
| Dependencies | requirements.txt, environment.yml, pyproject.toml, Dockerfile, renv.lock, DESCRIPTION; pinned versions are much better than unpinned |
| Training script | train.py or equivalent, a command in the README that reproduces training |
| Evaluation script | eval/evaluate/test script that produces the paper's metric |
| Pretrained models | checkpoint files, or links to Hugging Face / Zenodo / cloud storage that resolve |
| Results table | README table matching (or nearly matching) the paper's numbers |

`inspect_repo.py` guesses these from file names and README content; confirm by opening the files.

## 3. Paper-to-code consistency
Open the config files and the main training/inference script and compare against the paper:
- Hyperparameters (learning rate, batch size, epochs, temperature, thresholds)
- Model size (layers, hidden size, parameter count)
- Datasets and splits (are the same versions and splits used? any preprocessing not in the paper?)
- Metric implementation (does the eval code compute what the paper says, e.g. macro vs micro F1?)
- Tricks in code absent from the paper (warmup schedules, ensembling, test-time augmentation, early stopping on test)

Report matches and mismatches in a short table. Mismatches are common and not necessarily dishonest, but they change what a reader would need to do to reproduce.

## 4. Dry run protocol
Attempt this when the user wants `apply`, the repo is Python/R/Julia, and dependencies look installable in a sandbox. Time-box it to a few minutes; the aim is to learn whether the code runs at all, not to reproduce the paper.

1. Shallow clone (`inspect_repo.py --clone`) and read the README's quick-start.
2. Create an environment, install dependencies (`pip install -r requirements.txt --break-system-packages` in this sandbox). Record which packages fail and why (unavailable, version conflict, needs CUDA).
3. Run the smallest thing the README offers: unit tests, a demo notebook cell, inference on a bundled example, or `--help` on the main script.
4. Record the outcome in the report's "Dry run" field: **ran**, **installed but demo failed (error)**, **install failed (reason)**, or **skipped (reason: needs GPU / large download / not requested)**.

Never download multi-gigabyte datasets or weights, run training, or execute anything that needs credentials. If a step needs those, say so and stop.

## 5. Data assessment
For each dataset the paper uses or releases:
- Where is it (URL, accession), does the link resolve, and is a version or release date given?
- Licence and terms (research-only? attribution? redistribution of derivatives allowed?)
- Size and format; whether a small sample is available for testing.
- Documentation: datasheet, data card, README describing collection and known biases.
- Access restrictions (registration, DUA, controlled access for human data).
- Known problems: label noise reports, contamination in pretraining corpora, deprecations. Search the dataset name with "issues" or "errors" when it matters.
- For biology: accession numbers (GEO, SRA, PRIDE, PDB, ENA) that resolve; reference genome/proteome versions.

## 6. Concept-to-code map (learn + apply)
Pick the four to eight ideas that define the method and locate each in the code (file, class or function, line range if helpful). Add a reading note: what the variable names correspond to in the paper, and any default that differs from the paper. This table is what turns a paper into a learning resource - a newcomer can read the implementation next to the equation.

## 7. Adaptation plan (apply)
Write against the user's `my-context.md` when present; otherwise state your assumptions in the first line. Cover:

1. **Keep** - components that transfer unchanged.
2. **Swap** - data loaders, tokenisers/featurisers, label schemas, domain preprocessing, evaluation metrics. Name the files.
3. **Break first** - the step most likely to fail on the user's data (input format, sequence length, class count, missing modality) and how they would notice.
4. **Minimum viable experiment** - the smallest run that tests whether the method helps on their data before investing further; expected compute and time.
5. **Risks** - licence incompatibility, data scale mismatch, dependence on unreleased weights, maintenance burden, method assumptions the user's setting violates.
6. **Effort estimate** - hours/days for a competent engineer, with the main uncertainty named.

## 8. When there is no code
Say so plainly in the "Code & data" section, then still help: list what the paper gives (pseudocode, hyperparameters, architecture details), estimate what reimplementation would need, and search citing papers or GitHub for third-party implementations (report them as reimplementations). Set the Reproducibility score accordingly.
