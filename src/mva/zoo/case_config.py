"""The **case** and the run it configures — the only file that knows what a case is.

A *case* is one illness in one child: which gene is the confirmed answer, which docs folder
the answers land in, which phenotype ranking the reports quote. None of that is written into
the zoo's code; it is this dataclass, loaded from a TOML (``zoo.example.toml``, or a copy of
it under ``cases/``). Pointing the zoo at another illness is editing that file — the decision,
and the honest list of what still resists it, is `docs/notes/zoo-case-config.md`.

Split out of :mod:`mva.zoo.workflow_types`, which keeps the run's *working* shapes (state,
stage result, manifest, the injected dependency bundle). This module imports nothing from the
zoo, so it can be read — by the API, by a test, by a second case — without pulling in a
database driver.
"""

from __future__ import annotations

import hashlib
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = ["DEFAULT_ITERATION", "DEFAULT_PREFIX", "Config"]

#: The docs folder a run writes into when the config's ``[case]`` block names none, and the
#: table-name prefix that goes with it. They are *defaults*, not constants of the method: a
#: second case sets its own in ``[case]`` and nothing in this package has to change.
DEFAULT_ITERATION = "iteration4"
DEFAULT_PREFIX = "it4"


@dataclass(frozen=True)
class Config:
    """One run's configuration, read from ``zoo.example.toml`` (or a copy of it).

    Four blocks: ``[case]`` says *which illness* this run is about, ``[run]`` how it is
    scored, ``[merge]``/``[llm]`` how the lanes are combined, ``[paths]`` where the answer
    lands. Only ``[case]`` changes when the zoo is pointed at another child — that is the
    whole reusability claim, and `docs/notes/zoo-case-config.md` records what still resists it.
    """

    path: Path
    digest: str = ""
    #: ── the case ──────────────────────────────────────────────────────────────────────
    #: A human label for the case, printed in reports and manifests. Never a patient id.
    label: str = ""
    #: The docs folder this run writes into (``docs/<iteration>/…``) and the stem of the
    #: default private output directory.
    iteration: str = DEFAULT_ITERATION
    #: Prefix of the warehouse tables this run writes (``<prefix>_model_reports``) and of
    #: the run id. A second case with its own prefix does not collide with this one.
    table_prefix: str = DEFAULT_PREFIX
    #: The gene whose biallelic pair is the confirmed answer, **by symbol** — a coordinate
    #: never appears here (CLAUDE.md, coordinate gate). Empty means no confirmed pair is
    #: declared: nothing is flagged and every report says so, which is the normal state of
    #: an unsolved case.
    confirmed_gene: str = ""
    #: How the confirmed pair is picked when the gene carries more than one candidate pair:
    #: ``lof+missense`` prefers a truncating allele plus a missense allele, ``all`` flags
    #: every pair of the gene. See :data:`mva.zoo.pairs.PAIR_RULES`.
    confirmed_pair_rule: str = "lof+missense"
    #: Which phenotype ranking section 5 of every report quotes. ``with-parental`` is the
    #: child's HPO terms plus what the parents' testing contributed; ``proband-only`` is the
    #: child's alone. Naming it here keeps the clinical half of the evidence a configuration
    #: choice rather than a constant buried in a report renderer.
    phenotype_term_set: str = "with-parental"
    #: The warehouse table that holds the phenotype-only gene ranking read for section 5.
    hpo_table: str = "hpo_gene_scores"
    #: ── the run ───────────────────────────────────────────────────────────────────────
    mode: str = "catalogue-free"
    models: tuple[str, ...] = ()
    out_dir: Path = Path(f"build/{DEFAULT_PREFIX}")
    schema: str = "results"
    #: Where the shared, append-only tables live — ``allele_scores`` and ``data_lineage``.
    #: A different schema from :attr:`schema`, which holds this run's *results*. They were
    #: one field until the first real run read an empty score cache out of ``results`` and
    #: ranked nothing at all without erroring (entry 128).
    warehouse_schema: str = "warehouse"
    method: str = "fusion"
    rrf_k: int = 60
    llm_mode: str = "none"
    reports_dir: Path = Path(f"docs/{DEFAULT_ITERATION}/reports")
    docs_runs_dir: Path = Path(f"docs/{DEFAULT_ITERATION}/runs")
    merged_path: Path = Path(f"docs/{DEFAULT_ITERATION}/report.md")
    fixtures: Path | None = None

    @classmethod
    def load(cls, path: str | Path, **overrides: Any) -> Config:
        """Parse the TOML and hash its bytes — the digest is what the manifest records.

        ``iteration`` and ``table_prefix`` may be overridden by the caller (``mva-zoo run
        --iteration demo``). Doing so **re-derives every default path**, and the config's own
        ``[paths]`` block is then ignored: a caller who asks for another case's folder means
        the outputs to go there, not half of them.
        """
        file = Path(path)
        raw = file.read_bytes()
        data = tomllib.loads(raw.decode("utf-8"))
        case_block = data.get("case", {})
        run_block = data.get("run", {})
        merge_block = data.get("merge", {})
        llm_block = data.get("llm", {})
        paths = data.get("paths", {})
        moved = any(overrides.get(key) for key in ("iteration", "table_prefix"))
        iteration = str(
            overrides.pop("iteration", None) or case_block.get("iteration") or DEFAULT_ITERATION
        )
        prefix = str(
            overrides.pop("table_prefix", None) or case_block.get("table_prefix") or DEFAULT_PREFIX
        )
        if moved:
            paths, run_block = {}, {k: v for k, v in run_block.items() if k != "out_dir"}
        values: dict[str, Any] = {
            "path": file,
            "digest": hashlib.sha256(raw).hexdigest(),
            "label": str(case_block.get("label", "")),
            "iteration": iteration,
            "table_prefix": prefix,
            "confirmed_gene": str(case_block.get("confirmed_gene", "") or ""),
            "confirmed_pair_rule": str(case_block.get("confirmed_pair_rule", "lof+missense")),
            "phenotype_term_set": str(
                case_block.get("phenotype_term_set")
                # ``[run] hpo_term_set`` was where this lived before the case block existed.
                or run_block.get("hpo_term_set")
                or "with-parental"
            ),
            "hpo_table": str(case_block.get("hpo_table", "hpo_gene_scores")),
            "mode": run_block.get("mode", "catalogue-free"),
            "models": tuple(run_block.get("models", ())),
            "out_dir": Path(run_block.get("out_dir", f"build/{prefix}")),
            "schema": run_block.get("schema", "results"),
            "warehouse_schema": run_block.get("warehouse_schema", "warehouse"),
            "method": merge_block.get("method", "fusion"),
            "rrf_k": int(merge_block.get("rrf_k", 60)),
            "llm_mode": llm_block.get("mode", "none"),
            "reports_dir": Path(paths.get("reports_dir", f"docs/{iteration}/reports")),
            "docs_runs_dir": Path(paths.get("docs_runs_dir", f"docs/{iteration}/runs")),
            "merged_path": Path(paths.get("merged_report", f"docs/{iteration}/report.md")),
        }
        values.update(overrides)
        return cls(**values)

    @property
    def run_id(self) -> str:
        """Deterministic in the config: the same config re-run is the same run, not a new one."""
        return f"{self.table_prefix}-{self.digest[:12]}"

    def table(self, name: str) -> str:
        """``"model_reports"`` → ``"it4_model_reports"`` — a result table of this case.

        Only the writers this package threads the prefix through honour it; the inventory of
        the ones that still spell ``it4_`` themselves is in `docs/notes/zoo-case-config.md`.
        """
        return f"{self.table_prefix}_{name}"

    def case_json(self) -> dict[str, Any]:
        """The case block as plain JSON — what a report, a manifest or an API route prints."""
        return {
            "label": self.label,
            "iteration": self.iteration,
            "table_prefix": self.table_prefix,
            "confirmed_gene": self.confirmed_gene,
            "confirmed_pair_rule": self.confirmed_pair_rule,
            "phenotype_term_set": self.phenotype_term_set,
            "hpo_table": self.hpo_table,
        }
