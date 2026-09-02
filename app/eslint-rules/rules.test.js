/**
 * RuleTester coverage for the repo's own eslint rules.
 *
 * The point of these cases is the *negative* ones: a colour rule that only inspects plain
 * string literals passes a whole repo while `` `bg-[${hex}]` `` and an interpolated class
 * name walk straight through it. Each rule below is pinned on the shapes a colour can hide
 * in, and on the shapes it must not flag (a git SHA, a fragment id, a CSS `var()`).
 */

import { RuleTester } from 'eslint';
import { describe } from 'vitest';

import noBuiltinTailwindColor from './no-builtin-tailwind-color.js';
import noRawHexColor from './no-raw-hex-color.js';

const ruleTester = new RuleTester({
  languageOptions: { ecmaVersion: 2022, sourceType: 'module' },
});

describe('local/no-raw-hex-color', () => {
  ruleTester.run('no-raw-hex-color', noRawHexColor, {
    valid: [
      // The two sanctioned ways to name a colour.
      'const fill = RAMP.good[500];',
      "const cls = 'bg-good-950/25 text-good-300';",
      "const style = { color: 'var(--color-broken-400)' };",
      // Hash-prefixed strings that are not colours.
      "const anchor = '#legend';",
      'const href = `#${sectionId}`;',
      // A short hex-looking word that is not a colour literal: no leading '#'.
      "const sha = 'deadbeef';",
    ],
    invalid: [
      {
        code: "const fill = '#22c55e';",
        errors: [{ messageId: 'rawHex' }],
      },
      {
        // Inline style — the shape a lint rule scoped to className would miss.
        code: "const style = { color: '#eab308' };",
        errors: [{ messageId: 'rawHex' }],
      },
      {
        // Template literal: the quasi is a TemplateElement, not a Literal.
        code: 'const cls = `bg-[#22c55e]`;',
        errors: [{ messageId: 'rawHex' }],
      },
      {
        // Half-interpolated arbitrary value: the hex sits in the trailing quasi.
        code: 'const cls = `border-[${w}px] bg-[#0a0a0a]`;',
        errors: [{ messageId: 'rawHex' }],
      },
      {
        // 8-digit hex (colour + alpha), the form lib/palette used for translucent fills.
        code: "const fill = '#1e3a8a55';",
        errors: [{ messageId: 'rawHex' }],
      },
    ],
  });
});

describe('local/no-builtin-tailwind-color', () => {
  ruleTester.run('no-builtin-tailwind-color', noBuiltinTailwindColor, {
    valid: [
      // The semantic families, which is the whole point.
      "const cls = 'border-chrome-800 bg-chrome-900/40 text-chrome-300';",
      "const cls = 'text-good-400 hover:bg-broken-950/60';",
      "const cls = `text-${tone === 'good' ? 'good' : 'broken'}-400`;",
      // Non-colour utilities that merely end in a number.
      "const cls = 'grid-cols-3 gap-2 p-4 text-[11px] max-w-4xl z-50';",
      // A hue name with no shade attached is prose, not a class.
      "const legend = 'dark to blue to purple';",
    ],
    invalid: [
      {
        code: "const cls = 'text-emerald-400';",
        // The message must name the replacement family, not just the offence.
        errors: [
          { messageId: 'builtinHue', data: { match: 'emerald-400', instead: 'the `good` family' } },
        ],
      },
      {
        code: "const cls = 'border-zinc-800 bg-zinc-900/40';",
        errors: [{ messageId: 'builtinHue' }, { messageId: 'builtinHue' }],
      },
      {
        // Template literal, again the shape a Literal-only rule misses.
        code: 'const cls = `mt-1 text-amber-400 ${extra}`;',
        errors: [{ messageId: 'builtinHue' }],
      },
      {
        // A hue with no obvious semantic replacement still gets caught.
        code: "const cls = 'text-teal-300';",
        errors: [{ messageId: 'builtinHue' }],
      },
    ],
  });
});
