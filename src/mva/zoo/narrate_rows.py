"""The rows an interpretation may cite, and the prompt built from them.

Split out of :mod:`mva.zoo.narrate`, which keeps the *call* and the *record* — this module is
the **input**: how one model report's sections 2-5 become a flat list of citable rows, and how
those rows become the single string the model sees.

Two properties are worth naming, because the whole audit trail rests on them:

* **stable ids.** ``cov.missense_variant``, ``dist.p90``, ``pair.rank``, ``hpo.rank`` — the
  same id means the same fact in every run and in every case. A citation stored a month ago
  still resolves after the numbers behind it have changed.
* **nothing but rows.** The prompt is the fixed rules plus the rows. There is no system
  prompt, no repository context and no question — so the stored prompt *is* the whole input,
  which is what makes a stored reply re-checkable.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

__all__ = [
    "DEFAULT_MAX_WORDS",
    "MERGE_PROMPT_RULES",
    "MIN_CLASS_SHARE",
    "PROMPT_RULES",
    "build_merge_prompt",
    "build_prompt",
    "citable_rows",
    "merged_rows",
]

#: The word budget the prompt states and the checker enforces. Plan §5 step 5: ≤ 200 words.
DEFAULT_MAX_WORDS = 200

#: Consequence classes below this share of the record set are left out of the row list unless
#: the lane actually scored some of them. A 26-row coverage table would be most of the prompt
#: and almost all of it zeros; a class the lane scored is never dropped, whatever its size.
MIN_CLASS_SHARE = 0.01

#: The instruction half of the prompt. Fixed text: it is the same for every model and every
#: case, so a difference between two narratives is a difference between two row lists.
PROMPT_RULES = """\
You are writing section 6 ("Interpretation") of a model report for a software engineer who
has no background in genetics. Every number you may use is in the rows below; each row has
an id.

Rules:
- Write at most {max_words} words of plain prose. No headings, no lists, no code fences.
- Every sentence must end with a citation in square brackets naming the row it rests on,
  like this: "The lane scored about a quarter of the record set [cov.fraction]." A sentence
  may cite more than one row: "[cov.fraction][dist.n]".
- Do not rank anything and do not say which variant, pair or gene is the cause of anything.
- Do not name a gene, a disease, a model or a database that does not appear in the rows.
- Do not add facts, do not estimate, do not compute new numbers. Explain what the rows say
  and what a reader should and should not conclude from them.
- Where the rows show a gap — a class the lane could not score, a missing half of the pair —
  say so plainly, and say what that makes the lane unable to claim.

Rows:
{rows}

Write the interpretation now. Output the prose only."""


def citable_rows(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Sections 2–5 of one model report as ``{"id", "label", "text"}`` rows.

    The ids are stable across runs and across cases (``cov.*``, ``dist.*``, ``pair.*``,
    ``hpo.rank``), which is what makes a citation in a stored reply still resolvable after
    the numbers have changed — the row is still there, the value is not the same.
    """
    sections = report.get("sections", {})
    rows: list[dict[str, Any]] = []
    rows += _coverage_rows(sections.get("inputs", {}))
    rows += _distribution_rows(sections.get("distribution", {}))
    rows += _pair_rows(sections.get("confirmed_pair", {}))
    sentence = str((sections.get("clinical") or {}).get("sentence") or "").strip()
    if sentence:
        rows.append(_row("hpo.rank", "clinical (section 5)", sentence))
    return rows


def _row(row_id: str, label: str, text: str) -> dict[str, Any]:
    return {"id": row_id, "label": label, "text": text}


def _coverage_rows(inputs: Mapping[str, Any]) -> list[dict[str, Any]]:
    scored, total = int(inputs.get("scored", 0)), int(inputs.get("total", 0))
    fraction = inputs.get("fraction")
    rows = [
        _row("cov.scored", "records scored (section 2)", f"{scored} allele records scored"),
        _row("cov.total", "records in the set (section 2)", f"{total} allele records in total"),
        _row(
            "cov.fraction",
            "share of the record set scored (section 2)",
            _share(fraction, "of all allele records carry a score from this lane"),
        ),
    ]
    for entry in inputs.get("by_consequence", []) or []:
        name = str(entry.get("consequence", ""))
        class_total = int(entry.get("total", 0) or 0)
        class_scored = int(entry.get("scored", 0) or 0)
        share = class_total / total if total else 0.0
        if not name or (class_scored == 0 and share < MIN_CLASS_SHARE):
            continue
        rows.append(
            _row(
                f"cov.{name}",
                f"coverage of {name} (section 2)",
                f"{class_scored} of {class_total} `{name}` records scored "
                + _share(entry.get("fraction"), "of that class"),
            )
        )
    return rows


def _distribution_rows(dist: Mapping[str, Any]) -> list[dict[str, Any]]:
    quantiles = dist.get("quantiles") or {}
    rows = [
        _row("dist.n", "scored alleles (section 3)", f"{int(dist.get('n', 0))} alleles scored"),
        _row("dist.min", "lowest score (section 3)", f"minimum score {_num(dist.get('min'))}"),
        _row("dist.mean", "mean score (section 3)", f"mean score {_num(dist.get('mean'))}"),
        _row("dist.max", "highest score (section 3)", f"maximum score {_num(dist.get('max'))}"),
    ]
    rows.extend(
        _row(
            f"dist.{key}",
            f"{key} of the score distribution (section 3)",
            f"the {key} quantile of this lane's scores is {_num(quantiles[key])}",
        )
        for key in ("p50", "p90", "p99")
        if key in quantiles
    )
    for mark in dist.get("marks") or []:
        role = str(mark.get("role") or "half")
        score = mark.get("score")
        text = f"the {role} half of the confirmed pair (allele `{mark.get('allele_id', '')}`) " + (
            f"scores {_num(score)}, at percentile {_pct(mark.get('percentile'))} from the top"
            if score is not None
            else "was not scored by this lane"
        )
        rows.append(_row(f"dist.mark.{role}", f"marked allele, {role} half (section 3)", text))
    return rows


def _pair_rows(block: Mapping[str, Any]) -> list[dict[str, Any]]:
    gene = block.get("gene")
    rows: list[dict[str, Any]] = []
    if gene:
        rows.append(
            _row(
                "pair.gene",
                "the confirmed pair's gene (section 4)",
                f"the confirmed pair sits in the gene `{gene}`",
            )
        )
    rows.append(
        _row(
            "pair.n_ranked",
            "pairs this lane ranked (section 4)",
            f"{int(block.get('n_ranked', 0) or 0)} biallelic pairs are ranked by this lane; "
            "a pair with an unscored half is excluded, not scored zero",
        )
    )
    if block.get("rank") is None:
        rows.append(
            _row(
                "pair.rank",
                "the confirmed pair's rank (section 4)",
                "this lane did not score both halves of the confirmed pair, so it has no rank "
                "for it and is recorded as having no opinion rather than a bad one",
            )
        )
    else:
        rows.append(
            _row(
                "pair.rank",
                "the confirmed pair's rank (section 4)",
                f"the confirmed pair ranks {block.get('rank')} of "
                f"{block.get('n_ranked')} pairs, percentile {_pct(block.get('percentile'))} "
                f"from the top; pair score is (min, max) of its two allele scores",
            )
        )
    for side in ("left", "right"):
        value = block.get(f"{side}_percentile")
        rows.append(
            _row(
                f"pair.{side}_percentile",
                f"{side} half's percentile (section 4)",
                f"the {side} half of the pair sits at percentile {_pct(value)} of this lane's "
                "scored alleles"
                if value is not None
                else f"the {side} half of the pair has no percentile: this lane did not score it",
            )
        )
    mode = block.get("mode")
    if mode:
        rows.append(
            _row(
                "pair.mode",
                "catalogue mode (section 4)",
                f"the run was scored in catalogue mode `{mode}`; `catalogue-free` nulls every "
                "field a ClinVar-trained model could have learned from",
            )
        )
    return rows


def _share(value: Any, tail: str) -> str:
    return "an unrecorded share " + tail if value is None else f"{float(value):.1%} {tail}"


def _num(value: Any) -> str:
    return "not available" if value is None else f"{float(value):.6g}"


def _pct(value: Any) -> str:
    return "not available" if value is None else f"{float(value):.2f}%"


def build_prompt(rows: Sequence[Mapping[str, Any]], *, max_words: int = DEFAULT_MAX_WORDS) -> str:
    """The whole prompt: the fixed rules plus this lane's rows. Nothing else is sent."""
    body = "\n".join(f"[{row['id']}] {row.get('label', '')}: {row.get('text', '')}" for row in rows)
    return PROMPT_RULES.format(max_words=max_words, rows=body)


# ---------------------------------------------------------------------------------------
# The merged report (step 6, `fusion+synthesis`)
# ---------------------------------------------------------------------------------------

#: The synthesis prompt. Same shape and same discipline as :data:`PROMPT_RULES`, one rule
#: added: the per-lane interpretations are *rows too*, so a synthesis that repeats a lane's
#: reading has to cite that lane, not restate it as its own observation.
MERGE_PROMPT_RULES = """\
You are writing the "What this means" section of a merged report that combines several
variant-scoring models for a software engineer with no background in genetics. Every fact
you may use is in the rows below; each row has an id.

Rules:
- Write at most {max_words} words of plain prose. No headings, no lists, no code fences.
- Every sentence must end with a citation in square brackets naming the row it rests on,
  like this: "The two lanes barely agree [rho.a.b]." A sentence may cite several rows.
- Do not rank anything and do not say which variant, pair or gene is the cause of anything.
- Do not name a gene, a disease, a model or a database that does not appear in the rows.
- Do not add facts, do not estimate, do not compute new numbers.
- Rows whose id starts with `interp.` are what each lane's own report already says. You may
  build on them, but cite the lane you are building on rather than restating it as your own.
- Where the rows show that lanes abstained rather than disagreed, say so plainly, and say
  what that makes the consensus unable to claim.

Rows:
{rows}

Write the section now. Output the prose only."""


def merged_rows(
    merged: Mapping[str, Any], interpretations: Mapping[str, str] | None = None
) -> list[dict[str, Any]]:
    """The merged report's citable rows: lanes, agreement, fusion, disagreement, readings.

    Ids follow the same convention as the per-model rows — a prefix naming where the number
    came from, then the thing itself: ``lane.<model>.rank``, ``rho.<a>.<b>``,
    ``rrf.free.rank``, ``rrf.all.rank``, ``disagree.n``, ``interp.<model>``.
    """
    rows: list[dict[str, Any]] = [
        _row(
            "method",
            "merge method (merged report)",
            f"the lanes were merged with method `{merged.get('method', '')}` and reciprocal "
            f"rank fusion constant k = {merged.get('rrf_k', '')}; a lane that never ranks a "
            "pair contributes nothing to it",
        )
    ]
    rows += _lane_rows(merged.get("lanes", []))
    rows += _agreement_rows(merged.get("agreement", {}))
    rows += _consensus_rows(merged.get("consensus", {}))
    rows.append(
        _row(
            "disagree.n",
            "disagreement rows (merged report)",
            f"{len(merged.get('disagreements', []) or [])} alleles sit in the top 1% of one "
            "lane and the bottom half of another",
        )
    )
    for model, text in sorted((interpretations or {}).items()):
        if text.strip():
            rows.append(_row(f"interp.{model}", f"`{model}`'s own reading", text.strip()))
    return rows


def _lane_rows(lanes: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for lane in lanes:
        model = str(lane.get("model", ""))
        confirmed = lane.get("confirmed") or {}
        rank = confirmed.get("rank")
        verdict = (
            f"ranks the confirmed pair {rank} of {lane.get('n_ranked', 0)} pairs, percentile "
            f"{_pct(confirmed.get('percentile'))} from the top"
            if rank is not None
            else (
                f"has no rank for the confirmed pair: it scored only one of its two alleles, "
                f"so the pair left its ranking of {lane.get('n_ranked', 0)} pairs"
            )
        )
        adjacent = (
            " it is catalogue-adjacent (ClinVar was in its training data);"
            if lane.get("catalogue_adjacent")
            else ""
        )
        rows.append(
            _row(
                f"lane.{model}.rank",
                f"lane `{model}` (merged report)",
                f"lane `{model}` scored {lane.get('scored_alleles', 0)} alleles and {verdict};"
                f"{adjacent} {lane.get('unscored_pairs', 0)} pairs had an unscored half",
            )
        )
    return rows


def _agreement_rows(agreement: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cell in agreement.get("cells", []) or []:
        a, b, rho = str(cell.get("a", "")), str(cell.get("b", "")), cell.get("rho")
        if a >= b or rho is None:
            continue
        rows.append(
            _row(
                f"rho.{a}.{b}",
                f"agreement `{a}` vs `{b}` (merged report)",
                f"over the {cell.get('n', 0)} alleles both scored, `{a}` and `{b}` agree at "
                f"Spearman rank correlation {float(rho):+.3f} (+1 = same order, 0 = unrelated)",
            )
        )
    return rows


def _consensus_rows(consensus: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, label in (("catalogue_free", "free"), ("all_lanes", "all")):
        block = consensus.get(key) or {}
        lanes = ", ".join(block.get("lanes", [])) or "none"
        excluded = ", ".join(block.get("excluded_lanes", [])) or "none"
        rank = block.get("rank")
        rows.append(
            _row(
                f"rrf.{label}.rank",
                f"fused rank, {label.replace('free', 'catalogue-free lanes only')} (merged report)",
                f"fusing {lanes} (excluding {excluded}) puts the confirmed pair at rank "
                f"{rank if rank is not None else 'none'} of {block.get('n_pairs', 0)} pairs, "
                f"fused score {_num(block.get('fused_score'))}",
            )
        )
    return rows


def build_merge_prompt(
    rows: Sequence[Mapping[str, Any]], *, max_words: int = DEFAULT_MAX_WORDS
) -> str:
    """The synthesis prompt: the merge rules plus the merged report's rows. Nothing else."""
    body = "\n".join(f"[{row['id']}] {row.get('label', '')}: {row.get('text', '')}" for row in rows)
    return MERGE_PROMPT_RULES.format(max_words=max_words, rows=body)
