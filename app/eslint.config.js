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

const PLOTLY_IMPORT = {
  name: 'plotly.js-dist-min',
  message: 'plotly.js-dist-min may only be imported by src/components/Plot.tsx.',
};

const THREE_IMPORT = {
  name: 'three',
  message:
    'three may only be imported by src/viz3d/core/loadThree.ts, which import()s it dynamically ' +
    'so it lands in its own chunk. Pages use the viz3d barrel — see src/viz3d/README.md.',
};

const MERMAID_IMPORT = {
  name: 'mermaid',
  message:
    'mermaid may only be imported by src/pages/learn/Mermaid.tsx, which import()s it dynamically ' +
    'so the ~2.5 MB renderer lands in its own chunk and is fetched only on the Learn page.',
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
  //   pages      -> components, lib, api, viz3d
  //   components -> components, lib, api, viz3d            (never pages)
  //   api        -> lib
  //   viz3d      -> viz3d, lib                             (never api, never components)
  //   lib        -> lib, api (aiExport reaches api/client.ts for the shared fetch helper)
  //
  // The `lib -> api` edge is real, shipped code (`src/lib/aiExport` imports the shared
  // fetch helper), so the graph says so rather than pretending lib is the bottom layer.
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
        { type: 'app', pattern: 'src/app/**' },
        { type: 'pages', pattern: 'src/pages/**' },
        { type: 'components', pattern: 'src/components/**' },
        { type: 'api', pattern: 'src/api/**' },
        { type: 'lib', pattern: 'src/lib/**' },
        { type: 'viz3d', pattern: 'src/viz3d/**' },
      ],
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
              allow: {
                to: { element: { types: { anyOf: ['components', 'lib', 'api', 'viz3d'] } } },
              },
              message:
                'pages/** may import components, lib, api and viz3d — never another page. See app/README.md.',
            },
            {
              from: { element: { type: 'components' } },
              allow: {
                to: { element: { types: { anyOf: ['components', 'lib', 'api', 'viz3d'] } } },
              },
              message:
                'components/** may import components, lib, api and viz3d — never pages. See src/components/README.md.',
            },
            {
              from: { element: { type: 'api' } },
              allow: { to: { element: { type: 'lib' } } },
              message: 'src/api/** may only import lib.',
            },
            {
              from: { element: { type: 'lib' } },
              allow: { to: { element: { types: { anyOf: ['lib', 'api'] } } } },
              message:
                'lib/** is (almost) the bottom layer: lib and api only (src/lib/aiExport reaches src/api/client.ts for the shared fetch helper). Never components or pages.',
            },
            {
              from: { element: { type: 'viz3d' } },
              allow: { to: { element: { types: { anyOf: ['viz3d', 'lib'] } } } },
              message:
                'viz3d/** is domain-agnostic: lib only (palette, urlstate, format, ui). Never ' +
                'api, never components — a page maps API rows into a Scene3D and hands that in. ' +
                'See src/viz3d/README.md.',
            },
          ],
        },
      ],
    },
  },

  // ---------------------------------------------------------------------------
  // "`fetch(` is only allowed in src/api/**" (app/README.md's stack table: client.ts
  // owns the one fetch wrapper). Layered in two tiers because `no-restricted-syntax`
  // holds one severity per rule instance — each tier restates the FULL selector set for
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
    rules: {
      'no-restricted-syntax': ['error', FETCH_RESTRICTION, USE_QUERY_RESTRICTION],
    },
  },

  // A heavy rendering library may only be imported by the one in-repo wrapper that owns it:
  // `plotly.js-dist-min` by src/components/Plot.tsx, `three` by src/viz3d/core/loadThree.ts,
  // `mermaid` by src/pages/learn/Mermaid.tsx.
  // Both wrappers `import()` their library dynamically, which is what keeps the ~4 MB Plotly
  // chunk and the ~530 kB three chunk out of the initial payload — a static import anywhere
  // else silently undoes that, and `tools/bundle-budget.mjs` is the second line of defence.
  // Both sizes are the *emitted chunks* measured by that script on 2026-09-03:
  // plotly.min-*.js 4,066.61 kB raw / 1,234.12 kB gzip, three.module-*.js 529.85 kB raw / 131.78 kB gzip.
  //
  // Three blocks, not one with two `ignores`: flat config replaces a rule wholesale for the
  // files a later block matches, so each wrapper needs its own block restating the ban on the
  // *other* library. Without that, exempting Plot.tsx from this rule would also let it import
  // three.
  {
    files: ['src/**/*.{ts,tsx}'],
    ignores: [
      'src/components/Plot.tsx',
      'src/viz3d/core/loadThree.ts',
      'src/pages/learn/Mermaid.tsx',
    ],
    rules: {
      'no-restricted-imports': ['error', { paths: [PLOTLY_IMPORT, THREE_IMPORT, MERMAID_IMPORT] }],
    },
  },
  {
    files: ['src/components/Plot.tsx'],
    rules: { 'no-restricted-imports': ['error', { paths: [THREE_IMPORT, MERMAID_IMPORT] }] },
  },
  {
    files: ['src/viz3d/core/loadThree.ts'],
    rules: { 'no-restricted-imports': ['error', { paths: [PLOTLY_IMPORT, MERMAID_IMPORT] }] },
  },
  {
    files: ['src/pages/learn/Mermaid.tsx'],
    rules: { 'no-restricted-imports': ['error', { paths: [PLOTLY_IMPORT, THREE_IMPORT] }] },
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
    // eslint-rules/**: node scripts. Both colour rules are off here — a rule that bans a
    // hex has to contain one in its own source to match against.
    files: ['eslint-rules/**/*.js'],
    languageOptions: { globals: globals.node },
  },
  {
    // app-local gate scripts run in node, not the browser: `process`, `console`, `URL`.
    files: ['tools/**/*.mjs'],
    languageOptions: { globals: globals.node },
  },
  {
    files: ['vite.config.ts'],
    languageOptions: {
      globals: globals.node,
    },
  },
  prettierConfig,
];
