"""Request and response shapes for the reads API.

Validation happens here, at the edge, so a bad probe or a write statement is refused
with a 422 before a job ever exists — a failed scan over 1.07 billion reads is the
expensive way to learn a typo.
"""

from pydantic import BaseModel, Field, field_validator

from .. import scan

#: One statement, read-only. DuckDB happily executes ``DROP``; the API does not.
READ_ONLY_OPENERS = ("select", "with", "describe", "show", "explain", "summarize", "from")


class Probe(BaseModel):
    """One candidate subsequence — a k-mer — with an optional label for the report."""

    sequence: str = Field(
        description="DNA to search for, A/C/G/T/N only; matched on both strands automatically",
        min_length=1,
    )
    name: str | None = Field(
        default=None, description="label used in the results; defaults to kmer1, kmer2, …"
    )

    @field_validator("sequence")
    @classmethod
    def _dna(cls, value: str) -> str:
        return scan.clean(value)  # raises ValueError -> 422 with the reason


class ProbeRequest(BaseModel):
    """Common body for the probe verbs: which sequences, over which store."""

    probes: list[Probe] = Field(
        min_length=1,
        max_length=500,
        description="every probe is asked in the same single "
        "pass — batch them, do not loop requests",
    )
    root: str | None = Field(
        default=None,
        description="store root override: a staging path or an "
        "s3:// prefix (default: the object store)",
    )


class ScanRequest(ProbeRequest):
    limit: int = Field(
        default=100,
        ge=1,
        le=10_000,
        description="reads reported per probe; the scan itself is unlimited",
    )


class SqlRequest(BaseModel):
    """Arbitrary read-only SQL with the store bound as the ``reads`` view."""

    query: str = Field(
        min_length=1, description="one read-only statement; the view `reads` is the whole store"
    )
    limit: int = Field(default=10_000, ge=1, le=100_000, description="rows returned at most")
    root: str | None = None

    @field_validator("query")
    @classmethod
    def _read_only(cls, value: str) -> str:
        statement = value.strip().rstrip(";").strip()
        if ";" in statement:
            raise ValueError("one statement per request — remove the ';'")
        if not statement.lower().startswith(READ_ONLY_OPENERS):
            allowed = ", ".join(READ_ONLY_OPENERS).upper()
            raise ValueError(f"read-only queries only (must start with one of: {allowed})")
        return statement


class VerifyRequest(BaseModel):
    """Prove the store matches the delivery."""

    expected_total: int | None = Field(
        default=None, description="grand total from ideation/data-findings.md"
    )
    shallow: bool = Field(
        default=False, description="skip the full-decompression round-trip checks"
    )
    source: str | None = Field(
        default=None,
        description="delivery directory or s3 spec, needed for "
        "the deep checks (default: MVA_SOURCE_DIR)",
    )
    root: str | None = None


class BenchRequest(BaseModel):
    """Race the conversion engines on a sample."""

    reads: int = Field(default=1_000_000, ge=1_000, le=100_000_000)
    engines: list[str] = Field(default_factory=list, description="subset to race; empty means all")
    jobs: int = Field(
        default=1, ge=1, le=64, description="size the memory budget as one job of a JOBS-way run"
    )
    memory_limit: str | None = None
    source: str | None = None


class ConvertRequest(BaseModel):
    """Convert every FASTQ to sharded Parquet and (by default) upload the store."""

    engine: str = Field(default="oxbow")
    jobs: int = Field(default=4, ge=1, le=64)
    threads: int | None = Field(default=None, ge=1, le=128)
    staging: str | None = Field(
        default=None, description="local shard directory (default: MVA_STAGING_DIR)"
    )
    upload: bool = Field(default=True, description="False converts locally without publishing")
    source: str | None = None


class JobOut(BaseModel):
    """One job, in any state. ``result`` is null until ``state`` is ``done``."""

    id: str
    verb: str
    state: str
    params: dict
    submitted_at: float
    started_at: float | None
    finished_at: float | None
    elapsed_seconds: float | None
    result: dict | None
    error: str | None
