/**
 * The repo's own eslint rules — architecture that a type system cannot state.
 *
 * Kept in their own files rather than inline in eslint.config.js so that
 * eslint-rules/rules.test.js can load each one into `RuleTester` and pin both what it
 * catches and what it must not flag.
 */

import noBuiltinTailwindColor from './no-builtin-tailwind-color.js';
import noRawHexColor from './no-raw-hex-color.js';

export const localRules = {
  rules: {
    'no-raw-hex-color': noRawHexColor,
    'no-builtin-tailwind-color': noBuiltinTailwindColor,
  },
};
