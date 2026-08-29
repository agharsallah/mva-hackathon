# 011 — Is DuckDB lossless, and what should actually be ingested?

## Question

Before loading the delivered data for analysis: does DuckDB read it without losing or
altering anything, and how would we *know*?

## Finding first

**DuckDB reads the callset losslessly.** All 5,012,204 VCF records round-trip to a
byte-identical SHA-256. Of 24 adversarial values, 23 survived exactly; the single failure
is empty-string-to-NULL, which does not occur in a VCF and is detected rather than assumed
away. The general pattern is that DuckDB **fails loudly rather than corrupting silently**.

**But 99.6% of the 85 GB should not be ingested at all.** It is FASTQ — raw reads, which
are not tabular and are not queried with SQL.

## Inputs

- `WGS_EX2312012_HGWCNDSX7.vcf.gz` (315,153,971 bytes; 2,617 header lines; 10 columns;
  sample `WGS_EX2312012`), read from `~/ubuntu/data`.
- `duckdb` Python package, `postgres`/`ducklake` extensions unused here.
- Code: `src/mva/warehouse/{integrity,vcfstage,cli_vcf}.py`.

## Commands run and observed output

### 1. What the 85 GB actually is

```
  FASTQ (raw reads)       8 files    84.67 GB   99.6%
  VCF + index             2 files     0.32 GB    0.4%
  documents               2 files     0.00 GB    0.0%
  TOTAL                  12 files    84.99 GB
```

From the measured profile, the FASTQ hold **1,079,858,785 reads**. As database rows —
name + 149 bp sequence + 149-byte quality — that is ~0.4 TB from 85 GB of input, and
nothing done with reads is a SQL operation. The VCF is already the analytical summary the
caller produced from them.

### 2. Adversarial value round-trip

24 values chosen for being the ones that get silently mangled by TSV ingestion, written and
read back through the same path staging uses:

```
23/24 byte-identical; altered: ['empty_string']
```

`empty_string` `''` came back as `NULL`. Preserved exactly: `.`, `NA`, `NULL`, `None`,
`007`, BIGINT-max and one above it, 19-digit float, `1e-300`, `-0.0`, `Inf`, `NaN`, `T`,
`true`, date- and time-like strings, `1/2`, `0|1`, comma lists, unicode, embedded quotes, a
5,000-character string, whitespace-only.

### 3. Type-inference hazards

```
── a column of integers with VCF's '.' missing marker ──
ints + one dot (sample=-1)         type=VARCHAR  rows=4  nulls=0
ints + one dot (default sample)    type=VARCHAR  rows=4  nulls=0

── the classic sniffer trap: bad value AFTER the sample window ──
30k ints then text (sample=-1)     type=VARCHAR  rows=30011  nulls=0
30k ints then text (sample=1024)   ERROR: Conversion Error: CSV Error on Line: 30002

── empty cell inside a numeric column ──
ints + empty cell                  type=BIGINT   rows=4  nulls=1

── unparseable value against a declared type ──
forced INTEGER on bad data -> ERROR: Conversion Error: CSV Error on Line: 4
```

Three conclusions. A `.` keeps the whole column text, so no value is nulled. The sniffer
trap is real but `sample_size=-1` — what `mva-warehouse stage` already uses — avoids it,
and the narrow-sample case **errors** rather than corrupting. An empty cell in a numeric
column is the one genuine loss.

### 4. Full-callset round trip

```
$ uv run mva-warehouse vcf-verify WGS_EX2312012_HGWCNDSX7.vcf.gz
source rows    : 5,012,204
rebuilt rows   : 5,012,204
source sha256  : 33c78c35c2c407782b3429fcf4e7844533fede73c3cdbc4e3208dea5ffb19e59
rebuilt sha256 : 33c78c35c2c407782b3429fcf4e7844533fede73c3cdbc4e3208dea5ffb19e59
IDENTICAL      : True                                              (47 s)
```

The source digest is computed by reading the file in plain Python, never through DuckDB, so
the check does not depend on the component under test.

### 5. Conservation fingerprint, 1,000,000 records

```
staged 1,000,000 records in 14.4s -> 39 MB parquet
extrapolated to 5,012,204: ~72s, ~0.19 GB

column          type before   type after   content
chrom, pos, id, ref, alt, qual, filter, info, format, sample_call
                    VARCHAR      VARCHAR   identical  (all ten)

No discrepancies: every column's content is byte-identical.
```

The scratch Parquet was written outside the repository and deleted afterwards.

### 6. Tests

```
$ uv run pytest tests/ -q
209 passed in 4.52s
```

23 are new. They are adversarial by design: most corrupt data deliberately — drop a row,
swap an empty string for a NULL, reorder, duplicate — and assert the fingerprint notices. A
check that cannot fail is worthless.

## Bugs this work caught

1. **`executemany` row-by-row was unusably slow** — 200,000 records did not finish in two
   minutes. Replaced with DuckDB's native CSV reader over the VCF: 5,012,204 records in
   **15.5 s**, roughly 200× faster, and it means the ingest path and the verification path
   exercise the same reader, so verification actually says something about ingest.

2. **The fingerprint scanned once per column.** Unnoticeable on a 24-row profile table,
   ruinous at five million rows — a 1M-record comparison timed out at 115 s. Rewritten to
   gather every column's statistics in one pass.

3. **The row-count delta printed the wrong sign.** A *lost* row reported `(+1 rows)`.
   Caught by a test asserting the sign, not just the presence of a discrepancy.

4. **`line_no` was BIGINT while the docstring promised all-text.** Resolved by naming the
   distinction instead of hiding it: `line_no` is our own bookkeeping and is correctly
   typed; `FILE_COLUMNS` — everything that came out of the VCF — is text, and the test now
   asserts exactly that.

Also noted: `case` is a SQL reserved word, and `end` is already quoted in
`analysis.py`. Sanitising column names does not currently check for reserved words. Not a
live bug — no staged column collides — but it is a latent one worth fixing before layer 2
introduces more columns.

## Conclusion

DuckDB is trustworthy for this data, and the claim is now *checkable* rather than assumed:
`vcf-verify` reproduces the source bytes, and `fingerprint`/`compare` detect row loss,
content change, and NULL/empty conflation at every hop.

The proposed structure — a lossless all-text `variants_raw` anchor, with typed layers
derived from it — is written up for review in
[`docs/ingestion-plan.md`](../docs/ingestion-plan.md).

**No data has been ingested.** No FASTQ was read beyond the committed profile, nothing was
written to PostgreSQL, and only a 1,000,000-record sample was staged, outside the
repository and since deleted. Held pending review, as instructed.
