# Pitch script — 3 minutes, Track 2

**Standing:** draft, 2026-09-19, written from iteration 2's `report.md`; supersedes iteration 1's script. Not recorded. Target 2:50 spoken at a
calm pace (~420 words). Every number on screen comes from a committed table or figure; the
shot list names the file.

| t | shot | on screen | words |
|---|---|---|---|
| 0:00 | title | `figures/track2/evidence-ladder.png`, blurred behind the title | *One child. One gene. Which medicines that already exist could act on what is broken — and which ones might make it worse?* |
| 0:10 | the child | the eight clinical terms, plain words beside each | *A boy with mosaic variegated aneuploidy: in some of his cells a chromosome is missing or doubled, and different cells are wrong in different ways. Short stature, kidney calcium, and a rhabdomyosarcoma — a childhood muscle cancer.* |
| 0:30 | the cause, twice | the mechanism card: gene, two alleles, "confirmed by the answer key"; the step-6 agreement matrix behind it | *Track 1 found, and the challenge confirmed, two broken copies of one gene, BUB1B. Then we rebuilt the answer blind — from the raw reads and the symptoms, with instruments that shared no code — and the same pair came out first. BubR1 is the brake that holds a dividing cell until every chromosome is attached. One copy makes nothing. The other makes a weakened brake.* |
| 0:55 | the ladder | the five rungs, one line each | *Before we looked at a single drug, we wrote down the rules. Five rungs: approved and used in children; in a trial for this tumour; shown in an animal; shown in a dish; mechanism only — named, never submitted. Every approved drug on the market was placed on the highest rung it passes, and the table shows whether a program or a person put it there.* |
| 1:20 | the search | the data-flow diagram from the report §2 | *Seven public databases, driven by one structured card, gave us 359 approved drugs on 277 targets. Then we did what Track 1 does to every ranker: we ran the same pipeline on the same child with the wrong gene — twice.* |
| 1:35 | the control | `figures/track2/decoy-overlap.png` | *The tumour direction lit up for the decoy gene too — a quarter of its drugs overlap. The three mechanism directions did not. So the tumour direction is argued only from papers a person read, never from "this drug has a rhabdomyosarcoma trial".* |
| 1:55 | the shortlist | `figures/track2/evidence-ladder.png`, top eleven rows | *Eleven drugs carry a cited mechanism result. Statins: rhabdomyosarcoma cells depend on making their own cholesterol, lovastatin slowed them, and simvastatin has already been given to children with relapsed sarcoma in a completed trial. Vitamin B3 forms — niacin, nicotinamide: boosting the NAD pathway raised BubR1 in mice bred with too little of it. And we measured what earlier work only assumed: in the sample sequenced, no chromosome shows a mosaic population above two to three percent of cells — so the "kill the aneuploid cells" drugs stay a literature hypothesis, ranked last. Every inherited result is starred.* |
| 2:20 | the do-not table | the caution table from report §5.3 | *And the half we think matters most clinically. Thirteen approved drugs work by jamming cell division and relying on the checkpoint to hold the cell. This child's checkpoint is the broken part. Two of them are standard rhabdomyosarcoma chemotherapy. We flag the question for the treating team — we do not advise withholding treatment.* |
| 2:40 | the limits | the "what we do not know" list | *What we don't know: which tissue was sequenced, so the two-to-three-percent bound is about the sample, not the diagnosis; whether the weakened brake is unstable or just inactive; and whether any of this helps. Rung three is one mouse paper. These are hypotheses for follow-up.* |
| 2:52 | close | repository URL, dashboard `/track2` | *Every claim was registered before its test, every table has its lineage, and the whole pipeline runs on the next child by swapping one card. Thank you.* |

## Recording notes

- Screen capture of the dashboard's `/track2` page for shots 3, 6 and 7; the PNGs are the
  fallback if the page is not reachable at recording time.
- No patient data appears in any shot: gene symbol, allele *classes*, drug names, counts.
- Keep the two disclaimers verbatim (0:55 "named, never submitted"; 2:20 "we do not advise
  withholding treatment"); they are the report's own words.
