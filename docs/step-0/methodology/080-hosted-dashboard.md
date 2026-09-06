# 080 — Hosting the dashboard: a same-origin proxy, a token on the API, and a password gate

**Date:** 2026-09-06
**Question:** The dashboard has only ever run on one laptop against `http://127.0.0.1:8900`.
To show it to anyone else it has to be hosted — and three things about it are wrong the
moment it is. Can each be fixed without changing what the app *is*?

1. **The backend's address is in the bundle.** `VITE_API_URL` is inlined at build time, so a
   deployed build hands every visitor the API's hostname and port in devtools.
2. **The API has no authentication.** `mva-viz-api` was written for loopback: it holds no
   write verb, so nothing needed a token. `/api/panel/locus` serves **real patient
   positions**, and the moment the service binds a public interface that is a public fact.
3. **Anyone with the URL can read it.** There is no gate of any kind.

_(step-0 platform machinery: this entry records decisions and measurements, not a
hypothesis. Per [`docs/method.md`](../../method.md), step 0 takes no hypotheses. It is filed
in step 0 rather than a research step because it is a cross-step platform change — every
step's exhibits are served through it.)_

## The decisions, and the options rejected

### 1. Hide the backend: a proxy, not React Server Components

The obvious way to keep API calls off the client is to fetch on the server — React Server
Components. The app is a **Vite SPA**: 340 files, ~45k lines, 17 pages on `react-router-dom`
v7 with TanStack Query. Moving it to the Next.js App Router is a multi-day rewrite of every
page's data layer, days before a submission deadline, and it buys exactly one thing this
case needs: the backend's address not being in the bundle.

A proxy function buys the same thing for a one-line change at the single choke point every
request already passes through — [`app/src/api/client.ts`](../../../app/src/api/client.ts)
owns the only `fetch` in the app (an eslint rule enforces that). So:

- `VITE_API_URL=/` in the hosted build → `buildUrl()` produces same-origin paths;
- [`app/api/[...path].ts`](../../../app/api/%5B...path%5D.ts) receives them on Vercel and
  forwards to `MVA_VIZ_API_URL` with `MVA_VIZ_API_TOKEN` as `X-API-Key`.

Neither variable is `VITE_`-prefixed, so Vite **cannot** inline them: `import.meta.env`
exposes `VITE_*` and nothing else. That prefix rule is the mechanism, not a convention.

What this does *not* do: the network tab still shows `/api/panel/genes`. The request is
visible; the *backend* is not. RSC would hide both. Recorded as a deliberate trade, revisit
if the app ever moves to Next.js for other reasons.

One wrinkle the design had to absorb: the app's liveness probe calls `/health`, which on
`mva-viz-api` sits **outside** `/api` (it is the one route with no token, so an uptime probe
carries no secret). The catch-all only matches `/api/*`, so `vercel.json` rewrites `/health`
to [`api/liveness.ts`](../../../app/api/liveness.ts), which maps it back. The forwarding
itself is shared — [`app/server/upstream.ts`](../../../app/server/upstream.ts) — so the
token, the 30 s timeout, the response-header allowlist and the `no-store` rule are decided
once for both routes.

### 2. Authenticate the API: the same token mechanism as the read store

[`src/mva/viz/auth.py`](../../../src/mva/viz/auth.py) mirrors
[`mva.reads.api.app`](../../../src/mva/reads/api/app.py): `MVA_VIZ_TOKEN` empty leaves the
API open (correct on loopback), set makes every `/api/*` route require it as `X-API-Key`.
One mechanism to reason about, one header to configure. Two differences from the read-store
guard, both deliberate:

- the comparison is `secrets.compare_digest`, not `!=`. A plain comparison returns as soon
  as two bytes differ, so its duration leaks how much of a guess was right.
- an empty token installs **no dependency at all** rather than a no-op one, so an open
  deployment does not advertise a security scheme in its OpenAPI schema.

`/health` is outside the guard on purpose. Nothing else is.

The warning that used to print on a non-loopback bind became a **refusal**:
`mva-viz-api --host 0.0.0.0` with no token now exits `2` and says why. A warning printed
into a systemd log is not a control — nobody reads it, and the failure it describes is
"patient positions are now public". `--insecure` is the explicit override.

### 3. The password gate: middleware, not a route in the app

Vercel's built-in Password Protection is a Pro-plan feature and was not assumed. The
alternative had one hard requirement: **nothing may load before the password**. A login
route inside the SPA fails that by construction — by the time React renders it, the visitor
already has `index.html` and every JavaScript chunk.

So the gate is [`app/middleware.ts`](../../../app/middleware.ts), Vercel Routing Middleware,
which runs *before the CDN cache* on every path. Unauthenticated document requests get a
self-contained password page ([`server/loginPage.ts`](../../../app/server/loginPage.ts) —
inline CSS, inline script, no bundle, no font file); everything else gets a 401.

The session is a signed cookie, not a session store
([`server/session.ts`](../../../app/server/session.ts)):

```
mva_dash=1757260800.k7Qf...T4
         └ expiry ┘ └ HMAC-SHA256 ┘
key     = DASHBOARD_SESSION_SECRET + ":" + DASHBOARD_PASSWORD
message = "v1:<expiry>"
```

Folding the password into the key is what makes rotation work: changing
`DASHBOARD_PASSWORD` in the Vercel project invalidates every cookie already issued. With the
secret alone, everyone who logged in before a rotation would still be inside.

Three further choices, each with its reason:

- **The proxy re-checks the session.** The middleware already refused the request. The proxy
  is the one route that reaches patient data; a matcher edited wrongly must not be the only
  thing between the public and `/api/panel/locus`.
- **Fail closed.** With `DASHBOARD_PASSWORD` or `DASHBOARD_SESSION_SECRET` missing, the
  deployment answers `503` naming the missing variable. A misconfigured private dashboard
  must be unreachable, never public.
- **Every proxied reply is `Cache-Control: no-store, private`,** whatever upstream said. A
  CDN that cached a locus reply would serve it to the next visitor — including one who
  arrives after the password changed.

### 4. Patient coordinates transit Vercel — a decision, not an oversight

`/api/panel/locus` returns real positions. Three options were on the table: block that route
at the proxy (the hosted panel degrades to its fixture), allow it with no caching, or deploy
fixtures-only. **Allow it, no-store** was chosen by the user, with the trade stated: the
coordinates leave the VPS and pass through Vercel's edge to the browser of anyone past the
password. `no-store, private` means no shared cache retains them, and
[`tools/check_coordinates.py`](../../../tools/check_coordinates.py) is unaffected — it gates
the *repository*, and no coordinate is committed by any of this.

## What was changed

| File | Change |
|---|---|
| `src/mva/viz/auth.py` | new — the token guard, constant-time |
| `src/mva/viz/app.py` | every `/api/*` router carries the guard; `/health` does not |
| `src/mva/viz/serve.py` | a public bind without a token exits `2`; `--insecure` overrides |
| `src/mva/warehouse/settings.py` | `MVA_VIZ_TOKEN` default `""` |
| `.env.example` | `MVA_VIZ_TOKEN`, and why the hosted origin needs no CORS entry |
| `tools/setup-viz-api-service.sh` | new — systemd unit, loopback bind, prints the TLS proxy block |
| `app/middleware.ts` | new — the password gate |
| `app/server/{session,loginPage,upstream}.ts` | new — cookie, password page, one forwarder |
| `app/api/{[...path],liveness,login,logout}.ts` | new — the proxy and the two auth routes |
| `app/vercel.json`, `app/tsconfig.vercel.json` | new — rewrites, security headers, typechecking |
| `app/src/api/client.ts` | `VITE_API_URL` may be a same-origin prefix; `API_LABEL` for display; 502/504 count as unreachable |
| `app/src/components/{Header.tsx,failure.ts}` | messages that are true in both deployments |
| `app/src/test/setup.ts` | canvas stub guarded, so a node-environment test file can exist |
| `docs/dictionary.md` | 15 hosting terms in §15, plus the request-path diagram (486 entries) |

## Commands run, and what they printed

### The gates

```
$ ./tools/check-python.sh
1909 passed
python gate: green

$ cd app && pnpm run check
Test Files  41 passed (41)
     Tests  567 passed (567)

$ cd app && pnpm run build
✓ built in 1.42s

$ bash -n tools/setup-viz-api-service.sh
(no output — syntax valid)
```

### The token guard, against a live server

Not a stub: `mva-viz-api` started on loopback with a token, answering from the hosted
PostgreSQL and the object store.

```
$ MVA_VIZ_TOKEN=smoke-test-token-abc uv run mva-viz-api --port 8917
auth:    X-API-Key required

$ curl -s http://127.0.0.1:8917/health
{"ok":true,"service":"mva-viz-api"}                                 # 200, no token sent

$ curl -s http://127.0.0.1:8917/api/overview
{"detail":"missing or wrong X-API-Key"}                             # 401

$ curl -s -H 'X-API-Key: wrong' …/api/overview                      # 401
$ curl -s -H 'X-API-Key: smoke-test-token-abc' …/api/overview       # 200
```

### The bind refusal

```
$ uv run mva-viz-api --host 0.0.0.0 --port 8918
refusing to bind 0.0.0.0 with no MVA_VIZ_TOKEN: /api/panel/locus serves real patient
positions to anyone who can reach the port.
Set MVA_VIZ_TOKEN in .env (the Vercel proxy sends it as X-API-Key), or pass --insecure
if the port is genuinely private.
exit=2
```

### The proxy, against that same live server

`forward()` was run out of the app's own module against `http://127.0.0.1:8917` with the
token in the environment — the exact hop Vercel will make. It returned `200`,
`cache-control: no-store, private`, and the envelope's real provenance string:

```
source = pg.results.stats_sn + stats_tstv + allele_balance_flags,
         pg.warehouse.filter_gt_counts + contig_counts + profile_scalars +
         source_objects + probe_ledger, s3 runs.parquet
```

`/health` came back `{"ok":true,"service":"mva-viz-api"}`, a wrong token came back as the
proxy's own `502` (never the upstream `401`), and a dead port came back `502`. That run was
a throwaway; its assertions were then rewritten hermetically as
`app/src/test/upstream.test.ts` so they run in CI without a server.

### New tests

| File | Count | Covers |
|---|---|---|
| `tests/test_viz_auth.py` | 10 | `/health` open; 401 with no token and with a wrong one; 200 with it; empty token open; `resolve_token` precedence; the bind refusal and `--insecure` |
| `app/src/test/hosting.test.ts` | 19 | cookie forge / expiry-extension / expiry / password-rotation / secret-rotation rejection; the three `Set-Cookie` flags; `hasSession` failing closed when unconfigured; `safeNext` against five open-redirect shapes; the login page escaping what it reflects |
| `app/src/test/upstream.test.ts` | 11 | the URL and token sent upstream; no cookie forwarded; POST body buffered; `no-store` forced over the upstream's own caching header; upstream `Set-Cookie` dropped; 401→502, unreachable→502, timeout→504, unconfigured→503; a real upstream 404 passed through |
| `app/src/test/client-fallback.test.ts` | +2 | the proxy's 502/504 fall back to fixtures; a 503 does not |

## Verdict, and what is not verified

The code paths above are tested and both gates are green. **No deployment has been made**:
nothing here has met a real Vercel project, a real reverse proxy or a real certificate. The
runbook in [`infrastructure.md` §3](../infrastructure.md) says so at the top, and its
end-to-end check (four `401`s and one `{"ok":true}` from a laptop) is the thing that would
turn this from written to verified.

Two limits worth restating because they are properties of the design, not gaps in it:

- **One shared password**, so a session identifies "someone who knew it", never a person.
  No user, no role, no record of who read what. Right for a hackathon dashboard shown to
  judges; wrong for anything clinical.
- **No rate limiting.** Vercel Functions are stateless, so a per-instance counter is
  defeated by concurrency. A wrong password costs a fixed ~400 ms; the password's own
  entropy does the rest, which is why it must be generated and not chosen. `vercel firewall`
  rate-limiting rules are the upgrade path.
