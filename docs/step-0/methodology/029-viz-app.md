# 029 — The browser front end: `app/`

**A step-0 platform entry, so it carries no hypothesis.** It records what was built against
the [028](028-viz-api.md) contract, how it was verified, and the three contract facts the
live API corrected mid-build.

## Question

[028](028-viz-api.md) gave the browser one JSON origin. Can a React app consume it and turn
21 endpoints into a **reading surface** — seven pages that each answer one question, explain
their own domain terms to a reader with no genomics background, and carry a decoded legend on
every figure — while staying fully demoable with the API switched off?

Sub-question that shaped the build: the API was being written concurrently, so the app had to
be developed and demoed against nothing but the contract text.

## Inputs

| Input | Version / shape |
|---|---|
| Contract | `viz-api-contract.md`, shared with `mva-viz-api` |
| Live API | `mva-viz-api` on `http://127.0.0.1:8900`, all 21 endpoints |
| Live upstream | `mva-reads-api` at the operator's host, reached through the 6 proxy routes |
| Node | v24.14.0, npm 11.9.0 |
| Runtime deps | react 18.3.1, react-dom 18.3.1, @tanstack/react-query 5.102.8, react-router-dom 7.18.3, plotly.js-dist-min 4.0.0 |
| Build deps | vite 8.2.2, @vitejs/plugin-react 6.1.1, typescript 7.0.2, tailwindcss 4.3.3, @tailwindcss/vite 4.3.3, @types/react 18.3.31, @types/plotly.js-dist-min 2.3.4 |
| Fixture numbers | the measured aggregates in [`ideation/data-findings.md`](../../../ideation/data-findings.md) |

## Commands run

```
$ cd app && npm install
$ npm run build                     # tsc -b && vite build
$ npm run dev                       # 127.0.0.1:5173
$ find src -name '*.ts*' | xargs wc -l | sort -rn | head
```

Rendering was verified by dumping the post-JavaScript DOM of every route with headless Chrome
(the `chrome-devtools` MCP server was held by another session):

```
$ "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    --headless=new --disable-gpu --user-data-dir=<tmp> \
    --virtual-time-budget=14000 --dump-dom http://127.0.0.1:5173/<route>
```

Proxy envelope and job shape were confirmed directly:

```
$ curl -s http://127.0.0.1:8900/api/jobs
$ curl -s -X POST http://127.0.0.1:8900/api/probe/count \
    -H 'content-type: application/json' \
    -d '{"probes":[{"name":"client_shape_test","sequence":"ACGT…"}]}'
$ curl -s -X POST http://127.0.0.1:8900/api/jobs/<id>/cancel
```

## Observed output

Build, clean:

```
vite v8.2.2 building client environment for production...
✓ 123 modules transformed.
dist/index.html                          0.50 kB │ gzip:     0.32 kB
dist/assets/index-*.css                 26.59 kB │ gzip:     5.72 kB
dist/assets/Provenance-*.js              9.38 kB │ gzip:     3.62 kB
dist/assets/Overview-*.js               10.82 kB │ gzip:     4.00 kB
dist/assets/Panel-*.js                  11.24 kB │ gzip:     4.08 kB
dist/assets/Callset-*.js                13.47 kB │ gzip:     4.33 kB
dist/assets/Genome-*.js                 14.82 kB │ gzip:     5.11 kB
dist/assets/Probes-*.js                 18.38 kB │ gzip:     6.30 kB
dist/assets/Reads-*.js                  18.60 kB │ gzip:     6.19 kB
dist/assets/index-*.js                 232.26 kB │ gzip:    76.65 kB
dist/assets/plotly.min-*.js          4,066.60 kB │ gzip: 1,244.94 kB
✓ built in 1.10s
```

Plotly is 94 % of the shipped bytes and lands in its own chunk: the dynamic import keeps it
off the critical path, and each page is a separate chunk under 19 kB.

Every route rendered against the live API, fixtures enabled, with no error card and no
fixture fallback:

| Route | Plotly figures drawn | `fixture data` badge | API health dot | error cards |
|---|---|---|---|---|
| `/` | 2 | no | up | 0 |
| `/genome` | 5 | no | up | 0 |
| `/callset` | 5 | no | up | 0 |
| `/panel` | 3 | no | up | 0 |
| `/reads` | 6 | no | up | 0 |
| `/probes` | 1 | no | up | 0 |
| `/provenance` | 1 | no | up | 0 |

Re-run with `VITE_USE_FIXTURES=false` (fixture fallback disabled, so any failing endpoint
must surface): **0 error cards on all seven routes** — every endpoint answers live.

Re-run with the API stopped: all seven routes render from committed fixtures with the
`fixture data` badge shown, confirming the offline demo path.

Source size, against the repo's 400-line rule:

```
5945 total
 311 src/api/types.ts
 204 src/pages/panel/LocusExplorer.tsx
 200 src/fixtures/provenance.ts
 195 src/fixtures/genome.ts
 181 src/pages/reads/CycleQuality.tsx
```

Live job proxy, verified end to end:

```
GET  /api/jobs        → 200 {"data":[…2 jobs…],"cached_at":null,"source":"…/jobs"}
POST /api/probe/count → 200 {"data":{"id":"61e4a0521706","state":"running",…}}
POST /api/jobs/<id>/cancel → 200 {"data":{…,"elapsed_seconds":2.088}}
```

The probes page rendered that live list: 2 jobs, state chips, formatted timestamps, the
historical job's `IOException` truncated with the full text on hover.

The submitted job was followed to completion to confirm the result shape the app parses:

```
done  380.125 s
{"root": "s3://mva/reads", "seconds": 379.5,
 "expected": "expected ~35 reads for a real single-copy 31-mer at this depth (44x * (149 - k + 1) / 149)",
 "counts": [{"probe": "client_shape_test", "forward": 20, "reverse": 17,
             "total": 37, "lanes": 4, "verdict": "present"}]}
```

Matches `ProbeCountResult` field for field. One display consequence: `expected` is a whole
sentence, not `"~35 reads"`, so the chart annotation now shows the parsed number and the caption
carries the sentence. (The probe itself was a shape test — a synthetic `ACGT…` repeat, `verdict:
present` at 37 reads, which is what a low-complexity repeat is expected to do. It is not a
finding about the sample and is recorded here only as an API-contract confirmation.)

## Three contract facts the live API corrected

1. **The proxy routes are enveloped too.** The contract implied `/api/probe/*` and
   `/api/jobs*` returned upstream shapes directly. They carry the same
   `{data, cached_at, source}` envelope, so `post()` and `getBare()` now unwrap `body.data`.
2. **Job timestamps are Unix epoch floats, not ISO strings.** `submitted_at` came back as
   `1788194826.25`. The formatter would have thrown on `.replace`. `Instant = string | number`
   now covers both and `format.iso()` branches on the type. This was only findable against the
   live service — a contract-only build would have shipped a crash on the Probes page.
3. `mean_depth_x` is 44.3 (computed), not 44.0; `/api/callset/tstv` returns an object, not an
   array (already typed that way).

## One bug the live run exposed

With fixtures enabled, every page showed the `fixture data` badge even though every exhibit
displayed live data. Cause: `isUnreachable()` counted `AbortError` as "no server there", and
react-query aborts the first request of every React StrictMode double-mount. One spurious
abort flipped the whole session into fixture mode.

Fix: only a network-level `TypeError` counts as unreachable. A cancelled fetch propagates and
react-query handles it. The same edit removed `404` from the fallback triggers — now that the
API exists, an unknown gene or shard must reach the user as an error rather than be papered
over with fixture rows.

## Conclusions

- The contract was sufficient to build all seven pages and 23 exhibits before the API existed;
  the fixture layer is what made that possible and it doubles as the offline demo path.
- **Building against a contract alone is not enough to be correct.** Two of the three
  corrections above (the envelope on the proxy routes, epoch timestamps) were invisible in the
  contract text and would have been runtime failures. Verifying against the running service is
  not optional.
- Making `legend` a required prop of `Exhibit` turns a repo convention into a compile error.
  Cheap, and it held for all 23 exhibits without a single review note.
- 3D is used exactly three times, each with a genuine third axis. The discipline is worth
  recording because the temptation was to use it more.
- The patient-data rule survives contact with a UI: real positions exist only in the browser at
  runtime, and the locus fixture's synthetic `1000, 2000, 3000` ladder is documented as such in
  its module docstring.
