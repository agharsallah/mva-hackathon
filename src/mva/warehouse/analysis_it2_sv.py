"""Iteration 2, step 2 — the structural-variant half, kept apart from the allele half.

Its own module because the two ask different questions of different tables and because
one file holding both went past the 400-line limit. The rule
(``docs/notes/python-quality-gates.md``) is to split by concern rather than raise the
limit, and *small variants* and *structural variants* is the seam that was already there.

**Two controls stand between a consensus call and a finding, and both were earned.** The
first run of this query returned a 13 Mb deletion and a 40 Mb inversion in a living child,
because a baited alignment is islands of coverage with emptiness between them and a
read-pair caller reports the emptiness as one enormous event. The constants below say what
each control is for and what it cost to learn.
"""

from .derivation import RESULT, SOURCE, Derivation

__all__ = [
    "BAIT_EDGE_BP",
    "IT2_SV_CONSENSUS",
    "IT2_SV_DERIVATIONS",
    "IT2_SV_LEADS",
    "MIN_BAITED_SPAN",
    "MIN_SV_LENGTH",
]

#: A call within this many bases of a baited interval's boundary is a bait-edge call: the
#: coverage cliff and unpaired mates there are what a read-pair caller reads as a deletion.
#: Measured rather than assumed — 14.1 % of recovered fragments matched on one mate only
#: (entry 087), which is the empirical size of this zone.
BAIT_EDGE_BP = 1_000

#: The share of an SV's span that must actually be baited for the call to be evidence.
#:
#: Proximity to an edge is necessary but not sufficient, which the first run of this query
#: demonstrated: its "consensus" calls included a 13 Mb deletion and a 40 Mb inversion in a
#: living child. Those do not sit *near* a boundary, they **span** the unbaited gaps between
#: baited islands — a read-pair caller sees two coverage islands with emptiness between and
#: reports the emptiness as one enormous event. A real SV inside a baited gene has nearly
#: all of its span baited; an island-spanning artefact has almost none.
#:
#: The artefact class was named in the plan before the run; only the flag that catches it
#: was too narrow, and widening the implementation of a pre-registered control is not the
#: same as moving a threshold after seeing which side the data fell.
MIN_BAITED_SPAN = 0.5

#: The size at which a variant stops being an indel and becomes a structural variant. The
#: convention is 50 bp and it is load-bearing here: both SV callers emit sub-50 bp events,
#: those events are already counted by the small-variant callers, and letting them into a
#: consensus lets H023 be refuted by something that is not a structural variant at all.
#: Without this the consensus deletions had a median length of **1 bp**.
MIN_SV_LENGTH = 50

IT2_SV_CONSENSUS = Derivation(
    name="it2_sv_consensus",
    question=(
        "Which structural variants are supported by two different method classes, away from "
        "the bait's edges, and how much does short-read precision allow us to trust each "
        "type? (H023)"
    ),
    reads_loaded=("it2_sv_calls",),
    sql=f"""
    WITH calls AS (
        SELECT * FROM {RESULT}.it2_sv_calls
        WHERE sv_type NOT IN ('BND', 'TRA')
          AND abs(sv_len) >= {MIN_SV_LENGTH}
    ),
    -- How much of each call's span is territory the bait actually covered. The baited
    -- intervals are exactly the regions depth was measured over, so this reads them
    -- rather than keeping a second copy of where the bait was.
    baited AS (
        SELECT c.caller, c.chrom, c.pos, c.end_pos, c.sv_type,
               coalesce(sum(
                   greatest(0, least(c.end_pos, d."end") - greatest(c.pos, d.start))
               ), 0) * 1.0 / nullif(c.end_pos - c.pos, 0) AS baited_share
        FROM calls c
        LEFT JOIN {RESULT}.it2_exon_depth d
          ON c.chrom = d.chrom AND c.pos < d."end" AND c.end_pos > d.start
        GROUP BY c.caller, c.chrom, c.pos, c.end_pos, c.sv_type
    ),
    credible AS (
        SELECT c.*, b.baited_share
        FROM calls c
        JOIN baited b
          ON c.caller = b.caller AND c.chrom = b.chrom AND c.pos = b.pos
         AND c.end_pos = b.end_pos AND c.sv_type = b.sv_type
    ),
    -- Truvari's criteria, written out: same type and contig, both breakpoints within a
    -- slop window, and reciprocal overlap of at least half. An ad hoc distance test could
    -- be tuned after seeing the answer; this cannot.
    paired AS (
        SELECT a.caller AS caller_a, b.caller AS caller_b,
               a.method_class AS class_a, b.method_class AS class_b,
               a.chrom, a.pos, a.end_pos, a.sv_type, a.sv_len,
               a.bait_edge OR b.bait_edge AS bait_edge,
               least(a.baited_share, b.baited_share) AS baited_share,
               least(a.baited_share, b.baited_share) < {MIN_BAITED_SPAN} AS spans_unbaited,
               a.precision_prior,
               a.genotype
        FROM credible a
        JOIN credible b
          ON a.chrom = b.chrom
         AND a.sv_type = b.sv_type
         AND a.method_class <> b.method_class
         AND abs(a.pos - b.pos) <= {BAIT_EDGE_BP}
         AND abs(a.end_pos - b.end_pos) <= {BAIT_EDGE_BP}
         AND (
              least(a.end_pos, b.end_pos) - greatest(a.pos, b.pos)
             ) * 1.0
             / nullif(greatest(a.end_pos - a.pos, b.end_pos - b.pos), 0) >= 0.5
    )
    SELECT sv_type,
           bait_edge,
           spans_unbaited,
           count(*) AS consensus_calls,
           count(DISTINCT (chrom, pos, end_pos)) AS distinct_events,
           round(min(precision_prior), 3) AS precision_prior,
           round(median(abs(sv_len)), 0) AS median_length,
           min(abs(sv_len)) AS shortest,
           max(abs(sv_len)) AS longest
    FROM paired
    GROUP BY sv_type, bait_edge, spans_unbaited
    ORDER BY spans_unbaited, bait_edge, consensus_calls DESC
    """,
)


IT2_SV_LEADS = Derivation(
    name="it2_sv_leads",
    question=(
        "Does any credible consensus structural variant remove or duplicate a coding exon "
        "of a gene that also carries a rare protein-altering allele? (H023)"
    ),
    depends_on=("coding_regions",),
    reads_loaded=("it2_sv_calls", "it2_exon_depth"),
    sql=f"""
    WITH sized AS (
        SELECT * FROM {RESULT}.it2_sv_calls
        WHERE sv_type IN ('DEL', 'INS', 'DUP', 'INV')
          AND abs(sv_len) >= {MIN_SV_LENGTH}
          AND NOT bait_edge
    ),
    baited AS (
        SELECT s.caller, s.method_class, s.chrom, s.pos, s.end_pos, s.sv_type, s.sv_len,
               coalesce(sum(
                   greatest(0, least(s.end_pos, d."end") - greatest(s.pos, d.start))
               ), 0) * 1.0 / nullif(s.end_pos - s.pos, 0) AS baited_share
        FROM sized s
        LEFT JOIN {RESULT}.it2_exon_depth d
          ON s.chrom = d.chrom AND s.pos < d."end" AND s.end_pos > d.start
        GROUP BY s.caller, s.method_class, s.chrom, s.pos, s.end_pos, s.sv_type, s.sv_len
    ),
    credible AS (
        SELECT * FROM baited WHERE baited_share >= {MIN_BAITED_SPAN}
    ),
    consensus AS (
        SELECT DISTINCT a.chrom, a.pos, a.end_pos, a.sv_type, abs(a.sv_len) AS sv_len
        FROM credible a
        JOIN credible b
          ON a.chrom = b.chrom
         AND a.sv_type = b.sv_type
         AND a.method_class <> b.method_class
         AND abs(a.pos - b.pos) <= {BAIT_EDGE_BP}
         AND abs(a.end_pos - b.end_pos) <= {BAIT_EDGE_BP}
    ),
    leads AS (
        SELECT symbol, tier, rare_het, rare_hom_alt, truncating
        FROM {RESULT}.it2_scored_pairs
        WHERE rare_het >= 1 OR rare_hom_alt >= 1
    )
    SELECT c.sv_type,
           r.gene,
           l.tier,
           l.rare_het,
           count(*) AS consensus_calls,
           min(c.sv_len) AS shortest,
           max(c.sv_len) AS longest
    FROM consensus c
    JOIN {SOURCE}.coding_regions r
      ON c.chrom = r.chrom AND c.pos <= r."end" AND c.end_pos >= r.start
    JOIN leads l ON l.symbol = r.gene
    GROUP BY c.sv_type, r.gene, l.tier, l.rare_het
    ORDER BY c.sv_type, r.gene
    """,
)


#: The structural-variant half of step 2's registry, concatenated in
#: :data:`mva.warehouse.analysis.DERIVATIONS` beside the allele half.
IT2_SV_DERIVATIONS = (IT2_SV_CONSENSUS, IT2_SV_LEADS)
