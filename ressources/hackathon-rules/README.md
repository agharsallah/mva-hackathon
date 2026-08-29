# Challenge documents — the rules, the phenotype, the output contract

**Standing:** the four files below are the delivered challenge documents, unchanged. The
readings under each are settled unless the organisers reissue a document.
Extracted 2026-08-29 from `ideation/data-inventory.md` §A1–A3 (now in
[`archive/`](../../archive/)).

Strategy built on top of these: [`ideation/hackathon-intel.md`](../../ideation/hackathon-intel.md).

## The four files

| File | What it is |
|---|---|
| [`Challenge_Clinical_Phenotype_1.md`](Challenge_Clinical_Phenotype_1.md) | The proband's clinical presentation, already encoded as HPO terms. The *entire* phenotype input — there is no phenopacket. |
| [`track1_submission_template.csv`](track1_submission_template.csv) | Header + 2 example rows, 12 columns. The schema the pipeline must terminate in. |
| [`methods_description_form.xlsx`](methods_description_form.xlsx) | Two sheets (Track 1, Track 2), question/answer. Voluntary, and the judging rubric in disguise. |
| `raw_hackathon.txt` | 58 KB scrape of the HF Space: README, rules, timeline, FAQ, **and the Python source of the submit tabs and scorer**. The authority for anything procedural. |

---

## The phenotype — 8 HPO terms

**HPO** (Human Phenotype Ontology) — a controlled vocabulary of clinical features; each
term is a stable ID a ranking tool can consume, like an enum value rather than free text.

| HPO ID | Term | Note from doc |
|---|---|---|
| HP:0002859 | Rhabdomyosarcoma | primary oncological event, triggered urgent investigation |
| HP:0000121 | Nephrocalcinosis | present since birth |
| HP:0004322 | Short stature | below expected for age *and family background* |
| HP:0001508 | Failure to thrive | repeatedly documented |
| HP:0003202 | Skeletal muscle atrophy | reduced muscle bulk |
| HP:0001622 | Premature birth | 32 weeks gestation |
| HP:0001518 | Small for gestational age | ~1 kg at birth (IUGR) |
| HP:0200067 | Recurrent spontaneous abortion | parental history, multiple losses |

How the terms are used:

1. **Direct machine input.** These 8 IDs are the query vector for every phenotype-driven
   ranker — Exomiser, LIRICAL, AMELIE, Phen2Gene. Write them once; never retype them.
2. **Prior sharpening.** `HP:0002859` discriminates across MVA subtypes: BUB1B (MVA1) and
   TRIP13 (MVA3) carry cancer predisposition, CEP57 (MVA2) generally does not.
3. **ACMG PP4 evidence.** The co-occurring cluster (cancer + IUGR + nephrocalcinosis +
   parental reproductive loss) is what justifies PP4 in the written report.
4. **The miscarriage signal is data.** Recurrent parental loss is consistent with
   aneuploidy-generating mechanisms — it argues for a chromosomal-instability gene and for
   *biallelic* inheritance (both parents carriers).
5. **Absent-feature reasoning.** No microcephaly, no reported intellectual disability is
   listed. Classic BUB1B MVA1 usually has microcephaly. Flag the tension in the report
   rather than letting the prior override it.

**What it does not give:** no age, no sex, no ancestry, no karyotype, no aneuploidy
percentage, no parental sequencing. Sex was inferred from the data instead — see
[`ideation/data-findings.md`](../../ideation/data-findings.md) §5.

---

## The output contract — `track1_submission_template.csv`

```
proband_id,chrom_1,pos_1,ref_1,alt_1,chrom_2,pos_2,ref_2,alt_2,epcr,finding_type,notes
```

| Column | Constraint that bites |
|---|---|
| `proband_id` | must be exactly `PROBAND01` — the scorer rejects anything else |
| `chrom_1`/`chrom_2` | `chr`-prefixed, GRCh38 (`chr15`) |
| `pos_1`/`pos_2` | GRCh38 1-based VCF position |
| `ref_*`/`alt_*` | must string-match the answer key → left-align and normalize with `bcftools norm` first; an unnormalized indel is a silent miss |
| `*_2` group | fill only for compound-het pairs; blank = single-variant row |
| `epcr` | float in (0, 1]. Ties break by file order → always use strictly distinct descending values |
| `finding_type` | literally `primary` or `secondary` |
| `notes` | free text, unscored automatically, read by judges |

Max 10 rows. The emitter and its validator are `src/mva/pipeline/submission.py`; the
chr-prefix bridge that feeds it is [one function only](../../docs/step-0/notes/chr-prefix-bridge.md).
Row-layout strategy (pairs vs. singles as partial-match probes) is in
[`hackathon-intel.md` §9](../../ideation/hackathon-intel.md).

---

## The judging rubric — `methods_description_form.xlsx`

Voluntary, but the form states that submissions without it "may be judged less favorably on
Innovation and Scalability."

Track 1 asks, verbatim in substance:

- describe the model/approach in detail
- is the submission the **automated output** of the approach (*preferred*) or manually
  curated? describe any manual review
- **public data only** (*preferred*) or proprietary? describe each source
- "Is your approach able to output proposed pairs of compound heterozygous candidate
  variants, or only single candidate variants?"
- how were secondary/incidental findings handled?
- runtime and cost estimate
- 500-word method abstract with strengths *and limitations*

Track 2 mirrors it for drug repurposing: variant→mechanism→candidate reasoning, automated
vs. manual literature review, public sources (DrugBank, ChEMBL, ClinicalTrials.gov, OMIM,
PubMed), how the mechanism was characterized (LoF vs GoF, pathway, downstream
consequence), effort estimate, 500-word abstract.

Three design decisions fall straight out of it, and they are treated as spec, not
paperwork:

- The pipeline must **emit the CSV automatically**, end to end. "Automated output
  (preferred)" is stated twice.
- The ranker must **natively propose pairs**, not singles a human pairs up — see
  [ranking pairs, not variants](../../docs/notes/ranking-pairs-not-variants.md).
- Every external resource must be **public and logged**, with version and release date,
  written as the pipeline runs.
- Instrument runtime and cost from day one (wall clock + cloud spend per stage).
