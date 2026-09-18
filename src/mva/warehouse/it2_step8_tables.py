"""Load iteration 2's step-8 mosaic tables into the warehouse, with their lineage.

Same shape as :mod:`mva.warehouse.it2_step6_tables`, and for the same reason: these rows are
produced in Python — a beta-binomial fit, a BIC, a simulated power curve — so this module's
job is to put them where SQL and the dashboard can read them, and to record where each one
came from.

**Step 8's lineage names one raw input and one absence.** Every table here is derived from
the delivered callset through the three ``it2_mosaic_*`` derivations, and from the committed
reference geometry that decided which arm each call sat on. The **clinical** row is the
unusual one and it is recorded deliberately: the clinical document lists no karyotype and no
term that a blood-DNA aneuploid fraction would predict, and the delivery never says which
tissue was sequenced. So the clinical source is named as *what this result may not be read
against*, rather than as an input — the alternative is a reader quietly treating a cell
fraction as a severity statement.

**Nothing here carries a position.** A row is a contig, an arm, a model name, a fraction and
a count. The derivations aggregated position away before these tables existed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from . import lineage
from .postgres import ALIAS, safe_identifier

__all__ = ["CALLSET_REF", "CLINICAL_REF", "SCHEMAS", "TOOL", "Loaded", "load"]

#: One row per table: the columns, written out rather than sniffed, because these schemas
#: are a promise the dashboard reads.
SCHEMAS: dict[str, tuple[tuple[str, str], ...]] = {
    "it2_mosaic_bdev": (
        ("chrom", "VARCHAR"),
        ("arm", "VARCHAR"),
        ("n_sites", "BIGINT"),
        ("mean_depth", "DOUBLE"),
        ("bdev", "DOUBLE"),
        ("null_mean", "DOUBLE"),
        ("null_sd", "DOUBLE"),
        # The rejection threshold, per contig: the null is simulated from this contig's own
        # depths and site count, so a shallow contig is judged against a wider null rather
        # than flagged for being shallow.
        ("null_p95", "DOUBLE"),
        ("z", "DOUBLE"),
        ("p_value", "DOUBLE"),
        ("rho", "DOUBLE"),
        ("centre", "DOUBLE"),
        ("measurable", "BOOLEAN"),
        ("exceeds_null", "BOOLEAN"),
    ),
    "it2_mosaic_fractions": (
        ("chrom", "VARCHAR"),
        ("arm", "VARCHAR"),
        # The published DANFIP estimator as written, its value on null draws from the same
        # depths, and the difference. The gap between the first two is a measurement about
        # the instrument and is why all three columns travel together.
        ("f_raw", "DOUBLE"),
        ("f_null", "DOUBLE"),
        ("f_hat", "DOUBLE"),
        ("f_low", "DOUBLE"),
        ("f_high", "DOUBLE"),
        ("upper_sites", "BIGINT"),
        ("centre", "DOUBLE"),
    ),
    "it2_mosaic_models": (
        ("chrom", "VARCHAR"),
        ("model", "VARCHAR"),
        ("fraction", "DOUBLE"),
        ("tract", "DOUBLE"),
        # Fitted per chromosome here, unlike the genome-wide value the deviation null uses,
        # and the two together are how a reader tells a repeat-dispersed contig from a
        # mosaic one.
        ("rho", "DOUBLE"),
        ("noise_share", "DOUBLE"),
        ("depth_dispersion", "DOUBLE"),
        ("log_likelihood", "DOUBLE"),
        ("allele_log_likelihood", "DOUBLE"),
        ("depth_log_likelihood", "DOUBLE"),
        ("parameters", "BIGINT"),
        ("observations", "BIGINT"),
        ("bic", "DOUBLE"),
    ),
    "it2_mosaic_verdicts": (
        ("chrom", "VARCHAR"),
        # "not distinguishable" whenever the margin is under Kong 2018's ten, so a reader
        # cannot mistake a ranking for a call by reading the wrong column.
        ("call", "VARCHAR"),
        ("best", "VARCHAR"),
        ("runner_up", "VARCHAR"),
        ("delta_bic", "DOUBLE"),
        ("fraction", "DOUBLE"),
        ("trisomy_vs_cnloh", "DOUBLE"),
        ("confident", "BOOLEAN"),
        # The contig's tail burden under `normal`, and whether it is past the ceiling.
        ("noise_share", "DOUBLE"),
        ("measurable", "BOOLEAN"),
        # True when a parameter of the winning fit is pinned against its bound: the
        # optimiser reporting "as much as you let me" rather than an estimate. The leader's
        # own parameters travel with it so the verdict can be checked rather than trusted.
        ("degenerate", "BOOLEAN"),
        ("leader_rho", "DOUBLE"),
        ("leader_tract", "DOUBLE"),
        ("leader_noise", "DOUBLE"),
    ),
    "it2_mosaic_density": (
        ("chrom", "VARCHAR"),
        ("arm", "VARCHAR"),
        ("het_sites", "BIGINT"),
        ("pass_sites", "BIGINT"),
        ("arm_bp", "BIGINT"),
        ("acrocentric", "BOOLEAN"),
        ("het_per_mb", "DOUBLE"),
        ("het_share", "DOUBLE"),
    ),
    "it2_mosaic_multi": (
        ("fraction", "DOUBLE"),
        ("affected", "VARCHAR"),
        ("n_affected", "BIGINT"),
        ("recall", "DOUBLE"),
        # Untouched contigs flagged on the same replicate that recovered the injected ones.
        # Measured, not assumed from a nominal five per cent -- this is the column that says
        # whether a genome-wide bound survives on a variegated genome.
        ("false_positive_rate", "DOUBLE"),
        ("replicates", "BIGINT"),
        ("chromosomes_tested", "BIGINT"),
        # What the injected contigs did to the two constants a real run fits: the mechanism
        # behind any false positive, since nothing else here is shared between contigs.
        ("refit_centre", "DOUBLE"),
        ("refit_rho", "DOUBLE"),
        ("seconds", "DOUBLE"),
    ),
}

#: The step-8 limits table is written with one power column per simulated fraction, so its
#: schema is built from the grid the run actually used rather than fixed here.
LIMITS_TABLE = "it2_mosaic_limits"
LIMITS_FIXED: tuple[tuple[str, str], ...] = (
    ("chrom", "VARCHAR"),
    ("statistic", "VARCHAR"),
    ("n_sites", "BIGINT"),
    ("mean_depth", "DOUBLE"),
    # Empty when the contig never reaches 80 % power at any simulated fraction. Empty is the
    # honest value: a blind spot is not a large limit.
    ("f80", "DOUBLE"),
)

TRANSFORMS: dict[str, str] = {
    "it2_mosaic_bdev": (
        "mean |BAF - centre| over each contig's heterozygous PASS calls, against a null "
        "simulated from that contig's own depth margin and the genome-wide beta-binomial "
        "over-dispersion; mva.mosaic.bdev via tools/fit_it2_mosaic.py"
    ),
    "it2_mosaic_fractions": (
        "Markello 2012's DANFIP relation on the upper band, with the same estimator run on "
        "null draws and subtracted; mva.mosaic.bdev.danfip"
    ),
    "it2_mosaic_models": (
        "five per-chromosome models (normal, monosomy, mitotic trisomy, meiotic trisomy, "
        "copy-neutral LOH) re-implemented from Kong 2018 and fitted by bounded maximum "
        "likelihood: a beta-binomial mixture on allele fraction times one Gaussian on the "
        "contig's mean depth ratio; mva.mosaic.madseq"
    ),
    "it2_mosaic_verdicts": (
        "BIC ranking of the five fits with Kong 2018's Delta-BIC < 10 low-confidence rule "
        "adopted as written; mva.mosaic.madseq.best"
    ),
    "it2_mosaic_density": (
        "heterozygous calls per megabase of arm and per PASS call, straight from "
        "results.it2_mosaic_density"
    ),
    "it2_mosaic_multi": (
        "forward mixing simulation with two and three contigs abnormal at once, rescoring "
        "every contig on the same replicate; mva.mosaic.simulate.multi_chromosome"
    ),
    LIMITS_TABLE: (
        "power against injected cell fraction from the contig's own depths, for the "
        "fold-over statistic and for entry 037's mean-BAF statistic on identical draws; "
        "mva.mosaic.simulate.power_curve"
    ),
}

CALLSET_REF = (
    "results.it2_mosaic_sites + results.it2_mosaic_depth + results.it2_mosaic_density "
    "(all derived from warehouse.variants_raw) + warehouse.cytoband_arms"
)
CLINICAL_REF = "ressources/hackathon-rules/Challenge_Clinical_Phenotype_1.md"
CLINICAL_TRANSFORM = (
    "not an input: the clinical document lists no karyotype and no term a blood-DNA "
    "aneuploid fraction would predict, and the delivery never states which tissue was "
    "sequenced. Recorded so a reader cannot take a cell fraction here for a severity "
    "statement about the child"
)
TOOL = "mva-warehouse pg-load-it2-step8"


@dataclass(frozen=True)
class Loaded:
    """One table after loading: what it is called and how many rows arrived."""

    table: str
    rows: int
    source: Path


def _columns_for(table: str, path: Path) -> tuple[tuple[str, str], ...]:
    """The declared schema, narrowed to what this TSV actually carries.

    The schema is a promise about **types**, not about presence. A table written by an
    earlier run legitimately has fewer columns -- the fits on disk predate two of theirs --
    and loading should carry what is there rather than refuse the file or invent nulls for
    the rest. The limits table takes the opposite shape for the same reason: its power
    columns are one per simulated fraction, which is a parameter of the run.
    """
    header = tuple(path.read_text(encoding="utf-8").split("\n", 1)[0].rstrip("\r").split("\t"))
    if table == LIMITS_TABLE:
        declared = (
            *LIMITS_FIXED,
            *((name, "DOUBLE") for name in header if name.startswith("power_")),
        )
    else:
        declared = SCHEMAS[table]
    return tuple((name, sql_type) for name, sql_type in declared if name in header)


def _create(connection, schema: str, table: str, columns: tuple[tuple[str, str], ...]) -> str:
    """Replace the table: rebuilding from the TSV is the only way it is ever written, so a
    partial old copy left behind would be a silent mixture of two runs."""
    qualified = f"{ALIAS}.{safe_identifier(schema)}.{safe_identifier(table)}"
    body = ", ".join(f'"{name}" {sql_type}' for name, sql_type in columns)
    connection.execute(f"DROP TABLE IF EXISTS {qualified}")
    connection.execute(f"CREATE TABLE {qualified} ({body})")
    return qualified


def _load_tsv(
    connection, schema: str, table: str, path: Path, columns: tuple[tuple[str, str], ...]
) -> int:
    qualified = _create(connection, schema, table, columns)
    names = ", ".join(f'"{name}"' for name, _ in columns)
    casts = ", ".join(f"CAST(NULLIF(\"{name}\", '') AS {sql_type})" for name, sql_type in columns)
    connection.execute(
        f"INSERT INTO {qualified} ({names}) "
        f"SELECT {casts} FROM read_csv(?, delim='\t', header=true, all_varchar=true, "
        f"quote='\"', escape='\"')",
        [str(path)],
    )
    counted = connection.execute(f"SELECT count(*) FROM {qualified}").fetchone()
    return int((counted or [0])[0])


def load(connection, *, schema: str, result_schema: str, out_dir: Path) -> list[Loaded]:
    """Load every step-8 table present in ``out_dir``, and record its lineage.

    A table whose TSV is absent is skipped rather than created empty: an empty table and a
    stage that did not run look identical in SQL, and only one of them is a result.
    """
    analysis_path = out_dir / "analysis.json"
    analysis = (
        json.loads(analysis_path.read_text(encoding="utf-8")) if analysis_path.exists() else {}
    )
    constants = analysis.get("constants", {})
    version = " ".join(
        f"{name}={value}"
        for name, value in (
            ("centre", constants.get("centre", "")),
            ("rho", constants.get("rho", "")),
            ("seed", constants.get("seed", "")),
        )
    )
    lineage.ensure_tables(connection, schema)

    loaded: list[Loaded] = []
    for table in (*SCHEMAS, LIMITS_TABLE):
        path = out_dir / "tables" / f"{table}.tsv"
        if not path.exists():
            continue
        rows = _load_tsv(connection, result_schema, table, path, _columns_for(table, path))
        loaded.append(Loaded(table=table, rows=rows, source=path))
        lineage.record(
            connection,
            schema,
            target_schema=result_schema,
            target_table=table,
            target_rows=rows,
            source_kind="derived",
            source_ref=CALLSET_REF,
            source_version=version,
            transform=TRANSFORMS[table],
            tool=TOOL,
            notes=(
                "every result is 'in the sequenced sample': the delivery does not say which "
                "tissue was sequenced, and a karyotype's aneuploid fraction is measured in "
                "cultured cells"
            ),
        )
        lineage.record(
            connection,
            schema,
            target_schema=result_schema,
            target_table=table,
            target_rows=rows,
            source_kind="clinical",
            source_ref=CLINICAL_REF,
            transform=CLINICAL_TRANSFORM,
            tool=TOOL,
        )
    return loaded
