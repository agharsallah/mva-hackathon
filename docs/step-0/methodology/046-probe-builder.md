# 046 — The probe payload builder: a submission CSV nobody has to type

**A step-0 platform entry, so it carries no hypothesis.** It records what was built, the
byte-level conformance check that decided the file is safe to upload, and what the new
endpoint deliberately does *not* claim.

## Question

Everything upstream of this ranks alleles. The file that actually gets uploaded to the
HuggingFace Space was still assembled by hand, and a hand-typed coordinate is the one
mistake that costs a **whole submission out of eighteen** rather than a row out of ten —
the scorer compares `(chrom, pos, ref, alt)` by exact string/int equality and never
normalizes the chromosome (intel §8.1).

Two things had to be true at once:

1. a coordinate must move from the dashboard to the CSV **by reference**, never through a
   keyboard;
2. the rules must be the **same** rules the offline pipeline writes with, not a second
   implementation in the browser that can drift from it.

## Inputs

| Input | Role |
|---|---|
| `src/mva/pipeline/submission.py` | the single owner of the CSV contract (row cap, epcr interval, distinctness, finding types, `PROBAND01`) |
| `src/mva/pipeline/scorer.py` | the leaked-scorer replica, for rehearsal |
| `src/mva/pipeline/variant.py` | `Variant.from_vcf` — the only legal chromosome-string builder |
| `ressources/hackathon-rules/track1_submission_template.csv` | the organisers' own template, read as bytes for the conformance check |
| `/api/panel/annotations` | the candidate list the picker is fed from (bare contigs, as the callset spells them) |
| Code added | `src/mva/viz/probebuild.py`, `app/src/pages/probes/ProbeBuilder.tsx` (+ `CandidatePicker`, `PayloadTable`, `probePayload.ts`, `useProbeBuild.ts`), `app/src/api/types/probebuild.ts` |

## What was built

`POST /api/probe/build` — body `{rows: [{variant_1, variant_2?, epcr, finding_type,
notes?}]}` with **bare** contigs in; response `{csv, valid, problems, self_test}` with
`chr`-prefixed contigs in the CSV. Nothing is written to disk on the server; the browser
saves the string through a Blob URL.

Three additions were made to the pipeline rather than forked into the viz layer, because
the pipeline is the single owner of format rules:

| Addition | Why it could not live in `viz` |
|---|---|
| `submission.problems(rows, require_descending=False)` | an interactive builder needs **every** violation at once; `validate` now raises on the first of the same list, so the two can never disagree |
| `submission.read_submission(source)` | parses a written file back **the way the scorer parses it** — verbatim strings, no contig normalization. A reader that "helpfully" re-added `chr` would hide the exact bug it exists to expose |
| `Row.variants()` | a row holds a `frozenset` of alleles (§8.2); `scorer._variants` was the same function and now calls this one |

`require_descending` is the one rule the scorer does *not* have and a builder does: the
scorer sorts, so a shuffled file scores identically — but then the rows a human reads and
the ranks an oracle reply is decoded from are two different orderings.

### Validation, and where each rule lives

| Rule | Enforced in | Surfaced as |
|---|---|---|
| ≤ 10 rows | `submission.problems` | error |
| epcr ∈ (0, 1] | `submission.problems` | error, named by row |
| epcr distinct | `submission.problems` | error |
| epcr strictly descending in file order | `submission.problems(require_descending=True)` | error, named by row |
| `finding_type` ∈ {primary, secondary} | `submission.problems` | error, named by row |
| `proband_id` constant | `submission.PROBAND_ID`, written by `Row.as_fields` | never taken from the request at all |
| bare contig → `chr`-prefixed | `Variant.from_vcf` | the emitted CSV |
| duplicated allele in a pair row collapses (§8.2) | `Row.variants()` | **warning** — the file is legal, the payload is not what it looks like |
| two rows claiming the same allele set | `probebuild._repeat_warnings` | **warning** — a wasted rank |
| malformed body (missing field, `pos < 1`, empty allele) | the pydantic schema | HTTP 422, never reaches the rules |

An `error` blocks the file: `csv` comes back empty and `self_test` null, because the only
thing anyone would do with a rendered-but-invalid file is upload it.

### The self-test

There is no ground truth, so nothing here can say whether a candidate is right. What it
*can* prove is that the bytes parse the way the scorer parses them: the emitted CSV is read
back with `read_submission` and scored against a synthetic answer key equal to **row 1's
own alleles**. A correct file scores the maximum the scorer can give (§9.3).

## Commands run

```bash
uv run mva-viz-api --port 8955                       # own port; 8900 left alone
curl -s -X POST http://127.0.0.1:8955/api/probe/build -H 'content-type: application/json' \
     -d @body.json                                   # 2 rows: one synthetic pair, one synthetic single
curl -s -o /dev/null -w '%{http_code}' -X POST … -d '{"rows":[{…,"pos":0,…}]}'
uv run pytest -q
cd app && npm run typecheck && npm run build
```

## Observed output

### The live 2-row build (synthetic coordinates only)

`HTTP 200 in 0.021 s`, `valid: true`, `problems: []`,
`self_test: {rank_points: 100.0, f_max: 1.0, full_match_rank: 1, passed: true}`.

```csv
proband_id,chrom_1,pos_1,ref_1,alt_1,chrom_2,pos_2,ref_2,alt_2,epcr,finding_type,notes
PROBAND01,chr15,12345,C,T,chr15,12399,G,A,0.99,primary,"synthetic pair, live check"
PROBAND01,chr7,54321,A,G,,,,,0.98,secondary,synthetic single
```

Bare `15` and `7` went in; `chr15` and `chr7` came out. The pair sits in one row; the
single blanks all four `*_2` columns.

### Byte-level template conformance

The header line of the built file against the header line of the organisers' own
`track1_submission_template.csv`, compared as bytes:

| | value |
|---|---|
| template header (CRLF stripped) | 86 bytes |
| SHA-256, template | `1d4f7146a93b234bcc76c64009c64ccb090150e45f5abf4ca9b8d6edca02cafa` |
| SHA-256, built | `1d4f7146a93b234bcc76c64009c64ccb090150e45f5abf4ca9b8d6edca02cafa` |
| identical | **yes** |

`csv.reader` over both files gives the same header row and 12 fields on every line of
both.

**One difference, deliberate and recorded rather than copied: the shipped template uses
CRLF line endings, this writer emits LF.** `csv.reader` and pandas strip either. The
asymmetry favours LF: a scorer that split on `"\n"` by hand would leave a stray `\r` in the
last field of a *CRLF* file and never in one written here. The rule is asserted in
`tests/test_viz_probebuild.py` against the shipped file, not against a transcription of it.

### The error path, live

Two rows, ascending epcr and an unknown finding type:

```json
{"csv": "", "valid": false, "self_test": null, "problems": [
  {"severity": "error", "message": "row 2: finding_type must be one of ('primary', 'secondary'), got 'incidental'"},
  {"severity": "error", "message": "row 2: epcr 0.9 is not below row 1's 0.5 — file order must already be rank order"}]}
```

Both problems in one reply, each naming its row. `pos: 0` in the body is a **422** and
never reaches the rules.

## Findings

1. **The header was already right, and now it is *proven* right against the shipped file.**
   Transcription is not evidence. The conformance test reads
   `ressources/hackathon-rules/track1_submission_template.csv` itself, so a template the
   organisers revise breaks the test instead of breaking a submission.
2. **The self-test earns its keep through one negative control.** Scoring the same emitted
   bytes against a truth spelled with *bare* contigs gives `rank_points 0.0`
   (`test_a_bare_contig_in_the_truth_would_fail_the_self_test`). That is what makes
   `100.0 / 1.0` a statement rather than a tautology: the chr prefix is the difference
   between a full match and a miss, and the check can see it.
3. **Enumerating beats raising, and one list can do both.** Splitting `validate` into
   `problems` + a raise-on-first wrapper meant the browser could show every violation at
   once without a second rule set existing anywhere.
4. **A POST has no fixture path, and it must not get one.** `client.post` has no fixture
   fallback by design. A builder that "validates" against a stub would tell a user a file
   is safe to spend one of eighteen submissions on, with no rule having run — so the
   exhibit reports a down API as a down API and shows nothing where a verdict would be.

## Not claimed

* Nothing here says a candidate is causal. `self_test` is a statement about encoding.
* No submission was spent. Building costs nothing; the exhibit says so in a yellow callout
  and echoes the `mva-warehouse probe-log` command to run after a real upload.
* Indel representation is untouched: the scorer does no left-alignment on either side
  (§8.1), so a candidate must already be normalized before it reaches this builder.

## Tests

`tests/test_viz_probebuild.py`, 36 tests, hermetic — the endpoint reads no table, so the
router is mounted on a bare FastAPI app and nothing is faked. Every coordinate in the file
is synthetic (`pos 12345`). Covered: the template header against the shipped file, LF line
endings, the chr prefix in both directions and `chrM`, blank pair columns for a single,
quoted notes surviving a round trip, the constant `proband_id`, the row cap, epcr
distinctness / interval / descent, finding types, the §8.2 collapse and repeat warnings,
the self-test and its negative control, the 422s, the envelope, and the route being
registered on the real `create_app`.

`tests/test_submission.py` grew from 11 to 24 tests, covering the three pipeline
additions: `problems` enumerating rather than raising, `require_descending`,
`Row.variants()` order-independence and collapse, and `read_submission`'s round trip,
non-normalization, and its header / `proband_id` refusals.

`uv run pytest -q` → **1067 passed**, 11 failures, all pre-existing in
`tests/test_reads_api.py` and unrelated to this change. `npm run typecheck` and
`npm run build` both clean.
