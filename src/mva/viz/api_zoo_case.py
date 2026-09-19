"""Which case the zoo routes are serving — read from the run configuration, never typed.

The zoo is meant to run on the next child by changing inputs only, so no route may know
this case's gene, schemas or docs folder. All of it is one file:
``src/mva/zoo/zoo.example.toml``, or whatever ``MVA_ZOO_CONFIG`` points at.
:class:`mva.zoo.workflow_types.Config` parses it — the same parser the workflow itself uses,
so the API cannot read the configuration differently from the run that produced the data.

From its ``[case]`` block come the label, the confirmed gene, the table prefix and the docs
paths; from ``[run]`` the two schemas and the lanes. :class:`Case` is that, plus the one
fallback the API needs: a config that declares no ``confirmed_gene`` (an unsolved case, the
normal state) leaves ``gene`` empty and says so in ``gene_source``, rather than borrowing a
gene from anywhere.

``GET /api/zoo/case`` serves :meth:`Case.as_dict` so a dashboard shows the case it received.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..zoo.workflow_types import Config
from .api_zoo_reads import Tables

__all__ = ["CONFIG_ENV", "DEFAULT_CONFIG", "Case", "case_config", "sources"]

#: The environment variable that points these routes at another case's run configuration.
CONFIG_ENV = "MVA_ZOO_CONFIG"

#: The configuration shipped with the package, used when :data:`CONFIG_ENV` is unset.
#: Repository-relative, like every other path in this package — ``mva-viz-api`` anchors the
#: process at the repository root before anything reads a default (:func:`mva.paths.anchor_cwd`).
DEFAULT_CONFIG = Path("src/mva/zoo/zoo.example.toml")


@dataclass(frozen=True)
class Case:
    """One case's configuration, as the API serves it."""

    config: Config
    tables: Tables

    @property
    def gene(self) -> str:
        """The confirmed answer's gene symbol, or ``""`` when the case declares none."""
        return self.config.confirmed_gene

    @property
    def gene_source(self) -> str:
        """Where :attr:`gene` came from — a page should never have to guess."""
        if self.gene:
            return f"{self.config.path} [case].confirmed_gene"
        return "not declared: this case has no confirmed pair"

    def as_dict(self) -> dict[str, Any]:
        """The case as the dashboard shows it, paths included so a reader can find them."""
        config = self.config
        return {
            "gene": self.gene or None,
            "gene_source": self.gene_source,
            "case": config.case_json(),
            "config_path": str(config.path),
            "config_digest": config.digest,
            "run_id": config.run_id,
            "mode": config.mode,
            "merge_method": config.method,
            "rrf_k": config.rrf_k,
            "llm_mode": config.llm_mode,
            "models": list(config.models),
            "schemas": {"results": self.tables.results, "warehouse": self.tables.warehouse},
            "tables": list(self.tables.names),
            "paths": {
                "out_dir": str(config.out_dir),
                "reports_dir": str(config.reports_dir),
                "runs_dir": str(config.docs_runs_dir),
                "merged_report": str(config.merged_path),
            },
        }


def case_config(path: Path | str | None = None) -> Case:
    """Resolve the case from the run configuration. ``MVA_ZOO_CONFIG`` overrides the path.

    Read per request: the file is a few hundred bytes, and an operator who points the API at
    another case should not have to restart it.
    """
    file = Path(path or os.environ.get(CONFIG_ENV) or DEFAULT_CONFIG)
    config = Config.load(file)
    return Case(config=config, tables=Tables.of(config))


def sources(case: Case) -> dict[str, str]:
    """What each route reads, in the repository's ``pg.<schema>.<table>`` notation.

    Derived from the case rather than written down, so the ``source`` line a reply carries
    names the schemas and files *that* reply was served from — the catalogue entry every
    route in this API is required to carry.
    """
    tables = case.tables
    records = f"pg.{tables.results}.{tables.records}"
    scores = f"pg.{tables.warehouse}.{tables.scores}"
    config = case.config
    return {
        "case": str(config.path),
        "models": f"src/mva/zoo/models.toml + models.d/*.toml, {scores}, {records}",
        "scores": f"{scores}, {records}",
        "ranks": (
            f"pg.{tables.results}.{tables.ranks}, "
            f"{config.out_dir}/merged.json (the two allele percentiles)"
        ),
        "merge": f"{config.out_dir}/merged.json, {records}",
        "runs": f"{config.docs_runs_dir}/*.json",
        "reports": f"{config.reports_dir}/*.md + {config.merged_path}",
        "lineage": f"pg.{tables.warehouse}.data_lineage",
    }
