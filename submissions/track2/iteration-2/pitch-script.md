# Pitch script — 3 minutes, Track 2

**Standing:** draft, 2026-09-20, written from iteration 2's `report.md` (card v5, transfer run);
supersedes the 2026-09-19 script and iteration 1's. Not recorded. Target **2:52** spoken at a
calm pace (~500 words, the same spoken length as the 2026-09-19 script). Every number on screen comes from a committed table or figure; the shot
list names the file. Two beats are new — *what is new here* and *the transfer run* — and the
earlier beats were cut to pay for them.

| t | shot | on screen | words |
|---|---|---|---|
| 0:00 | title | `figures/track2/evidence-ladder.png`, blurred behind the title | *One child. One gene. Which medicines that already exist could act on what is broken — and which ones might make it worse?* |
| 0:08 | the child | the eight clinical terms, plain words beside each | *A boy with mosaic variegated aneuploidy: in some of his cells a chromosome is missing or doubled, and different cells are wrong in different ways. Short stature, kidney calcium, and a rhabdomyosarcoma — a childhood muscle cancer.* |
| 0:25 | the cause, twice | the mechanism card: gene, two alleles, "confirmed by the answer key"; the step-6 agreement matrix behind it | *Track 1 found, and the challenge confirmed, two broken copies of one gene, BUB1B. Then we rebuilt the answer blind, from the raw reads and the symptoms, and the same pair came out first. BubR1 is the brake that holds a dividing cell until every chromosome is attached. One copy makes nothing. The other makes a weakened brake.* |
| 0:45 | the ladder | the five rungs, one line each | *Before we looked at a single drug, we wrote down the rules. Five rungs: approved and used in children; in a trial for this tumour; shown in an animal; shown in a dish; mechanism only — named, never submitted. The table always shows whether a program or a person put a drug there.* |
| 1:02 | the search, and its control | the data-flow diagram from report §3, then `figures/track2/decoy-overlap.png` | *One structured card drove every query — seven public databases, 359 approved drugs on 277 targets, nothing typed by hand. Then we ran the same pipeline with the wrong gene. The tumour direction lit up for the decoy too, a quarter of its drugs overlapping. The three mechanism directions did not — so the tumour direction is argued only from papers a person read.* |
| 1:25 | the shortlist | `figures/track2/evidence-ladder.png`, top eleven rows | *Eleven drugs carry a cited mechanism result. Statins: rhabdomyosarcoma cells make their own cholesterol, lovastatin slowed them, and simvastatin has been given to children with relapsed sarcoma. Vitamin B3 — niacin, nicotinamide — raised BubR1 in BubR1-deficient mice. And we measured what earlier work assumed: on two independent instruments, no chromosome carries a mosaic population above two to three percent of cells — so the "kill the aneuploid cells" drugs stay a literature hypothesis, ranked last.* |
| 1:50 | the do-not table | the caution table from report §7.3 | *And the half we think matters most clinically. Thirteen approved drugs jam cell division and rely on the checkpoint to hold the cell. This child's checkpoint is the broken part. Two of them are standard rhabdomyosarcoma chemotherapy. We flag the question for the treating team — we do not advise withholding treatment.* |
| 2:08 | what is new here | report §9's two-column table | *What is new is the assembly, not the parts: one card instead of typed queries, a ladder written before the search, a decoy gene as a negative control, a do-not table as an output — and every claim filed with its refutation condition before its test.* |
| 2:24 | the transfer run | `figures/track2/transfer-scalability.png` | *Then we swapped the whole case — a different MVA gene, disease and tumour — and ran it unchanged. A second complete output, no code edited. Our own pre-registered claim came back refuted on one condition: a safety flag did not fire, because that case's pathway lookup returned nothing.* |
| 2:40 | the limits, and close | the "what we do not know" list, then the repository URL and dashboard `/track2` | *What we don't know: which tissue was sequenced; whether the weakened brake is unstable or just inactive; and whether any of this helps — the deepest lead is one mouse paper. Hypotheses for follow-up. The whole pipeline runs on the next child by swapping one card. Thank you.* |

## Recording notes

- Screen capture of the dashboard's `/track2` page for shots 3, 5 and 6; the PNGs are the
  fallback if the page is not reachable at recording time.
- No patient data appears in any shot: gene symbol, allele *classes*, drug names, counts.
- Keep the two disclaimers verbatim (0:45 "named, never submitted"; 1:50 "we do not advise
  withholding treatment"); they are the report's own words.
- The 2:24 beat must keep the refuted claim in it. A pitch that shows only the wins is the thing
  the rest of this submission is built to avoid.
