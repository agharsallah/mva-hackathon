# 066 — The dictionary becomes a page: generated from the markdown, linked both ways

**Date:** 2026-09-03
**Question:** `docs/dictionary.md` is the repository's one glossary — 1,735 lines, fifteen
chapters ordered so each word uses only words above it, twenty SVG diagrams and nineteen
mermaid blocks. The app's audience is exactly its audience, but the app only had it as a
link, and every page carried its own hand-written one-sentence definitions (121 distinct
`Explainer` chips) that nothing checked against the dictionary. Can the dictionary be put
*in* the app — with the reading order, the diagrams and a link from each word to the exhibit
that shows it — without creating a second glossary?

_(step-0 platform machinery: this entry records decisions and measurements, not a
hypothesis. Per [`docs/method.md`](../../method.md), step 0 takes no hypotheses.)_

**Decision recorded in** [dictionary is generated into the app](../notes/dictionary-is-generated-into-the-app.md).

## Inputs

- `docs/dictionary.md` at commit `dab961e` (before this work), `docs/assets/*.svg` (20 files).
- `app/` at the same commit: React 18, Vite 8, no markdown or diagram dependency.
- New build-time dependencies: `remark-parse` 11, `remark-gfm` 4, `remark-rehype` 11,
  `rehype-stringify` 10, `unified` 11, `mdast-util-to-string` (dev only). New runtime
  dependency: `mermaid` 11.17.2, lazy.

## Commands

```bash
cd app
pnpm dictionary            # tools/gen-dictionary.mjs → src/lib/dictionary/
pnpm dictionary:check      # drift + dead cross-links; now part of `pnpm run check`
pnpm exec vitest run       # 34 files
pnpm exec vite build && node tools/bundle-budget.mjs --skip-build
```

Screenshots taken with headless Chromium (Playwright) against the dev server at
`127.0.0.1:5173` on `/learn`, `/learn#allele`, `/learn#vaf-variant-allele-fraction`,
`/genome#allele-balance-per-chromosome-the-aneuploidy-screen` and `/genome` with all
definitions open.

## What the generator found in the markdown

First run, before any output was written:

```
gen-dictionary: docs/dictionary.md:94:  unresolved link #1-the-absolute-basics-what-is-dna
gen-dictionary: docs/dictionary.md:255: unresolved link #4-quality-what-can-go-wrong-and-how-you-see-it
gen-dictionary: docs/dictionary.md:925: unresolved link #8-the-toolbox-what-each-program-does
```

Three chapter anchors, stale since the chapters were renamed, used by fourteen links. Fixed in
the markdown (`1-dna-basics…`, `2-reading-dna…` for the Ti/Tv link, `8-command-line-tools…`).
The dictionary had no other link check.

Second finding, from the app's patient-data guard rather than the generator: the dictionary's
two illustrative coordinates (`("chr15", 40162526, "C", "T")` and the same position under
**Annotation**) are coordinate-shaped and not on the synthetic ladder, so committing them
inside `app/` failed `src/test/patient-data.test.ts`. Replaced with a round `40000000` in the
markdown — the example teaches the shape, not the position.

After the fixes:

```
gen-dictionary: wrote 15 chapters, 440 entries, 20 figures, 19 diagrams
```

| block kind | count | rendered as |
|---|---|---|
| entry (`**term** — …`) | 439 → 440 with the **Mermaid** entry this work added | card: term, alias chips, definition, example, anchor |
| figure (`![…](assets/…svg)`) | 20 | `<img>` on a white paper card, Legend beneath |
| mermaid | 19 | drawn in the browser on scroll; source as fallback |
| code (```text) | 13 | `<pre>`, Legend beneath where the markdown has one |
| prose (bold sentences, tables, lists, quotes) | 25 | HTML as written |
| subheading (`###`) | 1 | `<h3>` with GitHub's anchor |

One code block has no Legend — the mmCIF `atom_site` excerpt, a data-file sample rather than a
picture; every figure and diagram has one (asserted in `dictionary.test.ts`).

Generated artifact: `dictionary.generated.json` 273,420 bytes on disk, 196.54 kB raw /
65.16 kB gzip as its own Vite chunk. Prettier is told to leave it alone: `JSON.stringify`'s
one-item-per-line arrays would be collapsed and the drift check would then fail on formatting.

## The page

`/learn`, a fifth nav group **Learn — "What do the words mean?"**, placed first because the
other four groups are written in its words. Overview's map and the journey therefore start
there. One chapter at a time; the URL hash is the whole state and uses GitHub's anchors.

| piece | measured |
|---|---|
| Learn page chunk | 63.41 kB raw / 17.57 kB gzip, lazy |
| mermaid renderer | `mermaid.core` 94.31 kB / 32.55 kB plus per-diagram-type chunks, lazy, fetched only when a diagram scrolls into view |
| initial payload after the change | 282.28 kB raw / 90.46 kB gzip across 5 files, budget 290 / 92 — **OK**; the Learn page, the JSON and mermaid are all outside it |
| search | 440 terms + aliases, ranked exact → prefix → contains → definition text, top 12 |
| progress | chapters marked read, `localStorage`, a convenience not a record |

Verified in the browser: chapter 1 renders with three SVG figures and two mermaid diagrams
drawn (the allele diagram and the splicing flow), `#allele` opens chapter 1 and outlines the
entry, the "Mark read, next chapter" hand-off advances the hash.

## Links in both directions

**Out of the dictionary** — `pages/learn/seeIt*.ts`: 54 entries carry a "See it in the
app" line, 65 links to routes (most with an exhibit anchor) and 26 citations of methodology
entries, each opening the entry on GitHub. Three short paths (`tracks.ts`: read a callset,
20 terms; why this child, 18; decide and score, 12) list the terms to know before one part of
the app.

Every `Exhibit` now has a DOM id — a slug of its title unless given one — and scrolls itself
into view when mounted under the URL's hash, since the page is a lazy chunk and the browser's
own hash scroll runs before the figure exists. Verified: `/genome#allele-balance-per-chromosome-the-aneuploidy-screen`
lands on that exhibit.

**Into the dictionary** — `Explainer`'s `Term` gains `dict: '<slug>'`, rendered as
"full definition →" under the chip's sentence. 76 chips across 14 pages received a slug: the
41 whose term matches an entry by name or alias exactly, plus 35 obvious variants (a
spelled-out abbreviation, a slash pair, `sha256` → `checksum-sha-256`). 45 chips remain
unlinked because the dictionary has no entry for them (`QUAL`, `variant caller`, `long-poll`,
the Status page's operational words) — those are candidates for the dictionary, not for
page code.

## Gates added

| gate | what fails it |
|---|---|
| `pnpm dictionary:check` (in `pnpm run check`) | generated JSON or a copied SVG differs from the markdown; a cross-link names a missing heading; an SVG in `assets/` is no longer referenced |
| `src/test/dictionary.test.ts` (8 tests) | duplicate anchor, unresolved internal href, figure without a URL, definition still starting with its term, figure or diagram without a Legend |
| `src/test/learn-links.test.tsx` (17 tests) | a track or see-it slug the dictionary lacks; a route the manifest lacks; a methodology path not on disk; an exhibit anchor absent from the mounted page's DOM (one mount per linked page, offline) |
| `src/test/explainer-dict.test.ts` (3 tests) | a `dict` slug naming no entry; a chip whose term the dictionary defines without a `dict` |
| `eslint` `no-restricted-imports` | `mermaid` imported anywhere but `pages/learn/Mermaid.tsx` |

The first run of `learn-links` caught one real miss: `/probes#probe-counts-against-the-whole-read-store`
does not exist offline, because the Probes page renders the start-command card instead of
the exhibit when the reads API is absent. The link now points at the page.

Full suite after all four commits: **34 files, 491 tests, all passing**; `prettier --check`
clean; eslint clean on every touched file. `tsc -b` reports one error in a file belonging to a
parallel session (`PaletteDialog.tsx`, unused `IS_MAC`), not touched here; every file in this
work type-checks.

## Conclusion

The dictionary is in the app without being copied: one generator, one committed artifact
with a drift check, and the markdown's own anchors as the link contract. The reading order
the dictionary already had *is* the course. The two link tables — where the app shows a
word, and which word a chip means — are data with tests, so a renamed exhibit or a deleted
entry fails the build rather than a reader's click. The generator also turned out to be the
first link checker the dictionary ever had, and found three dead anchors on its first run.

Open: 45 Explainer chips name words the dictionary does not define; they should be added to
`docs/dictionary.md` (chapter 2 for the VCF fields, chapter 8 for the operational words) and
will then be required to link by the test.
