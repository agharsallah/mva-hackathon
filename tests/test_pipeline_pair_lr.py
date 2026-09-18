"""The genotype lanes, the pair scorer, and the P(trans) lookup.

The rules under test are the ones that were pre-registered before any score was seen: which
tool speaks for which consequence class, what a truncation is worth depending on where it
falls, that a suppressed call is down-weighted rather than dropped, that one allele on one
copy keeps the square root of its evidence, and that a pair gnomAD has never seen comes back
*undetermined* rather than zero or one.
"""

import httpx
import pytest

from mva.pipeline.acmg import Strength, likelihood_ratio
from mva.pipeline.compound_het import Phase
from mva.pipeline.genotype_lr import (
    ALLELE_EFFECT,
    NON_PASS_LR,
    AlleleEvidence,
    degrade,
    lane_class,
    lanes_for,
)
from mva.pipeline.likelihood import Lane
from mva.pipeline.pair_lr import Shape, context_lanes, gene_prior, score
from mva.pipeline.ptrans import (
    NOT_IN_GNOMAD,
    UNINFORMATIVE_PRIOR,
    GnomadCooccurrence,
    TransState,
    base_rate,
    estimate,
)
from mva.pipeline.variant import Variant
from mva.pipeline.vcf import Call

SOURCE = "test"


def lane(evidence: AlleleEvidence, name: str) -> Lane:
    return next(item for item in lanes_for(evidence, source=SOURCE).lanes if item.name == name)


class TestWhichToolSpeaks:
    def test_one_class_per_consequence(self):
        assert lane_class(AlleleEvidence(consequence="stop_gained")) == "truncating"
        assert lane_class(AlleleEvidence(consequence="missense_variant")) == "missense"
        assert lane_class(AlleleEvidence(consequence="splice_region_variant")) == "splice"
        assert lane_class(AlleleEvidence(consequence="synonymous_variant")) == "silent"
        assert lane_class(AlleleEvidence(consequence="intron_variant")) == "other"

    def test_vep_joins_its_terms_with_an_ampersand(self):
        evidence = AlleleEvidence(consequence="splice_region_variant&intron_variant")
        assert evidence.in_splice_window

    def test_a_splice_site_is_truncating_before_it_is_splice(self):
        # Both classes claim it; the truncating lane is the one with the published rule set.
        assert lane_class(AlleleEvidence(consequence="splice_donor_variant")) == "truncating"

    def test_every_allele_effect_lane_shares_one_correlation_group(self):
        lanes = lanes_for(AlleleEvidence(consequence="missense_variant"), source=SOURCE).lanes
        effect = {item.name for item in lanes if item.group == ALLELE_EFFECT}
        assert effect == {"consequence", "alphamissense", "spliceai", "clinvar"}

    def test_frequency_and_filter_are_independent_of_the_predictors(self):
        lanes = lanes_for(AlleleEvidence(consequence="missense_variant"), source=SOURCE).lanes
        for name in ("frequency", "filter"):
            assert next(item for item in lanes if item.name == name).group == ""


class TestTheTruncatingRule:
    def truncation(self, index: int | None, total: int | None) -> Lane:
        return lane(
            AlleleEvidence(consequence="stop_gained", exon_index=index, exon_total=total),
            "consequence",
        )

    def test_a_stop_in_the_body_is_very_strong(self):
        assert self.truncation(3, 12).strength is Strength.VERY_STRONG

    def test_a_stop_in_the_last_exon_escapes_decay_and_drops_to_moderate(self):
        assert self.truncation(12, 12).strength is Strength.MODERATE

    def test_a_single_exon_transcript_has_no_decay_to_escape(self):
        assert self.truncation(1, 1).strength is Strength.MODERATE

    def test_the_penultimate_exon_is_lowered_rather_than_guessed(self):
        # The published rule needs the last 50 bases of that exon, and REST VEP does not
        # report exon lengths. One rung down, with the reason in the note.
        result = self.truncation(11, 12)
        assert result.strength is Strength.STRONG
        assert "penultimate" in result.note

    def test_no_exon_numbering_means_the_rule_could_not_be_applied(self):
        result = self.truncation(None, None)
        assert result.strength is Strength.STRONG
        assert "could not be applied" in result.note


class TestTheOtherLanes:
    def test_alphamissense_speaks_only_for_a_missense_allele(self):
        silent = AlleleEvidence(consequence="synonymous_variant", am_class="likely_pathogenic")
        assert lane(silent, "alphamissense").is_silent

    def test_a_missense_call_is_capped_at_moderate(self):
        evidence = AlleleEvidence(
            consequence="missense_variant", am_class="likely_pathogenic", am_pathogenicity=0.99
        )
        assert lane(evidence, "alphamissense").strength is Strength.MODERATE

    def test_an_ambiguous_missense_call_says_nothing(self):
        evidence = AlleleEvidence(consequence="missense_variant", am_class="ambiguous")
        assert lane(evidence, "alphamissense").is_silent

    def test_the_splice_lane_follows_the_tools_own_cutoffs(self):
        rungs = {
            0.9: Strength.MODERATE,
            0.6: Strength.SUPPORTING,
            0.3: Strength.NONE,
            0.05: Strength.SUPPORTING_BENIGN,
        }
        for delta, expected in rungs.items():
            evidence = AlleleEvidence(consequence="intron_variant", spliceai_ds_max=delta)
            assert lane(evidence, "spliceai").strength is expected, delta

    def test_conflicting_clinvar_submissions_are_not_evidence_either_way(self):
        evidence = AlleleEvidence(clin_sig="conflicting_interpretations_of_pathogenicity")
        result = lane(evidence, "clinvar")
        assert result.is_silent
        assert "disagree" in result.note

    def test_clinvar_pathogenic_is_strong_and_benign_is_its_mirror(self):
        assert lane(AlleleEvidence(clin_sig="pathogenic"), "clinvar").strength is Strength.STRONG
        assert lane(AlleleEvidence(clin_sig="benign"), "clinvar").strength is Strength.STRONG_BENIGN

    def test_absence_from_gnomad_supports_rarity(self):
        assert lane(AlleleEvidence(), "frequency").strength is Strength.SUPPORTING

    def test_a_common_allele_is_divided_down_not_removed(self):
        result = lane(AlleleEvidence(gnomad_af=0.2), "frequency")
        assert result.strength is Strength.STRONG_BENIGN
        assert result.likelihood_ratio > 0

    def test_rarity_is_judged_on_the_highest_ancestry_group(self):
        # Rare overall and common in one population is common among that population's
        # carriers, which is the number a recessive hypothesis has to survive.
        evidence = AlleleEvidence(gnomad_af=1e-6, gnomad_af_grpmax=0.02)
        assert lane(evidence, "frequency").strength is Strength.STRONG_BENIGN

    def test_a_filtered_call_is_down_weighted_never_dropped(self):
        result = lane(AlleleEvidence(filters="LowQual"), "filter")
        assert result.likelihood_ratio == pytest.approx(NON_PASS_LR)
        assert result.likelihood_ratio > 0

    def test_an_empty_filter_column_means_the_caller_passed_it(self):
        for value in ("", ".", "PASS"):
            assert lane(AlleleEvidence(filters=value), "filter").is_silent


class TestDegrading:
    def test_both_alleles_seen_keeps_the_whole_ratio(self):
        assert degrade(100.0, observed=2) == pytest.approx(100.0)

    def test_one_of_two_keeps_the_square_root(self):
        assert degrade(100.0, observed=1) == pytest.approx(10.0)

    def test_nothing_seen_collapses_to_one_rather_than_to_zero(self):
        assert degrade(100.0, observed=0) == pytest.approx(1.0)

    def test_a_recessive_hypothesis_needs_at_least_one_allele(self):
        with pytest.raises(ValueError):
            degrade(100.0, observed=1, required=0)


class TestScoringAPair:
    def evidence(self) -> AlleleEvidence:
        return AlleleEvidence(consequence="stop_gained", exon_index=2, exon_total=9, filters="PASS")

    def context(self) -> list[Lane]:
        return context_lanes(phenotype_lr=50.0, phenotype_source="s", phenotype_rank=3)

    def test_a_compound_pair_counts_both_alleles(self):
        result = score(
            "G",
            self.evidence(),
            self.evidence(),
            shape=Shape.COMPOUND,
            context=self.context(),
            prior=gene_prior(),
            source=SOURCE,
        )
        names = {name for name, _ in result.posterior.terms}
        assert any(name.startswith("left:") for name in names)
        assert any(name.startswith("right:") for name in names)

    def test_a_homozygous_call_counts_its_allele_once(self):
        result = score(
            "G",
            self.evidence(),
            None,
            shape=Shape.HOMOZYGOUS,
            context=self.context(),
            prior=gene_prior(),
            source=SOURCE,
        )
        assert result.right is None
        assert result.combined_lr == pytest.approx(result.posterior.combined_lr)

    def test_correlation_groups_do_not_cross_alleles(self):
        # Two different alleles are two observations. If the sides shared a group, the
        # second allele's whole effect lane would be damped away by the first.
        result = score(
            "G",
            self.evidence(),
            self.evidence(),
            shape=Shape.COMPOUND,
            context=self.context(),
            prior=gene_prior(),
            source=SOURCE,
        )
        very_strong = likelihood_ratio(Strength.VERY_STRONG)
        assert dict(result.posterior.terms)["left:consequence"] == pytest.approx(very_strong)
        assert dict(result.posterior.terms)["right:consequence"] == pytest.approx(very_strong)

    def test_a_single_allele_is_degraded_not_dropped(self):
        result = score(
            "G",
            self.evidence(),
            None,
            shape=Shape.SINGLE,
            context=self.context(),
            prior=gene_prior(),
            source=SOURCE,
        )
        assert result.exponent == 0.5
        assert result.combined_lr == pytest.approx(result.posterior.combined_lr**0.5)
        assert result.combined_lr > 1

    def test_rescoring_substitutes_the_phenotype_lane_exactly(self):
        # What the permutation null relies on: because the degradation is a power, swapping
        # one factor is the same arithmetic, not an approximation.
        result = score(
            "G",
            self.evidence(),
            None,
            shape=Shape.SINGLE,
            context=self.context(),
            prior=gene_prior(),
            source=SOURCE,
        )
        assert result.rescored(50.0) == pytest.approx(result.combined_lr)
        assert result.rescored(1.0) < result.combined_lr

    def test_an_unphased_compound_pair_is_named_as_such(self):
        result = score(
            "G",
            self.evidence(),
            self.evidence(),
            shape=Shape.COMPOUND,
            context=self.context(),
            prior=gene_prior(),
            source=SOURCE,
        )
        assert result.phase is Phase.UNKNOWN
        assert result.unphaseable

    def test_physical_phasing_is_read_when_the_caller_provided_it(self):
        left = Call(Variant("chr1", 10, "A", "T"), "0|1", ("PASS",), 30, None, None, "1", "0|1")
        right = Call(Variant("chr1", 40, "C", "G"), "1|0", ("PASS",), 30, None, None, "1", "1|0")
        result = score(
            "G",
            self.evidence(),
            self.evidence(),
            shape=Shape.COMPOUND,
            context=self.context(),
            prior=gene_prior(),
            source=SOURCE,
            left_call=left,
            right_call=right,
        )
        assert result.phase is Phase.TRANS
        assert not result.unphaseable

    def test_a_homozygous_call_is_never_reported_as_trans(self):
        result = score(
            "G",
            self.evidence(),
            None,
            shape=Shape.HOMOZYGOUS,
            context=self.context(),
            prior=gene_prior(),
            source=SOURCE,
        )
        assert result.phase is Phase.UNKNOWN

    def test_the_prior_is_one_over_the_genes_scored(self):
        assert gene_prior(1000) == pytest.approx(0.001)
        with pytest.raises(ValueError):
            gene_prior(1)


class TestTheNetworkLane:
    def test_it_fires_only_for_a_gene_the_ranker_could_not_place(self):
        curated = context_lanes(
            phenotype_lr=50.0, phenotype_source="s", phenotype_rank=3, network_lr=2.0
        )
        assert {item.name for item in curated} == {"phenotype"}

    def test_an_uncurated_gene_may_enter_through_it(self):
        uncurated = context_lanes(
            phenotype_lr=0.38,
            phenotype_source="s",
            phenotype_rank=None,
            network_lr=2.0,
            network_source="string",
        )
        assert {item.name for item in uncurated} == {"phenotype", "network"}

    def test_an_inheritance_factor_of_one_is_not_a_lane(self):
        lanes = context_lanes(
            phenotype_lr=1.0, phenotype_source="s", phenotype_rank=1, inheritance_lr=1.0
        )
        assert all(item.name != "inheritance" for item in lanes)


def transport(handler) -> GnomadCooccurrence:
    return GnomadCooccurrence(client=httpx.Client(transport=httpx.MockTransport(handler)))


class TestPTrans:
    def test_a_pair_gnomad_has_never_seen_is_undetermined_not_zero(self):
        def handler(request):
            return httpx.Response(200, json={"data": {"variant": None}})

        result = estimate(transport(handler), left_rsid="rs1", right_rsid="rs2")
        assert result.state is TransState.UNDETERMINED
        assert result.p_trans == UNINFORMATIVE_PRIOR
        assert "undetermined" in result.caveat

    def test_an_allele_with_no_identifier_cannot_be_looked_up(self):
        # The only bridge from GRCh38 to the GRCh37 co-occurrence dataset is the dbSNP id.
        def handler(request):  # pragma: no cover - must never be called
            raise AssertionError("no request should be made without an identifier")

        result = estimate(transport(handler), left_rsid="", right_rsid="")
        assert result.state is TransState.UNDETERMINED

    def test_an_observed_pair_carries_the_number_and_its_caveat(self):
        def handler(request):
            body = request.content.decode()
            if "variant_cooccurrence" in body:
                return httpx.Response(
                    200,
                    json={"data": {"variant_cooccurrence": {"p_compound_heterozygous": 0.97}}},
                )
            return httpx.Response(200, json={"data": {"variant": {"variant_id": "1-2-A-T"}}})

        result = estimate(transport(handler), left_rsid="rs1", right_rsid="rs2")
        assert result.state is TransState.OBSERVED
        assert result.p_trans == pytest.approx(0.97)
        assert "not this child's haplotype" in result.caveat

    def test_gnomads_absence_message_is_read_as_absence(self):
        def handler(request):
            body = request.content.decode()
            if "variant_cooccurrence" in body:
                return httpx.Response(200, json={"errors": [{"message": NOT_IN_GNOMAD}]})
            return httpx.Response(200, json={"data": {"variant": {"variant_id": "1-2-A-T"}}})

        result = estimate(transport(handler), left_rsid="rs1", right_rsid="rs2")
        assert result.state is TransState.UNDETERMINED

    def test_a_broken_lookup_is_an_error_not_an_absence(self):
        # The distinction that stops a network outage being written down as "gnomAD has
        # never seen this pair", which would be a finding rather than a failure.
        def handler(request):
            body = request.content.decode()
            if "variant_cooccurrence" in body:
                return httpx.Response(200, json={"errors": [{"message": "internal error"}]})
            return httpx.Response(200, json={"data": {"variant": {"variant_id": "1-2-A-T"}}})

        result = estimate(transport(handler), left_rsid="rs1", right_rsid="rs2")
        assert result.state is TransState.ERROR

    def test_two_alts_of_one_site_are_trans_by_construction(self):
        result = estimate(None, left_rsid="", right_rsid="", same_site=True)
        assert result.state is TransState.SAME_SITE
        assert result.p_trans == 1.0

    def test_the_offline_path_reports_the_prior_and_says_so(self):
        result = estimate(None, left_rsid="rs1", right_rsid="rs2")
        assert result.state is TransState.UNDETERMINED
        assert "offline" in result.source

    def test_an_empirical_base_rate_needs_an_observation(self):
        assert base_rate([estimate(None, left_rsid="", right_rsid="")]) is None

    def test_identifiers_are_looked_up_once_per_allele(self):
        calls = []

        def handler(request):
            calls.append(request.content.decode())
            return httpx.Response(200, json={"data": {"variant": {"variant_id": "1-2-A-T"}}})

        lookup = transport(handler)
        lookup.variant_id("rs1")
        lookup.variant_id("rs1")
        assert len(calls) == 1
