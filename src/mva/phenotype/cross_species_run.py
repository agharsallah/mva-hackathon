"""One phenotype-twin study, end to end, as plain data (no printing, no files written).

:func:`load` reads the six public files from one directory into :class:`Inputs`.
:func:`twin_study` answers, for any HP query and any mouse gene:

* where the gene's best genotype ranks among every MGI genotype, per rollup;
* every genotype of the gene, with its MGI allele class;
* an IC-matched null and its empirical p-value;
* leave-one-term-out;
* where the gene ranks among genes (best genotype per gene).

:func:`disease_control` runs the same rank test for a disease's own HPO annotations against
the gene known to cause it - the positive control. Nothing here names the case.
"""

import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from . import cross_species_controls as cc
from . import cross_species_io as cio
from .cross_species import Bridge, MouseCorpus, Scores, build_bridge, build_corpus, explain
from .ontology import parse_obo

METRICS = ("symmetric", "phenodigm", "forward")

#: File names inside the raw directory. The CLI's fetch step owns the URLs.
FILES = {
    "mp": "mp.obo",
    "genotypes": "MGI_PhenoGenoMP.rpt",
    "alleles": "MGI_PhenotypicAllele.rpt",
    "mgi_sssom": "mp_hp_mgi_all.sssom.tsv",
    "upheno_logical": "upheno-species-independent.sssom.tsv",
    "upheno_best": "hp-to-mp-bestmatches.tsv",
    "hpoa": "phenotype.hpoa",
    "hp": "hp.obo",
}


@dataclass
class Inputs:
    """Everything a study needs, parsed once."""

    corpus: MouseCorpus
    bridge: Bridge
    genotypes: dict[str, cio.Genotype]
    alleles: dict[str, cio.Allele]
    markers: dict[str, str]
    hpoa: Path
    hp_names: dict[str, str]

    def marker_id(self, symbol: str) -> str:
        """MGI marker id for a gene symbol (exact, case-sensitive: mouse symbols)."""
        for marker, name in self.markers.items():
            if name == symbol:
                return marker
        raise KeyError(f"no MGI marker named {symbol!r}")


def load(raw: Path) -> Inputs:
    """Parse the raw directory (see :data:`FILES`)."""
    mp = parse_obo(raw / FILES["mp"])
    genotypes = cio.parse_pheno_geno_mp(raw / FILES["genotypes"])
    alleles = cio.parse_phenotypic_alleles(raw / FILES["alleles"])
    rows = (
        cio.parse_mgi_sssom(raw / FILES["mgi_sssom"])
        + cio.parse_upheno_logical(raw / FILES["upheno_logical"])
        + cio.parse_upheno_bestmatches(raw / FILES["upheno_best"])
    )
    hp = parse_obo(raw / FILES["hp"])
    return Inputs(
        corpus=build_corpus(mp, genotypes),
        bridge=build_bridge(rows, mp),
        genotypes=genotypes,
        alleles=alleles,
        markers=cio.marker_symbols(alleles),
        hpoa=raw / FILES["hpoa"],
        hp_names={k: c.name for k, c in hp.concepts.items()},
    )


def gene_rank(inputs: Inputs, scores: Scores, marker: str, metric: str) -> tuple[int, int]:
    """(pessimistic rank, number of genes) of ``marker`` by its best genotype's score."""
    values = scores.metric(metric)
    best: dict[str, float] = {}
    for gid, row in inputs.corpus.row_of.items():
        for m in inputs.genotypes[gid].marker_ids:
            if values[row] > best.get(m, -1.0):
                best[m] = float(values[row])
    mine = best.get(marker, 0.0)
    return sum(1 for v in best.values() if v >= mine - 1e-12), len(best)


def _hit(hit: cc.GeneHit | None) -> dict[str, Any] | None:
    return None if hit is None else hit.__dict__


def genotype_table(inputs: Inputs, scores: Scores, marker: str) -> list[dict[str, Any]]:
    """Every scored genotype of ``marker``: class, size, rank and percentile per rollup."""
    rows = cc.genotypes_of(inputs.corpus, inputs.genotypes, marker)
    out = []
    for row in rows:
        gid = inputs.corpus.genotype_ids[row]
        g = inputs.genotypes[gid]
        entry: dict[str, Any] = {
            "genotype_id": gid,
            "composition": g.composition,
            "background": g.background,
            "allele_class": cc.allele_class(g, inputs.alleles, marker),
            "n_mp_terms": len(inputs.corpus.genotype_terms(gid)),
            "pmids": sorted(g.pmids),
        }
        for m in METRICS:
            entry[f"{m}_score"] = round(float(scores.metric(m)[row]), 4)
            entry[f"{m}_rank"] = scores.rank(row, m)
            entry[f"{m}_percentile"] = round(scores.percentile(row, m), 4)
        entry["per_term"] = [round(float(v), 3) for v in scores.per_term[row]]
        out.append(entry)
    return sorted(out, key=lambda e: e["symmetric_rank"])


def twin_study(
    inputs: Inputs,
    query: Sequence[str],
    gene: str,
    n_null: int = 1000,
    seed: int = 0,
) -> dict[str, Any]:
    """The full rank test for one query and one gene symbol, with its controls."""
    corpus, bridge = inputs.corpus, inputs.bridge
    marker = inputs.marker_id(gene)
    rows = cc.genotypes_of(corpus, inputs.genotypes, marker)
    scores = corpus.score(query, bridge)
    best = {m: cc.best_for_gene(scores, corpus, rows, m) for m in METRICS}
    pool = cc.projected_ic(corpus, bridge)
    null_sets = cc.matched_null_sets(query, pool, n_null, seed=seed)
    null: dict[str, list[float]] = {m: [] for m in METRICS}
    for terms in null_sets:
        s = corpus.score(terms, bridge)
        for m in METRICS:
            hit = cc.best_for_gene(s, corpus, rows, m)
            null[m].append(hit.percentile if hit else 100.0)
    projection = [
        {
            "hp": hp,
            "hp_name": inputs.hp_names.get(hp, hp),
            "mp": list(bridge.mp_terms(hp)),
            "mp_names": [corpus.ontology.name(t) for t in bridge.mp_terms(hp)],
            "sources": sorted({r.source for r in bridge.project(hp)}),
            "tier": min((r.tier for r in bridge.project(hp)), default=None),
            "self_ic": round(pool.get(hp, 0.0), 3),
        }
        for hp in query
    ]
    top = np.argsort(-scores.symmetric, kind="stable")[:25]
    return {
        "query": list(query),
        "gene": gene,
        "marker_id": marker,
        "n_genotypes": len(corpus),
        "projection": projection,
        "best": {m: _hit(h) for m, h in best.items()},
        "gene_rank": {m: gene_rank(inputs, scores, marker, m) for m in METRICS},
        "genotypes": genotype_table(inputs, scores, marker),
        "null": {
            "n": n_null,
            "seed": seed,
            "window_nats": 0.25,
            "pool_size": len(pool),
            "percentiles": {m: [round(p, 4) for p in v] for m, v in null.items()},
            "median_percentile": {m: statistics.median(v) for m, v in null.items()},
            "empirical_p": {
                m: cc.empirical_p(hit.percentile, null[m]) if (hit := best[m]) else None
                for m in METRICS
            },
        },
        "leave_one_out": {
            m: [d.__dict__ for d in cc.leave_one_out(corpus, bridge, query, rows, m)]
            for m in METRICS
        },
        "explain": {
            m: [p.__dict__ for p in explain(corpus, h.genotype_id, query, bridge)]
            for m, h in best.items()
            if h is not None
        },
        "term_matrix": {
            gid: _matrix(inputs, gid, query)
            for gid in dict.fromkeys(h.genotype_id for h in best.values() if h is not None)
        },
        "top_genotypes": [
            {
                "genotype_id": corpus.genotype_ids[i],
                "composition": inputs.genotypes[corpus.genotype_ids[i]].composition,
                "n_mp_terms": len(corpus.genotype_terms(corpus.genotype_ids[i])),
                "symmetric": round(float(scores.symmetric[i]), 4),
                "phenodigm": round(float(scores.phenodigm[i]), 4),
            }
            for i in top
        ],
    }


def _matrix(inputs: Inputs, genotype_id: str, query: Sequence[str]) -> dict[str, Any]:
    """Query terms x one genotype's MP terms, as Resnik values, with labels for a heat map."""
    mouse, values = inputs.corpus.term_matrix(genotype_id, query, inputs.bridge)
    return {
        "composition": inputs.genotypes[genotype_id].composition,
        "mp": list(mouse),
        "mp_names": [inputs.corpus.ontology.name(t) for t in mouse],
        "values": [[round(float(v), 3) for v in row] for row in values],
    }


def pathway(inputs: Inputs, query: Sequence[str], genes: Sequence[str]) -> list[dict[str, Any]]:
    """Best genotype per gene for a list of related genes (absent genes reported, not skipped)."""
    scores = inputs.corpus.score(query, inputs.bridge)
    out: list[dict[str, Any]] = []
    for gene in genes:
        try:
            marker = inputs.marker_id(gene)
        except KeyError:
            out.append({"gene": gene, "marker_id": None, "best": None})
            continue
        rows = cc.genotypes_of(inputs.corpus, inputs.genotypes, marker)
        entry: dict[str, Any] = {"gene": gene, "marker_id": marker, "n_genotypes": len(rows)}
        for m in METRICS:
            hit = cc.best_for_gene(scores, inputs.corpus, rows, m)
            entry[m] = _hit(hit)
            if hit is not None:
                entry[m]["composition"] = inputs.genotypes[hit.genotype_id].composition
        out.append(entry)
    return out


def disease_control(
    inputs: Inputs, disease: str, gene: str, k: int = 8, n: int = 20, seed: int = 0
) -> dict[str, Any]:
    """Rank the causal gene's best genotype for ``n`` draws of ``k`` of a disease's terms."""
    terms = cio.parse_disease_terms(inputs.hpoa, disease)
    usable = [t for t in terms if inputs.bridge.mp_terms(t)]
    marker = inputs.marker_id(gene)
    rows = cc.genotypes_of(inputs.corpus, inputs.genotypes, marker)
    per_draw: dict[str, list[float]] = {m: [] for m in METRICS}
    for draw in cc.draws(usable, k, n, seed):
        scores = inputs.corpus.score(draw, inputs.bridge)
        for m in METRICS:
            hit = cc.best_for_gene(scores, inputs.corpus, rows, m)
            per_draw[m].append(round(hit.percentile, 4) if hit else 100.0)
    return {
        "disease": disease,
        "disease_name": cio.disease_name(inputs.hpoa, disease),
        "gene": gene,
        "n_terms": len(terms),
        "n_mappable": len(usable),
        "n_gene_genotypes": len(rows),
        "draws": n,
        "k": k,
        "percentiles": per_draw,
        "median_percentile": {m: statistics.median(v) for m, v in per_draw.items()},
    }
