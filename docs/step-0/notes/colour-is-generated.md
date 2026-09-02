# Colour is generated, from one source, into two halves

**Standing:** firm. The owner is `app/tools/gen-theme.mjs`. Verified 2026-09-02: the only
file in `app/src/` containing a hex colour literal is the generated
`src/lib/palette/ramps.generated.ts`, and the only file declaring a `--color-*` custom
property is the generated `src/theme.generated.css`; both are re-derived and diffed by
`pnpm theme:check`.

## The problem

The app needs the same colour in two places that cannot share a mechanism.

| Where | What it needs | Why the other form does not work |
|---|---|---|
| The DOM (a `<div>`'s class) | a Tailwind utility — `bg-good-950` | a class cannot be computed at runtime: Tailwind generates utilities by scanning source text, so a class built from a template string is never emitted |
| A canvas (Plotly, an SVG `fill`, an inline style) | a concrete hex string | Plotly parses colours in JavaScript; it cannot read a CSS variable, and its parser does not understand `oklch()` |

Before this note the two halves were both hand-written and *unrelated*: `lib/palette.ts`
held hand-typed hex values from Tailwind v3, while the class strings in `lib/ui.ts` named
Tailwind v4's built-in `emerald`/`amber` hues. Measured, the drift was real — the chart green
was `#22c55e` and the badge green resolved to a different value entirely. Nothing could have
failed; the two were never compared.

## The rule

One generator, one conversion, two artifacts:

```
node_modules/tailwindcss/theme.css        the installed dependency, in oklch
        |
        v  tools/gen-theme.mjs  (pnpm theme)   picks 7 families, converts oklch -> sRGB hex once
        |
        +--> src/lib/palette/ramps.generated.ts    RAMP.good[500]     charts, SVG, inline style
        +--> src/theme.generated.css               --color-good-500   bg-good-500, lib/ui.ts
```

- **Semantic families, not hues.** `good` (green), `broken` (red), `decision` (yellow),
  `machinery` (blue), `raw` (purple), `chrome` (grey furniture), `severity` (the one orange
  step between broken and decision, charts only). The Tailwind hue name never appears in app
  code — the mapping lives in the generator alone.
- **Tones, not families, at a call site.** A component takes a `Tone`
  (`neutral · good · broken · decision · machinery · raw`) and never a hue. `lib/ui.ts`'s
  recipe maps are `Record<Tone, string>` over that one union, so a seventh meaning is a
  compile error at every recipe rather than a silent gap.
- **Hex is emitted on the DOM half too**, rather than aliasing Tailwind's own
  `var(--color-green-500)`. That trades a little wide-gamut vividness for the two halves
  being byte-identical instead of "the same colour in two colour spaces".

## Why generated rather than hand-written once

A single hand-written table would still need a human to keep the DOM copy and the canvas copy
in step, and the failure is invisible: a wrong shade renders, it does not throw. Generating
both from the dependency makes the drift *checkable*, which is the only property that
survives contact with a deadline.

## Enforcement

| Gate | Catches |
|---|---|
| `pnpm theme:check` (CI step; `tools/gen-theme.mjs --check`) | either committed artifact drifting from the generator, including after a `tailwindcss` upgrade |
| `app/src/test/theme-tokens.test.ts` | a tone missing from a recipe map, a recipe tinting a tone in the wrong family, a shade that does not exist, a scale stop that is not a ramp entry |
| `local/no-raw-hex-color` (eslint) | a hex literal anywhere in `src/` outside the generated ramps — in a string, a template literal, or an inline `style` |
| `local/no-builtin-tailwind-color` (eslint) | `bg-emerald-400` and every other bare Tailwind hue in a class string |

Both eslint rules live in `app/eslint-rules/` with `RuleTester` tests in
`app/eslint-rules/rules.test.js`; the negative cases are the point, since a rule that only
inspects plain string literals passes a whole repo while `` `bg-[${hex}]` `` walks through it.

## Consequences

- Changing a colour means editing the generator's family list and running `pnpm theme` — never
  typing a value at a call site.
- The system documents itself at **`/style-guide`** in the running app: every ramp, tone,
  recipe, scale and primitive rendered live from the same exports the app uses, which also
  makes it the screenshot to diff after any styling change.
- The visible consequence of the migration is a hue shift in the DOM: `emerald` became
  `green` and `amber` became `yellow`, so the app's greens and yellows now match the charts
  rather than sitting one hue family away from them.

This note is the owner of the rule. Other documents state the result in one sentence and link
here.
