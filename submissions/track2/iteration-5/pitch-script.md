# Pitch script — Track 2, iteration 5 (3 minutes)

**Standing:** complete outline, 2026-09-25, written from the filed entries 158–162 and
[`report.md`](report.md). **Not recorded** — no video exists and no URL is published. Every
number here is the report's; read at about 150 words a minute; each shot names the figure on
screen. The script ends where the report ends: the stop allele is not the lever, the decisive
output is the cycloheximide-chase blot at 59 % of EVPI, and the top-ranked drug is not robust.

| # | time | on screen | voice-over |
|---|---|---|---|
| 1 | 0:00–0:20 | title; the child's 8 clinical terms | The case in one line, the confirmed cause (two broken copies of *BUB1B*), and the question iteration 5 asks: not "which drug", but **which of the child's two broken copies can be treated at all**. |
| 2 | 0:20–0:40 | `figures/it5/r1-stop-anatomy.svg` | What the stop copy is: an early stop in exon 17 of 23, far enough from the last junction that the cell destroys the message before it is ever read, and the part that is lost carries the whole working end of the protein. |
| 3 | 0:40–1:05 | `figures/it5/r1-control.svg` | The discipline: no claims this time, a positive control per route. Hide 14 stops the field already benchmarks, predict them, and only use the drugs that come back right — and check that with no drug at all the method fails, which it does. |
| 4 | 1:05–1:30 | `figures/it5/r1-dosage.svg` | The result that redirects the whole iteration: even a perfect readthrough drug adds about 1.4 points of working BubR1 against a gap of roughly 6.5. Doubling the *other* copy's protein is worth 12.5. The lever is the missense allele. |
| 5 | 1:30–2:00 | `figures/it5/r2-proliferation.svg` and `r2-hits.svg` | So we asked protein data directly, across 875 compounds. Almost everything a drug does to this protein is "it changed how many cells divide", so we remove that first — our control finds the textbook protein induction at ranks 1 and 2. What is left: five approved drugs raising BubR1 by 14 to 16 percent. Not a rescue. The big raisers point at degradation instead. |
| 6 | 2:00–2:25 | `figures/it5/r3-evidence-map.svg` and `r3-mva-exposures.svg` | The literature holds what no database encodes — seven ways to raise this protein, each with a sentence our code checked word for word against the source. And the disease's own safety record: a severe reaction to one chemotherapy drug, a published warning against two more, growth hormone ineffective in four reports. |
| 7 | 2:25–2:50 | `figures/it5/r4-voi-curve.svg`, then `figures/it5/r4-tornado.svg` | So we do not end with a ranked list. One unmeasured fact decides everything: is the missense protein unstable, or inactive? Perfect knowledge is worth 0.18 on our scale — all of it on that question, none on readthrough. A single bench test, a cycloheximide chase, buys 59 percent of it. And our top-ranked drug does not survive three of our own assumptions. The value of the test does. |
| 8 | 2:50–3:00 | `figures/it5/s1-transfer.svg`, then the repo URL | So our answer is a measurement and an avoid list, not a prescription. The same three routes re-ran on a second disease from configuration files, and every first-case table came back byte-identical. Two of our six controls failed; both are in the report. |
