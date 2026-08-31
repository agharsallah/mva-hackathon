"""The compound-heterozygous pair space: every het allele a panel gene could pair up.

The Track 1 answer is a *pair* — two different broken copies of one gene, one inherited
from each parent (a **compound heterozygote**). So the object worth materialising is not
a ranked variant list but the grid of candidate pairs per gene, with whatever the callset
can say about **phase** (which of the two copies each variant sits on).

**One row per heterozygous ALT allele, not per pair.** The pair grid is this set crossed
with itself, and it is quadratic: 58 het alleles in BUB1B are 1,653 pairs, and storing
them would be storing ``n(n-1)/2`` copies of the same two rows. The cross product is done
where it is displayed (the browser) or where it is classified (:mod:`mva.viz.phase`),
both of which see the whole gene at once. What the table owes them is the *members* of
the grid plus the two FORMAT fields phase is decided from.

Three conventions are load-bearing:

* **A ``1/2`` record contributes two rows.** One copy of each of two different ALT
  alleles is compound heterozygosity proven by the genotype itself, so the two alleles
  must be able to face each other in the grid. ``allele_ix`` distinguishes them. This is
  the same split :func:`mva.pipeline.vcf.iter_calls` performs.
* **PASS only.** A suppressed call is not evidence. That is a narrower set than
  ``methodology/006`` measured over all calls, and the difference is stated there rather
  than hidden here.
* **Annotation is a LEFT join and may be absent.** ``panel_annotations`` covers the
  alleles VEP was asked about; a het allele it does not cover gets ``annotated = false``
  and **null** for every annotation-derived flag — never ``false``, which would read as
  "measured and not rare".

Phase itself is *not* decided here. The rule is owned by
:func:`mva.pipeline.compound_het.classify_phase` and applied per pair; this table carries
the raw ``PGT``/``PID`` the rule reads, so the SQL and the classifier cannot drift apart.
"""

from .analysis_reference import PROTEIN_ALTERING, RARE_RECESSIVE_AF
from .derivation import SOURCE, Derivation

#: Genotypes that put exactly one copy of an ALT allele on one haplotype. Unphased and
#: phased spellings both appear in the callset (``PGT`` records the phased one separately,
#: but a caller may also write the bar into ``GT``), so both are matched.
HET_GENOTYPES = "('0/1', '1/0', '0|1', '1|0', '1/2', '2/1', '1|2', '2|1')"

#: The genotypes carrying two *different* ALT alleles — the auto-trans case.
MULTI_ALLELIC = "('1/2', '2/1', '1|2', '2|1')"


PANEL_HET_PAIRS = Derivation(
    name="panel_het_pairs",
    question=(
        "For each candidate gene, which heterozygous PASS alleles make up the "
        "compound-heterozygous pair space, and what physical phasing does the callset "
        "carry for them? One row per het ALT allele — the pair grid is this set crossed "
        "with itself, so a 1/2 record contributes two rows and the pair between those "
        "two is trans by construction. PGT/PID are carried raw so the pair classifier "
        "and this table cannot disagree about phase."),
    depends_on=("mva_panel_grch38", "variants_raw", "panel_annotations"),
    sql=f"""
        WITH panel AS (
            -- The panel BED is chr-prefixed and the callset is bare. Stripping in SQL is
            -- the same transform `mva.warehouse.reference` applies when it stages
            -- gnomAD; the Python side of the bridge is `mva.pipeline.variant`.
            SELECT name                         AS gene,
                   replace(chrom, 'chr', '')    AS chrom,
                   start,
                   "end"
            FROM {SOURCE}.mva_panel_grch38
        ),
        raw AS (
            SELECT p.gene,
                   r.chrom,
                   CAST(r.pos AS BIGINT)        AS pos,
                   r.ref,
                   r.alt,
                   TRY_CAST(r.qual AS DOUBLE)   AS qual,
                   str_split(r.format, ':')     AS keys,
                   str_split(r.sample_call, ':') AS vals
            FROM {SOURCE}.variants_raw r
            JOIN panel p
              ON r.chrom = p.chrom
             AND CAST(r.pos AS BIGINT) BETWEEN p.start AND p."end"
            -- Named separately from the join so the server can skip the other 17
            -- contigs instead of reading them and discarding the rows.
            WHERE r.chrom IN (SELECT chrom FROM panel)
              AND r.filter = 'PASS'
        ),
        call AS (
            -- FORMAT is self-describing: the keys travel with the record, so every field
            -- is located by name. PGT/PID are absent from ~85% of records and come back
            -- NULL there, which is the "unphased" state, not a missing measurement.
            SELECT gene, chrom, pos, ref, alt, qual,
                   list_extract(vals, coalesce(list_position(keys, 'GT'), 0))  AS gt,
                   TRY_CAST(list_extract(vals, coalesce(list_position(keys, 'DP'), 0))
                            AS BIGINT)                                         AS dp,
                   list_extract(vals, coalesce(list_position(keys, 'PGT'), 0)) AS pgt,
                   list_extract(vals, coalesce(list_position(keys, 'PID'), 0)) AS pid,
                   str_split(coalesce(
                       list_extract(vals, coalesce(list_position(keys, 'AD'), 0)), ''),
                       ',')                                                    AS ad
            FROM raw
        ),
        het AS (
            SELECT * FROM call WHERE gt IN {HET_GENOTYPES}
        ),
        -- One row per ALT allele present in the genotype. A 0/1 record carries ALT 1; a
        -- 1/2 record carries both, and joining a two-row index relation is how one row
        -- becomes two without an UNNEST whose ordering would be implicit.
        allele AS (
            SELECT h.gene, h.chrom, h.pos, h.ref,
                   str_split(h.alt, ',')[i.ix]                          AS alt,
                   i.ix                                                 AS allele_ix,
                   h.gt, h.qual, h.dp, h.pgt, h.pid,
                   -- Per-allele fraction: this allele's depth over the record's total.
                   -- `panel_candidates` reports NULL at a 1/2 site because "the" ALT is
                   -- ambiguous there; that ambiguity does not exist once the row *is* one
                   -- allele, so the fraction is well defined and is reported.
                   TRY_CAST(h.ad[i.ix + 1] AS BIGINT)                    AS ad_alt,
                   list_sum([TRY_CAST(x AS BIGINT) FOR x IN h.ad])       AS ad_total
            FROM het h
            JOIN (SELECT 1 AS ix UNION ALL SELECT 2 AS ix) i
              ON i.ix <= CASE WHEN h.gt IN {MULTI_ALLELIC} THEN 2 ELSE 1 END
            WHERE str_split(h.alt, ',')[i.ix] IS NOT NULL
        )
        SELECT a.gene,
               a.chrom,
               a.pos,
               a.ref,
               a.alt,
               a.allele_ix,
               a.gt,
               a.qual,
               a.dp,
               round(a.ad_alt / nullif(a.ad_total, 0), 4)               AS vaf,
               a.pgt,
               a.pid,
               n.rsid,
               n.consequence,
               n.impact,
               n.gnomad_af,
               n.gnomad_af_grpmax,
               n.clin_sig,
               n.chrom IS NOT NULL                                      AS annotated,
               -- NULL, not false, where VEP never saw the allele: `gnomad_af IS NULL`
               -- means "absent from gnomAD" only for an allele that was looked up.
               CASE WHEN n.chrom IS NULL THEN NULL
                    ELSE (n.gnomad_af IS NULL
                          OR n.gnomad_af < {RARE_RECESSIVE_AF}) END      AS is_rare_recessive,
               n.impact IN {PROTEIN_ALTERING}                            AS is_protein_altering
        FROM allele a
        LEFT JOIN {SOURCE}.panel_annotations n
               ON n.chrom = a.chrom
              AND n.pos   = a.pos
              AND n.ref   = a.ref
              AND n.alt   = a.alt
        ORDER BY a.gene, a.pos, a.allele_ix
    """,
)


#: The pair-space half of the derivation registry.
PAIR_DERIVATIONS: tuple[Derivation, ...] = (PANEL_HET_PAIRS,)
