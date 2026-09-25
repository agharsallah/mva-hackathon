"""A context model for nonsense readthrough, and the held-out control that licenses it.

**Nonsense readthrough** is a ribosome ignoring a premature stop codon and carrying on to the
real end of the message, producing full-length protein with one near-cognate amino acid where
the stop was. Some small molecules raise that rate. How much they raise it depends far less on
the drug than on the **context** of the stop: which of the three stops it is, and above all the
base immediately following it (*+4*). That is the only part of the problem a model can learn
from published measurements of *other* people's stops and then apply to a new one.

The model here is deliberately the simplest thing that can be checked:

1. group the measured rows by ``(drug, stop, +4)`` and take the mean;
2. when a cell is empty or too thin, back off to ``(drug, stop)``, then to ``(drug)``;
3. report which level answered, and with how many rows, on every prediction.

No coefficients are fitted, so there is nothing to overfit beyond the group means — and the
control below is exactly the test of whether even that much generalises.

**The control.** :func:`leave_one_context_out` refits the model with one PTC context entirely
removed, predicts that context, and repeats for every context. The two numbers it reports are a
rank correlation (Spearman's rho — do the predictions order the held-out contexts the way the
measurements do?) and pairwise ordering accuracy (of all context pairs, what share is ordered
correctly?). A route whose control fails is reported as uninterpretable; it is not applied to a
patient's stop. This is the discipline iteration 5 uses in place of pre-registration.

Case-agnostic: the model takes measurement rows and a ``(stop, +4)`` key. It never names a
gene, a patient or a position.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean

from scipy.stats import spearmanr

__all__ = [
    "ControlResult",
    "Measurement",
    "Prediction",
    "ReadthroughModel",
    "held_out_control",
    "leave_one_context_out",
    "read_measurements",
]

#: Rows needed in a cell before it is used instead of the next, coarser level.
MIN_ROWS = 2


def _rna(base: str) -> str:
    """``TGA`` -> ``UGA``: one spelling for DNA and RNA so a key never misses."""
    return base.upper().replace("T", "U")


@dataclass(frozen=True)
class Measurement:
    """One published, measured readthrough observation for one PTC context and one drug."""

    context: str
    stop: str
    plus4: str
    drug: str
    value: float
    unit: str
    assay: str
    source: str
    minus1: str = ""
    censored: bool = False

    @property
    def key(self) -> tuple[str, str]:
        return (_rna(self.stop), _rna(self.plus4))

    @property
    def fine_key(self) -> tuple[str, str, str]:
        return (_rna(self.stop), _rna(self.plus4), _rna(self.minus1))


@dataclass(frozen=True)
class Prediction:
    """A predicted readthrough value, with the evidence level that produced it."""

    drug: str
    stop: str
    plus4: str
    value: float | None
    level: str
    rows: int
    contexts: tuple[str, ...]
    unit: str
    minus1: str = ""

    @property
    def usable(self) -> bool:
        return self.value is not None


@dataclass(frozen=True)
class ControlResult:
    """The held-out check: does the model order PTC contexts the way the measurements do?"""

    drug: str
    contexts: int
    spearman: float | None
    p_value: float | None
    pairs_total: int
    pairs_correct: int
    passed: bool
    reason: str

    @property
    def pair_accuracy(self) -> float | None:
        return self.pairs_correct / self.pairs_total if self.pairs_total else None


class ReadthroughModel:
    """Group means over ``(drug, stop, +4, -1)`` with three levels of backoff."""

    def __init__(self, measurements: list[Measurement], *, min_rows: int = MIN_ROWS) -> None:
        units = {m.unit for m in measurements}
        if len(units) > 1:
            raise ValueError(f"one model, one unit: got {sorted(units)}")
        self.unit = units.pop() if units else ""
        self.min_rows = min_rows
        self._measurements = list(measurements)
        self._fine: dict[tuple[str, str, str, str], list[Measurement]] = defaultdict(list)
        self._cells: dict[tuple[str, str, str], list[Measurement]] = defaultdict(list)
        self._by_stop: dict[tuple[str, str], list[Measurement]] = defaultdict(list)
        self._by_drug: dict[str, list[Measurement]] = defaultdict(list)
        for row in measurements:
            stop, plus4, minus1 = row.fine_key
            self._fine[(row.drug, stop, plus4, minus1)].append(row)
            self._cells[(row.drug, stop, plus4)].append(row)
            self._by_stop[(row.drug, stop)].append(row)
            self._by_drug[row.drug].append(row)

    @property
    def drugs(self) -> tuple[str, ...]:
        return tuple(sorted(self._by_drug))

    @property
    def measurements(self) -> tuple[Measurement, ...]:
        return tuple(self._measurements)

    def predict(self, drug: str, stop: str, plus4: str, minus1: str = "") -> Prediction:
        """The most specific group mean with at least ``min_rows`` rows behind it."""
        stop, plus4, minus1 = _rna(stop), _rna(plus4), _rna(minus1)
        levels: tuple[tuple[str, list[Measurement]], ...] = (
            ("stop+4-1", self._fine.get((drug, stop, plus4, minus1), []) if minus1 else []),
            ("stop+4", self._cells.get((drug, stop, plus4), [])),
            ("stop", self._by_stop.get((drug, stop), [])),
            ("drug", self._by_drug.get(drug, [])),
        )
        for name, rows in levels:
            if len(rows) >= self.min_rows:
                return Prediction(
                    drug=drug,
                    stop=stop,
                    plus4=plus4,
                    value=fmean(r.value for r in rows),
                    level=name,
                    rows=len(rows),
                    contexts=tuple(sorted({r.context for r in rows}))[:6],
                    unit=self.unit,
                    minus1=minus1,
                )
        return Prediction(drug, stop, plus4, None, "none", 0, (), self.unit, minus1)

    def without(self, context: str) -> ReadthroughModel:
        """The same model with every row of one PTC context removed."""
        return ReadthroughModel(
            [m for m in self._measurements if m.context != context], min_rows=self.min_rows
        )


def _refused(drug: str, contexts: int, reason: str) -> ControlResult:
    return ControlResult(drug, contexts, None, None, 0, 0, passed=False, reason=reason)


def _score(
    drug: str, kept: list[str], predicted: list[float], observed: list[float], min_spearman: float
) -> ControlResult:
    """Rank correlation and pairwise ordering accuracy over the held-out contexts."""
    rho, p_value = spearmanr(predicted, observed)
    total = correct = 0
    for i in range(len(kept)):
        for j in range(i + 1, len(kept)):
            if observed[i] == observed[j] or predicted[i] == predicted[j]:
                continue
            total += 1
            correct += (predicted[i] > predicted[j]) == (observed[i] > observed[j])
    passed = bool(rho == rho and float(rho) >= min_spearman)  # rho != rho when undefined
    return ControlResult(
        drug=drug,
        contexts=len(kept),
        spearman=float(rho),
        p_value=float(p_value),
        pairs_total=total,
        pairs_correct=correct,
        passed=passed,
        reason=(
            f"held-out rank correlation {float(rho):.2f} "
            f"{'meets' if passed else 'is below'} the pre-stated {min_spearman:.2f} bar"
        ),
    )


def _held_out(
    train: list[Measurement],
    test: list[Measurement],
    drug: str,
    min_rows: int,
    min_contexts: int,
    min_spearman: float,
) -> ControlResult:
    """Fit on ``train``, predict every context of ``test``, score the ordering."""
    model = ReadthroughModel([m for m in train if m.drug == drug], min_rows=min_rows)
    held = [m for m in test if m.drug == drug]
    contexts = sorted({m.context for m in held})
    if len(contexts) < min_contexts:
        return _refused(
            drug, len(contexts), f"only {len(contexts)} held-out contexts; needs {min_contexts}"
        )
    observed: list[float] = []
    predicted: list[float] = []
    kept: list[str] = []
    for context in contexts:
        rows = [m for m in held if m.context == context]
        stop, plus4, minus1 = rows[0].fine_key
        guess = model.predict(drug, stop, plus4, minus1)
        if guess.value is None:
            continue
        observed.append(fmean(m.value for m in rows))
        predicted.append(guess.value)
        kept.append(context)
    if len(kept) < min_contexts:
        return _refused(
            drug,
            len(kept),
            f"only {len(kept)} of {len(contexts)} held-out contexts could be predicted at all",
        )
    return _score(drug, kept, predicted, observed, min_spearman)


def held_out_control(
    measurements: list[Measurement],
    drug: str,
    held_out: frozenset[str] | set[str],
    *,
    min_rows: int = MIN_ROWS,
    min_contexts: int = 4,
    min_spearman: float = 0.5,
) -> ControlResult:
    """Refit with a named benchmark panel removed, then predict exactly that panel.

    This is the control a large published dataset deserves: the held-out contexts are chosen
    *before* the run and are the ones the literature already discusses, so the number is a
    statement about known cases rather than about a random split.
    """
    train = [m for m in measurements if m.context not in held_out]
    test = [m for m in measurements if m.context in held_out]
    return _held_out(train, test, drug, min_rows, min_contexts, min_spearman)


def leave_one_context_out(
    measurements: list[Measurement],
    drug: str,
    *,
    min_rows: int = MIN_ROWS,
    min_contexts: int = 4,
    min_spearman: float = 0.5,
) -> ControlResult:
    """Hold out each PTC context in turn, predict it, and score the ordering."""
    rows = [m for m in measurements if m.drug == drug]
    contexts = sorted({m.context for m in rows})
    if len(contexts) < min_contexts:
        return _refused(
            drug, len(contexts), f"only {len(contexts)} contexts measured; needs {min_contexts}"
        )
    observed: list[float] = []
    predicted: list[float] = []
    kept: list[str] = []
    full = ReadthroughModel(rows, min_rows=min_rows)
    for context in contexts:
        held = [m for m in rows if m.context == context]
        stop, plus4, minus1 = held[0].fine_key
        guess = full.without(context).predict(drug, stop, plus4, minus1)
        if guess.value is None:
            continue
        observed.append(fmean(m.value for m in held))
        predicted.append(guess.value)
        kept.append(context)
    if len(kept) < min_contexts:
        return _refused(
            drug,
            len(kept),
            (
                f"only {len(kept)} of {len(contexts)} contexts could be predicted with the "
                "context held out; the rest had no other row at any backoff level"
            ),
        )
    return _score(drug, kept, predicted, observed, min_spearman)


def read_measurements(path: Path) -> list[Measurement]:
    """Read a measurement table (TSV with the :class:`Measurement` field names as headers)."""
    with path.open(encoding="utf-8", newline="") as handle:
        return [
            Measurement(
                context=row["context"],
                stop=row["stop"],
                plus4=row["plus4"],
                drug=row["drug"],
                value=float(row["value"]),
                unit=row["unit"],
                assay=row["assay"],
                source=row["source"],
                minus1=row.get("minus1", ""),
            )
            for row in csv.DictReader(handle, delimiter="\t")
            if not row["context"].startswith("#")
        ]
