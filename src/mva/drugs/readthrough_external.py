"""The external check: predict a PTC context the fit has never seen, against its measurement.

A positive control shows a method recovers something already known *in general*. This is
stronger and rarer: when the published measurement set happens to contain the very allele a
case is about, that context can be **deleted from the model entirely**, predicted from the
others, and compared with the measurement that was held back.

Two numbers per context, both reported whether they flatter the model or not:

* **rank correlation across compounds** — does the model order the drugs for this unseen stop
  the way the measurement does?
* **mean absolute error** — how far off are the values, in the assay's own unit?

A rank correlation over a handful of compounds is weak evidence and the docstring says so;
the per-row table is the real output, so a reader can see *which* compound the model missed.

Case-agnostic: contexts are names in a measurement table; no gene, patient or position here.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from scipy.stats import spearmanr

from mva.drugs.readthrough import Measurement, ReadthroughModel

__all__ = ["COLUMNS", "external_check"]

COLUMNS = (
    "context",
    "drug_name",
    "predicted",
    "measured",
    "absolute_error",
    "backoff_level",
    "rows_behind_prediction",
    "censored_measurement",
    "unit",
    "source",
)


def external_check(
    measurements: Sequence[Measurement], contexts: Sequence[str]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """``(rows, summary)``: one row per held-out context × compound, and a per-context summary.

    Raises ``KeyError`` naming a context the measurement set does not hold, rather than
    silently reporting on the contexts it happens to have.
    """
    full = ReadthroughModel(list(measurements))
    rows: list[dict[str, Any]] = []
    summary: dict[str, Any] = {}
    for context in contexts:
        held = [m for m in measurements if m.context == context]
        if not held:
            raise KeyError(f"{context}: not in the measurement set")
        model = full.without(context)
        stop, plus4, minus1 = held[0].fine_key
        pairs: list[tuple[float, float]] = []
        for measurement in sorted(held, key=lambda m: m.drug):
            guess = model.predict(measurement.drug, stop, plus4, minus1)
            if guess.value is None:
                continue
            pairs.append((guess.value, measurement.value))
            rows.append(
                {
                    "context": context,
                    "drug_name": measurement.drug,
                    "predicted": round(guess.value, 3),
                    "measured": round(measurement.value, 3),
                    "absolute_error": round(guess.value - measurement.value, 3),
                    "backoff_level": guess.level,
                    "rows_behind_prediction": guess.rows,
                    "censored_measurement": str(measurement.censored).lower(),
                    "unit": measurement.unit,
                    "source": measurement.source,
                }
            )
        summary[context] = _score(pairs)
    return rows, summary


def _score(pairs: Sequence[tuple[float, float]]) -> dict[str, Any]:
    if not pairs:
        return {"drugs_compared": 0, "note": "no compound could be predicted for this context"}
    rho, p_value = spearmanr([a for a, _ in pairs], [b for _, b in pairs])
    measured = sorted(b for _, b in pairs)
    return {
        "drugs_compared": len(pairs),
        "spearman_across_drugs": round(float(rho), 4),
        "p_value": round(float(p_value), 6),
        "mean_absolute_error": round(sum(abs(a - b) for a, b in pairs) / len(pairs), 4),
        "median_measured": round(measured[len(measured) // 2], 3),
    }
