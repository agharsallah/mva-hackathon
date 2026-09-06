# 081 — Fewer requests from the hosted dashboard: a persisted query cache and quieter polls

**Date:** 2026-09-06
**Question:** The deployed dashboard ([080](080-hosted-dashboard.md)) asks the API for
everything on every visit. On Vercel's free plan the budget being spent is **invocations**,
and each `/api/*` request costs two — the middleware password gate, then `api/proxy` — plus
a WAN round trip to `mva-viz-api`. How much of that traffic is asking for rows the browser
already had, and can it be removed without weakening the data perimeter or showing a stale
answer where staleness is wrong?

_(step-0 platform machinery: this entry records decisions and measurements, not a
hypothesis. Per [`docs/method.md`](../../method.md), step 0 takes no hypotheses. Filed in
step 0 rather than a research step because every step's exhibits are served through it.)_

## Where the requests were going

Three sources, read off the code before changing it:

| Source | Before | Cost |
|---|---|---|
| Header status dot (`src/components/Header.tsx`) | `/health` every **15 s**, `staleTime: 0` | 240 requests/hour per tab being looked at |
| Job queue (`useJobs`) | `/api/jobs` every **20 s** while idle | 180 requests/hour on an open Probes tab |
| Every panel on every page | in-memory cache only, `staleTime` 5 min | a reload, a new tab, or a return visit refetches **all of them** |

The third is the big one and the least visible: react-query's cache lives in the tab. A hard
reload of `/panel` re-asks for every exhibit on it, against tables that change only when an
ingest runs.

## What was changed

1. **The query cache is persisted to `localStorage`**
   ([`app/src/lib/queryPersistence.ts`](../../../app/src/lib/queryPersistence.ts), wired in
   `app/src/app/providers.tsx`). A reload restores and re-renders; only entries past
   `staleTime` are refetched.
2. **`staleTime` 5 min → 30 min**, `gcTime` → 24 h, in one shared constant
   (`app/src/lib/queryClient.ts`), because these payloads are aggregates over a fixed
   callset, not a live feed. The endpoints where staleness is wrong keep their own short
   times where they are declared.
3. **The status dot polls at 60 s, not 15 s**, with `staleTime` matched to the interval.
   react-query does not run the timer while the tab is hidden, so this is the cost of a tab
   being *looked at* — and a minute is well inside how fast anyone reacts to a red dot.
4. **The idle job poll drops to 60 s**; a queue with something in flight still polls at 4 s.

## The data-perimeter rule this created

Persisting means writing payloads to a visitor's disk, where they outlive the tab, the
session cookie and the password. So the module holds an **allowlist, never a denylist** — a
new endpoint is not persisted until someone puts it there on purpose. 45 paths are listed,
all coordinate-free aggregates, reference tables or the research record. Never listed:

| Path | Why never |
|---|---|
| `/api/panel/locus`, `/api/callset/region`, `/api/search` | real patient positions |
| `/api/panel/het-pairs`, `/api/panel/clinvar-presence` | carry `pos` per variant |
| `/health`, `/api/health/dependencies`, `/api/jobs` | liveness — a stale answer is a wrong answer |

Two more fences: the **buster is the build's commit** (`VERCEL_GIT_COMMIT_SHA`, inlined by
`vite.config.ts` as `__BUILD_ID__`), so no deployment can restore a payload shape it does
not understand; and `maxAge` is 24 h. Nothing about the *server* changed: every proxied
reply is still `no-store, private`, so no shared cache holds any of it.

## Measured

Executed, not estimated:

- **A reload costs one request instead of two, in the test that measures it**
  (`app/src/test/query-persistence.test.ts`). Cold session: 2 fetches (one allowlisted path,
  one excluded). After a save-and-restore against the same store: **1** — the excluded path,
  which is exactly the one that may not be persisted. With the buster changed to another
  deployment's: **2** again, as cold as a first visit.
- **The store holds what it should.** The serialized cache contains the allowlisted path and
  does **not** contain `/api/panel/locus`.
- **Poll arithmetic.** 15 s → 60 s is 240 → 60 `/health` requests per hour per foreground
  tab; 20 s → 60 s is 180 → 60 for an idle Probes tab. Each avoided request is 2 Vercel
  invocations.
- **Bundle cost, measured against the same tree with only `providers.tsx` reverted:**
  284.90 kB raw / 91.39 kB gzip → **290.84 / 93.28**, i.e. **+5.94 kB raw, +1.90 kB gzip**
  for the two persistence packages. The budget gate
  ([`app/tools/bundle-budget.mjs`](../../../app/tools/bundle-budget.mjs)) failed on this and
  was re-blessed to 293 / 94 with that arithmetic recorded in the file — one-time bytes
  against per-visit requests, on a deployment whose scarce resource is invocations.
- **Gates green:** 598 app tests pass (19 of them new), typecheck, lint, format, theme and
  dictionary checks all clean.

## What was considered and not done

- **CDN caching of `/api/*` replies (`s-maxage`).** It would remove the proxy invocation
  entirely for a cached path. Rejected for now: the responses sit behind a per-session
  password gate, the CDN cache key does not include the session, and `/api/panel/locus`
  serves patient positions — getting the split wrong caches private data in a shared cache.
  The browser-side allowlist buys most of the same traffic with none of that risk.
- **Exempting static assets from the middleware gate.** Every JS chunk, font and image
  currently costs one middleware invocation because the gate deliberately runs before the
  CDN — that is what stops an unauthenticated visitor downloading the bundle
  ([080](080-hosted-dashboard.md)). Cheaper, but it would publish the app to anyone with the
  URL. Not changed.
- **Hand-rolling the persister** over `dehydrate`/`hydrate` to save ~1 kB gzip. Not worth
  owning and testing serialization for that margin.

## Not measured

Nothing here was measured against the live deployment — there are no before/after Vercel
invocation counts in this entry, only the mechanism's own test and the arithmetic of the
poll intervals. The first hosted session after this lands is where the real number is.
