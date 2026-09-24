"""Executing a :class:`~mva.drugs.screen_replication_plan.ReplicationPlan`, in fixed order.

The order matters and is the same for every case:

1. read the screen and the line annotations,
2. build the groups — every contrast definition is frozen before any p value is computed,
3. the two **primary** contrasts, Benjamini-Hochberg over the candidates inside each,
4. the **sensitivity** contrasts (other group definition, line-level offset removed, other
   release and metric) — raw p only, because correcting a robustness check against the
   result it checks would be double counting,
5. the drugs the screen never tested, one row each: an absent candidate is a result,
6. the background sweep over every compound, for the "where do the candidates sit?" figure,
7. the controls: negative band, positive control, literature direction, confounders,
8. the provenance manifest naming every input with its digest.

Nothing here names a gene, a disease or a patient; all of that arrives in the plan.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

import numpy as np
import polars as pl
import scipy

from mva.drugs import provenance
from mva.drugs.screen_replication import Group, median_split, run_contrast
from mva.drugs.screen_replication_plan import (
    ReplicationPlan,
    absent_rows,
    candidates,
    coverage_table,
    match_drug,
    meta_by_item,
)
from mva.drugs.screen_replication_prism import (
    CompoundIndex,
    ResponseMatrix,
    core_broad_id,
    lineage_group,
    load_compound_list,
    load_model_table,
    load_primary_matrix,
    load_secondary_auc,
    load_secondary_compound_list,
    load_signatures,
    normalise_name,
)
from mva.drugs.screen_replication_report import (
    confounder_summary,
    negative_control_band,
    positive_control,
    run_group,
    write_provenance,
)

__all__ = ["execute"]


def execute(plan: ReplicationPlan) -> int:
    """Run the plan end to end; returns a process exit code."""
    plan.build_dir.mkdir(parents=True, exist_ok=True)
    index = load_compound_list(plan.path("primary_compounds"))
    secondary_index = load_secondary_compound_list(plan.path("secondary_compounds"))
    models = load_model_table(plan.path("models"))
    signatures = load_signatures(plan.path("signatures"))
    primary = load_primary_matrix(plan.path("primary_matrix"))
    print(f"primary: {len(primary.item_ids)} compounds x {len(primary.lines)} lines")

    spec = candidates(plan, index)
    matches = {key: match_drug(index, primary, key) for key, _, _ in spec}
    meta = meta_by_item(spec, matches)
    annotation = {
        str(model): float(score)
        for model, score in signatures.select("ModelID", plan.annotation_column).drop_nulls().rows()
        if model in set(primary.lines)
    }
    ann = plan.annotation_column.lower()
    groups = {
        "lineage-vs-all": lineage_group(
            models,
            codes=plan.in_group_codes,
            screened=primary.lines,
            name="lineage-vs-all",
            in_label=plan.in_group_label,
            out_label="every other screened line",
        ),
        f"{ann}-high-vs-low": median_split(
            annotation,
            name=f"{ann}-high-vs-low",
            high_label=f"high-{ann} lines",
            low_label=f"low-{ann} lines",
        ),
    }
    sensitivity = {
        "lineage-vs-same-tissue": lineage_group(
            models,
            codes=plan.in_group_codes,
            screened=primary.lines,
            name="lineage-vs-same-tissue",
            in_label=plan.in_group_label,
            out_label=f"other {plan.in_group_lineage} lines",
            restrict_lineage=plan.in_group_lineage,
        ),
        f"{ann}-tertile": median_split(
            annotation,
            name=f"{ann}-tertile",
            high_label=f"top-tertile {ann}",
            low_label=f"bottom-tertile {ann}",
            quantiles=(1 / 3, 2 / 3),
        ),
    }
    for name, group in {**groups, **sensitivity}.items():
        print(f"  {name}: {len(group.inside)} in / {len(group.outside)} out — {group.definition}")

    rows: list[dict[str, Any]] = []
    for group in groups.values():
        rows += run_group(
            primary,
            group,
            matches,
            meta,
            role="primary",
            family=True,
            seed=plan.seed,
            resamples=plan.resamples,
        )
    for group in sensitivity.values():
        rows += run_group(
            primary,
            group,
            matches,
            meta,
            role="sensitivity: group definition",
            family=False,
            seed=plan.seed,
            resamples=plan.resamples,
        )
    ranked = primary.rank_normalised()
    base = groups["lineage-vs-all"]
    rank_group = Group(
        name="lineage-vs-all-rank-normalised",
        inside=base.inside,
        outside=base.outside,
        in_label=base.in_label,
        out_label=base.out_label,
        definition=base.definition + "; responses rank-normalised within each line",
    )
    rows += run_group(
        ranked,
        rank_group,
        matches,
        meta,
        role="sensitivity: line-level offset removed",
        family=False,
        seed=plan.seed,
        resamples=plan.resamples,
    )

    secondary = load_secondary_auc(plan.path("secondary_auc"))
    print(f"secondary: {len(secondary.item_ids)} compounds x {len(secondary.lines)} lines")
    sec_matches = {key: match_drug(secondary_index, secondary, key) for key, _, _ in spec}
    sec_meta = meta_by_item(spec, sec_matches)
    sec_groups = {
        "lineage-vs-all-auc": lineage_group(
            models,
            codes=plan.in_group_codes,
            screened=secondary.lines,
            name="lineage-vs-all-auc",
            in_label=plan.in_group_label,
            out_label="every other screened line",
        ),
        f"{ann}-high-vs-low-auc": median_split(
            {k: v for k, v in annotation.items() if k in set(secondary.lines)},
            name=f"{ann}-high-vs-low-auc",
            high_label=f"high-{ann} lines",
            low_label=f"low-{ann} lines",
        ),
    }
    for name, group in sec_groups.items():
        print(f"  {name}: {len(group.inside)} in / {len(group.outside)} out")
        rows += run_group(
            secondary,
            group,
            sec_matches,
            sec_meta,
            role="sensitivity: other release and metric",
            family=False,
            seed=plan.seed,
            resamples=plan.resamples,
        )
    rows += absent_rows(spec, matches, primary, "lineage-vs-all")

    table = pl.DataFrame(rows).sort("contrast", "candidate", "prism_item_id")
    plan.out.parent.mkdir(parents=True, exist_ok=True)
    table.write_csv(plan.out, separator="\t")
    print(f"wrote {plan.out} ({table.height} rows)")

    names = index.names()
    for name, group in groups.items():
        sweep = run_contrast(primary, group, names=names, resamples=0, seed=plan.seed)
        pl.DataFrame([asdict(r) for r in sweep]).join(
            index.table.select("item_id", "moa", "target", "screen").unique("item_id"),
            on="item_id",
            how="left",
        ).write_parquet(plan.build_dir / f"background-{name}.parquet")
        print(f"  background sweep {name}: {len(sweep)} compounds")
    coverage_table(plan, spec, primary, matches, sec_matches, base.inside).write_csv(
        plan.build_dir / "coverage.tsv", separator="\t"
    )
    controls = _controls(
        plan,
        primary,
        groups,
        index,
        secondary_index,
        {i for ids in matches.values() for i in ids},
        models,
        annotation,
    )
    (plan.build_dir / "controls.json").write_text(
        json.dumps(controls, indent=2, default=str) + "\n"
    )
    print(f"wrote {plan.build_dir / 'controls.json'} and {plan.build_dir / 'coverage.tsv'}")

    inputs: list[dict[str, Any]] = []
    for source in plan.sources:
        sha, size = provenance.digest(plan.raw_dir / source.name)
        inputs.append(
            {
                "name": source.name,
                "role": source.role,
                "url": source.url,
                "sha256": sha,
                "bytes": size,
                "licence": source.licence,
                "release": source.release,
            }
        )
    for path in plan.candidate_tables:
        sha, size = provenance.digest(path)
        inputs.append(
            {
                "name": path.as_posix(),
                "role": "candidate list (this repository)",
                "url": None,
                "sha256": sha,
                "bytes": size,
                "licence": "this repository",
                "release": None,
            }
        )
    write_provenance(
        plan.out,
        name=plan.out.stem,
        built_by="tools/screen_replication.py",
        entry=plan.entry,
        inputs=inputs,
        parameters={
            "seed": plan.seed,
            "bootstrap_resamples": plan.resamples,
            "negative_control_size": plan.negative_control_size,
            "in_group_codes": list(plan.in_group_codes),
            "annotation_column": plan.annotation_column,
            "groups": {
                k: v.definition
                for k, v in {
                    **groups,
                    **sensitivity,
                    "lineage-vs-all-rank-normalised": rank_group,
                    **sec_groups,
                }.items()
            },
            "bh_family": "representative row of every candidate, within each primary contrast",
            "candidates": len(spec),
        },
        test=(
            "Mann-Whitney U, one-sided 'in-group more sensitive'; effect size Cliff's delta "
            "from the same U; 95 % percentile bootstrap CI; Benjamini-Hochberg within each "
            "primary contrast over the representative row of every candidate"
        ),
        software={
            "scipy": scipy.__version__,
            "numpy": np.__version__,
            "polars": pl.__version__,
            **plan.software,
        },
        rows=table.height,
        patient_data=plan.patient_data,
    )
    print(f"wrote {plan.out.with_suffix('.provenance.json')}")
    return 0


def _controls(
    plan: ReplicationPlan,
    primary: ResponseMatrix,
    groups: dict[str, Group],
    index: CompoundIndex,
    secondary_index: CompoundIndex,
    candidate_items: set[str],
    models: pl.DataFrame,
    annotation: dict[str, float],
) -> dict[str, Any]:
    """The negative band, the positive control, the literature direction and confounders."""
    launched = set(
        secondary_index.table.filter(pl.col("phase") == "Launched")["broad_core"].to_list()
    )
    moa = index.moa()
    universe = [
        item
        for item in primary.item_ids
        if core_broad_id(item) in launched
        and not any(word in moa.get(item, "").upper() for word in plan.control_exclude)
    ]
    names = index.names()
    codes = tuple(
        models.filter(pl.col("OncotreeLineage") == plan.positive_control_lineage)["OncotreeCode"]
        .drop_nulls()
        .unique()
        .to_list()
    )
    pc_group = lineage_group(
        models,
        codes=codes,
        screened=primary.lines,
        name="positive-control",
        in_label=f"{plan.positive_control_lineage} lines",
        out_label="every other screened line",
    )
    lineage_key = next(iter(groups))
    lit: list[dict[str, Any]] = []
    for moa_word in plan.literature_moa:
        items = [
            i for i in index.by_moa(moa_word)["item_id"].to_list() if i in set(primary.item_ids)
        ]
        for name, group in groups.items():
            if name == lineage_key:
                continue
            lit.extend(
                {"moa": moa_word, **asdict(r)}
                for r in run_contrast(
                    primary.subset(items), group, names=names, resamples=0, seed=plan.seed
                )
            )
    return {
        "negative_control": negative_control_band(
            primary,
            groups,
            universe=universe,
            exclude=sorted(candidate_items),
            names=names,
            size=plan.negative_control_size,
            seed=plan.seed,
            definition=(
                "seeded random sample of compounds marked Launched in the secondary release "
                f"whose MOA mentions none of {list(plan.control_exclude)}"
            ),
        ),
        "positive_control": positive_control(
            primary,
            pc_group,
            {n: match_drug(index, primary, normalise_name(n)) for n in plan.positive_control_drugs},
            definition=plan.positive_control_note,
            seed=plan.seed,
        ),
        "literature_direction_check": {"definition": plan.literature_note, "results": lit},
        "confounders": {
            **confounder_summary(
                primary, groups[lineage_key], annotation, annotation_name=plan.annotation_column
            ),
            "in_group_lines": models.filter(
                pl.col("ModelID").is_in(sorted(groups[lineage_key].inside))
            )
            .select("StrippedCellLineName", "OncotreeCode", "Age", "AgeCategory")
            .to_dicts(),
        },
    }
