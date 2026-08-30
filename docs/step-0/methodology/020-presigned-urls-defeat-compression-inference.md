# 020 — A presigned URL does not end in `.gz`

**A step-0 platform entry, so it carries no hypothesis.** It **amends**
[019](019-where-the-read-bytes-come-from.md), which established the presigned-URL route
into the object store but did not state how the reader learns the object is compressed.
019's conclusion stands; this adds the one detail that makes it work.

## Question

`--source s3` hands oxbow a presigned HTTPS link. Does the reader still recognise the
object as gzip?

## Finding

**No — and left alone it would have silently mis-read every object.** oxbow infers
compression from the *name*:

```python
if compression == "infer":
    bgzf_compressed = str(source).endswith(".gz") or str(source).endswith(".bgz")
```

A presigned link ends in its signature, not in the filename:

```
https://…/mva/source/WGS_….fastq.gz?X-Amz-Algorithm=…&X-Amz-Signature=…&X-Amz-Expires=43200
```

so `endswith(".gz")` is `False`, and the reader would open the object as plain text and
hand raw gzip bytes to the FASTQ parser. A local path is unaffected — it really does end
in `.gz` — which is exactly why this would have passed every local test and failed only on
the server.

## Fix

`mva.reads.engines.oxbow` now **states** the compression for a URL instead of letting it
be inferred. Every source reaching this code is gzip by construction: the delivery pattern
(`schema.FASTQ_NAME`) requires `.fastq.gz` or `.fq.gz`.

The regression test serves the file from a localhost range-capable server at a URL
carrying `?X-Amz-Signature=…&X-Amz-Expires=…`, and the test server strips the query string
as a real one does — so the name the reader sees is the presigned shape, not a tidy
filename.

## Conclusion

Never let a remote reader infer a format from a URL. The query string is part of the URL
and not part of the name, and the two only coincide for local paths — where the mistake
cannot be observed.
