"""P(trans) — the probability two alleles sit on *opposite* copies of a chromosome.

A recessive disease needs both copies of a gene broken. Two heterozygous variants in one
gene do that only if they are on different copies (**in trans**); if both sit on the same
copy (**in cis**) the other copy is intact and there is no diagnosis. Which it is, is
called **phase**.

Phase is normally settled two ways, and neither is available here:

* **read-backed phasing** — one sequencing fragment covering both variants. Step 2 measured
  the lead pair 10,911 bases apart against ~266-base fragments, so no fragment can span it;
* **parental genotypes** — one allele from each parent. No parental DNA exists for this case.

What remains is a population statistic. Guo 2024 showed that if a pair of variants is seen
together in enough people, the *counts of the genotype combinations* reveal how often the
two travel on the same chromosome, and gnomAD publishes the resulting probability per pair.
That is what this module fetches.

**It is not this child's haplotype.** It is how a pair behaves in a reference population,
and every quotation of the number carries that sentence. A pair with either allele absent
from the dataset — which is the expected state for an ultra-rare disease allele — gets the
state :data:`UNDETERMINED` and the uninformative prior, never zero and never silently 1.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import httpx

#: gnomAD's public GraphQL endpoint.
GNOMAD_API = "https://gnomad.broadinstitute.org/api"

#: The only dataset that carries variant co-occurrence: gnomAD v2.1.1 exomes, on **GRCh37**.
#: A GRCh38 allele therefore reaches it by dbSNP identifier, not by coordinate — which is
#: also why an allele with no rsID is undetermined by construction.
DATASET = "gnomad_r2_1"

#: The fallback probability when the population says nothing. Two heterozygous variants in
#: one gene are, with no information at all, equally likely to sit on the same copy as on
#: opposite ones — so the uninformative prior is one half.
#:
#: The plan named "the paper's rare-pair base rate" instead. That number could not be read
#: from Guo 2024 during this step, and inventing one would be worse than using a prior whose
#: derivation is one sentence long. The deviation is recorded in methodology entry 098, and
#: :func:`base_rate` measures an empirical rate from whatever pairs *were* resolvable, so the
#: assumption is reported next to a number from this run rather than left as an assertion.
UNINFORMATIVE_PRIOR = 0.5

#: gnomAD's own words when a pair cannot be looked up. Matched so a genuine API failure is
#: never silently recorded as "not in gnomAD".
NOT_IN_GNOMAD = "only available for variants found in gnomAD"


class TransState(Enum):
    """Where a pair's P(trans) came from — the provenance is part of the answer."""

    #: gnomAD returned a co-occurrence estimate for this exact pair.
    OBSERVED = "observed"
    #: At least one allele is not in the dataset, so no estimate exists.
    UNDETERMINED = "undetermined"
    #: The two alleles are two ALTs of one site, so one copy of each: trans by construction.
    SAME_SITE = "same-site"
    #: The lookup itself failed. Not the same as "absent", and never reported as one.
    ERROR = "error"


UNDETERMINED = TransState.UNDETERMINED


@dataclass(frozen=True)
class TransEstimate:
    """One pair's P(trans), its state, and the receipt."""

    p_trans: float
    state: TransState
    source: str
    left_id: str = ""
    right_id: str = ""
    note: str = ""

    @property
    def is_measured(self) -> bool:
        return self.state is TransState.OBSERVED

    @property
    def caveat(self) -> str:
        """The sentence that must travel with the number wherever it is quoted."""
        if self.state is TransState.OBSERVED:
            return (
                "a population co-occurrence statistic, not this child's haplotype; "
                "poorly calibrated for ultra-rare pairs (Guo 2024)"
            )
        if self.state is TransState.SAME_SITE:
            return "two ALT alleles of one site: one copy of each, trans by construction"
        return (
            "no population estimate exists for this pair; the uninformative prior is "
            "reported and the pair is labelled undetermined"
        )


class GnomadCooccurrence:
    """The gnomAD co-occurrence lookup, behind a client that never raises at the caller.

    Two queries, both tiny: an rsID resolves to the dataset's own variant identifier, and a
    pair of identifiers resolves to ``p_compound_heterozygous``. Replies are memoised for
    the life of the instance, because a genome-wide ranking asks about the same allele in
    many pairs.
    """

    def __init__(
        self,
        *,
        base_url: str = GNOMAD_API,
        dataset: str = DATASET,
        client: httpx.Client | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url
        self.dataset = dataset
        self._client = client or httpx.Client(timeout=timeout)
        self._owned = client is None
        self._ids: dict[str, str | None] = {}
        self.requests = 0

    def close(self) -> None:
        if self._owned:
            self._client.close()

    def __enter__(self) -> GnomadCooccurrence:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def variant_id(self, rsid: str) -> str | None:
        """The dataset's identifier for ``rsid``, or ``None`` if it holds no such variant."""
        if not rsid:
            return None
        if rsid in self._ids:
            return self._ids[rsid]
        query = f'{{ variant(rsid: "{rsid}", dataset: {self.dataset}) {{ variant_id }} }}'
        payload = self._post(query)
        variant = ((payload or {}).get("data") or {}).get("variant") or {}
        found = variant.get("variant_id")
        self._ids[rsid] = found
        return found

    def cooccurrence(self, left: str, right: str) -> tuple[float | None, str]:
        """``p_compound_heterozygous`` for two dataset identifiers, and any message."""
        query = (
            f'{{ variant_cooccurrence(variants: ["{left}", "{right}"], dataset: {self.dataset}) '
            f"{{ p_compound_heterozygous genotype_counts }} }}"
        )
        payload = self._post(query)
        if payload is None:
            return None, "the co-occurrence request failed"
        errors = payload.get("errors") or []
        if errors:
            return None, str(errors[0].get("message", "")).strip()
        block = (payload.get("data") or {}).get("variant_cooccurrence") or {}
        value = block.get("p_compound_heterozygous")
        return (float(value) if value is not None else None), ""

    def _post(self, query: str) -> dict | None:
        try:
            self.requests += 1
            response = self._client.post(self.base_url, json={"query": query})
            response.raise_for_status()
            body = response.json()
            return body if isinstance(body, dict) else None
        except (httpx.HTTPError, ValueError):
            return None


def estimate(
    lookup: GnomadCooccurrence | None,
    *,
    left_rsid: str,
    right_rsid: str,
    same_site: bool = False,
    prior: float = UNINFORMATIVE_PRIOR,
) -> TransEstimate:
    """P(trans) for one pair, with the state that says how much to believe it.

    ``lookup`` may be ``None``, which is the offline path: everything becomes
    *undetermined* and the prior is reported. That is a real mode, not a degraded one — it
    is what a reviewer runs to reproduce the ranking without a network.
    """
    source = f"gnomAD {DATASET} variant_cooccurrence" if lookup else "offline: no lookup"
    if same_site:
        return TransEstimate(
            p_trans=1.0,
            state=TransState.SAME_SITE,
            source="the genotype itself",
            note="two ALT alleles of one site",
        )
    if lookup is None:
        return TransEstimate(prior, TransState.UNDETERMINED, source, note="no lookup configured")
    left = lookup.variant_id(left_rsid)
    right = lookup.variant_id(right_rsid)
    if not left or not right:
        missing = "left" if not left else "right"
        if not left and not right:
            missing = "both"
        return TransEstimate(
            prior,
            TransState.UNDETERMINED,
            source,
            left_id=left or "",
            right_id=right or "",
            note=f"{missing} allele not in {DATASET} (no rsID, or not called there)",
        )
    value, message = lookup.cooccurrence(left, right)
    if value is not None:
        return TransEstimate(value, TransState.OBSERVED, source, left_id=left, right_id=right)
    state = TransState.UNDETERMINED if NOT_IN_GNOMAD in message else TransState.ERROR
    return TransEstimate(
        prior, state, source, left_id=left, right_id=right, note=message or "no estimate returned"
    )


def base_rate(estimates: list[TransEstimate]) -> float | None:
    """The mean P(trans) over the pairs that *were* resolvable, or ``None`` if none were.

    Reported beside every undetermined pair: it is this run's own answer to "what does a
    rare pair in this dataset usually look like", and it is a measurement rather than an
    assumption, so the prior and the empirical rate can be compared in the write-up.
    """
    observed = [item.p_trans for item in estimates if item.is_measured]
    return sum(observed) / len(observed) if observed else None
