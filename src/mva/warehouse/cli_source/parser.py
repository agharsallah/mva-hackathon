"""The argument parser: every ``source-*`` verb, its flags, and its help text.

One module because it is one concern — the command-line surface — separate from the
handlers in :mod:`.upload`, :mod:`.fetch` and :mod:`.check` that do the actual work.
"""

from pathlib import Path

from . import check, context, fetch, upload


def register(subparsers) -> None:
    """Attach the ``source-*`` verbs to the top-level parser."""

    def add(name, handler, help_text):
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument(
            "--directory",
            type=Path,
            default=context.DEFAULT_SOURCE,
            help=f"the delivery directory (default: {context.DEFAULT_SOURCE})",
        )
        sub.set_defaults(handler=handler)
        return sub

    add("source-scan", upload.do_scan, "inventory the delivery without uploading")
    up = add(
        "source-upload",
        upload.do_upload,
        "hash, upload unchanged, verify, and record in the ledger",
    )
    up.add_argument("--only", nargs="*", help="file names or kinds (fastq, vcf, index, document)")
    up.add_argument(
        "--force",
        action="store_true",
        help="re-upload even when an identical copy is already there",
    )
    add("source-status", upload.do_status, "compare the delivery on disk with the ledger")
    add(
        "source-check",
        check.do_check,
        "survey the bucket, verify hashes, refresh the object inventory",
    )

    fetch_parser = subparsers.add_parser(
        "source-fetch",
        help="RUN ON THE SERVER: download from the publisher straight into the bucket",
    )
    fetch_parser.add_argument(
        "--repo", default=context.DEFAULT_REPO, help="Hugging Face dataset repo"
    )
    fetch_parser.add_argument("--only", nargs="*", help="file names (default: all published)")
    fetch_parser.add_argument("--token", help="Hugging Face token; else $HF_TOKEN")
    fetch_parser.add_argument(
        "--staging",
        type=Path,
        default=context.DEFAULT_STAGING,
        help="scratch directory, used only with --verify",
    )
    fetch_parser.add_argument(
        "--keep",
        action="store_true",
        help="with --verify, keep the downloaded copy instead of deleting",
    )
    fetch_parser.add_argument(
        "--tee",
        type=Path,
        help="also write each streamed file here, so a failed upload does "
        "not throw the download away",
    )
    fetch_parser.add_argument(
        "--verify",
        action="store_true",
        help="download to disk and check the publisher's SHA-256 first "
        "(slower, needs disk for one file)",
    )
    fetch_parser.set_defaults(handler=fetch.do_fetch)
