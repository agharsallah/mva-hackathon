"""Iteration 2, step 5 as JSON: what the literature says, and the two nulls that judge it.

``/api/steps`` shows every step's goal, claims and figure names. This route shows one
step's *tables*, because the result of step 5 is an ordering produced by public knowledge
and the only honest way to read one is beside the two things that could explain it away.

**Seven blocks, and three of them exist to argue against the other four.**

``leaders``      the knowledge ordering, each row carrying where the genome-wide ranking
                 and a raw publication count put the same gene
``catalogue``    per gene, how many of this child's alleles anyone has published about -
                 with the ones that could not be looked up counted separately
``anchors``      papers that discuss a gene alongside several of the child's features
``protein``      the leading missense alleles against the domain map and the structure
``groups``       targets, decoys and the rest of the genome side by side
``citations``    how far the knowledge ordering moves a gene from where its publication
                 count alone would have put it
``domains``      the InterPro map of each leading protein, as fractions of its length

**A publication is not evidence about this child.** ``catalogue`` keeps *somebody wrote
about this variant* and *this child carries it* in different columns, and only the second
is a statement about the patient. The route serves both and never a merged score.

**Nothing served here has a position.** An allele is named by its consequence class and
its dbSNP identifier; a protein position is a fraction of the protein's length. The
coordinates and the residue numbers stay in ``build/``.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter

from ..warehouse.postgres import ALIAS
from ..warehouse.settings import Postgres
from .queries.access import fetch
from .response import Envelope, live

SOURCE = "pg.results.it2_pub_alleles + it2_anchors + it2_protein_* + it2_knowledge_ranks"

#: How many rows of each ordering the page shows. The knowledge table has one row per gene
#: in the step-5 set; a page showing all of them is a download, not a result.
LEADERS = 25

#: Where the run leaves the numbers no SQL table holds — the decoy AUC and its interval,
#: the Spearman correlation against the citation baseline, the coverage counts. Read from
#: the build directory for the same reason the figures are: they are outputs of a fit.
ANALYSIS = Path("build/it2/step-5")

#: Each block is ``name -> SQL``. See the module docstring.
BLOCKS: dict[str, str] = {
    "leaders": f"""
        SELECT knowledge_rank, gene, knowledge_score, best_terms_matched,
               terms_with_any_paper, described_alleles, carried_pathogenic,
               pubmed_count, citation_rank, lr_rank, is_target, is_decoy, curated
        FROM {ALIAS}.results.it2_knowledge_leaders
        ORDER BY knowledge_rank
        LIMIT {LEADERS}
    """,
    # Genes where either instrument found something, most informative first. A gene with
    # nothing is the common case and is counted in ``groups`` rather than listed here.
    "catalogue": f"""
        SELECT gene, is_target, is_decoy, in_top_leaders, alleles, queryable,
               unqueryable, described, most_cited_allele, carried_pathogenic
        FROM {ALIAS}.results.it2_catalogue_overlap
        WHERE carried_pathogenic > 0 OR described > 0 OR in_top_leaders
        ORDER BY carried_pathogenic DESC, described DESC, gene
        LIMIT {LEADERS * 2}
    """,
    "anchors": f"""
        SELECT gene, pmid, title, journal, year, terms_matched, terms_total,
               matched_terms, is_target, is_decoy, in_top_leaders, reaches_threshold
        FROM {ALIAS}.results.it2_anchor_match
        ORDER BY terms_matched DESC, in_top_leaders DESC, gene
        LIMIT {LEADERS * 2}
    """,
    "protein": f"""
        SELECT gene, gene_rank, uniprot, rsid, in_domain, in_superfamily,
               domain_accession, domain_name, plddt, confident, fraction,
               am_class, am_agrees, all_three, note
        FROM {ALIAS}.results.it2_protein_agreement
        ORDER BY gene_rank, gene
    """,
    "groups": f"""
        SELECT grouping, genes, mean_score, median_score, max_score,
               genes_with_anchor, genes_with_published_allele, median_pubmed_count
        FROM {ALIAS}.results.it2_knowledge_separation
        ORDER BY median_score DESC, grouping
    """,
    # The headline comparison: a gene that the literature moves a long way from where its
    # citation count alone would have put it is the only kind of row this route can claim.
    "citations": f"""
        SELECT gene, knowledge_rank, citation_rank, lr_rank, knowledge_score,
               pubmed_count, best_terms_matched, described_alleles,
               is_target, is_decoy, moved, distance
        FROM {ALIAS}.results.it2_knowledge_vs_citations
        ORDER BY knowledge_rank
        LIMIT {LEADERS}
    """,
    "domains": f"""
        SELECT d.gene, d.uniprot, d.protein_length, d.interpro, d.domain_name,
               d.entry_type, d.start_fraction, d.end_fraction
        FROM {ALIAS}.results.it2_protein_domains d
        ORDER BY d.gene, d.start_fraction
    """,
}


def payload(settings: Postgres, root: Path = ANALYSIS) -> dict:
    """Every block, plus the fitted numbers no table holds.

    A block whose table does not exist yet comes back **empty rather than raising**, the
    rule steps 3 and 4 already follow: the four stages land one at a time, and a page that
    500s until the last one finishes hides the results that are already in.
    """
    data: dict[str, object] = {}
    for name, sql in BLOCKS.items():
        try:
            data[name] = fetch(settings, sql)
        except Exception:
            data[name] = []
    data["coverage"] = _read(root / "catalogue.json")
    data["anchor_summary"] = _read(root / "anchors.json")
    data["protein_summary"] = _read(root / "protein.json")
    data["baselines"] = _read(root / "baselines.json")
    return data


#: Keys held back from the served payload: long per-gene maps the SQL blocks already
#: serve, and shipping both invites the page and the database to disagree.
BULKY = frozenset({"best_per_gene", "leaders", "clinvar_carried_genes"})


def _read(path: Path) -> dict:
    """One analysis file, or an empty object — an absent stage renders as an absent block."""
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(loaded, dict):
        return {}
    return {key: value for key, value in loaded.items() if key not in BULKY}


def add_routes(api: APIRouter, settings: Postgres) -> None:
    """Register the step-5 detail route on the warehouse router."""

    @api.get(
        "/steps/step-5",
        response_model=Envelope,
        tags=["science"],
        summary=f"iteration 2 step 5's literature, protein and citation baselines ({SOURCE})",
    )
    def it2_step_5() -> dict:
        """What public knowledge says about the candidate set, and whether that is worth
        anything.

        The ordering and the two nulls that qualify it are fetched by the same request and
        rendered on the same page: a literature route that agrees with a raw publication
        count has measured fame, and the page has to be able to say so.
        """
        return live(payload(settings), SOURCE)
