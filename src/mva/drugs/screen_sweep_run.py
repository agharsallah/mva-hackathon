"""Executing a screen-wide sweep, in a fixed order, from a declared :class:`SweepPlan`.

1. verify every reused raw file against the manifest of the entry that fetched it,
2. read the screen, the line annotations and PRISM's own ``Launched`` label,
3. build the two groups (frozen before any p value exists) and the eligibility rule,
4. both contrasts over every eligible compound, BH over one representative per drug,
5. a line-offset sensitivity (rank-normalised lineage contrast, raw p, outside the family),
6. the controls (:mod:`mva.drugs.screen_sweep_controls`),
7. the wide table, the generator list and universe, one provenance manifest each.

Nothing here names a gene, a disease or a patient; all of that arrives in the plan.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

import numpy as np
import polars as pl
import scipy

from mva.drugs import provenance
from mva.drugs.screen_replication import Group, median_split, run_contrast
from mva.drugs.screen_replication_prism import (
    CompoundIndex,
    ResponseMatrix,
    lineage_group,
    load_compound_list,
    load_model_table,
    load_primary_matrix,
    load_signatures,
)
from mva.drugs.screen_replication_report import write_provenance
from mva.drugs.screen_sweep import (
    Eligibility,
    FamilyRow,
    eligible_items,
    family,
    opposite_p,
    sweep_contrast,
)
from mva.drugs.screen_sweep_controls import (
    drug_keys,
    in_group_line_sets,
    positive_control_sweep,
    sweep_controls,
)
from mva.drugs.screen_sweep_plan import SweepPlan, verify_inputs
from mva.drugs.screen_sweep_prism import (
    launched_cores,
    launched_items,
    load_phase_table,
    phase_disagreements,
)
from mva.drugs.screen_sweep_report import generator_rows, sweep_table, universe_rows

__all__ = ["execute"]

TEST = (
    "entry 151 unchanged: Mann-Whitney U one-sided 'in-group more sensitive'; Cliff's delta "
    "from the same U; 95 % percentile bootstrap CI; Benjamini-Hochberg over every eligible "
    "Launched drug within each contrast"
)


def execute(plan: SweepPlan) -> int:
    """Run the sweep end to end; returns a process exit code."""
    plan.build_dir.mkdir(parents=True, exist_ok=True)
    inputs = verify_inputs(plan)
    print(f"verified {len(inputs)} input digests against {plan.reused_manifest}")
    index = load_compound_list(plan.path("primary_compounds"))
    phases = [
        load_phase_table(plan.path("secondary_compounds"), release="20Q2 secondary"),
        load_phase_table(plan.path("primary_treatment_info"), release="20Q2 primary"),
    ]
    cores = launched_cores(phases)
    launched = launched_items(index, cores)
    models = load_model_table(plan.path("models"))
    signatures = load_signatures(plan.path("signatures"))
    primary = load_primary_matrix(plan.path("primary_matrix"))
    screened = set(primary.lines)
    annotation = {
        str(m): float(s)
        for m, s in signatures.select("ModelID", plan.annotation_column).drop_nulls().rows()
        if m in screened
    }
    ann = plan.annotation_column.lower()
    groups = {
        "rms": lineage_group(
            models,
            codes=plan.in_group_codes,
            screened=primary.lines,
            name="lineage-vs-all",
            in_label="in-group lineage lines",
            out_label="every other screened line",
        ),
        ann: median_split(
            annotation,
            name=f"{ann}-high-vs-low",
            high_label=f"high-{ann} lines",
            low_label=f"low-{ann} lines",
        ),
    }
    rules = [
        Eligibility(groups["rms"], plan.min_in_group, plan.min_in_group),
        Eligibility(groups[ann], plan.min_arm, plan.min_arm),
    ]
    in_matrix = [i for i in primary.item_ids if i in launched]
    items = eligible_items(primary, in_matrix, rules)
    meta = index.table.unique("item_id").select(
        "item_id", "name", "broad_core", "screen", "moa", "target"
    )
    info = {r["item_id"]: r for r in meta.iter_rows(named=True)}
    drug_of = drug_keys(items, info)
    names = {i: info[i]["name"] for i in items}
    print(
        f"{primary.matrix.shape[0]} compounds; {len(in_matrix)} Launched; {len(items)} "
        f"eligible copies = {len(set(drug_of.values()))} drugs"
    )
    for tag, g in groups.items():
        print(f"  {tag}: {len(g.inside)} in / {len(g.outside)} out — {g.definition}")

    fams: dict[str, list[FamilyRow]] = {}
    extra: dict[tuple[str, str], dict[str, Any]] = {}
    for tag, group in groups.items():
        results = sweep_contrast(
            primary,
            group,
            items,
            names,
            seed=plan.seed,
            resamples=plan.resamples,
            workers=plan.workers,
        )
        fams[tag] = family(primary, group, results, drug_of)
        for item, p_opp in opposite_p(primary, group, items).items():
            extra[(item, tag)] = {"p_opposite": p_opp}
        print(f"  swept {tag}: {len(results)} copies")
    ranked = primary.rank_normalised().subset(items)
    for r in run_contrast(ranked, groups["rms"], names=names, resamples=0):
        extra[(r.item_id, "rms")].update(rank_normalised_delta=r.delta, rank_normalised_p=r.p_raw)
    annot = {
        i: {
            "prism_name": info[i]["name"],
            "broad_core": info[i]["broad_core"],
            "screen": info[i]["screen"],
            "moa": info[i]["moa"],
            "target": info[i]["target"],
            "launched_source": launched[i],
        }
        for i in items
    }
    cores_of: dict[str, set[str]] = {}
    for i in items:
        cores_of.setdefault(drug_of[i], set()).add(info[i]["broad_core"])
    table = sweep_table(fams, annot, alpha=plan.alpha, extra=extra)
    gen = generator_rows(
        fams,
        plan.hints,
        names,
        {d: sorted(c) for d, c in cores_of.items()},
        {i: info[i]["moa"] or "" for i in items},
        generator=plan.generator,
        fraction=plan.top_fraction,
        approval_evidence="PRISM Launched",
    )
    table = table.with_columns(g3_listed=pl.col("drug").is_in(gen["drug"].implode()))
    lead = ["drug", "contrast", "item_id", "prism_name", "broad_core", "screen", "moa", "target"]
    table = table.select(lead + [c for c in table.columns if c not in lead])
    plan.out.parent.mkdir(parents=True, exist_ok=True)
    table.write_csv(plan.out, separator="\t")
    hits = table.filter(pl.col("hit_both"))["drug"].n_unique()
    print(f"wrote {plan.out} ({table.height} rows); {hits} drugs with q < alpha in both")

    controls = _all_controls(
        plan, primary, groups, fams, items, in_matrix, info, annotation, models
    )
    controls["funnel"] = _funnel(
        index, phases, primary, in_matrix, items, info, drug_of, gen, table
    )
    out = plan.build_dir / "controls.json"
    out.write_text(json.dumps(controls, indent=2, default=str) + "\n")
    print(f"wrote {out}")
    _write_manifests(plan, table, gen, universe_rows(fams), inputs, groups)
    return 0


def _all_controls(
    plan: SweepPlan,
    primary: ResponseMatrix,
    groups: dict[str, Group],
    fams: dict[str, list[FamilyRow]],
    items: list[str],
    in_matrix: list[str],
    info: dict[str, dict[str, Any]],
    annotation: dict[str, float],
    models: pl.DataFrame,
) -> dict[str, Any]:
    """Every control of :mod:`mva.drugs.screen_sweep_controls`, in one dict for the JSON."""
    controls = sweep_controls(
        primary,
        groups,
        fams,
        items,
        info,
        annotation,
        lineage_tag="rms",
        annotation_name=plan.annotation_column,
        exclude_words=plan.control_exclude,
        band_size=plan.negative_control_size,
        report_drugs=plan.report_drugs,
        alpha=plan.alpha,
        seed=plan.seed,
    )
    label = dict(models.select("ModelID", "StrippedCellLineName").rows())
    controls["confounders"]["in_group_line_sets"] = in_group_line_sets(
        primary, groups["rms"], items, label
    )
    controls["positive_control_sweep"] = positive_control_sweep(
        primary,
        models,
        in_matrix,
        info,
        lineage=plan.positive_control_lineage,
        drugs=plan.positive_control_drugs,
        alpha=plan.alpha,
        seed=plan.seed,
        out=plan.build_dir / "positive-control-sweep.tsv",
    )
    return controls


def _funnel(
    index: CompoundIndex,
    phases: list[pl.DataFrame],
    primary: ResponseMatrix,
    in_matrix: list[str],
    items: list[str],
    info: dict[str, dict[str, Any]],
    drug_of: dict[str, str],
    gen: pl.DataFrame,
    table: pl.DataFrame,
) -> dict[str, Any]:
    """How many compounds survive each filter, and what the Launched label could not see."""
    no_phase = index.table.filter(
        ~pl.col("broad_core").is_in(pl.concat(phases)["broad_core"].implode())
    )
    return {
        "compounds_in_matrix": primary.matrix.shape[0],
        "launched_cores": len(launched_cores(phases)),
        "launched_in_matrix": len(in_matrix),
        "launched_by_screen": dict(Counter(info[i]["screen"] for i in in_matrix)),
        "eligible_copies": len(items),
        "eligible_drugs": len(set(drug_of.values())),
        "eligible_by_screen": dict(Counter(info[i]["screen"] for i in items)),
        "g3_listed": gen.height,
        "hit_both_drugs": int(table.filter(pl.col("hit_both"))["drug"].n_unique()),
        "no_phase_in_any_20q2_file": dict(no_phase["screen"].value_counts().rows()),
        "phase_disagreements": phase_disagreements(phases),
    }


def _write_manifests(
    plan: SweepPlan,
    table: pl.DataFrame,
    gen: pl.DataFrame,
    universe: pl.DataFrame,
    inputs: list[dict[str, Any]],
    groups: dict[str, Any],
) -> None:
    parameters = {
        "seed": plan.seed,
        "bootstrap_resamples": plan.resamples,
        "alpha": plan.alpha,
        "min_in_group_lines": plan.min_in_group,
        "min_lines_per_aneuploidy_arm": plan.min_arm,
        "in_group_codes": list(plan.in_group_codes),
        "annotation_column": plan.annotation_column,
        "groups": {t: g.definition for t, g in groups.items()},
        "launched_rule": "core BRD id marked Launched in the 20Q2 primary or secondary file",
        "join_key": (
            "prism_join_key: drop a trailing '-(+/-)', then "
            "mva.drugs.names.base_name(name.replace('-', ' '))"
        ),
        "bh_family": "one representative copy per eligible drug, within each contrast",
        "top_fraction": plan.top_fraction,
        "hints": plan.hints,
    }
    software = {
        "scipy": scipy.__version__,
        "numpy": np.__version__,
        "polars": pl.__version__,
        **plan.software,
    }
    write_provenance(
        plan.out,
        name=plan.out.stem,
        built_by="tools/screen_sweep.py",
        entry=plan.entry,
        inputs=inputs,
        parameters=parameters,
        test=TEST,
        software=software,
        rows=table.height,
        patient_data=plan.patient_data,
    )
    plan.generator_dir.mkdir(parents=True, exist_ok=True)
    listed = plan.generator_dir / f"{plan.generator}.tsv"
    uni = plan.generator_dir / f"{plan.generator}.universe.tsv"
    gen.write_csv(listed, separator="\t")
    universe.write_csv(uni, separator="\t")
    manifest = provenance.envelope(plan.generator, "tools/screen_sweep.py")
    sweep_sha, sweep_bytes = provenance.digest(plan.out)
    manifest.update(
        {
            "entry": plan.entry,
            "inputs": [
                *inputs,
                {
                    "name": provenance.repo_relative(plan.out),
                    "role": "the sweep table this list is cut from",
                    "sha256": sweep_sha,
                    "bytes": sweep_bytes,
                    "licence": "this repository",
                },
            ],
            "parameters": parameters,
            "method": (
                f"G3: union of the top {plan.top_fraction:.1%} (ceil) of eligible Launched "
                "drugs on each contrast, ranked by one-sided p (ties by larger delta); the "
                "union is ranked by best within-contrast rank, then p; universe = every "
                f"eligible Launched drug; direction_hint per contrast {plan.hints}; "
                "approved = PRISM Launched"
            ),
            "test": TEST,
            "software": software,
            "patient_data": plan.patient_data,
            "outputs": [
                provenance.output(listed, gen.height),
                provenance.output(uni, universe.height),
            ],
        }
    )
    provenance.write(manifest, plan.generator_dir / f"{plan.generator}.provenance.json")
    print(f"wrote {listed} ({gen.height}) and {uni} ({universe.height})")
