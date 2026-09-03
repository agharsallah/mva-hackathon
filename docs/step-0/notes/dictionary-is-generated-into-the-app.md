# The dictionary is generated into the app, never copied

**Standing:** firm. Decided 2026-09-03. Enforced by `pnpm dictionary:check` (drift and
dead cross-links), `app/src/test/dictionary.test.ts` (shape), `app/src/test/learn-links.test.tsx`
(every link out of the Learn page lands) and `app/src/test/explainer-dict.test.ts` (every
Explainer chip the dictionary defines links to it). Verified against the running app on
2026-09-03 ([066](../methodology/066-learn-page.md)).

[`docs/dictionary.md`](../../dictionary.md) is the one glossary in the repository, and the
documentation rules say it is never duplicated. The app needed it — a reader with no genomics
background meets a hundred domain words across fourteen pages — and the obvious way to get it
there, a hand-written glossary component, would have been a second glossary the moment the
markdown changed.

**The rule:** the markdown is the source; the app renders a build artifact generated from it.
Nobody writes a definition in `app/`.

| | Where | Owner |
|---|---|---|
| The words, their order, their diagrams | `docs/dictionary.md`, `docs/assets/*.svg` | the dictionary |
| The generator | `app/tools/gen-dictionary.mjs` | the app |
| The artifact | `app/src/lib/dictionary/dictionary.generated.json` + `assets/` | generated, committed, checked |
| The rendering | `app/src/pages/Learn.tsx` and `pages/learn/` | the app |
| Where the app *shows* a word | `app/src/pages/learn/seeIt*.ts` | the app — a map, not a definition |

Three consequences, each with a gate:

- **Drift is a build failure.** `pnpm dictionary:check` regenerates in memory and compares
  byte-for-byte; it sits in `pnpm run check` beside `theme:check`, on the same reasoning as
  [colour is generated](colour-is-generated.md): two artifacts that must agree get one source
  and a check, not a convention.
- **The generator is the dictionary's link checker.** A `[phasing](#4-inheritance…)` whose
  heading no longer exists fails generation. The first run found three such anchors, stale
  since the chapters were renamed; the markdown had no other check for them.
- **Pages link, they do not restate.** An `Explainer` chip keeps its one-sentence hint and
  gains `dict: '<slug>'`, rendered as "full definition →". A chip whose term the dictionary
  defines and that does not link is a test failure, so the long form cannot creep back into
  page code.

What was rejected:

- **A markdown renderer in the browser** reading `docs/dictionary.md` at runtime. The Vite dev
  server refuses files outside `app/`, the page would parse 1,700 lines on every visit, and
  nothing would check the cross-links.
- **Pre-rendering the mermaid diagrams to SVG at build time.** It needs a headless browser
  in CI. `mermaid` is instead `import()`ed on the Learn page only and drawn when a diagram
  scrolls into view; the source is the fallback, which is exactly what the markdown shows in a
  plain editor. The renderer is a lazy chunk and does not touch the initial payload
  ([`tools/bundle-budget.mjs`](../../../app/tools/bundle-budget.mjs)).
- **Recolouring the diagrams for the dark theme.** They carry their own light-paper colours
  and every Legend decodes exactly those colours, so they render on a white "paper" card in
  both themes rather than being repainted into a palette the legend no longer describes.

Anchors are GitHub's: a chapter's id is the slug GitHub gives its heading, so a link written
for the markdown (`dictionary.md#4-inheritance--how-the-answer-is-shaped`) is the same link
on `/learn`. Term anchors use the app's own `slugify`, one per entry, and are the contract
`seeIt.ts`, `tracks.ts` and every `dict:` slug are checked against.
