# Reading figures and tables

Figures are where most claims are actually made, and where over-selling hides. Text extraction is blind to them, so `scan_paper.py` rasterises every page that carries a figure or table caption. Open each of those images and work through this file. Budget: a rasterised page costs roughly 1,600 tokens, so read the pages that matter for headline claims first and skip decorative or purely illustrative figures if the paper is long.

## Procedure per figure or table

1. **Locate** - which claim in your running claims list does this figure support? If none, it is context, not evidence; note it briefly and move on.
2. **Describe** - in one sentence, what does it show, for whom (which dataset/condition), measured how?
3. **Read the caption and legend fully** - the caption often contains the n, the number of runs, the error-bar definition, and the exclusions the main text omits.
4. **Check the picture against the text** - does the visual support the sentence that cites it? Record a verdict: **OK**, **Caution** (supports the claim but weaker than the text implies), **Problem** (does not support the claim, or the presentation misleads).
5. **Recompute when possible** - for tables, redo the arithmetic behind the headline number (differences, relative vs absolute, averages across rows). Use the CSVs `scan_paper.py` extracted or transcribe the numbers you can see.
6. **Note what is missing** - the baseline that appears in related work but not in this figure, the dataset omitted from this plot, the error bars that vanished for one method.

## Red flags in plots

- **Truncated or shifted axes** - y-axis starting at 78% makes a 1-point gap look like a chasm. Note the axis range in your verdict.
- **Log scales without saying so**, or mixing log and linear across panels being compared.
- **No error bars or shading** on a plot that compares methods; or error bars defined nowhere (SD? SEM? 95% CI? across seeds or across examples?).
- **Selective x-range** - a scaling curve that stops exactly where the proposed method would be overtaken.
- **Different conditions across panels** presented as if comparable (different datasets, different model sizes, different epochs).
- **Smoothing** of training curves without disclosure.
- **Cherry-picked qualitative examples** with no failure cases shown - note the absence.
- **Colour or marker choices** that hide the strongest competitor (grey dashed line at the back).
- **Schematics that imply a pipeline the methods section does not describe** - architecture diagrams often show components that the ablations reveal to be optional.

## Red flags in tables

- Bold "best" that beats the runner-up by less than the reported standard deviation, or with no standard deviation reported.
- Rows with results copied from other papers (citation marks) mixed with rerun rows, without saying which preprocessing each used.
- Missing cells ("-") for the strongest baseline on the hardest benchmark.
- Aggregate averages that hide a loss on individual tasks; recompute the per-task wins/losses count.
- A metric that changes between tables (accuracy in Table 1, F1 in Table 2) without explanation.
- Relative improvement stated as if absolute ("improves by 12%" when the metric moved from 60.1 to 67.3 = 7.2 points, 12% relative).

## Red flags in biology figures

- n stated as wells, fields, or cells rather than independent biological samples.
- Representative images with no quantification, or quantification with no representative image.
- Blots spliced without a marked line; loading controls not from the same membrane.
- Scale bars missing or inconsistent across compared micrographs.
- Survival curves without the number at risk over time.
- Duplicated or mirrored panels across figures - report exactly what you saw ("panels 3B and 5D appear identical") and leave the interpretation to the reader.

## Recording the result

Write one row per figure/table in the report's "Figures & tables check" table. Below it, list every recomputation you did and whether it matched. When you could not read a figure (low resolution, dense heatmap), say so rather than guessing; offer to rasterise at a higher DPI on request:

```bash
pdftoppm -png -r 200 -f <page> -l <page> paper.pdf work/paper1/pages/hires
```

## Supplementary material

Supplementary figures often contain the ablations and negative results that did not fit the main paper. If the PDF includes an appendix, run the caption inventory on it too. If the supplement is a separate file the user has not provided, list the supplementary figures the main text references and note that they were not checked.
