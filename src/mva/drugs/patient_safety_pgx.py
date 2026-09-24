"""Read a PharmCAT run as *actionability words*, and measure how much of it was observed.

PharmCAT turns a VCF into star-allele diplotypes and CPIC-matched recommendations. Two
things make its output unusable as-is for this repository:

1. a diplotype **is** a genotype, so it may not appear in any tracked file. Everything
   crossing this module's boundary is a phenotype word ("Poor Metabolizer") or a count;
2. a **variant-only callset** — the ordinary output of a small-variant pipeline — contains
   a record only where the sample differs from the reference. Every PGx position the
   sample matches is therefore *absent*, and PharmCAT reads absent as **no call**, not as
   reference. PharmCAT's own escape hatch, ``--absent-to-ref``, is labelled DANGEROUS by
   its authors because it converts "unknown" into "reference" wholesale.

So this module reads **both** runs and reports the difference as the uncertainty. A gene
whose phenotype is identical in both runs is a real result. A gene that only acquires a
phenotype under ``--absent-to-ref`` is an assumption, carried as ``observed=False`` to
every consumer.

**The callability proxy.** A no-call at a PGx position has two very different causes:
"the sample matches the reference here" (harmless) and "this region was never callable"
(a hole). The callset cannot distinguish them at the position. It can at the *region*:
count the PASS variants the pipeline did call across each pharmacogene's interval and
compare with the genome-wide density. A gene whose region carries variants at close to
the genome-wide rate was demonstrably sequenced and called, so absent PGx positions there
are far more likely to be true reference; a gene whose region is empty is a hole and its
``--absent-to-ref`` phenotype is not to be believed. That ratio is a *proxy*, not a depth
measurement: only a targeted re-call from the reads gives observed reference calls.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .patient_safety import GeneCall

#: `PX=GENE` in the INFO column of PharmCAT's positions VCF.
PX = re.compile(r"PX=([^;\t]+)")


@dataclass(frozen=True)
class Callability:
    """How much of one pharmacogene the callset could speak to."""

    gene: str
    positions_total: int
    positions_called: int
    region_kb: float
    region_variants: int
    genome_per_kb: float

    @property
    def density_ratio(self) -> float:
        """Region variant density ÷ genome-wide density. ~1 means "normally callable"."""
        if not self.region_kb or not self.genome_per_kb:
            return 0.0
        return (self.region_variants / self.region_kb) / self.genome_per_kb

    @property
    def verdict(self) -> str:
        """Plain words for whether an absent-to-ref assumption is defensible here."""
        if self.positions_called == self.positions_total:
            return "fully observed"
        if self.density_ratio >= 0.5:
            return "region normally callable; absent positions probably reference"
        if self.density_ratio >= 0.2:
            return "region sparsely called; absent-to-ref weakly supported"
        return "region has almost no calls; absent-to-ref not supported"


def gene_positions(positions_vcf: Path) -> dict[str, int]:
    """Count the **distinct** definition positions PharmCAT expects, per gene.

    Distinct rather than rows: PharmCAT's "missing positions" file represents a
    multi-allelic site as one row per alternate allele, so counting rows there and rows in
    the definition file gives different denominators for the same site — which shows up as
    a negative "called" count. One genomic position is one unit of callability.
    """
    seen: dict[str, set[tuple[str, str]]] = {}
    with positions_vcf.open() as handle:
        for line in handle:
            if line.startswith("#"):
                continue
            fields = line.split("\t")
            if len(fields) < 8:
                continue
            match = PX.search(fields[7])
            gene = match.group(1) if match else "OTHER"
            seen.setdefault(gene, set()).add((fields[0], fields[1]))
    return {gene: len(positions) for gene, positions in seen.items()}


def missing_positions(missing_vcf: Path) -> dict[str, int]:
    """Count the distinct positions the preprocessor could not find in the sample, per gene."""
    return gene_positions(missing_vcf)


def regions(bed: Path) -> dict[str, tuple[str, int, int]]:
    """Gene → (contig, start, end) from PharmCAT's regions BED, contig prefix stripped."""
    out: dict[str, tuple[str, int, int]] = {}
    with bed.open() as handle:
        for line in handle:
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 4:
                continue
            gene = fields[3].removeprefix("PX=")
            if not gene:
                continue
            contig = fields[0].removeprefix("chr")
            out[gene] = (contig, int(fields[1]), int(fields[2]))
    return out


def callability(
    positions_vcf: Path,
    missing_vcf: Path,
    bed: Path,
    region_variants: Mapping[str, int],
    genome_per_kb: float,
) -> dict[str, Callability]:
    """Join the three counts into one per-gene callability record."""
    totals = gene_positions(positions_vcf)
    missing = missing_positions(missing_vcf)
    spans = regions(bed)
    out: dict[str, Callability] = {}
    for gene, total in totals.items():
        contig_start_end = spans.get(gene)
        kb = (contig_start_end[2] - contig_start_end[1]) / 1000 if contig_start_end else 0.0
        out[gene] = Callability(
            gene=gene,
            positions_total=total,
            positions_called=total - missing.get(gene, 0),
            region_kb=kb,
            region_variants=region_variants.get(gene, 0),
            genome_per_kb=genome_per_kb,
        )
    return out


def _phenotypes(report: Mapping[str, object]) -> list[str]:
    """The phenotype words of one gene report, de-duplicated and ordered."""
    diplotypes = report.get("recommendationDiplotypes") or report.get("sourceDiplotypes") or []
    found: list[str] = []
    if isinstance(diplotypes, list):
        for entry in diplotypes:
            if not isinstance(entry, dict):
                continue
            for phenotype in entry.get("phenotypes") or []:
                if isinstance(phenotype, str) and phenotype not in found:
                    found.append(phenotype)
    return found


def gene_calls(
    phenotype_json: Path,
    assumed_json: Path | None = None,
    coverage: Mapping[str, Callability] | None = None,
) -> dict[str, GeneCall]:
    """Gene → :class:`GeneCall`, preferring the observed run and falling back to the assumed one.

    ``assumed_json`` is the ``--absent-to-ref`` run. A gene that only gets a phenotype
    there is returned with ``observed=False``; a gene with no phenotype in either run is
    returned as a no call, which is a result, not a gap to be filled.
    """
    observed = json.loads(phenotype_json.read_text()).get("geneReports", {})
    assumed = json.loads(assumed_json.read_text()).get("geneReports", {}) if assumed_json else {}
    calls: dict[str, GeneCall] = {}
    for gene in sorted(set(observed) | set(assumed)):
        strict = _phenotypes(observed.get(gene, {}))
        loose = _phenotypes(assumed.get(gene, {}))
        strict_useful = [p for p in strict if p.lower() not in {"no result", "indeterminate"}]
        cover = (coverage or {}).get(gene)
        if strict_useful:
            phenotype, was_observed = "/".join(strict_useful), True
        elif loose:
            phenotype, was_observed = "/".join(loose), False
        else:
            phenotype, was_observed = "no call", True
        calls[gene] = GeneCall(
            gene=gene,
            phenotype=phenotype,
            observed=was_observed,
            positions_total=cover.positions_total if cover else 0,
            positions_called=cover.positions_called if cover else 0,
            note=cover.verdict if cover else "",
        )
    return calls


#: PharmCAT names a guideline "Annotation of <source> for <drug> and <GENE[, GENE]>". The
#: gene list is the only place the reporter states which genes a drug's guideline uses when
#: the guideline produced no annotation (which is exactly the no-call case we care about).
GUIDELINE_NAME = re.compile(r"^Annotation of .+ for (?P<drug>.+?) and (?P<genes>[A-Z0-9,\- ]+)$")

#: Annotation sources that name their genes that way. "FDA PGx Association" does not, and is
#: therefore read for recommendations only.
NAMED_SOURCES: tuple[str, ...] = (
    "CPIC Guideline Annotation",
    "DPWG Guideline Annotation",
    "FDA Label Annotation",
)


def drug_genes(report_json: Path, sources: Sequence[str] = NAMED_SOURCES) -> dict[str, list[str]]:
    """Drug → the pharmacogenes its guideline names, from PharmCAT's reporter JSON.

    Read from the guideline *name* rather than from a matched annotation on purpose: a
    drug whose gene could not be called has no annotations at all, and that is the case
    this experiment exists to report.
    """
    payload = json.loads(report_json.read_text()).get("drugs", {})
    out: dict[str, list[str]] = {}
    for source in sources:
        for drug, block in (payload.get(source) or {}).items():
            genes = out.setdefault(drug.lower(), [])
            for guideline in block.get("guidelines") or []:
                match = GUIDELINE_NAME.match(str(guideline.get("name", "")))
                if not match:
                    continue
                for gene in match.group("genes").split(","):
                    symbol = gene.strip()
                    if symbol and symbol not in genes:
                        genes.append(symbol)
    return {drug: genes for drug, genes in out.items() if genes}


def drug_recommendations(report_json: Path) -> dict[str, str]:
    """Drug → the guideline implication and recommendation PharmCAT matched for this patient.

    Recommendation *text* is not patient data: it is the published guideline sentence the
    matched phenotype selects, and the phenotype is an actionability word. The diplotype
    that selected it is deliberately not read.
    """
    payload = json.loads(report_json.read_text()).get("drugs", {})
    out: dict[str, str] = {}
    for source, drugs in payload.items():
        for drug, block in (drugs or {}).items():
            texts: list[str] = []
            for guideline in block.get("guidelines") or []:
                for annotation in guideline.get("annotations") or []:
                    implications = " ; ".join(annotation.get("implications") or [])
                    recommendation = annotation.get("drugRecommendation") or ""
                    line = f"[{source.split()[0]}] {implications} -> {recommendation}".strip()
                    if implications or recommendation:
                        texts.append(line)
            if texts:
                joined = " | ".join(texts)
                previous = out.get(drug.lower(), "")
                out[drug.lower()] = (previous + " | " + joined if previous else joined)[:600]
    return out
