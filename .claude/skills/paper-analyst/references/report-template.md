# Report template

Use this skeleton for every full analysis. Sections marked with a flag in brackets appear only when that flag is on; everything else always appears. Keep headings exactly as written so reports stay comparable across papers and can be parsed later. Write in the reader's language (the language of the request), but keep the headings in English so the index stays consistent.

Length guide: a typical paper produces 900-1,800 words plus tables. A screen-mode entry is 60-120 words. Do not pad; a short, honest section beats a long, vague one.

---

```markdown
---
title: "<full paper title>"
authors: [<Last, First>, ...]
year: <YYYY>
venue: "<conference or journal, or 'arXiv preprint'>"
doi: "<DOI or null>"
arxiv: "<arXiv ID or null>"
url: "<canonical URL>"
paper_type: <empirical | theoretical | systems | survey | dataset-benchmark | position | replication | mixed>
domains: [<field>, <subfield>, <technique>, <task>]
lens: <ml-cs | bio | bioinformatics | none>
modes: [<learn>, <apply>, ...]
code: "<repo URL or none>"
data: "<dataset URL(s) or none>"
relevance: <1-5 for this user's goal>
analysed: <YYYY-MM-DD>
analyst: paper-analyst
---

# <Paper title>

## Identity & citation
One block: authors, venue, year, DOI/arXiv, pages, open-access link. Then the three citation formats produced by `make_citation.py` in a fenced block (APA 7, BibTeX, Vancouver). Note the venue's nature if the reader wouldn't know it (e.g. "NeurIPS - top-tier ML conference, peer reviewed" vs "arXiv - not peer reviewed"). Never invent an impact factor or acceptance rate; if you look one up, cite it.

## Paper type & how to read it
One paragraph: the type (see paper-types.md), what that type owes the reader, and how that shaped this analysis. Example: "This is a dataset-benchmark paper, so the key questions are whether the data are representative and licensed, whether the baselines are meaningful, and whether the metric measures what it claims - not whether the authors' own model wins."

## One-minute pitch
Spoken register, 120-160 words, no jargon that isn't defined in the same breath: the problem, why it was hard, what the authors did, what happened, why anyone should care. Then a **TL;DR** of three sentences.

## Domains & keywords
Field > subfield > techniques > tasks/datasets. Include the fieldsOfStudy/topics from the metadata script if available, but curate them - drop generic ones.

## Problem & research questions
The gap the authors claim exists; the explicit or implied research questions/hypotheses; what a successful answer would look like in the authors' own framing. Quote the paper's own thesis sentence in under 15 words if there is one.

## Background primer  [learn]
What a newcomer needs to know before the method makes sense: the two or three prior ideas the paper builds on, each in a short paragraph with an analogy. Point to the cited works that introduced them. Finish with a "prerequisite reading" list of at most five items, ordered.

## Method
**In plain language.** No symbols, one analogy, what goes in and what comes out.
**Technically.** The actual pipeline/architecture/experimental design, key equations named (not necessarily reproduced), datasets, hyperparameters or protocol details that matter for reproduction, compute or lab resources used.

## Figures & tables check
A table, one row per figure/table that a claim rests on:

| Fig/Table | Page | What it shows | Claim it supports | Verdict | Note |
|---|---|---|---|---|---|
| Fig. 2 | 5 | ... | C1 | OK / Caution / Problem | e.g. no error bars; y-axis starts at 80% |

Then any recomputation you did ("Table 3: claimed +12.4% is +12.4 absolute points, i.e. +18% relative").

## Claims vs evidence
| # | Claim (paper's wording, short) | Evidence offered | Where | Strength | Analyst note |
|---|---|---|---|---|---|
| C1 | ... | ... | Sec 4.2, Tab 2 | strong / moderate / weak / unsupported | ... |

Strength definitions live in SKILL.md ("Writing for a newcomer"). List 4-8 claims; the contribution list in the introduction is the usual source.

## What works
Results that hold up, with the numbers and the conditions under which they hold. Include positive ablation findings ("removing X drops Y by Z, so X is doing real work").

## What doesn't work (or isn't shown)
Negative results, failure cases, settings where the method loses, ablations that show a component is unnecessary, and the experiments a reader would expect but that are absent. Absence of evidence is worth a line.

## Limitations
**Stated by the authors.** Bullet list, paraphrased.
**Not stated (analyst).** Bullet list. This is where the lens file earns its keep. If you found none, say "none beyond the stated ones" and why you believe that.

## Validity, bias & reproducibility
Apply the lens checklist here in prose, grouped: internal validity (does the design support the inference), external validity (does it generalise), reporting (seeds, variance, compute, protocol), and conflicts of interest or funding if disclosed. End with a **Reproducibility score** using this scale:

- **5** - code, data, weights and exact configs released; independent reproduction exists
- **4** - code and data released, configs complete, no independent reproduction yet
- **3** - code released but incomplete (missing data, weights, or configs), or data only
- **2** - detailed protocol in paper, no artefacts
- **1** - key details missing; reproduction would require guesswork

State the score and the single biggest obstacle.

## Related work & key citations
Group the paper's important references (from the reference list in metadata or the PDF):
- **Foundations** - ideas this paper builds on (2-4)
- **Competitors / baselines** - what it is compared against (2-5)
- **Data & tools** - datasets, benchmarks, libraries used
Each entry: `Author (Year) - Title - one line on why it matters here`. Mark which of these the reader should read next, and in what order.

## Impact & follow-ups
Citation count and date checked; most influential citing papers (Semantic Scholar's `isInfluential`); whether later work confirms, extends, or contradicts the result; any erratum, retraction, or known reproduction attempt. If the paper is under six months old, say that impact can't be judged yet. Mark "unverified" if the metadata step failed.

## Code & data
**Availability.** Repo URL, official or reimplementation, licence, last commit, stars, open issues mentioning reproduction. Data: where, licence, size, format, access restrictions.
**Completeness.** The five checklist items as a table with yes/no/partial and evidence.
**Paper-to-code consistency.** Hyperparameters, model sizes, datasets, metrics - match or mismatch.
**Dry run.** What was attempted and the outcome (installed? demo ran? which errors?), or why it was skipped.

## Concept-to-code map  [learn + apply]
| Concept in the paper | Where it lives in the code | Reading note |
|---|---|---|
| e.g. contrastive loss (Eq. 3) | `losses/nt_xent.py::NTXentLoss` | temperature is `tau`, default 0.07 matches paper |

## Adaptation plan  [apply]
Written against the user's context if known, otherwise against stated assumptions:
1. What to keep as-is
2. What to swap (data loaders, labels, domain-specific preprocessing)
3. What will break first and how you'd know
4. Compute/time estimate and the minimum viable experiment to run before committing
5. Risks: licence, data mismatch, scale, missing pieces

## Positioning  [review]
One paragraph a related-work section could absorb: what strand of the literature the paper belongs to, what it adds over its nearest neighbours, and what it leaves open. Then a **citation-ready summary** of 60-90 words in neutral academic register.

## Referee report  [critique]
Summary of contribution, then **Major issues** (each: what, why it matters, what would fix it) and **Minor issues**. End with a recommendation line (accept / minor revision / major revision / reject) and the confidence you have in it.

## Glossary
Term - one-sentence definition - one sentence on its role in this paper. Alphabetical. Include acronyms.

## Open questions & extension ideas
Authors' future work (paraphrased), then your own: 3-5 concrete experiments or applications, each with why it would be informative. Add two or three questions you would ask the authors.

## Confidence notes
What you could not verify, where you inferred, which steps failed (metadata, repo, dry run), and how much weight the reader should put on each section as a result.
```

---

## Screen-mode entry (used in index.md)

```markdown
| # | Paper | Type | Contribution (one line) | Relevance (1-5) | Verdict | Why |
|---|---|---|---|---|---|---|
```

Relevance is relative to the user's stated goal; if no goal is known, ask once or score against the most likely goal and say so. Verdicts: **Read fully**, **Skim method only**, **Reference only**, **Skip**.

## Comparison table (used in index.md for compare/review)

```markdown
| | Paper A | Paper B | Paper C |
|---|---|---|---|
| Problem | | | |
| Method | | | |
| Data / setting | | | |
| Headline result | | | |
| Strongest evidence | | | |
| Main limitation | | | |
| Code | | | |
| Reproducibility score | | | |
```

Follow the table with a synthesis paragraph: agreements, conflicts, and which conflicts the evidence resolves.
