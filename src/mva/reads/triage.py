"""Turn a probe count into words — shared by the CLI table and the API.

Kept apart from :mod:`.scan` so the query engine and the interpretation of its numbers
can change independently.
"""

#: Rule of thumb for a real single-copy 31-mer at this dataset's depth:
#: depth x (read_length - k + 1) / read_length ≈ 44 x (149 - 31 + 1) / 149.
EXPECTED_HINT = (
    "expected ~35 reads for a real single-copy 31-mer at this depth (44x * (149 - k + 1) / 149)"
)


def verdict(total: int, lanes: int) -> str:
    """Triage words for one probe's count."""
    if total == 0:
        return "absent"
    if total <= 2:
        return "error-level"
    return "present" if lanes >= 2 else "one lane only — suspect"
