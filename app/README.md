# `app/` — the dashboard

A data-understanding and visualization web app. It is a **reading tool**, not a control
panel: every page opens with an explainer that names its domain concepts in the repo's
`technical term (plain-English meaning)` pattern, and every chart carries a `Legend` line
decoding its own colours.

**Verified:** 2026-10-05 — stripped to a domain-agnostic shell. `pnpm run typecheck`,
`pnpm run lint`, `pnpm run format:check`, `pnpm run theme:check`, `pnpm run build` and
`node tools/bundle-budget.mjs` all green. `pnpm run dictionary:check` is red while
`docs/dictionary.md` is being rewritten — see [The dictionary](#the-dictionary). There are no
tests in this repository, by decision.

## Quickstart

```bash
cd app
pnpm install
pnpm run dev      # http://127.0.0.1:5173
```

With no backend running, every panel renders its own shell and shows a classified error card
naming what to do about it. Point `VITE_API_URL` at a backend to fill them in.

### Prerequisites

| Dependency | Needed for          | Check                                             |
| ---------- | ------------------- | ------------------------------------------------- |
| Node 22+   | the app itself      | `node -v` — pinned by `engines` in `package.json` |
| pnpm 11+   | installing app deps | `pnpm -v` — pinned by `packageManager`            |

### Environment

One variable, copied from [`.env.example`](.env.example):

| Variable       | Unset                                  | Set to `/`                                                           |
| -------------- | -------------------------------------- | -------------------------------------------------------------------- |
| `VITE_API_URL` | requests go to `http://127.0.0.1:8900` | requests go to this page's own origin, where the proxy forwards them |

An absolute URL in the bundle would tell every visitor the backend's hostname and port, which
is why the hosted build uses `/` and lets the server-side proxy hold the real address.

## Scripts

| Script                           | Does                                                                            |
| -------------------------------- | ------------------------------------------------------------------------------- |
| `pnpm run dev`                   | Vite dev server, port 5173, strict (a busy port is an error, not a silent 5174) |
| `pnpm run build`                 | `tsc -b && vite build` — must pass clean                                        |
| `pnpm run typecheck`             | `tsc -b` over the app, the Node config and the serverless functions             |
| `pnpm run lint` / `lint:strict`  | ESLint, including the layer graph and the colour rules                          |
| `pnpm run format` / `:check`     | Prettier                                                                        |
| `pnpm run theme` / `:check`      | regenerate the colour tokens from Tailwind, or fail if they have drifted        |
| `pnpm run dictionary` / `:check` | regenerate `/learn` from `docs/dictionary.md`, or fail if it has drifted        |
| `pnpm run check`                 | all of the above checks, in order                                               |
| `pnpm run bundle-budget`         | builds, then fails if the initial payload grew past the budget                  |

## Stack

| Layer     | Choice                         | Why                                                                                          |
| --------- | ------------------------------ | -------------------------------------------------------------------------------------------- |
| build     | Vite + React 18 + TypeScript   | fast dev server, real code splitting, strict types                                           |
| routing   | react-router-dom               | one `<Route>` per manifest entry, generated                                                  |
| data      | TanStack Query                 | one hook per endpoint, one retry policy, one cache                                           |
| styling   | Tailwind v4 + generated tokens | colour is generated once and read by both CSS and canvases                                   |
| 2D charts | `plotly.js-dist-min`           | dynamically imported by `components/Plot.tsx`, so it is never in first paint                 |
| 3D        | `three`, behind `src/viz3d`    | dynamically imported by `viz3d/core/loadThree.ts`; a page hands in data, never three.js code |
| diagrams  | `mermaid`                      | dynamically imported by `pages/learn/Mermaid.tsx`, for the dictionary's diagrams             |

## Architecture

```
src/
  main.tsx          bootstrap: theme, providers, shell
  app/              the shell and THE MANIFEST — see src/app/README.md
  pages/            one folder or file per page, default-exported, lazily loaded
  components/       the shared primitives — see src/components/README.md
  viz3d/            the domain-agnostic 3D module — see src/viz3d/README.md
  api/              client.ts (the one fetch wrapper), hooks.ts (one hook per endpoint), types/
  lib/              palette, theme, url state, formatting, the section registry, the AI export
server/, api/       the hosted deployment: the password gate and the API proxy (never bundled)
tools/              the generators and the bundle gate
```

The layer graph is enforced by `eslint-plugin-boundaries`, so a violation is a failed build
rather than a review note. The allowed edges are listed at the top of that block in
[`eslint.config.js`](eslint.config.js).

Three rules are worth knowing before writing a page:

- **A page is declared once**, in `src/app/modules/index.ts`. Routing, the nav rows, the page
  heading and the previous/next links all read that entry.
- **`fetch(` only exists in `src/api/`**, and a page never calls `useQuery` directly — both
  enforced by lint. Data access goes through a hook in `src/api/hooks.ts`.
- **A chart enters through `Exhibit`**, which requires a `legend` prop. That is how "every
  figure decodes its own colours" is enforced in code instead of in a checklist.

## The dictionary

`docs/dictionary.md` is the one glossary in the repository and it is never copied.
`tools/gen-dictionary.mjs` turns it into `src/lib/dictionary/dictionary.generated.json` plus
the diagrams it embeds, and `/learn` renders that. The generator also checks the markdown's
own integrity: a cross-link naming a missing heading, or a `*Context:*` line naming a file
that does not exist, fails the build.

```bash
pnpm run dictionary        # regenerate after editing the markdown
pnpm run dictionary:check  # fail if the committed artifacts have drifted
```

The page renders **whatever chapters the markdown contains** — it knows block kinds (entry,
figure, mermaid, code, prose, subheading), never terms — so a rewritten dictionary needs no
code change.

## Hosting

The hosted deployment adds two things the local one does not have: a shared-password gate,
and a server-side proxy so the browser never learns the backend's address.

### The files

| Path                            | Runs                            | Does                                                                                                         |
| ------------------------------- | ------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| `middleware.ts`                 | Vercel Routing Middleware, edge | the gate: valid session → through; document → the password page; anything else → 401                         |
| `server/session.ts`             | edge                            | the signed cookie — HMAC-SHA256 over the expiry, keyed by secret **+** password                              |
| `server/loginPage.ts`           | edge                            | the self-contained password page (no bundle, no font file)                                                   |
| `server/upstream.ts`            | edge                            | the one forwarder to the backend: token, timeout, header allowlist, `no-store`                               |
| `api/proxy.ts`                  | Edge Function                   | every `/api/*` request, forwarded (`vercel.json` rewrites the path into `?upstream=`). Re-checks the session |
| `api/liveness.ts`               | Edge Function                   | `/health` (rewritten in `vercel.json`), because that path is outside `/api` upstream                         |
| `api/login.ts`, `api/logout.ts` | Edge Function                   | issue and expire the cookie; the only routes the gate lets through                                           |
| `vercel.json`                   | build                           | the `/health` and `/api/:path*` rewrites, the SPA fallback, and the security headers                         |
| `tsconfig.vercel.json`          | `tsc -b`                        | typechecks all of the above — it is outside the Vite build, so it needs its own project                      |

### Project settings

Root Directory **`app`**. Framework preset Vite (`vercel.json` states it). Then:

| Variable                   | Example                   | Meaning                                                                                                           |
| -------------------------- | ------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `API_UPSTREAM_URL`         | `https://api.example.org` | where the backend is reachable from Vercel. Server-side only. **Must be a hostname, never a bare IP** — see below |
| `API_UPSTREAM_TOKEN`       | (32 random characters)    | must equal the API key the backend expects. Server-side only                                                      |
| `DASHBOARD_PASSWORD`       | (generated, not chosen)   | the one shared password. Rotating it invalidates every session                                                    |
| `DASHBOARD_SESSION_SECRET` | (32 random characters)    | signs the cookie. Rotating it also invalidates every session                                                      |
| `VITE_API_URL`             | `/`                       | build-time: makes every request same-origin so the proxy sees it                                                  |

Two constraints that are not obvious until a deployment fails on them, both measured against a
live one rather than assumed:

- **`API_UPSTREAM_URL` must be a hostname.** The Edge runtime answers a fetch to a bare IP
  itself, with `403 Direct IP access is not allowed in Vercel's Edge environment` — past any
  try/catch, so it reaches the dashboard as an unexplained 403 on every panel. A server
  reachable only by address still works: give it any name that resolves to it, such as the
  hosting provider's default reverse-DNS name. `server/upstream.ts` checks for this and answers
  503 with that sentence rather than letting the platform's 403 through.
- **The `/api/:path*` rewrite is load-bearing.** Vercel's catch-all route (`api/[...path].ts`)
  expands like a single `[path]` on a deployed Vite project, so a one-segment path reached the
  function and a two-segment one came back `x-vercel-error: NOT_FOUND`. The rewrite in
  `vercel.json` routes every depth explicitly; the filesystem check that runs before rewrites is
  what keeps `/api/proxy`, `/api/login`, `/api/logout` and `/api/liveness` on their own functions.

### Running the hosted setup locally

`vercel dev` runs the middleware, the proxy and the Vite dev server together, which is the only
way to exercise the gate and the proxy before deploying — and the way to develop against a
remote API that requires a token, since a browser cannot hold one.

```bash
cd app
DASHBOARD_PASSWORD=... DASHBOARD_SESSION_SECRET=... \
API_UPSTREAM_URL=https://api.example.org API_UPSTREAM_TOKEN=... \
  vercel dev --listen 3000
```

Export the variables into the shell rather than relying on `.env.local`: `vercel env pull`
cannot decrypt Secret-type variables, they come back empty, and the deployment then answers
`503` naming them — the fail-closed path working, not a bug.

### What this is not

One shared password, so a session identifies "someone who knew the password", never a person.
No user, no role, no audit trail of who looked at what. That is the right level for a small
private dashboard and wrong for anything else.

## Where to look first

| Question                          | File                                                   |
| --------------------------------- | ------------------------------------------------------ |
| How do I add a page?              | [`src/app/README.md`](src/app/README.md)               |
| What components exist?            | [`src/components/README.md`](src/components/README.md) |
| How do I draw a 3D figure?        | [`src/viz3d/README.md`](src/viz3d/README.md)           |
| Where does colour come from?      | [`src/lib/palette/index.ts`](src/lib/palette/index.ts) |
| How does a request reach the API? | [`src/api/client.ts`](src/api/client.ts)               |
| Why is the bundle this size?      | [`tools/bundle-budget.mjs`](tools/bundle-budget.mjs)   |
