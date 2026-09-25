"""Every sequence fact a readthrough route needs, derived from public gene models.

Given one allele record (a coding HGVS spelling and its transcript) this module asks Ensembl
for the transcript model and coding sequence and UniProt for the protein's domains, and
derives four things a reader can check:

* the **stop codon's identity and context** — which of UGA/UAG/UAA it is, and the +4 and -1
  bases that decide how readable-through it is;
* the **NMD verdict** — how far the stop sits from the last exon-exon junction, against the
  50-55 nt rule, and therefore whether the message is destroyed before it is translated;
* the **truncation** — how much protein and which annotated domains are lost;
* the record's own provenance line.

The result holds **transcript offsets**, which are patient-derived when the allele came from a
callset, so callers keep the file under ``build/``. Nothing here names a genomic position.

Case-agnostic: the gene, the transcript, the UniProt accession and the rule length are all
arguments.
"""

from __future__ import annotations

from typing import Any

from mva.drugs.cache import Fetcher
from mva.drugs.readthrough_context import (
    Domain,
    TranscriptModel,
    nmd_call,
    parse_hgvs_c,
    stop_context,
    transcript_from_ensembl,
    truncation,
)

__all__ = ["ENSEMBL", "UNIPROT", "stop_facts", "transcript_model"]

ENSEMBL = "https://rest.ensembl.org"
UNIPROT = "https://rest.uniprot.org/uniprotkb"


def transcript_model(fetcher: Fetcher, transcript: str, accession: str) -> TranscriptModel:
    lookup = fetcher.get_json(
        f"{ENSEMBL}/lookup/id/{transcript}", {"expand": 1, "content-type": "application/json"}
    )
    cds = fetcher.get_json(
        f"{ENSEMBL}/sequence/id/{transcript}", {"type": "cds", "content-type": "application/json"}
    )["seq"]
    features = fetcher.get_json(
        f"{UNIPROT}/{accession}.json", {"fields": "ft_domain,ft_region,ft_motif,ft_mod_res"}
    )
    domains = tuple(
        Domain(
            feature.get("description") or feature["type"],
            int(feature["location"]["start"]["value"]),
            int(feature["location"]["end"]["value"]),
        )
        for feature in features.get("features", [])
        if feature["type"] == "Domain"
    )
    return transcript_from_ensembl(lookup, cds, domains=domains)


def stop_facts(
    record: dict[str, Any],
    model: TranscriptModel,
    *,
    gene: str,
    accession: str,
    flank: int = 6,
    nmd_rule_nt: int = 55,
) -> dict[str, Any]:
    """The derived facts for one premature stop, as a JSON-ready dict."""
    spelling = parse_hgvs_c(str(record["hgvs_c"]).split(":", 1)[-1])
    context = stop_context(model, spelling.offset, spelling.alt, flank=flank)
    decay = nmd_call(model, context.codon_index, rule_nt=nmd_rule_nt)
    lost = truncation(model, context.codon_index)
    return {
        "gene": gene,
        "transcript": model.transcript_id,
        "uniprot": accession,
        "coding_length_nt": len(model.cds),
        "protein_length_aa": model.protein_length,
        "exons_total": model.exons_total,
        "coding_exons": model.coding_exons,
        "stop": {
            "rna_stop": context.rna_stop,
            "tetranucleotide": context.tetranucleotide,
            "plus4": context.plus4,
            "minus1": context.minus1,
            "reference_codon": context.reference_codon,
            "upstream": context.upstream,
            "downstream": context.downstream,
            "codon_index": context.codon_index,
        },
        "nmd": {
            "exon_index": decay.exon_index,
            "nt_to_last_junction": decay.nt_to_last_junction,
            "junctions_downstream": decay.junctions_downstream,
            "rule_nt": decay.rule_nt,
            "competent": decay.competent,
            "reason": decay.reason,
        },
        "truncation": {
            "residues_kept": lost.residues_kept,
            "protein_length": lost.protein_length,
            "fraction_lost": lost.fraction_lost,
            "domains_lost": list(lost.domains_lost),
            "domains_truncated": list(lost.domains_truncated),
            "domains_kept": list(lost.domains_kept),
        },
        "clin_sig": record["clin_sig"],
        "af_gnomad": record["af_gnomad"],
        "source": "Ensembl REST (gene model, CDS) + UniProt (domains); allele from "
        + str(record.get("source") or "the case's callset"),
        "patient_data": (
            "transcript offsets only, no genomic position; this file stays under build/"
        ),
    }
