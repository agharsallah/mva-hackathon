"""Cross-species phenotype twin: pure logic on a six-term synthetic MP ontology.

The ontology (MP ids are synthetic):

    MP:1 root
    +-- MP:2 growth
    |   +-- MP:4 small body
    |   +-- MP:5 short gestation
    +-- MP:3 tumour
        +-- MP:6 sarcoma

Four genotypes; IC comes from how many of them carry each term's closure.
"""

import math
from pathlib import Path

import numpy as np
import pytest

from mva.phenotype import cross_species as cs
from mva.phenotype import cross_species_controls as cc
from mva.phenotype import cross_species_io as cio
from mva.phenotype.ontology import parse_obo

OBO = """format-version: 1.2

[Term]
id: MP:1
name: root

[Term]
id: MP:2
name: growth
is_a: MP:1 ! root

[Term]
id: MP:3
name: tumour
is_a: MP:1 ! root

[Term]
id: MP:4
name: small body
is_a: MP:2 ! growth

[Term]
id: MP:5
name: short gestation
is_a: MP:2 ! growth

[Term]
id: MP:6
name: sarcoma
is_a: MP:3 ! tumour
alt_id: MP:66
"""

# composition, allele symbols, background, MP, PMID, markers, genotype id
GENO_ROWS = [
    ("A<h>/A<h>", "A<h>", "B6", "MP:4", "1", "MGI:A", "G1"),
    ("A<h>/A<h>", "A<h>", "B6", "MP:66", "2", "MGI:A", "G1"),  # alt id, second paper
    ("A<ko>/A<+>", "A<ko>|A<+>", "B6", "MP:6", "3", "MGI:A", "G2"),
    ("B<ko>/B<ko>", "B<ko>", "B6", "MP:5", "4", "MGI:B", "G3"),
    ("C<ko>/C<ko>", "C<ko>", "B6", "MP:2", "", "MGI:C", "G4"),
]


@pytest.fixture()
def world(tmp_path: Path) -> tuple[cs.MouseCorpus, dict[str, cio.Genotype], cs.Bridge]:
    (tmp_path / "mp.obo").write_text(OBO)
    rpt = tmp_path / "geno.rpt"
    rpt.write_text("".join("\t".join(r) + "\n" for r in GENO_ROWS))
    mp = parse_obo(tmp_path / "mp.obo")
    genotypes = cio.parse_pheno_geno_mp(rpt)
    rows = [
        cio.BridgeRow("HP:small", "MP:4", "skos:exactMatch", "mgi-curated", 1),
        cio.BridgeRow("HP:sarc", "MP:6", "jaccard 1", "upheno-bestmatch", 2),
        cio.BridgeRow("HP:gest", "MP:5", "skos:relatedMatch", "mgi-curated", 1),
        cio.BridgeRow("HP:gest", "MP:2", "jaccard 0.8", "upheno-bestmatch", 2),
        cio.BridgeRow("HP:gone", "MP:999", "skos:exactMatch", "mgi-curated", 1),
    ]
    return cs.build_corpus(mp, genotypes), genotypes, cs.build_bridge(rows, mp)


def test_rows_of_one_genotype_merge_and_alt_ids_resolve(world) -> None:
    corpus, genotypes, _ = world
    assert genotypes["G1"].mp_terms == {"MP:4", "MP:66"}
    assert genotypes["G1"].pmids == {"1", "2"}
    assert corpus.genotype_terms("G1") == ("MP:4", "MP:6")
    assert corpus.unresolved == 0


def test_ic_is_minus_log_share_of_genotypes_whose_closure_holds_the_term(world) -> None:
    corpus, _, _ = world
    ic = dict(zip(corpus.terms, corpus.ic, strict=True))
    assert ic["MP:1"] == 0.0
    assert ic["MP:2"] == pytest.approx(-math.log(3 / 4))  # G1, G3, G4
    assert ic["MP:6"] == pytest.approx(-math.log(2 / 4))  # G1, G2
    assert ic["MP:5"] == pytest.approx(-math.log(1 / 4))


def test_tier_two_is_a_fallback_and_unknown_targets_are_dropped(world) -> None:
    _, _, bridge = world
    assert bridge.mp_terms("HP:gest") == ("MP:5",)
    assert bridge.mp_terms("HP:sarc") == ("MP:6",)
    assert bridge.mp_terms("HP:gone") == ()


def test_vectorised_scores_equal_the_pairwise_resnik_walk(world) -> None:
    corpus, _, bridge = world
    query = ("HP:small", "HP:sarc", "HP:gest")
    scores = corpus.score(query, bridge)
    for gid in corpus.genotype_ids:
        row = corpus.row_of[gid]
        pairs = cs.explain(corpus, gid, query, bridge)
        assert scores.per_term[row] == pytest.approx([p.ic for p in pairs])
        mouse = corpus.genotype_terms(gid)
        projected = [m for hp in query for m in bridge.mp_terms(hp)]
        reverse = np.mean([max(corpus.mica(p, m)[1] for p in projected) for m in mouse])
        assert scores.reverse[row] == pytest.approx(reverse)
        assert scores.symmetric[row] == pytest.approx((scores.forward[row] + reverse) / 2)


def test_the_genotype_sharing_the_rare_terms_ranks_first_and_ties_are_pessimistic(world) -> None:
    corpus, _, bridge = world
    scores = corpus.score(("HP:small", "HP:sarc"), bridge)
    assert scores.rank(corpus.row_of["G1"]) == 1
    tied = corpus.score(("HP:gone",), bridge)  # unmappable: everyone scores zero
    assert tied.rank(0) == len(corpus)
    assert tied.percentile(0) == 100.0


def test_allele_class_reads_mgi_attributes() -> None:
    def allele(symbol: str, attrs: tuple[str, ...], kind: str = "Targeted") -> cio.Allele:
        return cio.Allele("id", symbol, kind, attrs, (), "MGI:A", "A", ())

    alleles = {
        "A<h>": allele("A<h>", ("Conditional ready", "Hypomorph")),
        "A<ko>": allele("A<ko>", ("Null/knockout",)),
        "A<ki>": allele("A<ki>", ("Humanized sequence",)),
    }

    def geno(*symbols: str) -> cio.Genotype:
        return cio.Genotype(
            "G", "/".join(symbols), symbols, "", ("MGI:A",), frozenset(), frozenset()
        )

    assert cc.allele_class(geno("A<h>", "A<ko>"), alleles, "MGI:A") == cc.HYPOMORPH
    assert cc.allele_class(geno("A<ko>", "A<+>"), alleles, "MGI:A") == cc.NULL
    assert cc.allele_class(geno("A<ki>", "A<+>"), alleles, "MGI:A") == cc.KNOCK_IN


def test_empirical_p_never_reaches_zero() -> None:
    assert cc.empirical_p(1.0, [5.0, 10.0, 0.5]) == pytest.approx(2 / 4)
    assert cc.empirical_p(0.1, [5.0] * 99) == pytest.approx(1 / 100)


def test_null_sets_are_ic_matched_and_exclude_the_query() -> None:
    pool = {f"HP:{i}": i / 100 for i in range(1000)}
    sets = cc.matched_null_sets(("HP:500", "HP:900"), pool, n=50, window=0.25, seed=1)
    assert len(sets) == 50
    for first, second in sets:
        assert first != "HP:500" and second != "HP:900"
        assert abs(pool[first] - 5.0) <= 0.25 and abs(pool[second] - 9.0) <= 0.25


def test_a_thin_ic_band_widens_to_the_ten_nearest_terms() -> None:
    pool = {f"HP:{i}": float(i) for i in range(30)}
    drawn = {s[0] for s in cc.matched_null_sets(("HP:15",), pool, n=300, window=0.25, seed=2)}
    assert drawn <= {f"HP:{i}" for i in (10, 11, 12, 13, 14, 16, 17, 18, 19, 20)}
    assert len(drawn) > 5


def test_mgi_sssom_columns_are_found_by_name(tmp_path: Path) -> None:
    path = tmp_path / "m.sssom.tsv"
    path.write_text(
        "#curie_map:\n"
        "object_id\tobject_label\tpredicate_id\tsubject_id\n"
        "HP:1\tx\tskos:exactMatch\tMP:4\n"
        "HP:2\ty\tskos:exactMatch\tGO:1\n"
    )
    rows = cio.parse_mgi_sssom(path)
    assert [(r.hp, r.mp, r.tier) for r in rows] == [("HP:1", "MP:4", 1)]
