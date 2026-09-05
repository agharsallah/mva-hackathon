# Citation formats

`make_citation.py` produces APA 7, BibTeX and Vancouver from the metadata JSON. Check its output against these rules when metadata is incomplete (preprints, workshops, missing pages) and fix by hand. Never invent volume, issue, or page numbers; leave them out rather than guess.

## APA 7

**Journal article**
Last, F. M., Last, F. M., & Last, F. M. (Year). Title of the article. *Journal Name*, *Volume*(Issue), pages. https://doi.org/xx.xxxx

**Conference paper (published proceedings)**
Last, F. M., & Last, F. M. (Year). Title of the paper. In *Proceedings Name* (pp. x-y). Publisher. https://doi.org/xx.xxxx

**Preprint**
Last, F. M., & Last, F. M. (Year). *Title of the paper*. arXiv. https://doi.org/10.48550/arXiv.xxxx.xxxxx

Rules: up to 20 authors listed; for 21+, list the first 19, an ellipsis, then the last. Sentence case for titles; italicise journal and volume. Use the DOI URL form. If no DOI, give the URL.

## BibTeX

```bibtex
@article{lastname2024keyword,
  title   = {Title of the Article},
  author  = {Last, First and Last, First},
  journal = {Journal Name},
  volume  = {12},
  number  = {3},
  pages   = {45--67},
  year    = {2024},
  doi     = {10.xxxx/yyyy}
}

@inproceedings{lastname2024keyword,
  title     = {Title of the Paper},
  author    = {Last, First and Last, First},
  booktitle = {Proceedings of the Conference Name},
  pages     = {45--67},
  year      = {2024},
  doi       = {10.xxxx/yyyy}
}

@misc{lastname2024keyword,
  title         = {Title of the Preprint},
  author        = {Last, First and Last, First},
  year          = {2024},
  eprint        = {2401.01234},
  archivePrefix = {arXiv},
  primaryClass  = {cs.LG},
  doi           = {10.48550/arXiv.2401.01234}
}
```

Key convention: `firstauthorlastname` + year + first meaningful title word, lowercase, ASCII only. Protect capitalisation in titles with braces where needed (`{BERT}`, `{DNA}`).

## Vancouver (common in biology and medicine)

Last FM, Last FM, Last FM. Title of the article. Journal Abbrev. Year;Volume(Issue):pages. doi:xx.xxxx

Rules: list up to six authors, then "et al."; no italics; journal abbreviated per NLM catalog (the script uses the full name if the abbreviation is unknown - note this); year;volume(issue):pages without spaces.

## In-text forms
- APA: (Last & Last, 2024) or (Last et al., 2024) for three or more authors.
- Vancouver: numbered in order of appearance [1].
- Markdown notes: `[@lastname2024keyword]` (Pandoc) if the user uses citation keys.

## Edge cases
- **Preprint later published**: cite the published version; mention the arXiv ID in the report's Identity section. The metadata script often returns both; prefer the DOI that is not 10.48550.
- **Workshop papers**: `@inproceedings` with the workshop name in `booktitle`; note "workshop, lightly reviewed" in the Identity section.
- **Group authors / consortia**: use the consortium name as author.
- **No year**: use the arXiv submission year; write (n.d.) only if truly unknown.
- **Software citation**: if the user wants to cite the code, use the repository's CITATION.cff if present (`inspect_repo.py` reports it), otherwise `@software{}` with the URL and the version/commit hash.
