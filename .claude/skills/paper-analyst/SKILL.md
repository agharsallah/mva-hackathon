---
name: paper-analyst
description: Analyse academic papers into a structured Markdown report - citation, one-minute pitch, domains, claims-vs-evidence table, what works and what doesn't, stated and unstated limitations, figure and table checks, validity and reproducibility assessment, key cited works, follow-up and impact research, and - when code or data exist - how to run, inspect and adapt them. Use this whenever the user shares a paper (PDF, arXiv or DOI link, or pasted text), asks to summarise, explain, critique, compare or screen research papers, asks whether a paper is worth reading, asks how to apply a paper's method or code, or is building a literature review or thesis - even if they never say "analyse". Also use for "explain this paper like I'm new", "is this result trustworthy", "what does figure 3 show", "find the code for this paper", or a folder of PDFs to triage. Covers CS/AI/ML and biology/bioinformatics with domain-specific critique lenses, and is designed to be extended to new fields.
---

# Paper Analyst

Turn a research paper into an analysis a newcomer can act on: understand it, judge it, place it in its field, and know what to do with it next. The skill combines three traditions:

- **Keshav's three-pass reading** for structure: skim to triage, read to grasp, dig to verify. It gives a stopping rule so effort matches the paper's relevance.
- **Critical appraisal** (CASP/Cochrane-style) for judgement: is the question clear, are the methods valid, what could have confounded the result, do the conclusions follow?
- **Reproducibility checklists** (Pineau's ML checklist, the ML Code Completeness Checklist) for the code: is what's released enough to rerun and reuse?

Three habits matter more than any template. First, separate _what the paper says_ from _what you conclude_ - label them. Second, never fill a gap with a plausible guess: if a citation count, venue, or repo detail wasn't verified, write "unverified". Third, remember the reader is new to the field: define terms on first use and explain why a result matters, not only what it is.

## Inputs

Accept any of: a PDF , an arXiv/DOI/publisher URL, a bare arXiv ID or DOI, pasted text, or several of these at once. If only a URL is given, fetch it with web_fetch (arXiv abstract pages link to the PDF as `/pdf/<id>`). If a paper can't be retrieved, say so and analyse what is available rather than reconstructing the paper from memory.

## Workflow

Run the scripts from the skill's `scripts/` directory. Each prints JSON to stdout and never crashes on missing network - it reports `errors` and `fallback_urls` instead, so read those fields.

### Step 0 - Decide flags, lens and depth

Detect the **mode flags** from the request (several may be on at once; see the table below), pick the **domain lens** (see "Choosing the lens"), and decide the **depth**: `screen` means pass 1 only; everything else means the full pipeline. If the user attached a `my-context.md` (or described their project), read it - the `apply` sections are written against it.

### Step 1 - Scan the PDF

```bash
python scripts/scan_paper.py paper.pdf --out work/paper1
```

This extracts layout-preserving text, detects sections, finds every code/data URL and identifier (DOI, arXiv ID, GitHub, Zenodo, GEO, PDB...), inventories figure and table captions with page numbers, rasterises only the pages that carry figures or tables, and tries to pull tables to CSV. Read `manifest.json` first, then `text.txt`. Scanned PDFs with no text layer are flagged; rasterise and read those pages visually instead.

### Step 2 - Fetch metadata and impact

```bash
python scripts/fetch_metadata.py --doi 10.xxxx/yyyy --out work/paper1/metadata.json
# or --arxiv 2401.01234 | --title "Exact title" | --url https://...
```

Queries Semantic Scholar, OpenAlex, Crossref and arXiv for authors, venue, year, abstract, fields of study, citation counts, the reference list, citing papers (with "influential" flags), and any open-access PDF. This is the source for **Related work**, **Impact & follow-ups** and the citation. If the sandbox blocks these hosts, the JSON lists `fallback_urls`: fetch each with web_fetch and fill the same fields by hand. Skip this step in `screen` mode unless the user asks for impact.

### Step 3 - Pass 1: triage (5 minutes of reading)

Read title, abstract, introduction, section headings, conclusion, and glance at the references and the math. Produce: paper type, one-line contribution, domains, the three or four claims the paper hinges on, and a **relevance verdict** for this user. In `screen` mode, stop here and emit the screening table. Otherwise continue.

### Step 4 - Pass 2: grasp (the full read)

Read everything except proofs and appendix minutiae. While reading, keep a running list of claims with where each is made. Open every rasterised figure/table page from Step 1 and apply `references/figure-analysis.md`: what does the figure show, which claim does it support, and does the picture actually support the text? Recompute headline numbers from tables where possible. Note every term a newcomer would stumble on for the glossary. Read `references/paper-types.md` to know what a paper of this type owes the reader, and the chosen lens file for the domain-specific questions.

### Step 5 - Pass 3: verify (conditional)

Do this when the user wants `apply`, when trust matters (`review`, "is this credible"), or when Pass 2 raised red flags. Reconstruct the argument from the claims table: for each claim, is the evidence sufficient, is the comparison fair, could something else explain the result? Check that the limitations the authors state cover the ones you found. If code or data exist, run Step 6.

### Step 6 - Inspect code and data (when links exist)

```bash
python scripts/inspect_repo.py https://github.com/org/repo --out work/paper1/repo.json
# add --clone work/paper1/src for a shallow clone to read the code itself
```

Reports repo health (last push, stars, licence, open issues mentioning reproduction problems, archived status), the five ML Code Completeness items (dependencies, training script, evaluation script, pretrained models, results table), and a file tree. Then follow `references/code-and-data-assessment.md`: check paper-to-code consistency (hyperparameters, model sizes, datasets), attempt the smallest dry run if dependencies install cleanly, assess data availability and licence, and write the adaptation plan. Unofficial reimplementations are useful but say so - they are not evidence the paper's numbers hold.

### Step 7 - Write the report

```bash
python scripts/make_citation.py work/paper1/metadata.json    # APA, BibTeX, Vancouver
```

Fill `references/report-template.md` section by section. Save as Markdown at `/mnt/user-data/outputs/<firstauthor>-<year>-<short-slug>.md` with the YAML header filled in, then present the file. For several papers add `index.md` with the comparison or screening table. Offer a Word version only if asked.

Before presenting, run the quality check at the end of this file.

## Mode flags

Flags are additive; detect all that apply and say which you used in the report's YAML header. `learn + apply` is the default when a paper has code and the user has not signalled otherwise, because that is the combination that teaches the idea through its implementation.

| Flag       | Signals in the request                                                            | What it adds to the report                                                                                                                             |
| ---------- | --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `learn`    | "I'm new", "explain", "teach me", "what is", first paper in a topic               | Background primer, expanded glossary, plain-language method before the technical one, prerequisite reading list                                        |
| `apply`    | "how can I use", "in my project", code or data mentioned, `my-context.md` present | Code & data inspection made central, run instructions, concept-to-code map, adaptation plan with effort and risk estimate                              |
| `screen`   | several papers, "worth reading?", "which first", "triage"                         | Pass 1 only per paper, one-line verdict, relevance score 1-5, ranked table; offer to promote any paper to full analysis                                |
| `review`   | "literature review", "thesis", "related work", "survey", "compare"                | Positioning paragraph (what this paper is _for_ in a literature), citation-ready one-paragraph summary, comparison table across papers analysed so far |
| `critique` | "is this trustworthy", "review this", "find the flaws", "referee"                 | Pass 3 always, expanded validity section written as a referee report with major/minor issues                                                           |

When the user names a combination in plain words ("learn and apply", "screen then review the top two"), map it to flags and confirm in one line.

## Choosing the lens

The lens decides what counts as good evidence. Pick by the paper's field, not the user's; a bioinformatics paper read by an ML engineer still needs the bio questions asked.

| Paper is mainly about                                          | Read                                                 | Core question                                                                                         |
| -------------------------------------------------------------- | ---------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| Algorithms, models, systems, benchmarks, HCI, theory           | `references/lens-ml-cs.md`                           | Are the baselines and benchmarks fair, and would the gain survive a different seed?                   |
| Wet-lab, clinical, ecological, genomics experiments            | `references/lens-bio.md`                             | Do design, controls and sample size support a causal reading?                                         |
| Computational methods on biological data, pipelines, databases | `references/lens-bioinformatics.md`                  | Is the evaluation free of leakage between related sequences/structures, and is the biology validated? |
| Something else                                                 | closest lens above + `references/adding-a-domain.md` | Note in the report that no dedicated lens exists yet                                                  |

Always also read `references/paper-types.md`: a survey, a dataset paper and a theory paper each owe the reader different things, and judging one by another's standard is the most common analytic mistake.

## Handling several papers

- **Screening**: run Steps 1 and 3 per paper, then produce `index.md` with a table (paper, type, one-line contribution, relevance 1-5, verdict, why). Rank by relevance to the user's stated goal. Keep per-paper notes short; the point is deciding where to spend time.
- **Comparing**: run the full pipeline per paper, then add to `index.md` a comparison table (problem, method, data, headline result, limitations, code) and a short synthesis: where they agree, where they conflict, and which conflict the evidence actually settles.
- **Review mode across a session**: keep appending analysed papers to `index.md` so it becomes the skeleton of a related-work section.

## Network fallback

The scripts need `api.semanticscholar.org`, `api.openalex.org`, `api.crossref.org`, `export.arxiv.org` and `api.github.com`. In Claude Code or Cowork on the user's machine they run normally. Chat sandboxes often allow only GitHub, and their web-fetch tool may accept only URLs that already appeared in a search result - so a bare API URL printed by a script is not fetchable. When `fetch_metadata.py` reports failures, use this path, which is verified to work:

1. Web-search `"<paper title>" semanticscholar` and `"<paper title>" arxiv` (add the first author if the title is generic).
2. Fetch the Semantic Scholar paper page from the results: it carries the BibTeX entry, venue, citation count, TLDR, and lists of citing papers - enough for Identity, Impact and the citation.
3. Fetch the arXiv abstract page (or the publisher/DOI page) for the abstract, categories, version history and any "code" comment.
4. Fill the same fields `fetch_metadata.py` would have, then run `make_citation.py` with `--title/--authors/--year/--venue/--doi/--arxiv` flags.

Tell the user once, briefly, that metadata came via search rather than the API; do not repeat it in every section. If nothing is reachable, mark the affected fields "unverified" and derive related work from the PDF's own reference list (`references.txt` from Step 1). Mention that an org owner can widen the sandbox allow-list if the user wants the scripts to run directly.

## Writing for a newcomer

Write the pitch as speech, not prose - it should take sixty seconds aloud. Explain the method twice: first as an analogy or plain description with no symbols, then technically. In the glossary, define a term in one sentence and add one sentence on why it matters for this paper. In the claims table, strength ratings mean: **strong** = direct evidence, fair comparison, replicated or multi-seed; **moderate** = direct evidence with one notable gap; **weak** = indirect, single run, or self-reported; **unsupported** = asserted without evidence in the paper. Prefer "the authors report" over "the paper proves".

## Quality check before presenting

- Every claim in the claims table points to a section, figure or table in the paper.
- Every number in the report appears in the paper or was recomputed from its tables (say which).
- Stated limitations and unstated limitations are separate lists; the second is not empty unless you say why.
- Figures & tables section covers every figure that a headline claim rests on.
- Code section says "official" or "reimplementation", and whether the dry run was attempted, succeeded, or skipped (and why).
- Anything not verified against a source is marked "unverified", and the Confidence notes section lists them.
- Glossary covers every term you used that a newcomer would not know.
- File saved to `/mnt/user-data/outputs/` with a filled YAML header, and presented.

## Reference files

| File                                     | Read when                                                                  |
| ---------------------------------------- | -------------------------------------------------------------------------- |
| `references/report-template.md`          | Writing the report (always)                                                |
| `references/paper-types.md`              | Classifying the paper in Pass 1 (always)                                   |
| `references/lens-ml-cs.md`               | Paper is CS/AI/ML/systems/theory                                           |
| `references/lens-bio.md`                 | Paper is experimental or clinical biology                                  |
| `references/lens-bioinformatics.md`      | Paper is computational biology                                             |
| `references/figure-analysis.md`          | Reading figures and tables in Pass 2 (always in full analysis)             |
| `references/code-and-data-assessment.md` | A code or data link exists                                                 |
| `references/citation-formats.md`         | `make_citation.py` output needs checking or the paper has unusual metadata |
| `references/adding-a-domain.md`          | The paper's field has no lens yet, or the user wants to extend the skill   |
| `assets/my-context-template.md`          | Give to the user when `apply` is on and no project context exists          |
