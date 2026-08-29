# The delivery is immutable, and the bucket is the source of truth

**Standing:** firm. Verified 2026-08-29 — 12/12 objects `hash_verified`, 0 mismatches,
bucket versioning Enabled.

A scientific submission has to be able to say *which bytes* produced a result. That is only
possible if the input bytes cannot drift. So the delivered dataset is treated as
append-only, content-addressed, and never rewritten:

- **Stored unchanged.** The bytes in MinIO under `source/` are the publisher's bytes. No
  decompression, no re-compression, no renaming on the way in.
- **Hash-verified.** Every object carries a SHA-256; where the publisher hashes a file, ours
  is checked against theirs.
- **Versioned.** The bucket has versioning Enabled, so no upload can destroy an earlier
  one — a mistaken overwrite is recoverable rather than fatal.
- **Ledgered.** `warehouse.source_files` is **append-only**. The same file uploaded twice
  produces two rows with the same hash. That is a record of two events, not drift, and the
  ledger must not be deduplicated into "current state".

Fetching happens **on the server, from the publisher** rather than uploading a local copy.
It is faster (uploading the local copy would have taken 8.7 hours at the measured rate) and
it is better provenance: the bytes come from the source, and the publisher's own SHA-256
makes the result checkable. Evidence:
[`methodology/014`](../methodology/014-source-of-truth-and-lineage.md).

The local `~/ubuntu/data/` copy is a **convenience mirror**, not the source of truth.
Deleting it costs a download.

## Consequences

Everything downstream is derived and therefore disposable: `variants_raw` is a
`vcf-ingest` away, `results` is a `pg-derive` away, `build/warehouse/` is a `stage` away.
The only irreplaceable thing is the bucket, and even that is re-fetchable while the
publisher's dataset stands.

`source-check` is the standing audit: it surveys the bucket, re-verifies hashes and
refreshes the object inventory. Run it before trusting a number that came out of the chain.

**The lineage half of this is not finished.** `warehouse.data_lineage` holds one row, it
points at a *local* path, its sha256 is empty, and there are no edges recording which
source objects produced the five derivations. Until that is fixed, "which bytes produced
this result" is answerable by argument, not by query. Tracked in
[`../roadmap.md`](../../roadmap.md).
