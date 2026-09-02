import babelParser from '@babel/eslint-parser';
import js from '@eslint/js';
import prettierConfig from 'eslint-config-prettier';
import boundaries from 'eslint-plugin-boundaries';
import jsxA11y from 'eslint-plugin-jsx-a11y';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import simpleImportSort from 'eslint-plugin-simple-import-sort';
import globals from 'globals';

import { localRules } from './eslint-rules/index.js';

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

// ---------------------------------------------------------------------------------
// Architecture-as-lint. Every rule below turns a prose rule from CLAUDE.md or a
// src/**/README.md into something `npm run lint` fails on. Grouped by the concern
// each one protects; each restricted-import/-syntax rule carries a `message` that
// names the one correct place for the thing it bans.
// ---------------------------------------------------------------------------------

// The repo's own rules live in eslint-rules/ (one file each, with a RuleTester test in
// eslint-rules/rules.test.js) rather than inline here: a rule that encodes an architecture
// decision deserves the same negative-test treatment as the code it guards.
const FETCH_RESTRICTION = {
  selector: "CallExpression[callee.name='fetch']",
  message:
    'Raw fetch() is only allowed inside src/api/** (src/api/client.ts owns the one fetch wrapper). Use get()/post() from src/api/client.ts or a hook from src/api/hooks.ts.',
};

const USE_QUERY_RESTRICTION = {
  selector: "CallExpression[callee.name='useQuery']",
  message:
    'Pages do not call useQuery() directly — add or reuse a hook in src/api/hooks.ts and call that instead. (components/** may still call useQuery directly, e.g. Header.tsx.)',
};

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
      // error since 2026-09-02, when the last 12 sites were split: a module that
      // exports both a component and a plain value cannot be hot-swapped, so Vite
      // full-reloads it and silently drops component state.
      'react-refresh/only-export-components': ['error', { allowConstantExport: true }],
      'simple-import-sort/imports': 'error',
      'simple-import-sort/exports': 'error',

      // tsc (strict, noUnusedLocals/noUnusedParameters) owns these; the Babel parser
      // does not resolve TS-only scope (types, generics, interfaces) well enough to
      // avoid false positives.
      'no-unused-vars': 'off',
      'no-undef': 'off',
      // TS syntax the base JS parser config doesn't need to gate.
      'no-unused-expressions': 'off',

      'jsx-a11y/no-autofocus': 'error',
      'jsx-a11y/click-events-have-key-events': 'warn',
      'jsx-a11y/no-static-element-interactions': 'warn',

      // CLAUDE.md's hard cap: "No script or module longer than 400 lines." Counts
      // real lines — blank lines and comments are not a discount.
      'max-lines': ['error', { max: 400, skipBlankLines: false, skipComments: false }],
    },
  },

  // ---------------------------------------------------------------------------
  // Layer graph (CLAUDE.md's "Code structure" + each src/**/README.md).
  //
  //   app        -> components, lib, pages (lazy import()), api
  //   pages      -> components, lib, api
  //   components -> components, lib, api                  (never pages, never fixtures)
  //   api        -> lib, fixtures (client.ts only)
  //   fixtures   -> api, lib                               (never components, never pages)
  //   lib        -> lib, api (aiExport reaches api/client.ts for the shared fetch helper)
  //   test       -> anything
  //
  // Verified against the real tree before writing this: 0 violations today for every
  // edge above, including the `lib -> api` edge (src/lib/aiExport/{types,wholeCase}.ts
  // import `Origin`/`get` from src/api/client.ts) — the READMEs describe lib as "the
  // bottom layer", but aiExport is real, shipped code that reaches api, so the graph
  // says so rather than pretending it doesn't.
  // ---------------------------------------------------------------------------
  {
    files: ['src/**/*.{ts,tsx}'],
    plugins: { boundaries },
    settings: {
      // eslint-plugin-boundaries resolves import sources via eslint-module-utils +
      // eslint-import-resolver-node (both its own transitive deps, nothing to install).
      // That resolver's default extension list is .js/.json/.node only, so without this
      // every `.ts`/`.tsx` import target comes back unresolved ("to" element unknown)
      // and the whole rule silently no-ops — verified by forcing a components -> pages
      // violation locally and watching it go unreported until this was added.
      'import/resolver': {
        node: { extensions: ['.js', '.jsx', '.ts', '.tsx'] },
      },
      'boundaries/root-path': import.meta.dirname,
      'boundaries/elements': [
        { type: 'test', pattern: 'src/test/**' },
        { type: 'app', pattern: 'src/app/**' },
        { type: 'pages', pattern: 'src/pages/**' },
        { type: 'components', pattern: 'src/components/**' },
        { type: 'api', pattern: 'src/api/**' },
        { type: 'fixtures', pattern: 'src/fixtures/**' },
        { type: 'lib', pattern: 'src/lib/**' },
      ],
      'boundaries/files': [{ category: 'api-client', pattern: 'src/api/client.ts' }],
    },
    rules: {
      'boundaries/dependencies': [
        'error',
        {
          default: 'disallow',
          message:
            'Layer graph violation (CLAUDE.md "Code structure" + the src/**/README.md files) — see eslint.config.js for the allowed edges.',
          policies: [
            {
              from: { element: { type: 'app' } },
              allow: {
                to: { element: { types: { anyOf: ['components', 'lib', 'pages', 'api'] } } },
              },
              message:
                'app/** is the shell — it may import components, lib, pages (lazy import()) and api. See src/app/README.md.',
            },
            {
              from: { element: { type: 'pages' } },
              allow: { to: { element: { types: { anyOf: ['components', 'lib', 'api'] } } } },
              message:
                'pages/** may import components, lib and api — never fixtures directly (go through src/api/hooks.ts) and never another page. See app/README.md.',
            },
            {
              from: { element: { type: 'components' } },
              allow: { to: { element: { types: { anyOf: ['components', 'lib', 'api'] } } } },
              message:
                'components/** may import components, lib and api — never pages, never fixtures. See src/components/README.md.',
            },
            {
              from: { element: { type: 'api' }, file: { categories: 'api-client' } },
              allow: { to: { element: { types: { anyOf: ['lib', 'fixtures'] } } } },
              message:
                'src/api/client.ts is the one file allowed to reach fixtures — the offline fallback boundary. See src/fixtures/README.md.',
            },
            {
              from: { element: { type: 'api' } },
              allow: { to: { element: { type: 'lib' } } },
              message:
                'src/api/** (outside client.ts) may only import lib — fixtures are reached exclusively through src/api/client.ts. See src/fixtures/README.md.',
            },
            {
              from: { element: { type: 'fixtures' } },
              allow: { to: { element: { types: { anyOf: ['api', 'lib'] } } } },
              message:
                'fixtures/** may import api (types) and lib — never components, never pages. See src/fixtures/README.md.',
            },
            {
              from: { element: { type: 'lib' } },
              allow: { to: { element: { types: { anyOf: ['lib', 'api'] } } } },
              message:
                'lib/** is (almost) the bottom layer: lib and api only (src/lib/aiExport reaches src/api/client.ts for the shared fetch helper). Never components, pages or fixtures.',
            },
            {
              from: { element: { type: 'test' } },
              allow: {
                to: {
                  element: {
                    types: {
                      anyOf: ['app', 'pages', 'components', 'api', 'fixtures', 'lib', 'test'],
                    },
                  },
                },
              },
              message: 'src/test/** may import anything.',
            },
          ],
        },
      ],
    },
  },

  // ---------------------------------------------------------------------------
  // "`fetch(` is only allowed in src/api/**" (app/README.md's stack table: client.ts
  // owns the one fetch wrapper). Layered in three tiers because `no-restricted-syntax`
  // holds one severity per rule instance and pages/JobsMonitor.tsx need selector sets
  // that differ from the blanket one — each tier restates the FULL selector set for
  // its scope rather than relying on a later block to merge with an earlier one
  // (flat config replaces a rule wholesale per matching file, it does not merge arrays).
  // ---------------------------------------------------------------------------
  {
    // Tier 1: every non-api src file gets the fetch ban.
    files: ['src/**/*.{ts,tsx}'],
    ignores: ['src/api/**'],
    rules: {
      'no-restricted-syntax': ['error', FETCH_RESTRICTION],
    },
  },
  {
    // Tier 2: pages additionally ban direct useQuery() — data access goes through
    // src/api/hooks.ts (app/README.md: "Exhibit ... the single hook the AI export
    // uses"; hooks.ts: "One react-query hook per endpoint"). components/** keeps only
    // the fetch ban (Header.tsx's health-dot useQuery is an intentional exception,
    // allowed simply by components/** never getting the useQuery selector).
    files: ['src/pages/**/*.{ts,tsx}'],
    ignores: ['src/pages/probes/JobsMonitor.tsx'],
    rules: {
      'no-restricted-syntax': ['error', FETCH_RESTRICTION, USE_QUERY_RESTRICTION],
    },
  },
  {
    // Tier 3: src/pages/probes/JobsMonitor.tsx — documented exception. It only calls
    // useQueryClient() (cache invalidation for the cancel button), never useQuery()
    // directly, so today this override changes nothing observable; it stays explicit
    // per the architecture note so a future switch to direct polling here doesn't
    // silently need rediscovering. The fetch ban still applies.
    files: ['src/pages/probes/JobsMonitor.tsx'],
    rules: {
      'no-restricted-syntax': ['error', FETCH_RESTRICTION],
    },
  },

  // "`plotly.js-dist-min` may only be imported by src/components/Plot.tsx" — the one
  // in-repo wrapper (app/README.md: "Plotly is wrapped by a small in-repo component
  // ... rather than react-plotly.js, so the ~4 MB bundle is loaded on demand").
  {
    files: ['src/**/*.{ts,tsx}'],
    ignores: ['src/components/Plot.tsx'],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          paths: [
            {
              name: 'plotly.js-dist-min',
              message: 'plotly.js-dist-min may only be imported by src/components/Plot.tsx.',
            },
          ],
        },
      ],
    },
  },

  // ---------------------------------------------------------------------------
  // Colour: one source, two halves (src/lib/palette/index.ts explains the split).
  //
  //   local/no-raw-hex-color          a hex literal may only appear in the generated ramps
  //   local/no-builtin-tailwind-color a class may only name a semantic family, never a
  //                                   Tailwind hue (`bg-emerald-400` renders a colour that
  //                                   exists in the DOM and nowhere in the palette)
  //
  // Scoped to all of src/** — not just pages/components — because app/**, lib/** and the
  // tests paint too. The two generated artifacts are the only exemption: they are written
  // by tools/gen-theme.mjs, which is the one place a number is allowed to be typed.
  // Both rules run over template literals as well as plain strings, so `bg-[${hex}]` and a
  // built-in hue interpolated into a className are caught; eslint-rules/rules.test.js pins
  // that.
  // ---------------------------------------------------------------------------
  {
    files: ['src/**/*.{ts,tsx}'],
    ignores: ['src/lib/palette/ramps.generated.ts'],
    plugins: { local: localRules },
    rules: {
      'local/no-raw-hex-color': 'error',
      'local/no-builtin-tailwind-color': 'error',
    },
  },

  {
    // eslint-rules/**: node scripts, and the RuleTester test needs vitest globals. Both
    // colour rules are off here — a rule that bans a hex has to contain one to test it.
    files: ['eslint-rules/**/*.js'],
    languageOptions: { globals: { ...globals.node, ...globals.vitest } },
  },

  {
    files: ['src/test/**', '**/*.test.{ts,tsx}'],
    languageOptions: {
      globals: { ...globals.browser, ...globals.node },
    },
  },
  {
    // app-local gate scripts run in node, not the browser: `process`, `console`, `URL`.
    files: ['tools/**/*.mjs'],
    languageOptions: { globals: globals.node },
  },
  {
    files: ['vite.config.ts', 'vitest.config.ts'],
    languageOptions: {
      globals: globals.node,
    },
  },
  prettierConfig,
];
