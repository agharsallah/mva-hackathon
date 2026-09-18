"""Everything step 4's likelihood ratio reads, in two queries and one file.

The step is deliberately thin on new data: the callset was annotated in iteration 1, the
phenotype ranking in step 1, the read confirmation in step 3, and the only genuinely new
table is the in-silico one. So this module's job is to hand the ranker two flat shapes —
**one row per allele carried** and **one row per gene** — and to leave every judgement to
:mod:`mva.pipeline.genotype_lr` and :mod:`mva.pipeline.pair_lr`.

Two properties matter and are enforced here rather than hoped for:

* **No filter.** ``results.coding_alleles`` keeps every FILTER value and every zygosity by
  construction, and nothing below narrows it. A gene with one suppressed low-depth call is
  scored, badly, rather than being absent.
* **A missing annotation is a null, not a dropped row.** Every join is a ``LEFT JOIN``, and
  the in-silico columns fall back to the iteration-1 annotation where the newer pass has no
  answer, so an allele the second pass missed keeps the first pass's consequence.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..pipeline.genotype_lr import AlleleEvidence
from ..pipeline.variant import Variant
from ..pipeline.vcf import Call
from .postgres import ALIAS, attached, safe_identifier
from .settings import Postgres

__all__ = [
    "TERM_SET",
    "AlleleRow",
    "GeneRow",
    "alleles",
    "gene_context",
    "has_insilico",
]

#: The phenotype term set every iteration-2 query reads: the child's own terms, not the
#: parents' (entry 067 §5, hypothesis H002).
TERM_SET = "proband-only"

#: Target tiers, as step 1 wrote them. Anything else in ``it2_targets`` is not a target.
TARGET_TIERS = ("core", "mechanism-term", "net")


@dataclass(frozen=True)
class AlleleRow:
    """One ALT allele the proband carries, with everything known about it."""

    gene: str
    chrom: str
    pos: int
    ref: str
    alt: str
    zygosity: str
    genotype: str
    filters: str
    depth: int | None
    vaf: float | None
    phase_gt: str | None
    phase_set: str | None
    rsid: str
    evidence: AlleleEvidence

    @property
    def variant(self) -> Variant:
        return Variant.from_vcf(self.chrom, self.pos, self.ref, self.alt)

    @property
    def key(self) -> tuple[str, int, str, str]:
        return (self.chrom, self.pos, self.ref, self.alt)

    @property
    def is_het(self) -> bool:
        """Heterozygous, including one ALT of a two-ALT site."""
        return self.zygosity in ("het", "multi")

    @property
    def is_hom(self) -> bool:
        return self.zygosity == "hom"

    def call(self) -> Call:
        """The VCF-shaped record :func:`mva.pipeline.compound_het.classify_phase` reads."""
        return Call(
            variant=self.variant,
            genotype=self.genotype,
            filters=tuple(f for f in self.filters.split(";") if f) or ("PASS",),
            depth=self.depth,
            ref_depth=None,
            alt_depth=None,
            phase_set=self.phase_set or None,
            phase_gt=self.phase_gt or None,
        )


@dataclass(frozen=True)
class GeneRow:
    """What is known about a gene, independent of any allele in it."""

    symbol: str
    phenotype_rank: int | None = None
    phenotype_score: float | None = None
    tier: str = ""
    is_decoy: bool = False
    loeuf: float | None = None
    reachable: bool | None = None
    confirmed_het: int | None = None
    biallelic_confirmed: bool | None = None

    @property
    def is_target(self) -> bool:
        return self.tier in TARGET_TIERS

    @property
    def curated(self) -> bool:
        """Whether the symptom ranker could place this gene at all."""
        return self.phenotype_rank is not None


def has_insilico(connection, schema: str) -> bool:
    """Whether the in-silico pass has landed. Absent is a *state*, not a failure.

    A reviewer who reruns the ranking without repeating the VEP pass gets the same code
    path with the missense and splice lanes silent, and is told so — rather than a crash,
    or worse, a ranking that quietly dropped two lanes.
    """
    (found,) = connection.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_schema = ? AND table_name = ?",
        [schema, "it2_insilico_annotations"],
    ).fetchone()
    return bool(found)


def alleles(settings: Postgres) -> list[AlleleRow]:
    """Every carried ALT allele in a coding interval, annotated, with no filter applied."""
    ingest = safe_identifier(settings.schema)
    result = safe_identifier(settings.result_schema)
    with attached(settings, read_only=True) as connection:
        if not has_insilico(connection, settings.schema):
            return [
                _allele_row(row)
                for row in connection.execute(_sql(ingest, result, False)).fetchall()
            ]
        return [
            _allele_row(row) for row in connection.execute(_sql(ingest, result, True)).fetchall()
        ]


def _sql(ingest: str, result: str, insilico: bool) -> str:
    """The one query, with the in-silico columns either joined or written as nulls."""
    columns = (
        """i.am_pathogenicity,
               coalesce(i.am_class, '')                          AS am_class,
               i.spliceai_ds_max,
               i.exon_index,
               i.exon_total"""
        if insilico
        else """CAST(NULL AS DOUBLE)  AS am_pathogenicity,
               ''                    AS am_class,
               CAST(NULL AS DOUBLE)  AS spliceai_ds_max,
               CAST(NULL AS INTEGER) AS exon_index,
               CAST(NULL AS INTEGER) AS exon_total"""
    )
    join = (
        f"""LEFT JOIN {ALIAS}.{ingest}.it2_insilico_annotations i
               ON i.chrom = a.chrom AND i.pos = a.pos AND i.ref = a.ref AND i.alt = a.alt"""
        if insilico
        else ""
    )
    prefer = (
        (lambda name: f"coalesce(i.{name}, n.{name})") if insilico else (lambda name: f"n.{name}")
    )
    prefer_text = (
        (lambda name: f"coalesce(i.{name}, n.{name}, '')")
        if insilico
        else (lambda name: f"coalesce(n.{name}, '')")
    )
    return f"""
        SELECT a.gene,
               a.chrom,
               a.pos,
               a.ref,
               a.alt,
               a.zygosity,
               a.gt,
               coalesce(a.filter, '')                            AS filters,
               a.dp,
               a.vaf,
               a.pgt,
               a.pid,
               {prefer_text("rsid")}                              AS rsid,
               {prefer_text("consequence")}                       AS consequence,
               {prefer_text("impact")}                            AS impact,
               {prefer("gnomad_af")}                              AS gnomad_af,
               {prefer("gnomad_af_grpmax")}                       AS gnomad_af_grpmax,
               {prefer_text("clin_sig")}                          AS clin_sig,
               {columns}
        FROM {ALIAS}.{result}.coding_alleles a
        LEFT JOIN {ALIAS}.{ingest}.coding_annotations n
               ON n.chrom = a.chrom AND n.pos = a.pos AND n.ref = a.ref AND n.alt = a.alt
        {join}
        WHERE a.gene IS NOT NULL
        ORDER BY a.gene, a.chrom, a.pos, a.alt
    """


def gene_context(settings: Postgres) -> dict[str, GeneRow]:
    """One row per gene named anywhere the step reads — ranking, tiers, constraint, reads."""
    ingest = safe_identifier(settings.schema)
    result = safe_identifier(settings.result_schema)
    sql = f"""
        WITH ranked AS (
            SELECT gene_symbol AS symbol, CAST(rank AS BIGINT) AS rank, score
            FROM {ALIAS}.{ingest}.hpo_gene_scores
            WHERE term_set = '{TERM_SET}'
        ),
        target AS (SELECT symbol, tier FROM {ALIAS}.{result}.it2_targets),
        decoy AS (SELECT symbol FROM {ALIAS}.{result}.it2_decoys),
        constraint_ AS (
            SELECT gene AS symbol, min(loeuf) AS loeuf
            FROM {ALIAS}.{ingest}.gnomad_constraint
            GROUP BY gene
        ),
        reads AS (
            SELECT symbol, reachable, confirmed_het, biallelic_confirmed
            FROM {ALIAS}.{result}.it2_kmer_pairs
        ),
        every_gene AS (
            SELECT symbol FROM ranked
            UNION SELECT symbol FROM target
            UNION SELECT symbol FROM decoy
            UNION SELECT symbol FROM constraint_
            UNION SELECT symbol FROM reads
            UNION SELECT DISTINCT gene AS symbol
              FROM {ALIAS}.{result}.coding_alleles WHERE gene IS NOT NULL
        )
        SELECT g.symbol, r.rank, r.score, coalesce(t.tier, ''), d.symbol IS NOT NULL,
               c.loeuf, k.reachable, k.confirmed_het, k.biallelic_confirmed
        FROM every_gene g
        LEFT JOIN ranked r ON r.symbol = g.symbol
        LEFT JOIN target t ON t.symbol = g.symbol
        LEFT JOIN decoy d ON d.symbol = g.symbol
        LEFT JOIN constraint_ c ON c.symbol = g.symbol
        LEFT JOIN reads k ON k.symbol = g.symbol
    """
    with attached(settings, read_only=True) as connection:
        rows = connection.execute(sql).fetchall()
    return {
        str(symbol): GeneRow(
            symbol=str(symbol),
            phenotype_rank=int(rank) if rank is not None else None,
            phenotype_score=float(score) if score is not None else None,
            tier=str(tier or ""),
            is_decoy=bool(is_decoy),
            loeuf=float(loeuf) if loeuf is not None else None,
            reachable=None if reachable is None else bool(reachable),
            confirmed_het=int(confirmed) if confirmed is not None else None,
            biallelic_confirmed=None if biallelic is None else bool(biallelic),
        )
        for symbol, rank, score, tier, is_decoy, loeuf, reachable, confirmed, biallelic in rows
    }


def _allele_row(row: tuple) -> AlleleRow:
    (
        gene,
        chrom,
        pos,
        ref,
        alt,
        zygosity,
        genotype,
        filters,
        depth,
        vaf,
        pgt,
        pid,
        rsid,
        consequence,
        impact,
        gnomad_af,
        grpmax,
        clin_sig,
        am_pathogenicity,
        am_class,
        spliceai,
        exon_index,
        exon_total,
    ) = row
    return AlleleRow(
        gene=str(gene),
        chrom=str(chrom),
        pos=int(pos),
        ref=str(ref),
        alt=str(alt),
        zygosity=str(zygosity),
        genotype=str(genotype or ""),
        filters=str(filters or ""),
        depth=int(depth) if depth is not None else None,
        vaf=float(vaf) if vaf is not None else None,
        phase_gt=str(pgt) if pgt else None,
        phase_set=str(pid) if pid else None,
        rsid=str(rsid or ""),
        evidence=AlleleEvidence(
            consequence=str(consequence or ""),
            impact=str(impact or ""),
            gnomad_af=float(gnomad_af) if gnomad_af is not None else None,
            gnomad_af_grpmax=float(grpmax) if grpmax is not None else None,
            clin_sig=str(clin_sig or ""),
            am_pathogenicity=float(am_pathogenicity) if am_pathogenicity is not None else None,
            am_class=str(am_class or ""),
            spliceai_ds_max=float(spliceai) if spliceai is not None else None,
            exon_index=int(exon_index) if exon_index is not None else None,
            exon_total=int(exon_total) if exon_total is not None else None,
            filters=str(filters or ""),
        ),
    )
