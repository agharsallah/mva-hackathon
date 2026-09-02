import babelParser from '@babel/eslint-parser';
import js from '@eslint/js';
import prettierConfig from 'eslint-config-prettier';
import boundaries from 'eslint-plugin-boundaries';
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

// ---------------------------------------------------------------------------------
// Architecture-as-lint. Every rule below turns a prose rule from CLAUDE.md or a
// src/**/README.md into something `npm run lint` fails on. Grouped by the concern
// each one protects; each restricted-import/-syntax rule carries a `message` that
// names the one correct place for the thing it bans.
// ---------------------------------------------------------------------------------

// `no-restricted-syntax` can only carry one severity per rule *instance*, and a raw
// hex colour literal is a `warn` (existing debt) while `fetch(` and `useQuery(` are
// `error` (already clean). Rather than fighting flat-config's "later block replaces
// the whole rule for files matched by both" merge behaviour, the hex check gets its
// own tiny local rule so its severity never has to share a key with the others.
const HEX_COLOR_RE = /#[0-9a-fA-F]{3,8}\b/;
const localRules = {
  rules: {
    'no-raw-hex-color': {
      meta: {
        type: 'problem',
        docs: {
          description:
            'disallow raw hex colour literals outside lib/palette.ts (CLAUDE.md: colour lives in one place)',
        },
        schema: [],
      },
      create(context) {
        return {
          Literal(node) {
            if (typeof node.value === 'string' && HEX_COLOR_RE.test(node.value)) {
              context.report({
                node,
                message:
                  'Raw hex colour literal — colour lives in src/lib/palette.ts. Add or reuse a named constant there instead. (TODO: existing debt, ~30 call sites — this rule is `warn` until a later wave migrates them.)',
              });
            }
          },
        };
      },
    },
  },
};

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

  // Raw hex colour literals in pages/components — CLAUDE.md: "Colour lives in one
  // place" (lib/palette.ts). NOTE: ~30 existing call sites, so this stays `warn` (not
  // `error`) until a later wave migrates them to lib/palette.ts; `npm run lint:strict`
  // (max-warnings 0) is how CI will eventually demand that migration is done.
  {
    files: ['src/pages/**/*.{ts,tsx}', 'src/components/**/*.{ts,tsx}'],
    plugins: { local: localRules },
    rules: {
      'local/no-raw-hex-color': 'warn',
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
