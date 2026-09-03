"""Why each table exists, and which verb wrote it — plus the rule that keeps this current.

:mod:`mva.viz.catalog` already answers *what* a table holds: the staged catalogue, the
derivation's question, or an in-code one-liner. Two questions it does not answer are the
ones a reviewer asks next:

* **How did this table get here?** Not "SQL", but which named command writes it, and
  whether that command *replaces* the table or *appends* to it. Re-running ``pg-ingest``
  cannot destroy a result; re-running ``pg-derive`` cannot corrupt an input; a ledger is
  never rewritten at all. Knowing which of the three a table is tells a reader what a
  re-run would do to it.
* **Why does it exist?** One sentence naming the reason, so a table nobody remembers
  adding can still be defended or deleted on purpose.

:data:`TABLE_FACTS` answers both, keyed by bare table name — the schema names are
configurable, so keying on them would break the moment somebody set ``PGSCHEMA``.
Derivations are not listed here at all: their ``why`` *is* the question declared beside
their SQL, so :func:`_derived` reads the registry rather than restating it, and a new
derivation is described the moment it is added.

**How this stays current.** ``tests/test_catalog_semantics.py`` walks
:func:`declared_tables` — every table name declared anywhere in the code — and fails if
any of them has no ``created_by`` and ``why``. Adding a table without describing it
therefore breaks the build, and the failure message names the entry to add and the file to
add it to. The one gap that discipline cannot close is a *new source file* dropped into
the profile directory: the sniffer in :mod:`mva.warehouse.catalog` will stage it under a
name no constant mentions. Giving it a :data:`mva.warehouse.catalog.NOTES` entry brings it
back under the check.
"""

from dataclasses import dataclass

from ..science.evidence import EVIDENCE_TABLE
from ..science.hypothesis import HYPOTHESIS_TABLE
from ..warehouse import reference
from ..warehouse.analysis import DERIVATIONS, PROVENANCE_TABLE
from ..warehouse.annotate import ANNOTATIONS_TABLE, RAW_TABLE
from ..warehouse.catalog import NOTES, OVERRIDES
from ..warehouse.lineage import LINEAGE_TABLE, OBJECTS_TABLE
from ..warehouse.probes import PROBE_TABLE
from ..warehouse.source import LEDGER_TABLE
from ..warehouse.stage import CATALOG_TABLE, SCALARS_TABLE
from .catalog_columns import meaning  # noqa: F401  (re-exported for the endpoint)

#: The verbs, written once so a renamed command is one edit.
STAGED = "mva-warehouse stage + pg-ingest"
DERIVED = "mva-warehouse pg-derive"


def _ledger(verb: str) -> str:
    """The ``created_by`` string for an append-only table: never rewritten, only added to."""
    return f"append-only ledger — written by {verb}"


@dataclass(frozen=True)
class TableFact:
    """How one table comes into existence, and the reason it does."""

    #: The command that writes it, and whether that write replaces or appends.
    created_by: str
    #: One sentence: the reason the table exists, or the question it answers.
    why: str


#: Tables written by something other than a derivation. Keyed by bare table name.
TABLE_FACTS: dict[str, TableFact] = {
    # ── the delivered profile, sniffed or overridden, staged to Parquet then ingested ──
    "contig_counts": TableFact(
        STAGED,
        "Gives every contig a denominator: without its length, a raw record count says "
        "nothing about whether a chromosome is unusually variable.",
    ),
    "vcf_fields": TableFact(
        STAGED,
        "Records what the callset's own header declares, so a query against INFO or "
        "FORMAT can be checked against the field list rather than guessed at.",
    ),
    "filter_gt_counts": TableFact(
        STAGED,
        "Two counts the callset cannot be judged without: how much the caller suppressed, "
        "and how the genotypes split — the heterozygous/homozygous ratio is a standard "
        "quality check.",
    ),
    "vcf_header_lines": TableFact(
        STAGED,
        "Keeps the callset's header verbatim, so the reference build, the caller and its "
        "settings stay auditable after the records have been parsed away.",
    ),
    "stats_summary": TableFact(
        STAGED,
        "Holds `bcftools stats` output unparsed, so every derived statistic can be traced "
        "back to the exact line the tool printed.",
    ),
    "fastq_profile": TableFact(
        STAGED,
        "Says how much raw sequence was actually delivered, per file — the yield that "
        "every coverage claim rests on.",
    ),
    "fastq_qc_l001": TableFact(
        STAGED,
        "One lane's fastp quality metrics, as the sample check on whether the raw reads "
        "are worth trusting before any variant is looked at.",
    ),
    "fastq_read_headers": TableFact(
        STAGED,
        "Identifies the instrument and run behind each FASTQ, with the index barcode "
        "redacted, so the delivery can be traced to a machine without carrying an "
        "identifier.",
    ),
    "manifest": TableFact(
        STAGED,
        "The publisher's own file list and partial checksums — the external claim our own "
        "digests are checked against.",
    ),
    "panel_variant_counts": TableFact(
        STAGED,
        "Counts how much variation landed in each candidate gene, which is where a "
        "gene-by-gene search starts.",
    ),
    "vcf_chrom_allele_balance": TableFact(
        STAGED,
        "Per-contig allele balance, the measurement the whole case turns on: mosaic "
        "variegated aneuploidy is about chromosome copy number, and a copy-number change "
        "pushes heterozygous allele fractions off 0.50.",
    ),
    "mva_panel_grch38": TableFact(
        STAGED,
        "The candidate gene panel as coordinates, so 'inside a candidate gene' is a join "
        "condition rather than a judgement call.",
    ),
    SCALARS_TABLE: TableFact(
        STAGED,
        "Rescues the totals stated at the foot of a source file, which are not rows of "
        "the table above them and would otherwise be dropped by the parser.",
    ),
    CATALOG_TABLE: TableFact(
        STAGED,
        "Makes the database self-describing: someone opening it cold can read what every "
        "staged table holds without going back to the repository.",
    ),
    # ── the committed public reference tables ─────────────────────────────────────────
    "gnomad_constraint": TableFact(
        STAGED,
        "Supplies the comparison a raw variant count cannot make on its own: how much "
        "damage healthy people tolerate in each gene, so an observation can be called "
        "unusual.",
    ),
    "clinvar_panel": TableFact(
        STAGED,
        "Says what clinical labs have already concluded about variants in the panel, so "
        "the search does not re-derive a classification somebody has published.",
    ),
    "qc_norms": TableFact(
        STAGED,
        "Gives every QC metric a cited healthy range, turning 'is this number normal?' "
        "into a join instead of an opinion.",
    ),
    "hpo_term_ic": TableFact(
        STAGED,
        "Prices every clinical feature. A symptom shared by thousands of genes proves "
        "nothing and one seen in a handful proves a great deal, and this table is the "
        "measured difference between them — which is what stops the phenotype ranking "
        "rewarding a vague match.",
    ),
    "hpo_gene_scores": TableFact(
        STAGED,
        "Where every curated gene placed against the child's symptoms, ranked by a scorer "
        "that never saw the candidate panel or a single variant. That independence is the "
        "point: the panel-first candidate list cannot corroborate itself, and this is the "
        "column that can.",
    ),
    # ── the callset ───────────────────────────────────────────────────────────────────
    RAW_TABLE: TableFact(
        "mva-warehouse vcf-ingest (replaces the table wholesale)",
        "The lossless landing layer: every VCF record, every field as text, nothing "
        "coerced. Because nothing is interpreted, the original file can be rebuilt from "
        "it and checked against the source digest — which is what makes 'we kept "
        "everything' a testable claim.",
    ),
    ANNOTATIONS_TABLE: TableFact(
        "mva-warehouse annotate-panel (replaces the table wholesale)",
        "The callset ships no usable annotation — its `INFO/AF` is within-sample, not a "
        "population frequency — so consequence and rarity have to come from Ensembl VEP, "
        "and this is where those answers land.",
    ),
    # ── the ledgers ───────────────────────────────────────────────────────────────────
    LEDGER_TABLE: TableFact(
        _ledger("mva-warehouse source-upload"),
        "Records every upload with a digest computed before the bytes left the machine, "
        "so 'has the delivery changed since we started?' is answerable from records "
        "rather than memory.",
    ),
    OBJECTS_TABLE: TableFact(
        "mva-warehouse source-check (replaces the table wholesale each survey)",
        "The current contents of the bucket, hash-checked against the publisher's "
        "manifest. Current state is kept separate from the append-only upload history so "
        "the two records cannot disagree.",
    ),
    LINEAGE_TABLE: TableFact(
        _ledger("mva-warehouse pg-ingest, pg-derive, annotate-panel and lineage-repair"),
        "A table with no recorded input cannot be re-derived or invalidated. This is the "
        "edge list that makes every other table's origin a fact instead of a "
        "recollection.",
    ),
    PROBE_TABLE: TableFact(
        _ledger("mva-warehouse probe-log"),
        "Oracle submissions are a consumable resource with a hard budget, and a budget "
        "tracked in chat messages is a budget that gets double-spent.",
    ),
    PROVENANCE_TABLE: TableFact(
        _ledger(DERIVED),
        "Answers 'which run produced this table, and how many rows did it write?' — kept "
        "as history rather than a current-state row, so a changed result stays visible "
        "next to the one before it.",
    ),
    # ── the research record ───────────────────────────────────────────────────────────
    HYPOTHESIS_TABLE: TableFact(
        _ledger("mva-science hypothesis-add and hypothesis-revise"),
        "Every claim is registered before it is tested, with its prediction and its "
        "refutation condition, so a belief cannot be quietly rewritten to match whatever "
        "the data turned out to say.",
    ),
    EVIDENCE_TABLE: TableFact(
        _ledger("mva-science evidence-add"),
        "Every observation is bound to the claim it moves and to the source it came from; "
        "an unsourced observation is refused rather than recorded.",
    ),
}


def _derived() -> dict[str, TableFact]:
    """One fact per derivation, read off the registry rather than restated here.

    A derivation already declares the single question it answers, beside its SQL. That is
    exactly the ``why``, so copying it into :data:`TABLE_FACTS` would create a second
    version of the sentence that could drift from the first.
    """
    return {
        item.name: TableFact(
            f"{DERIVED} (the output table is rebuilt from scratch, never appended to)",
            item.question,
        )
        for item in DERIVATIONS
    }


def facts(table: str) -> TableFact | None:
    """How ``table`` is created and why it exists, or ``None`` if nothing says."""
    return TABLE_FACTS.get(table) or _derived().get(table)


def declared_tables() -> dict[str, str]:
    """Every table name declared anywhere in the code, mapped to where it is declared.

    This is the input to the enforcement test: a name in here with no :func:`facts` entry
    is a table somebody added without describing, and the test says so by name.
    """
    where: dict[str, str] = {}
    for dataset in OVERRIDES.values():
        where[dataset.table] = "mva.warehouse.catalog.OVERRIDES"
    for name in NOTES:
        where[name] = "mva.warehouse.catalog.NOTES"
    for dataset in reference.datasets():
        where[dataset.table] = "mva.warehouse.reference.datasets()"
    for item in DERIVATIONS:
        where[item.name] = "mva.warehouse.analysis.DERIVATIONS"
    where[SCALARS_TABLE] = "mva.warehouse.stage.SCALARS_TABLE"
    where[CATALOG_TABLE] = "mva.warehouse.stage.CATALOG_TABLE"
    where[RAW_TABLE] = "mva.warehouse.annotate.RAW_TABLE"
    where[ANNOTATIONS_TABLE] = "mva.warehouse.annotate.ANNOTATIONS_TABLE"
    where[LEDGER_TABLE] = "mva.warehouse.source.LEDGER_TABLE"
    where[OBJECTS_TABLE] = "mva.warehouse.lineage.OBJECTS_TABLE"
    where[LINEAGE_TABLE] = "mva.warehouse.lineage.LINEAGE_TABLE"
    where[PROBE_TABLE] = "mva.warehouse.probes.PROBE_TABLE"
    where[PROVENANCE_TABLE] = "mva.warehouse.analysis.PROVENANCE_TABLE"
    where[HYPOTHESIS_TABLE] = "mva.science.hypothesis.HYPOTHESIS_TABLE"
    where[EVIDENCE_TABLE] = "mva.science.evidence.EVIDENCE_TABLE"
    return where


def undescribed() -> dict[str, str]:
    """Declared tables with no ``created_by``/``why``, mapped to where they were declared.

    Empty is the passing state. The enforcement test renders whatever this returns into a
    message naming the entry to add and the file to add it to.
    """
    return {
        name: source for name, source in sorted(declared_tables().items()) if facts(name) is None
    }
