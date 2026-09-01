import babelParser from '@babel/eslint-parser';
import js from '@eslint/js';
import prettierConfig from 'eslint-config-prettier';
import jsxA11y from 'eslint-plugin-jsx-a11y';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import simpleImportSort from 'eslint-plugin-simple-import-sort';
import globals from 'globals';

// NOTE on the parser choice: `typescript-eslint` (all published 8.x releases, checked up
// to 8.69.0) hard-fails at import time against TypeScript 7.x — this repo pins
// `typescript@^7.0.2`, the new Go-ported native compiler. It is not a version-range
// nit: `@typescript-eslint/typescript-estree` reaches into `ts.Extension.Cjs`, an enum
// TS 7's public API does not expose, so even syntax-only parsing throws before any lint
// rule runs. Tracked upstream: https://github.com/typescript-eslint/typescript-eslint/issues/10940
//
// Until that lands, TS/TSX files are parsed with `@babel/eslint-parser` +
// `@babel/preset-typescript` instead — it strips types via Babel and never touches the
// `typescript` package, so it is unaffected by the TS7 incompatibility. The trade-off:
// no `@typescript-eslint` rules (no type-aware linting, no TS-specific unused-vars/no-
// explicit-any). `noUnusedLocals`/`noUnusedParameters` are already `true` in
// tsconfig.app.json, so `npm run typecheck` (tsc) still catches unused code — `no-unused-vars`
// and `no-undef` are turned off below rather than duplicated with a parser that does not
// understand TS syntax well enough to avoid false positives on types/generics.
// Revisit once typescript-eslint ships TS7 support: swap this parser block back for
// `typescript-eslint`'s recommended + stylistic configs.

export default [
  {
    ignores: ['dist/**', 'node_modules/**', 'coverage/**'],
  },
  js.configs.recommended,
  {
    files: ['**/*.{js,jsx,ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      globals: globals.browser,
      parser: babelParser,
      parserOptions: {
        requireConfigFile: false,
        babelOptions: {
          presets: ['@babel/preset-react', '@babel/preset-typescript'],
        },
      },
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
      'jsx-a11y': jsxA11y,
      'simple-import-sort': simpleImportSort,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      ...jsxA11y.configs.recommended.rules,
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
      'simple-import-sort/imports': 'error',
      'simple-import-sort/exports': 'error',

      // tsc (strict, noUnusedLocals/noUnusedParameters) owns these; the Babel parser
      // does not resolve TS-only scope (types, generics, interfaces) well enough to
      // avoid false positives.
      'no-unused-vars': 'off',
      'no-undef': 'off',
      // TS syntax the base JS parser config doesn't need to gate.
      'no-unused-expressions': 'off',

      'jsx-a11y/no-autofocus': 'warn',
      'jsx-a11y/click-events-have-key-events': 'warn',
      'jsx-a11y/no-static-element-interactions': 'warn',
    },
  },
  {
    files: ['src/test/**', '**/*.test.{ts,tsx}'],
    languageOptions: {
      globals: { ...globals.browser, ...globals.node },
    },
  },
  {
    files: ['vite.config.ts', 'vitest.config.ts'],
    languageOptions: {
      globals: globals.node,
    },
  },
  prettierConfig,
];
