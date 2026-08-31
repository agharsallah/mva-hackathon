"""Reading one Ensembl VEP REST result object into the fields the ranker needs.

Split from the HTTP client on purpose: everything here is a pure function of a decoded
JSON object, so the whole parse is testable without a network, a mock server, or a
recorded cassette. :mod:`mva.pipeline.annotate_vep` owns the transport; this module owns
the meaning.

Three things about the live response shape drove the code, all verified against
``https://rest.ensembl.org`` (Ensembl release 116, GRCh38) rather than assumed:

* **Results come back unordered.** Each object echoes the exact query line in ``input``,
  so that string — not the list position — is the join key.
* **Frequencies are keyed by VEP's own allele spelling.** A ``CTT>C`` deletion is keyed
  ``"-"``, not ``"C"``. :func:`vep_allele` reproduces that spelling from the VCF pair.
* **``clin_sig`` is per *variant*, ``clin_sig_allele`` is per *allele*.** A site can be
  pathogenic for one ALT and benign for another, so the allele-specific field is
  preferred and the variant-level list is only the fallback.
"""

import re
from dataclasses import dataclass

from .annotation import Annotation
from .variant import Variant, to_vcf_contig

#: dbSNP identifiers, as opposed to the COSMIC/HGMD/ClinVar ids that share the field.
RSID = re.compile(r"^rs\d+$")

#: The gnomAD genetic-ancestry groups that count toward *grpmax* (the highest frequency
#: in any one group). gnomAD excludes the small and admixture-heavy groups — ``ami``,
#: ``asj``, ``fin``, ``mid`` — and the ``remaining`` catch-all from that maximum, so we do
#: too; including them would report a higher "common somewhere" frequency than gnomAD does.
GRPMAX_GROUPS = ("afr", "amr", "eas", "nfe", "sas")

#: Preference order for the overall frequency: whole-genome sequencing first, since the
#: proband's callset is WGS and exome capture misses the introns this panel spans.
FREQUENCY_SOURCES = ("gnomadg", "gnomade")


def query_line(variant: Variant) -> str:
    """The one-line VCF-style query VEP's region endpoint accepts for ``variant``.

    The contig is emitted **bare** (``15``), because Ensembl's coordinate system has no
    ``chr`` prefix and a prefixed name silently matches nothing. The conversion goes
    through :func:`~mva.pipeline.variant.to_vcf_contig`, the repository's single owner of
    that bridge — building the name here with a ``removeprefix`` would be a second
    normalizer, which is the failure mode the chr-prefix rule exists to prevent.
    """
    return (f"{to_vcf_contig(variant.chrom)} {variant.pos} . "
            f"{variant.ref} {variant.alt} . . .")


def vep_allele(ref: str, alt: str) -> str:
    """VEP's spelling of the ALT allele: the minimal edit, with ``-`` for a deletion.

    VCF writes an indel with an anchoring base shared by REF and ALT (``CTT`` → ``C``).
    Ensembl strips that anchor and writes what actually changed (``TT`` → ``-``), and its
    ``frequencies`` block is keyed by that spelling. Reproducing it here is what makes the
    gnomAD lookup hit on indels instead of silently returning ``None``.
    """
    left, right = ref.upper(), alt.upper()
    if len(left) == 1 and len(right) == 1:
        return right
    head = 0
    while head < len(left) and head < len(right) and left[head] == right[head]:
        head += 1
    left, right = left[head:], right[head:]
    tail = 0
    while tail < len(left) and tail < len(right) and left[-1 - tail] == right[-1 - tail]:
        tail += 1
    if tail:
        left, right = left[:len(left) - tail], right[:len(right) - tail]
    return right or "-"


@dataclass(frozen=True)
class VepRecord:
    """One annotated allele: everything VEP told us that is worth storing.

    Wider than :class:`~mva.pipeline.annotation.Annotation` on purpose. The port's record
    is what *ranking* consumes and stays deliberately narrow; this is what lands in the
    warehouse, where a clinical significance or an rsID is worth keeping even though no
    ranker reads it yet.
    """

    variant: Variant
    rsid: str | None = None
    gene: str | None = None
    consequence: str | None = None
    impact: str | None = None
    gnomad_af: float | None = None
    gnomad_af_grpmax: float | None = None
    clin_sig: tuple[str, ...] = ()

    @property
    def annotation(self) -> Annotation:
        """The narrow record the :class:`~mva.pipeline.annotation.Annotator` port returns."""
        return Annotation(gene=self.gene, consequence=self.consequence,
                          gnomad_af=self.gnomad_af)


def parse(item: dict, variant: Variant, genes: frozenset[str] = frozenset()) -> VepRecord:
    """Turn one VEP result object into a :class:`VepRecord` for ``variant``.

    ``genes`` is the panel's symbol set. It only breaks ties: where a position falls in
    two overlapping genes, the panel gene is the one the case is about.
    """
    allele = vep_allele(variant.ref, variant.alt)
    gene, impact = _pick_consequence(item, genes)
    overall, grpmax = _frequencies(item, allele)
    return VepRecord(
        variant=variant,
        rsid=_rsid(item),
        gene=gene,
        consequence=item.get("most_severe_consequence"),
        impact=impact,
        gnomad_af=overall,
        gnomad_af_grpmax=grpmax,
        clin_sig=_clin_sig(item, allele),
    )


def _pick_consequence(item: dict, genes: frozenset[str]) -> tuple[str | None, str | None]:
    """The gene symbol and impact to report, chosen from every transcript VEP returned.

    VEP hands back one entry per overlapping transcript — 39 of them for a TP53 SNV — and
    they disagree. The order of preference is: a panel gene beats a neighbour, a transcript
    carrying the most severe consequence beats one that does not, the canonical transcript
    beats an alternative, and protein-coding beats everything else.
    """
    severe = item.get("most_severe_consequence")
    wanted = {name.upper() for name in genes}

    def rank(entry: dict) -> tuple[int, int, int, int]:
        symbol = (entry.get("gene_symbol") or "").upper()
        return (
            1 if wanted and symbol in wanted else 0,
            1 if severe in (entry.get("consequence_terms") or ()) else 0,
            1 if entry.get("canonical") else 0,
            1 if entry.get("biotype") == "protein_coding" else 0,
        )

    transcripts = item.get("transcript_consequences") or []
    if transcripts:
        best = max(transcripts, key=rank)
        return best.get("gene_symbol"), best.get("impact")
    # Outside every transcript VEP still reports an impact, on a regulatory feature or on
    # the intergenic pseudo-consequence. There is no gene there, and inventing the nearest
    # one would be a guess the ranker cannot tell from a fact.
    for key in ("regulatory_feature_consequences", "motif_feature_consequences",
                "intergenic_consequences"):
        entries = item.get(key) or []
        if entries:
            return None, entries[0].get("impact")
    return None, None


def _frequencies(item: dict, allele: str) -> tuple[float | None, float | None]:
    """The overall gnomAD AF and the grpmax AF for ``allele``, or ``(None, None)``.

    A variant absent from gnomAD has no ``frequencies`` block at all — which is the
    interesting case here, since a causal recessive allele is expected to be rare or novel.
    """
    table = _allele_frequencies(item, allele)
    if not table:
        return None, None
    for source in FREQUENCY_SOURCES:
        overall = table.get(source)
        if overall is None:
            continue
        groups = [table[f"{source}_{name}"] for name in GRPMAX_GROUPS
                  if table.get(f"{source}_{name}") is not None]
        return float(overall), (max(groups) if groups else None)
    return None, None


def _allele_frequencies(item: dict, allele: str) -> dict:
    """The frequency table for one allele, matched by VEP's spelling then by the raw ALT."""
    for colocated in item.get("colocated_variants") or ():
        table = colocated.get("frequencies") or {}
        if allele in table:
            return table[allele]
    return {}


def _rsid(item: dict) -> str | None:
    """The dbSNP identifier, if the site has one.

    ``colocated_variants`` mixes dbSNP, COSMIC, HGMD and ClinVar records in one list under
    the same ``id`` key, so the field is filtered by shape rather than taken positionally.
    """
    for colocated in item.get("colocated_variants") or ():
        name = colocated.get("id") or ""
        if RSID.match(name):
            return name
    return None


def _clin_sig(item: dict, allele: str) -> tuple[str, ...]:
    """ClinVar significance terms for ``allele``, falling back to the site's terms.

    Allele-specific first, and it matters: at the TP53 codon-72 site the ``C`` allele is
    classified benign while other alternates carry a pathogenic submission. Reporting the
    site's whole list against every allele would manufacture a pathogenic call.
    """
    site: list[str] = []
    for colocated in item.get("colocated_variants") or ():
        per_allele = _split_clin_sig_allele(colocated.get("clin_sig_allele") or "")
        if allele in per_allele:
            return tuple(per_allele[allele])
        site.extend(colocated.get("clin_sig") or ())
    return tuple(dict.fromkeys(site))


def _split_clin_sig_allele(field: str) -> dict[str, list[str]]:
    """Decode ``"C:pathogenic;T:benign;T:likely_benign"`` into terms per allele."""
    out: dict[str, list[str]] = {}
    for pair in field.split(";"):
        allele, _, term = pair.partition(":")
        if allele and term:
            out.setdefault(allele, []).append(term)
    return out
